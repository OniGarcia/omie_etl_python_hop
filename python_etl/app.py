import os
import sys
import time
import datetime
import calendar
import logging
import threading
from collections import defaultdict
from typing import List, Optional
from fastapi import FastAPI, BackgroundTasks, HTTPException, Header, Query
from fastapi.responses import HTMLResponse, JSONResponse

# Certifica-se de que a pasta atual está no PYTHONPATH para importar localmente
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import Config
from main import setup_logging
from orchestrator import rodar_lote_completo
from database import get_db_connection
from dre_html import get_dre_html

# Inicializa logs
setup_logging()
logger = logging.getLogger("ETLWebApp")

app = FastAPI(title="Painel de Controle - OMIE ETL 2026")

# Chave de segurança para controle de chamadas externas da API.
# Sem valor padrão: se ETL_API_KEY não estiver definida no ambiente (Render),
# o disparo de ETL fica bloqueado por padrão (fail-closed).
ADMIN_API_KEY = os.getenv("ETL_API_KEY")
if not ADMIN_API_KEY:
    logger.warning(
        "ETL_API_KEY não configurada. O endpoint /api/run permanecerá bloqueado "
        "até que a variável seja definida no ambiente."
    )

# Estado da Execução em Memória
class ETLState:
    def __init__(self):
        self.running = False
        self.last_status = "Aguardando Início"
        self.last_run_time = "Nenhuma execução registrada"
        self.last_run_duration = 0.0
        self.records_processed = 0
        self.error_message = None
        self.mode = "N/A"

state = ETLState()

# Protege o guard de concorrência do endpoint /api/run contra TOCTOU.
_run_lock = threading.Lock()

def run_etl_worker(modo: str, empresa_ids: Optional[List[int]] = None):
    global state
    # state.running já foi marcado como True (sob _run_lock) pelo endpoint /api/run.
    state.last_status = "EXECUTANDO"
    state.mode = modo
    start_time = time.time()

    desc = f"empresas={empresa_ids}" if empresa_ids else "todas as empresas"
    logger.info(f"[API Web] Disparando execução de ETL em segundo plano. Modo: {modo} | Escopo: {desc}")

    try:
        rodar_lote_completo(dry_run=False, modo=modo, empresa_ids=empresa_ids or None)
        
        # Após conclusão com sucesso, atualiza o status em memória buscando o log do banco
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT status, dt_inicio, dt_fim, linhas, mensagem 
                        FROM config.etl_execucao 
                        WHERE entidade = 'LOTE' 
                        ORDER BY id DESC LIMIT 1
                        """
                    )
                    row = cursor.fetchone()
                    if row:
                        status, dt_inicio, dt_fim, linhas, mensagem = row
                        state.last_status = status
                        state.records_processed = linhas or 0
                        state.error_message = mensagem
                    else:
                        state.last_status = "SUCESSO"
                        state.records_processed = 0
        except Exception as db_err:
            logger.error(f"[API Web] Erro ao consultar resultados da execução no banco: {db_err}")
            state.last_status = "SUCESSO"
            
    except Exception as e:
        logger.error(f"[API Web] Erro crítico durante o processo em segundo plano: {e}")
        state.last_status = "ERRO"
        state.error_message = str(e)
    finally:
        state.running = False
        state.last_run_duration = round(time.time() - start_time, 2)
        state.last_run_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logger.info(f"[API Web] Execução em segundo plano finalizada. Status: {state.last_status}")

def get_last_logs(n_lines: int = 150) -> str:
    log_file = "etl_execution.log"
    if not os.path.exists(log_file):
        return "Arquivo de log não encontrado ainda. A execução precisa ser iniciada."
    
    try:
        with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
            return "".join(lines[-n_lines:])
    except Exception as e:
        return f"Erro ao ler os logs: {e}"

# Rota Principal: Dashboard HTML com design moderno e responsivo
@app.get("/", response_class=HTMLResponse)
def get_dashboard():
    # Esconde a senha e token do banco para exibição segura
    masked_db = f"postgresql://{Config.DB_USER}@...:{Config.DB_PORT}/{Config.DB_NAME}"
    masked_host = Config.DB_HOST

    html_content = f"""
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>OMIE ETL Control Panel</title>
        <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
        <style>
            :root {{
                --bg-primary: #0a0c16;
                --bg-secondary: rgba(21, 26, 48, 0.4);
                --border-color: rgba(255, 255, 255, 0.08);
                --text-primary: #f3f4f6;
                --text-secondary: #9ca3af;
                --accent-color: #6366f1;
                --accent-hover: #4f46e5;
                --success: #10b981;
                --error: #ef4444;
                --warning: #f59e0b;
                --card-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
            }}

            * {{
                box-sizing: border-box;
                margin: 0;
                padding: 0;
            }}

            body {{
                font-family: 'Plus Jakarta Sans', sans-serif;
                background: radial-gradient(circle at top right, #1d1b3c, var(--bg-primary) 60%);
                color: var(--text-primary);
                min-height: 100vh;
                padding: 2rem;
                line-height: 1.5;
            }}

            .container {{
                max-width: 1400px;
                margin: 0 auto;
            }}

            header {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 2rem;
                padding-bottom: 1rem;
                border-bottom: 1px solid var(--border-color);
            }}

            .logo-area h1 {{
                font-size: 1.8rem;
                font-weight: 700;
                background: linear-gradient(135deg, #a78bfa, #6366f1);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                letter-spacing: -0.5px;
            }}

            .logo-area p {{
                font-size: 0.9rem;
                color: var(--text-secondary);
                margin-top: 0.25rem;
            }}

            .connection-status {{
                display: flex;
                align-items: center;
                gap: 0.5rem;
                font-size: 0.85rem;
                background: var(--bg-secondary);
                padding: 0.5rem 1rem;
                border-radius: 9999px;
                border: 1px solid var(--border-color);
                backdrop-filter: blur(10px);
            }}

            .status-dot {{
                width: 8px;
                height: 8px;
                background-color: var(--success);
                border-radius: 50%;
                box-shadow: 0 0 10px var(--success);
            }}

            .status-dot.loading {{
                background-color: var(--warning);
                box-shadow: 0 0 10px var(--warning);
                animation: pulse 1.5s infinite;
            }}

            @keyframes pulse {{
                0% {{ opacity: 0.4; }}
                50% {{ opacity: 1; }}
                100% {{ opacity: 0.4; }}
            }}

            .grid {{
                display: grid;
                grid-template-columns: 1fr 2fr;
                gap: 2rem;
            }}

            @media(max-width: 1024px) {{
                .grid {{
                    grid-template-columns: 1fr;
                }}
            }}

            .card {{
                background: var(--bg-secondary);
                border: 1px solid var(--border-color);
                border-radius: 16px;
                padding: 1.5rem;
                backdrop-filter: blur(16px);
                box-shadow: var(--card-shadow);
                display: flex;
                flex-direction: column;
                gap: 1.25rem;
            }}

            .card-title {{
                font-size: 1.1rem;
                font-weight: 600;
                border-bottom: 1px solid var(--border-color);
                padding-bottom: 0.75rem;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }}

            .btn {{
                background: linear-gradient(135deg, #a78bfa, #6366f1);
                color: white;
                border: none;
                padding: 0.75rem 1.5rem;
                font-size: 0.95rem;
                font-weight: 600;
                border-radius: 10px;
                cursor: pointer;
                transition: all 0.2s ease;
                display: inline-flex;
                align-items: center;
                justify-content: center;
                gap: 0.5rem;
                box-shadow: 0 4px 15px rgba(99, 102, 241, 0.4);
            }}

            .btn:hover:not(:disabled) {{
                transform: translateY(-2px);
                box-shadow: 0 6px 20px rgba(99, 102, 241, 0.6);
            }}

            .btn:active:not(:disabled) {{
                transform: translateY(0);
            }}

            .btn:disabled {{
                background: #374151;
                color: #9ca3af;
                cursor: not-allowed;
                box-shadow: none;
            }}

            .form-group {{
                display: flex;
                flex-direction: column;
                gap: 0.5rem;
            }}

            label {{
                font-size: 0.85rem;
                font-weight: 600;
                color: var(--text-secondary);
            }}

            select, input {{
                background: #111827;
                border: 1px solid var(--border-color);
                color: white;
                padding: 0.75rem;
                border-radius: 8px;
                font-family: inherit;
                outline: none;
                transition: border-color 0.2s;
            }}

            select:focus, input:focus {{
                border-color: var(--accent-color);
            }}

            .badge {{
                display: inline-block;
                padding: 0.25rem 0.75rem;
                font-size: 0.8rem;
                font-weight: 600;
                border-radius: 9999px;
            }}

            .badge-success {{ background: rgba(16, 185, 129, 0.15); color: var(--success); border: 1px solid rgba(16, 185, 129, 0.3); }}
            .badge-error {{ background: rgba(239, 68, 68, 0.15); color: var(--error); border: 1px solid rgba(239, 68, 68, 0.3); }}
            .badge-warning {{ background: rgba(245, 158, 11, 0.15); color: var(--warning); border: 1px solid rgba(245, 158, 11, 0.3); }}
            .badge-info {{ background: rgba(99, 102, 241, 0.15); color: #818cf8; border: 1px solid rgba(99, 102, 241, 0.3); }}

            .status-metric {{
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 1rem;
            }}

            .metric-box {{
                background: rgba(0, 0, 0, 0.2);
                border: 1px solid var(--border-color);
                padding: 1rem;
                border-radius: 10px;
            }}

            .metric-box span {{
                display: block;
                font-size: 0.75rem;
                color: var(--text-secondary);
                text-transform: uppercase;
                margin-bottom: 0.25rem;
            }}

            .metric-box div {{
                font-size: 1.2rem;
                font-weight: 700;
            }}

            /* Terminal logs */
            .terminal-container {{
                display: flex;
                flex-direction: column;
                height: 500px;
                border-radius: 12px;
                overflow: hidden;
                border: 1px solid var(--border-color);
            }}

            .terminal-header {{
                background: #1f2937;
                padding: 0.75rem 1rem;
                font-family: 'Plus Jakarta Sans', sans-serif;
                font-size: 0.85rem;
                display: flex;
                justify-content: space-between;
                align-items: center;
                border-bottom: 1px solid var(--border-color);
            }}

            .terminal-body {{
                background: #030712;
                font-family: 'JetBrains Mono', monospace;
                font-size: 0.85rem;
                padding: 1rem;
                overflow-y: auto;
                flex: 1;
                white-space: pre-wrap;
                word-break: break-all;
                color: #e5e7eb;
                line-height: 1.6;
            }}

            /* Tabela de Histórico */
            .table-container {{
                overflow-x: auto;
                border-radius: 10px;
                border: 1px solid var(--border-color);
            }}

            table {{
                width: 100%;
                border-collapse: collapse;
                text-align: left;
                font-size: 0.85rem;
            }}

            th {{
                background: #111827;
                padding: 0.75rem 1rem;
                font-weight: 600;
                color: var(--text-secondary);
                border-bottom: 1px solid var(--border-color);
            }}

            td {{
                padding: 0.75rem 1rem;
                border-bottom: 1px solid var(--border-color);
            }}

            tr:last-child td {{
                border-bottom: none;
            }}

            tr:hover {{
                background: rgba(255, 255, 255, 0.02);
            }}

            .text-muted {{
                font-size: 0.75rem;
                color: var(--text-secondary);
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <header>
                <div class="logo-area">
                    <h1>OMIE ETL Control Panel</h1>
                    <p>Orquestrador Integrado & Data Warehouse</p>
                </div>
                <div style="display:flex; align-items:center; gap:0.75rem; flex-wrap:wrap;">
                    <a href="/dre" style="display:inline-flex;align-items:center;gap:0.4rem;padding:0.5rem 1rem;background:rgba(99,102,241,0.12);border:1px solid rgba(99,102,241,0.3);border-radius:9999px;color:#a5b4fc;text-decoration:none;font-size:0.85rem;font-family:inherit;transition:all 0.2s;" onmouseover="this.style.background='rgba(99,102,241,0.2)'" onmouseout="this.style.background='rgba(99,102,241,0.12)'">
                        DRE
                    </a>
                    <div class="connection-status">
                        <span id="conn-dot" class="status-dot"></span>
                        <span id="conn-text">Banco: Conectado ({masked_host})</span>
                    </div>
                </div>
            </header>

            <div class="grid">
                <!-- Coluna de Ações e Status -->
                <div style="display: flex; flex-direction: column; gap: 2rem;">
                    <!-- Painel de Controle -->
                    <div class="card">
                        <div class="card-title">
                            <span>Painel de Controle</span>
                        </div>
                        <div class="form-group">
                            <label for="etl-mode">Modo de Extração</label>
                            <select id="etl-mode">
                                <option value="incremental">Incremental (Recomendado - 7 dias de overlap)</option>
                                <option value="full">Full Reload (Carga Completa)</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label for="empresa-filter">Empresas</label>
                            <div style="position: relative;">
                                <select id="empresa-filter" multiple style="width:100%; min-height: 100px; padding: 0.5rem; background: #111827; border: 1px solid var(--border-color); color: white; border-radius: 8px; font-family: inherit; outline: none; transition: border-color 0.2s;">
                                    <option value="" disabled>Carregando empresas...</option>
                                </select>
                                <p class="text-muted" style="margin-top: 0.35rem;">Segure Ctrl/Cmd para selecionar múltiplas. Sem seleção = todas as empresas ativas.</p>
                            </div>
                        </div>
                        <div class="form-group">
                            <label for="api-key">Chave de API do ETL (Render)</label>
                            <input type="password" id="api-key" placeholder="Insira a chave ETL_API_KEY para rodar">
                        </div>
                        <button id="btn-run" class="btn" onclick="triggerETL()">
                            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>
                            Executar ETL Agora
                        </button>
                    </div>

                    <!-- Status Atual -->
                    <div class="card">
                        <div class="card-title">
                            <span>Status da Execução</span>
                            <span id="run-badge" class="badge badge-info">NOT STARTED</span>
                        </div>
                        
                        <div class="status-metric">
                            <div class="metric-box">
                                <span>Última Execução</span>
                                <div id="m-last-run" style="font-size: 1rem; white-space: nowrap;">-</div>
                            </div>
                            <div class="metric-box">
                                <span>Tempo de Execução</span>
                                <div id="m-duration">-</div>
                            </div>
                        </div>

                        <div class="status-metric">
                            <div class="metric-box">
                                <span>Registros Gravados</span>
                                <div id="m-records">0</div>
                            </div>
                            <div class="metric-box">
                                <span>Modo Atual</span>
                                <div id="m-mode">-</div>
                            </div>
                        </div>

                        <div id="error-card-wrapper" style="display:none;" class="metric-box" style="border-color: rgba(239,68,68,0.3); background: rgba(239,68,68,0.05);">
                            <span style="color: var(--error);">Detalhes do Erro</span>
                            <div id="m-error" style="font-size: 0.85rem; color: #f87171; font-weight: normal; margin-top: 0.25rem;"></div>
                        </div>
                    </div>

                    <!-- Configurações Ambientais -->
                    <div class="card">
                        <div class="card-title">
                            <span>Informações do Ambiente</span>
                        </div>
                        <div style="font-size: 0.85rem; display: flex; flex-direction: column; gap: 0.5rem; color: var(--text-secondary);">
                            <div><strong>Database URL:</strong> <code style="color: #a78bfa;">{masked_db}</code></div>
                            <div><strong>Log Level:</strong> <code>{Config.LOG_LEVEL}</code></div>
                            <div><strong>Limite de Concorrência:</strong> <code>{Config.CONCURRENCY_LIMIT}</code></div>
                            <div><strong>CDC Overlap:</strong> <code>{Config.INCREMENTAL_OVERLAP_DAYS} dias</code></div>
                            <div><strong>CC Janela:</strong> <code>{Config.CC_WINDOW_DAYS} dias</code></div>
                        </div>
                    </div>
                </div>

                <!-- Coluna de Logs e Histórico -->
                <div style="display: flex; flex-direction: column; gap: 2rem;">
                    <!-- Terminal de Logs -->
                    <div class="card" style="padding: 0; border: none; background: transparent; box-shadow: none;">
                        <div class="terminal-container">
                            <div class="terminal-header">
                                <span style="font-weight: 600;">Logs de Execução (etl_execution.log)</span>
                                <div style="display: flex; gap: 1rem; align-items: center;">
                                    <label style="font-size:0.75rem; display:flex; align-items:center; gap:0.25rem; margin:0;">
                                        <input type="checkbox" id="auto-refresh" checked style="width: auto; height: auto;"> Auto-update (3s)
                                    </label>
                                    <span style="cursor: pointer; text-decoration: underline;" onclick="fetchLogs()">Atualizar logs</span>
                                </div>
                            </div>
                            <div id="terminal-body" class="terminal-body">
                                Carregando logs de execução...
                            </div>
                        </div>
                    </div>

                    <!-- Histórico Recente do Banco -->
                    <div class="card">
                        <div class="card-title">
                            <span>Histórico Recente de Execuções (Banco de Dados)</span>
                        </div>
                        <div class="table-container">
                            <table id="history-table">
                                <thead>
                                    <tr>
                                        <th>ID</th>
                                        <th>Empresa</th>
                                        <th>Entidade</th>
                                        <th>Status</th>
                                        <th>Linhas</th>
                                        <th>Início</th>
                                        <th>Duração</th>
                                    </tr>
                                </thead>
                                <tbody id="history-body">
                                    <tr>
                                        <td colspan="7" style="text-align: center; color: var(--text-secondary);">Carregando histórico...</td>
                                    </tr>
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <script>
            let pollingInterval = null;

            async function loadEmpresas() {{
                try {{
                    const res = await fetch("/api/empresas");
                    if (!res.ok) return;
                    const empresas = await res.json();
                    const sel = document.getElementById("empresa-filter");
                    sel.innerHTML = "";
                    empresas.forEach(emp => {{
                        const opt = document.createElement("option");
                        opt.value = emp.id;
                        opt.textContent = emp.nome;
                        sel.appendChild(opt);
                    }});
                }} catch (e) {{
                    console.error("Erro ao carregar empresas:", e);
                }}
            }}

            async function updateStatus() {{
                try {{
                    const res = await fetch("/api/status");
                    if (!res.ok) return;
                    const data = await res.json();
                    
                    // Atualiza Estado em Memória
                    const state = data.state;
                    const btn = document.getElementById("btn-run");
                    const badge = document.getElementById("run-badge");
                    const connDot = document.getElementById("conn-dot");
                    
                    if (state.running) {{
                        btn.disabled = true;
                        btn.innerHTML = `<span class="status-dot loading"></span> Executando ETL...`;
                        badge.className = "badge badge-warning";
                        badge.textContent = "RUNNING";
                        connDot.className = "status-dot loading";
                    }} else {{
                        btn.disabled = false;
                        btn.innerHTML = `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg> Executar ETL Agora`;
                        connDot.className = "status-dot";
                        
                        if (state.last_status === "SUCESSO") {{
                            badge.className = "badge badge-success";
                            badge.textContent = "SUCCESS";
                        }} else if (state.last_status === "ERRO" || state.last_status === "FALHA") {{
                            badge.className = "badge badge-error";
                            badge.textContent = "ERROR";
                        }} else {{
                            badge.className = "badge badge-info";
                            badge.textContent = state.last_status.toUpperCase();
                        }}
                    }}

                    document.getElementById("m-last-run").textContent = state.last_run_time || "-";
                    document.getElementById("m-duration").textContent = state.last_run_duration ? state.last_run_duration + "s" : "-";
                    document.getElementById("m-records").textContent = state.records_processed || "0";
                    document.getElementById("m-mode").textContent = state.mode || "-";

                    const errWrapper = document.getElementById("error-card-wrapper");
                    if (state.error_message) {{
                        errWrapper.style.display = "block";
                        document.getElementById("m-error").textContent = state.error_message;
                    }} else {{
                        errWrapper.style.display = "none";
                    }}

                    // Atualiza histórico na tabela
                    const historyBody = document.getElementById("history-body");
                    if (data.history && data.history.length > 0) {{
                        historyBody.innerHTML = "";
                        data.history.forEach(row => {{
                            const tr = document.createElement("tr");
                            
                            let statusBadge = `<span class="badge badge-info">${{row.status}}</span>`;
                            if (row.status === "SUCESSO") statusBadge = `<span class="badge badge-success">SUCESSO</span>`;
                            if (row.status === "ERRO") statusBadge = `<span class="badge badge-error">ERRO</span>`;
                            if (row.status === "INICIADO") statusBadge = `<span class="badge badge-warning">INICIADO</span>`;

                            const dur = row.duracao ? parseFloat(row.duracao).toFixed(1) + "s" : "-";

                            tr.innerHTML = `
                                <td>${{row.id}}</td>
                                <td>${{row.nome_empresa || 'Empresa ' + row.id_empresa}}</td>
                                <td><code>${{row.entidade}}</code></td>
                                <td>${{statusBadge}}</td>
                                <td>${{row.linhas !== null ? row.linhas : '-'}}</td>
                                <td class="text-muted">${{row.dt_inicio}}</td>
                                <td>${{dur}}</td>
                            `;
                            historyBody.appendChild(tr);
                        }});
                    }} else if (data.history && data.history.length === 0) {{
                        historyBody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--text-secondary);">Nenhuma execução no banco.</td></tr>`;
                    }}
                }} catch (e) {{
                    console.error("Erro ao atualizar status:", e);
                }}
            }}

            async function fetchLogs() {{
                try {{
                    const res = await fetch("/api/logs");
                    if (!res.ok) return;
                    const logText = await res.text();
                    const term = document.getElementById("terminal-body");
                    
                    // Verifica se o scroll estava perto do final antes de atualizar
                    const isNearBottom = term.scrollHeight - term.clientHeight - term.scrollTop < 60;
                    
                    term.textContent = logText;
                    
                    if (isNearBottom) {{
                        term.scrollTop = term.scrollHeight;
                    }}
                }} catch (e) {{
                    console.error("Erro ao obter logs:", e);
                }}
            }}

            async function triggerETL() {{
                const mode = document.getElementById("etl-mode").value;
                const apiKey = document.getElementById("api-key").value;
                const btn = document.getElementById("btn-run");

                // Coleta empresas selecionadas
                const sel = document.getElementById("empresa-filter");
                const selectedIds = Array.from(sel.selectedOptions).map(o => o.value);
                const empresaDesc = selectedIds.length === 0
                    ? "TODAS as empresas ativas"
                    : sel.selectedOptions.length + " empresa(s): " + Array.from(sel.selectedOptions).map(o => o.textContent).join(", ");

                if (!confirm(`Deseja iniciar o ETL Omie?\n\nModo: ${{mode.toUpperCase()}}\nEscopos: ${{empresaDesc}}`)) return;

                btn.disabled = true;

                // Monta a URL com os filtros de empresa (query params repetidos)
                let url = `/api/run?modo=${{mode}}`;
                selectedIds.forEach(id => {{ url += `&empresa_ids=${{id}}`; }});

                try {{
                    const res = await fetch(url, {{
                        method: "POST",
                        headers: {{
                            "X-API-Key": apiKey
                        }}
                    }});

                    const data = await res.json();
                    if (!res.ok) {{
                        alert("Falha ao iniciar ETL: " + (data.detail || "Erro inesperado"));
                    }} else {{
                        updateStatus();
                        fetchLogs();
                    }}
                }} catch (e) {{
                    alert("Erro de conexão ao disparar ETL: " + e);
                }}
            }}

            // Loop de atualização automática
            setInterval(() => {{
                updateStatus();
                if (document.getElementById("auto-refresh").checked) {{
                    fetchLogs();
                }}
            }}, 3000);

            // Carregamento inicial
            window.onload = () => {{
                loadEmpresas();
                updateStatus();
                fetchLogs();
                setTimeout(() => {{
                    const term = document.getElementById("terminal-body");
                    term.scrollTop = term.scrollHeight;
                }}, 1000);
            }};
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

# Endpoint: logs em tempo real
@app.get("/api/logs")
def get_logs_endpoint(n: int = 150):
    return HTMLResponse(content=get_last_logs(n), media_type="text/plain")

# Endpoint: status em memória e histórico
@app.get("/api/status")
def get_status_endpoint():
    history = []
    
    # Busca histórico do banco de dados (tabela config.etl_execucao)
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT 
                        log.id, 
                        log.id_empresa, 
                        emp.nome_empresa, 
                        log.entidade, 
                        log.status, 
                        log.linhas, 
                        to_char(log.dt_inicio, 'YYYY-MM-DD HH24:MI:SS') as dt_inicio,
                        EXTRACT(EPOCH FROM (log.dt_fim - log.dt_inicio)) as duracao
                    FROM config.etl_execucao log
                    LEFT JOIN config.empresas emp ON log.id_empresa = emp.id
                    ORDER BY log.dt_inicio DESC 
                    LIMIT 15
                    """
                )
                for r in cursor.fetchall():
                    history.append({
                        "id": r[0],
                        "id_empresa": r[1],
                        "nome_empresa": r[2],
                        "entidade": r[3],
                        "status": r[4],
                        "linhas": r[5],
                        "dt_inicio": r[6],
                        "duracao": r[7]
                    })
    except Exception as db_err:
        logger.error(f"[API Web] Falha ao ler histórico de execuções do banco: {db_err}")
    
    return {
        "state": {
            "running": state.running,
            "last_status": state.last_status,
            "last_run_time": state.last_run_time,
            "last_run_duration": state.last_run_duration,
            "records_processed": state.records_processed,
            "error_message": state.error_message,
            "mode": state.mode
        },
        "history": history
    }

# Endpoint: lista empresas ativas (para popular o select do dashboard)
@app.get("/api/empresas")
def get_empresas_endpoint():
    empresas = []
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT id, nome_empresa FROM config.empresas WHERE ativo = TRUE ORDER BY nome_empresa"
                )
                for r in cursor.fetchall():
                    empresas.append({"id": r[0], "nome": r[1]})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao buscar empresas: {e}")
    return empresas


# Endpoint: disparar execução do ETL
@app.post("/api/run")
def trigger_etl_endpoint(
    background_tasks: BackgroundTasks,
    modo: str = "incremental",
    empresa_ids: Optional[List[int]] = Query(default=None),
    x_api_key: str = Header(None)
):
    # Fail-closed: sem chave configurada no servidor, ninguém dispara o ETL
    if not ADMIN_API_KEY:
        raise HTTPException(status_code=503, detail="ETL_API_KEY não configurada no servidor.")

    if x_api_key != ADMIN_API_KEY:
        raise HTTPException(status_code=401, detail="Não autorizado: Chave de API inválida.")

    if modo not in ("incremental", "full"):
        raise HTTPException(status_code=400, detail="Modo de extração inválido. Escolha 'incremental' ou 'full'.")

    # Guard de concorrência atômico: marca running de forma síncrona, ANTES de
    # agendar a task, para evitar TOCTOU entre dois POST simultâneos.
    with _run_lock:
        if state.running:
            raise HTTPException(status_code=409, detail="ETL já está em execução no momento.")
        state.running = True

    # Inicia a execução em segundo plano
    background_tasks.add_task(run_etl_worker, modo, empresa_ids if empresa_ids else None)

    desc = f"empresas={empresa_ids}" if empresa_ids else "todas as empresas"
    return {"status": "iniciado", "mensagem": f"Processo do ETL iniciado em segundo plano ({modo}) | {desc}."}

# ── Tela DRE ────────────────────────────────────────────────────────────────

@app.get("/dre", response_class=HTMLResponse)
def get_dre_page():
    return HTMLResponse(content=get_dre_html())


@app.get("/api/departamentos")
def get_departamentos_endpoint():
    """Lista todos os centros de custo disponíveis no DW."""
    resultado = []
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT cod_departamento, descricao
                    FROM   dw.dim_departamento
                    WHERE  descricao IS NOT NULL
                    ORDER  BY descricao
                    """
                )
                for r in cursor.fetchall():
                    resultado.append({"codigo": r[0], "descricao": r[1]})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao buscar departamentos: {e}")
    return resultado


@app.get("/api/dre")
def get_dre_endpoint(
    ano: int = Query(..., description="Ano do período (ex: 2026)"),
    mes_ini: int = Query(..., ge=1, le=12, description="Mês inicial (1-12)"),
    mes_fim: int = Query(..., ge=1, le=12, description="Mês final (1-12)"),
    departamento: Optional[str] = Query(default=None, description="Código do departamento (Centro de Custo)"),
):
    """
    Retorna os dados estruturados para o DRE mensal.
    Hierarquia: grupo → categoria → entidade, com valores por mês.
    """
    if mes_ini > mes_fim:
        raise HTTPException(status_code=400, detail="mes_ini não pode ser maior que mes_fim.")

    # Chaves de data no formato YYYYMMDD (inteiro)
    sk_ini = int(f"{ano}{mes_ini:02d}01")
    ultimo_dia = calendar.monthrange(ano, mes_fim)[1]
    sk_fim = int(f"{ano}{mes_fim:02d}{ultimo_dia:02d}")

    # Lista de meses do período como strings "YYYYMM"
    meses = []
    for m in range(mes_ini, mes_fim + 1):
        meses.append(f"{ano}{m:02d}")

    depart_param = departamento if departamento else None

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:

                # ── 1) Saldo Inicial acumulado ──
                cursor.execute(
                    """
                    SELECT COALESCE(
                        SUM(
                            CASE WHEN f.natureza = 'C' THEN  f.valor_rateio
                                 WHEN f.natureza = 'D' THEN -f.valor_rateio
                            END
                        ), 0
                    ) AS saldo_inicial
                    FROM dw.fact_movimento_financeiro f
                    WHERE f.sk_data_pagamento < %(sk_ini)s
                      AND f.is_transferencia = 'N'
                      AND f.status_titulo IN ('LIQUIDADO', 'RECEBIDO', 'PAGO')
                      AND (%(depart)s IS NULL OR f.cod_departamento = %(depart)s)
                    """,
                    {"sk_ini": sk_ini, "depart": depart_param}
                )
                saldo_acumulado = float(cursor.fetchone()[0] or 0)

                # ── 2) Movimentos do período ──
                cursor.execute(
                    """
                    SELECT
                        f.natureza,
                        COALESCE(
                            (
                                SELECT s_pai.descricao
                                FROM   staging.stg_cad_categorias s_pai
                                WHERE  s_pai.codigo     = s_filho.categoria_superior
                                  AND  s_pai.id_empresa = f.id_empresa
                                LIMIT  1
                            ),
                            c.tipo_categoria,
                            c.descricao
                        )                                           AS descricao_grupo,
                        COALESCE(s_filho.categoria_superior, f.cod_categoria)
                                                                    AS cod_grupo,
                        f.cod_categoria,
                        c.descricao                                 AS descricao_categoria,
                        f.cod_entidade,
                        COALESCE(e.nome_fantasia, e.razao_social, f.cod_entidade)
                                                                    AS nome_entidade,
                        (f.sk_data_pagamento / 100)::INTEGER        AS ano_mes,
                        SUM(f.valor_rateio)                         AS total
                    FROM dw.fact_movimento_financeiro f
                    LEFT JOIN dw.dim_categoria c
                           ON c.sk_categoria = f.sk_categoria
                    LEFT JOIN dw.dim_entidade e
                           ON e.sk_entidade = f.sk_entidade
                    LEFT JOIN LATERAL (
                        SELECT s.categoria_superior
                        FROM   staging.stg_cad_categorias s
                        WHERE  s.codigo     = f.cod_categoria
                          AND  s.id_empresa = f.id_empresa
                        LIMIT  1
                    ) s_filho ON TRUE
                    WHERE
                        f.sk_data_pagamento BETWEEN %(sk_ini)s AND %(sk_fim)s
                        AND f.is_transferencia = 'N'
                        AND f.status_titulo IN ('LIQUIDADO', 'RECEBIDO', 'PAGO')
                        AND (%(depart)s IS NULL OR f.cod_departamento = %(depart)s)
                    GROUP BY
                        f.natureza,
                        s_filho.categoria_superior,
                        c.tipo_categoria,
                        c.descricao,
                        f.cod_categoria,
                        f.cod_entidade,
                        e.nome_fantasia,
                        e.razao_social,
                        (f.sk_data_pagamento / 100)::INTEGER,
                        f.id_empresa
                    ORDER BY
                        f.natureza DESC,
                        cod_grupo,
                        f.cod_categoria,
                        ano_mes
                    """,
                    {"sk_ini": sk_ini, "sk_fim": sk_fim, "depart": depart_param}
                )
                rows = cursor.fetchall()

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao consultar DRE: {e}")

    # ── 3) Agrupamento em memória ──────────────────────────────────────────
    # Estruturas intermediárias:
    #   receitas_grupos[cod_grupo] = {descricao, valores: {yyyymm: total},
    #                                 cats: {cod_cat: {descricao, valores, entidades}}}

    def make_grupo():
        return {"descricao": None, "valores": defaultdict(float),
                "cats": defaultdict(lambda: {"descricao": None, "valores": defaultdict(float),
                                             "entidades": defaultdict(lambda: {"nome": None, "valores": defaultdict(float)})})}

    receitas_grupos = defaultdict(make_grupo)
    despesas_grupos = defaultdict(make_grupo)
    total_receitas = defaultdict(float)
    total_despesas = defaultdict(float)

    for row in rows:
        (natureza, desc_grupo, cod_grupo, cod_cat, desc_cat,
         cod_ent, nome_ent, ano_mes, total) = row
        ano_mes_str = str(ano_mes)
        total_f = float(total or 0)

        bucket = receitas_grupos if natureza == 'C' else despesas_grupos
        tot_bucket = total_receitas if natureza == 'C' else total_despesas

        g = bucket[cod_grupo]
        if g["descricao"] is None:
            g["descricao"] = desc_grupo or cod_grupo or "Sem grupo"

        g["valores"][ano_mes_str] += total_f
        tot_bucket[ano_mes_str] += total_f

        cat = g["cats"][cod_cat]
        if cat["descricao"] is None:
            cat["descricao"] = desc_cat or cod_cat or "Sem categoria"
        cat["valores"][ano_mes_str] += total_f

        if cod_ent:
            ent = cat["entidades"][cod_ent]
            if ent["nome"] is None:
                ent["nome"] = nome_ent or cod_ent
            ent["valores"][ano_mes_str] += total_f

    def serializar_grupos(grupos_dict):
        result = []
        for cod_grupo, g in sorted(grupos_dict.items()):
            cats = []
            for cod_cat, cat in sorted(g["cats"].items()):
                entidades = []
                for cod_ent, ent in sorted(cat["entidades"].items()):
                    entidades.append({
                        "cod_entidade": cod_ent,
                        "nome": ent["nome"],
                        "valores": dict(ent["valores"]),
                    })
                cats.append({
                    "cod_categoria": cod_cat,
                    "descricao": cat["descricao"],
                    "valores": dict(cat["valores"]),
                    "entidades": entidades,
                })
            result.append({
                "cod_grupo": cod_grupo,
                "descricao": g["descricao"],
                "valores": dict(g["valores"]),
                "categorias": cats,
            })
        return result

    # ── 4) Calcular saldo_inicial / variação / saldo_final por mês ────────
    saldo_ini_por_mes = {}
    variacoes = {}
    saldo_final_por_mes = {}

    saldo_corrente = saldo_acumulado
    for m in meses:
        rec = float(total_receitas.get(m, 0))
        desp = float(total_despesas.get(m, 0))
        variacao = rec - desp

        saldo_ini_por_mes[m] = saldo_corrente
        variacoes[m] = variacao
        saldo_corrente += variacao
        saldo_final_por_mes[m] = saldo_corrente

    return {
        "meses": meses,
        "saldo_inicial": saldo_ini_por_mes,
        "receitas": serializar_grupos(receitas_grupos),
        "despesas": serializar_grupos(despesas_grupos),
        "total_receitas": {k: float(v) for k, v in total_receitas.items()},
        "total_despesas": {k: float(v) for k, v in total_despesas.items()},
        "variacoes": variacoes,
        "saldo_final": saldo_final_por_mes,
    }


# Para rodar localmente de forma simples se executado diretamente
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
