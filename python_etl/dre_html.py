"""
Módulo de conteúdo HTML para a tela do DRE.
Mantido separado de app.py para deixar o arquivo principal limpo.
"""


def get_dre_html() -> str:
    return """<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DRE — Demonstrativo de Resultado</title>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-primary: #0a0c16;
            --bg-secondary: rgba(21, 26, 48, 0.4);
            --bg-tertiary: rgba(30, 36, 68, 0.6);
            --border-color: rgba(255, 255, 255, 0.08);
            --text-primary: #f3f4f6;
            --text-secondary: #9ca3af;
            --text-muted: #6b7280;
            --accent-color: #6366f1;
            --accent-hover: #4f46e5;
            --success: #10b981;
            --error: #ef4444;
            --warning: #f59e0b;
            --receita: #10b981;
            --despesa: #ef4444;
            --saldo-pos: #10b981;
            --saldo-neg: #ef4444;
            --card-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
            --row-hover: rgba(99, 102, 241, 0.06);
        }

        * { box-sizing: border-box; margin: 0; padding: 0; }

        body {
            font-family: 'Plus Jakarta Sans', sans-serif;
            background: radial-gradient(circle at top right, #1d1b3c, var(--bg-primary) 60%);
            color: var(--text-primary);
            min-height: 100vh;
            padding: 2rem;
            line-height: 1.5;
        }

        .container { max-width: 1600px; margin: 0 auto; }

        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 2rem;
            padding-bottom: 1rem;
            border-bottom: 1px solid var(--border-color);
            flex-wrap: wrap;
            gap: 1rem;
        }

        .logo-area h1 {
            font-size: 1.8rem;
            font-weight: 700;
            background: linear-gradient(135deg, #a78bfa, #6366f1);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            letter-spacing: -0.5px;
        }

        .logo-area p {
            font-size: 0.9rem;
            color: var(--text-secondary);
            margin-top: 0.25rem;
        }

        .nav-back {
            display: inline-flex;
            align-items: center;
            gap: 0.4rem;
            padding: 0.5rem 1rem;
            background: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: 9999px;
            color: var(--text-secondary);
            text-decoration: none;
            font-size: 0.85rem;
            backdrop-filter: blur(10px);
            transition: all 0.2s;
        }
        .nav-back:hover { color: var(--text-primary); border-color: var(--accent-color); }

        /* ── Filtros ── */
        .filters-card {
            background: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            padding: 1.25rem 1.5rem;
            backdrop-filter: blur(16px);
            box-shadow: var(--card-shadow);
            display: flex;
            flex-wrap: wrap;
            gap: 1rem;
            align-items: flex-end;
            margin-bottom: 1.5rem;
        }

        .filter-group {
            display: flex;
            flex-direction: column;
            gap: 0.4rem;
        }

        .filter-group label {
            font-size: 0.75rem;
            font-weight: 600;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }

        .filter-group select,
        .filter-group input {
            background: rgba(255,255,255,0.05);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            color: var(--text-primary);
            padding: 0.5rem 0.75rem;
            font-size: 0.9rem;
            font-family: inherit;
            min-width: 140px;
            outline: none;
            transition: border-color 0.2s;
        }

        .filter-group select:focus,
        .filter-group input:focus { border-color: var(--accent-color); }
        .filter-group select option { background: #1a1d2e; }

        .btn {
            padding: 0.55rem 1.25rem;
            border-radius: 8px;
            font-size: 0.9rem;
            font-weight: 600;
            font-family: inherit;
            cursor: pointer;
            border: none;
            transition: all 0.2s;
        }

        .btn-primary {
            background: var(--accent-color);
            color: #fff;
        }
        .btn-primary:hover { background: var(--accent-hover); }
        .btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }

        .btn-ghost {
            background: transparent;
            border: 1px solid var(--border-color);
            color: var(--text-secondary);
        }
        .btn-ghost:hover { border-color: var(--accent-color); color: var(--text-primary); }

        /* ── Tabela DRE ── */
        .table-card {
            background: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            backdrop-filter: blur(16px);
            box-shadow: var(--card-shadow);
            overflow: hidden;
        }

        .table-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 1.25rem 1.5rem;
            border-bottom: 1px solid var(--border-color);
        }

        .table-header h2 {
            font-size: 1rem;
            font-weight: 600;
        }

        .table-meta {
            font-size: 0.8rem;
            color: var(--text-secondary);
        }

        .table-wrapper {
            overflow-x: auto;
        }

        table {
            width: 100%;
            border-collapse: collapse;
            font-size: 0.875rem;
        }

        thead th {
            position: sticky;
            top: 0;
            background: rgba(10, 12, 22, 0.95);
            padding: 0.75rem 1rem;
            text-align: right;
            font-size: 0.75rem;
            font-weight: 600;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 0.05em;
            border-bottom: 1px solid var(--border-color);
            white-space: nowrap;
        }

        thead th:first-child { text-align: left; position: sticky; left: 0; z-index: 2; min-width: 280px; }
        thead th:last-child { font-weight: 700; color: var(--text-primary); }

        /* ── Linhas ── */
        tbody tr { border-bottom: 1px solid rgba(255,255,255,0.03); transition: background 0.15s; }
        tbody tr:hover { background: var(--row-hover); }

        td {
            padding: 0.5rem 1rem;
            text-align: right;
            white-space: nowrap;
            color: var(--text-secondary);
        }

        td:first-child {
            text-align: left;
            position: sticky;
            left: 0;
            background: rgba(10, 12, 22, 0.9);
        }
        tr:hover td:first-child { background: rgba(20, 22, 40, 0.97); }

        /* ── Níveis hierárquicos ── */

        /* Linhas de seção (SALDO INICIAL, TOTAL RECEITAS, etc.) */
        tr.row-section td {
            background: rgba(99, 102, 241, 0.12);
            font-weight: 700;
            font-size: 0.82rem;
            text-transform: uppercase;
            letter-spacing: 0.04em;
            color: var(--text-primary);
            padding-top: 0.65rem;
            padding-bottom: 0.65rem;
        }
        tr.row-section td:first-child { background: rgba(99, 102, 241, 0.14); }

        /* Grupo (nível 0) */
        tr.row-grupo td {
            font-weight: 600;
            color: var(--text-primary);
            padding-top: 0.6rem;
            padding-bottom: 0.6rem;
        }
        tr.row-grupo td:first-child { padding-left: 1rem; }

        /* Categoria filha (nível 1) */
        tr.row-categoria td { color: var(--text-secondary); }
        tr.row-categoria td:first-child { padding-left: 2.25rem; }

        /* Fornecedor/entidade (nível 2) */
        tr.row-entidade td { color: var(--text-muted); font-size: 0.82rem; }
        tr.row-entidade td:first-child { padding-left: 3.5rem; }

        /* Separadores visuais */
        tr.row-divider td { padding: 0; border-bottom: 1px solid rgba(255,255,255,0.08); }

        /* Toggle expand */
        .toggle-btn {
            cursor: pointer;
            display: inline-flex;
            align-items: center;
            gap: 0.4rem;
            user-select: none;
        }
        .toggle-btn .arrow {
            display: inline-block;
            width: 14px;
            height: 14px;
            transition: transform 0.2s;
            opacity: 0.6;
            flex-shrink: 0;
        }
        .toggle-btn .arrow.open { transform: rotate(90deg); }

        /* Valores coloridos */
        .val-receita { color: var(--receita); }
        .val-despesa { color: var(--despesa); }
        .val-pos { color: var(--saldo-pos); }
        .val-neg { color: var(--saldo-neg); }
        .val-neutral { color: var(--text-secondary); }
        .val-total { font-weight: 600; color: var(--text-primary); }

        /* Estado de carregamento / vazio */
        .state-overlay {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 4rem 2rem;
            gap: 1rem;
            color: var(--text-secondary);
        }
        .state-overlay svg { opacity: 0.3; }
        .state-overlay p { font-size: 0.95rem; }

        .spinner {
            width: 36px; height: 36px;
            border: 3px solid rgba(99,102,241,0.2);
            border-top-color: var(--accent-color);
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
        }
        @keyframes spin { to { transform: rotate(360deg); } }

        .error-msg {
            background: rgba(239,68,68,0.1);
            border: 1px solid rgba(239,68,68,0.3);
            border-radius: 8px;
            padding: 0.75rem 1rem;
            color: #fca5a5;
            font-size: 0.85rem;
            margin: 1rem 1.5rem;
        }

        /* Centro de custo badge */
        .cc-badge {
            display: inline-block;
            padding: 0.15rem 0.5rem;
            border-radius: 9999px;
            background: rgba(99,102,241,0.15);
            border: 1px solid rgba(99,102,241,0.3);
            font-size: 0.72rem;
            color: #a5b4fc;
            margin-left: 0.5rem;
            vertical-align: middle;
        }
    </style>
</head>
<body>
<div class="container">

    <header>
        <div class="logo-area">
            <h1>DRE — Demonstrativo de Resultado</h1>
            <p>Estrutura hierárquica: grupo → categoria → fornecedor · colunas mensais</p>
        </div>
        <a href="/" class="nav-back">
            ← Painel ETL
        </a>
    </header>

    <!-- Filtros -->
    <div class="filters-card">
        <div class="filter-group">
            <label>Ano</label>
            <input type="number" id="filtro-ano" value="" min="2022" max="2030" style="width:90px;">
        </div>
        <div class="filter-group">
            <label>Mês Inicial</label>
            <select id="filtro-mes-ini">
                <option value="1">Janeiro</option>
                <option value="2">Fevereiro</option>
                <option value="3">Março</option>
                <option value="4">Abril</option>
                <option value="5">Maio</option>
                <option value="6">Junho</option>
                <option value="7">Julho</option>
                <option value="8">Agosto</option>
                <option value="9">Setembro</option>
                <option value="10">Outubro</option>
                <option value="11">Novembro</option>
                <option value="12">Dezembro</option>
            </select>
        </div>
        <div class="filter-group">
            <label>Mês Final</label>
            <select id="filtro-mes-fim">
                <option value="1">Janeiro</option>
                <option value="2">Fevereiro</option>
                <option value="3">Março</option>
                <option value="4">Abril</option>
                <option value="5">Maio</option>
                <option value="6">Junho</option>
                <option value="7">Julho</option>
                <option value="8">Agosto</option>
                <option value="9">Setembro</option>
                <option value="10">Outubro</option>
                <option value="11">Novembro</option>
                <option value="12" selected>Dezembro</option>
            </select>
        </div>
        <div class="filter-group">
            <label>Empresa</label>
            <select id="filtro-empresa" style="min-width:200px;">
                <option value="">Todas as empresas</option>
            </select>
        </div>
        <div class="filter-group">
            <label>Centro de Custo</label>
            <select id="filtro-departamento" style="min-width:200px;">
                <option value="">Todos os centros de custo</option>
            </select>
        </div>
        <button class="btn btn-primary" id="btn-gerar" onclick="gerarDRE()">
            Gerar DRE
        </button>
        <button class="btn btn-ghost" onclick="expandirTudo()">Expandir tudo</button>
        <button class="btn btn-ghost" onclick="recolherTudo()">Recolher tudo</button>
    </div>

    <!-- Tabela -->
    <div class="table-card">
        <div class="table-header">
            <h2 id="table-title">DRE</h2>
            <span class="table-meta" id="table-meta"></span>
        </div>
        <div id="error-container"></div>
        <div class="table-wrapper" id="table-wrapper">
            <div class="state-overlay" id="state-overlay">
                <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                    <rect x="3" y="3" width="18" height="18" rx="2"/><line x1="3" y1="9" x2="21" y2="9"/>
                    <line x1="9" y1="21" x2="9" y2="9"/><line x1="12" y1="14" x2="16" y2="14"/>
                    <line x1="12" y1="17" x2="16" y2="17"/>
                </svg>
                <p>Selecione o período e clique em <strong>Gerar DRE</strong></p>
            </div>
        </div>
    </div>

</div>

<script>
// ── Utilitários ──────────────────────────────────────────────────────────────

const MESES_PT = ['Jan','Fev','Mar','Abr','Mai','Jun','Jul','Ago','Set','Out','Nov','Dez'];

function nomeMes(anoMes) {
    // anoMes = 202601
    const m = parseInt(String(anoMes).slice(4)) - 1;
    const a = String(anoMes).slice(2, 4);
    return `${MESES_PT[m]}/${a}`;
}

function fmt(val) {
    if (val === null || val === undefined || val === 0) return '—';
    return new Intl.NumberFormat('pt-BR', { style: 'decimal', minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(val);
}

function colorVal(val, classe) {
    if (!val) return `<span class="val-neutral">—</span>`;
    return `<span class="${classe}">${fmt(val)}</span>`;
}

function colorSaldo(val) {
    if (val === null || val === undefined) return `<span class="val-neutral">—</span>`;
    if (val === 0) return `<span class="val-neutral">${fmt(val)}</span>`;
    return val > 0
        ? `<span class="val-pos">${fmt(val)}</span>`
        : `<span class="val-neg">${fmt(val)}</span>`;
}

// ── Inicialização ────────────────────────────────────────────────────────────

window.addEventListener('DOMContentLoaded', async () => {
    // Padrão: ano atual, mês 1 a mês atual
    const hoje = new Date();
    document.getElementById('filtro-ano').value = hoje.getFullYear();
    document.getElementById('filtro-mes-ini').value = 1;
    document.getElementById('filtro-mes-fim').value = hoje.getMonth() + 1;

    // Carrega empresas
    try {
        const emps = await fetch('/api/empresas').then(r => r.json());
        const selEmp = document.getElementById('filtro-empresa');
        emps.forEach(e => {
            const opt = document.createElement('option');
            opt.value = e.id;
            opt.textContent = e.nome;
            selEmp.appendChild(opt);
        });
    } catch (e) {
        console.warn('Não foi possível carregar empresas:', e);
    }

    // Carrega departamentos
    try {
        const deps = await fetch('/api/departamentos').then(r => r.json());
        const sel = document.getElementById('filtro-departamento');
        deps.forEach(d => {
            const opt = document.createElement('option');
            opt.value = d.codigo;
            opt.textContent = d.descricao;
            sel.appendChild(opt);
        });
    } catch (e) {
        console.warn('Não foi possível carregar departamentos:', e);
    }
});

// ── Geração do DRE ───────────────────────────────────────────────────────────

async function gerarDRE() {
    const ano      = document.getElementById('filtro-ano').value;
    const mesIni   = document.getElementById('filtro-mes-ini').value;
    const mesFim   = document.getElementById('filtro-mes-fim').value;
    const depart   = document.getElementById('filtro-departamento').value;
    const empresa  = document.getElementById('filtro-empresa').value;

    if (!ano || parseInt(mesIni) > parseInt(mesFim)) {
        mostrarErro('Período inválido: verifique o ano e os meses selecionados.');
        return;
    }

    const btn = document.getElementById('btn-gerar');
    btn.disabled = true;
    btn.textContent = 'Carregando...';
    limparErro();
    mostrarSpinner();

    try {
        const params = new URLSearchParams({ ano, mes_ini: mesIni, mes_fim: mesFim });
        if (depart) params.append('departamento', depart);
        if (empresa) params.append('empresa_id', empresa);

        const data = await fetch(`/api/dre?${params}`).then(async r => {
            if (!r.ok) {
                const err = await r.json().catch(() => ({ detail: r.statusText }));
                throw new Error(err.detail || r.statusText);
            }
            return r.json();
        });

        renderizarTabela(data, depart);
    } catch (e) {
        ocultarSpinner();
        mostrarErro(`Erro ao carregar DRE: ${e.message}`);
    } finally {
        btn.disabled = false;
        btn.textContent = 'Gerar DRE';
    }
}

// ── Renderização ─────────────────────────────────────────────────────────────

function renderizarTabela(data, codDepart) {
    const { meses, saldo_inicial, receitas, despesas, variacoes, saldo_final } = data;
    const total_receitas = data.total_receitas;
    const total_despesas = data.total_despesas;

    // Título
    const depSel = document.getElementById('filtro-departamento');
    const depLabel = depSel.options[depSel.selectedIndex].text;
    const empSel = document.getElementById('filtro-empresa');
    const empLabel = empSel.options[empSel.selectedIndex].text;
    const codEmpresa = empSel.value;
    const title = document.getElementById('table-title');
    let badges = '';
    if (codEmpresa) badges += ` <span class="cc-badge">${empLabel}</span>`;
    if (codDepart)  badges += ` <span class="cc-badge">${depLabel}</span>`;
    title.innerHTML = 'DRE' + badges;
    document.getElementById('table-meta').textContent =
        `${meses.length} mese${meses.length !== 1 ? 's' : ''}`;

    const wrapper = document.getElementById('table-wrapper');
    const overlay = document.getElementById('state-overlay');
    if (overlay) overlay.remove();

    // ── Cabeçalho ──
    let html = '<table id="dre-table"><thead><tr>';
    html += '<th>Descrição</th>';
    meses.forEach(m => { html += `<th>${nomeMes(m)}</th>`; });
    html += '<th>Total</th>';
    html += '</tr></thead><tbody>';

    // ── Função auxiliar: células de valores ──
    function celulasMeses(mapaValores, classeValor, comTotal = true) {
        let total = 0;
        let cells = '';
        meses.forEach(m => {
            const v = mapaValores[String(m)] || 0;
            total += v;
            cells += `<td>${v ? colorVal(v, classeValor) : '<span class="val-neutral">—</span>'}</td>`;
        });
        if (comTotal) cells += `<td class="val-total">${total ? colorVal(total, classeValor) : '<span class="val-neutral">—</span>'}</td>`;
        return cells;
    }

    function celulasSaldo(mapaValores) {
        let total = 0;
        let cells = '';
        meses.forEach(m => {
            const v = mapaValores[String(m)] !== undefined ? mapaValores[String(m)] : null;
            if (v !== null) total += v;
            cells += `<td>${colorSaldo(v)}</td>`;
        });
        cells += `<td class="val-total">${colorSaldo(total / (meses.length || 1))}</td>`; // média para saldo
        return cells;
    }

    // ── SALDO INICIAL ──
    html += '<tr class="row-section">';
    html += '<td>Saldo Inicial</td>';
    html += celulasSaldo(saldo_inicial);
    html += '</tr>';
    html += '<tr class="row-divider"><td colspan="' + (meses.length + 2) + '"></td></tr>';

    // ── RECEITAS ──
    html += '<tr class="row-section">';
    html += '<td>Receitas</td>';
    html += celulasMeses(total_receitas, 'val-receita');
    html += '</tr>';
    html += renderizarBlocoHierarquico(receitas, meses, 'val-receita', 'receita');
    html += '<tr class="row-divider"><td colspan="' + (meses.length + 2) + '"></td></tr>';

    // ── DESPESAS ──
    html += '<tr class="row-section">';
    html += '<td>Despesas</td>';
    html += celulasMeses(total_despesas, 'val-despesa');
    html += '</tr>';
    html += renderizarBlocoHierarquico(despesas, meses, 'val-despesa', 'despesa');
    html += '<tr class="row-divider"><td colspan="' + (meses.length + 2) + '"></td></tr>';

    // ── VARIAÇÃO DE CAIXA ──
    html += '<tr class="row-section">';
    html += '<td>Variação de Caixa do Período</td>';
    html += celulasSaldo(variacoes);
    html += '</tr>';

    // ── SALDO FINAL ──
    html += '<tr class="row-section">';
    html += '<td>Saldo Final</td>';
    // Saldo final por mês (cumulativo), exibir o valor de cada mês
    let cells = '';
    let totalFinal = 0;
    meses.forEach(m => {
        const v = saldo_final[String(m)] !== undefined ? saldo_final[String(m)] : null;
        if (v !== null) totalFinal = v; // último saldo final = o total relevante
        cells += `<td>${colorSaldo(v)}</td>`;
    });
    cells += `<td class="val-total">${colorSaldo(totalFinal)}</td>`;
    html += cells;
    html += '</tr>';

    html += '</tbody></table>';
    wrapper.innerHTML = html;
}

function renderizarBlocoHierarquico(grupos, meses, classeValor, prefixo) {
    let html = '';
    let grupoIdx = 0;

    grupos.forEach(grupo => {
        const gId = `${prefixo}-g-${grupoIdx++}`;
        let catIdx = 0;

        // Linha do grupo (nível 0)
        html += `<tr class="row-grupo" id="row-${gId}">`;
        html += `<td><span class="toggle-btn" onclick="toggleGrupo('${gId}')">
                    <svg class="arrow open" id="arrow-${gId}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                        <polyline points="9 18 15 12 9 6"/>
                    </svg>
                    ${escHtml(grupo.descricao)}
                </span></td>`;
        meses.forEach(m => {
            const v = grupo.valores[String(m)] || 0;
            html += `<td>${v ? colorVal(v, classeValor) : '<span class="val-neutral">—</span>'}</td>`;
        });
        // Total do grupo
        const totalGrupo = Object.values(grupo.valores).reduce((a, b) => a + b, 0);
        html += `<td class="val-total">${totalGrupo ? colorVal(totalGrupo, classeValor) : '<span class="val-neutral">—</span>'}</td>`;
        html += '</tr>';

        // Categorias filhas (nível 1)
        grupo.categorias.forEach(cat => {
            const cId = `${gId}-c-${catIdx++}`;
            let entIdx = 0;

            html += `<tr class="row-categoria" id="row-${cId}" data-grupo="${gId}">`;
            html += `<td><span class="toggle-btn" onclick="toggleCat('${cId}')">
                        <svg class="arrow open" id="arrow-${cId}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                            <polyline points="9 18 15 12 9 6"/>
                        </svg>
                        ${escHtml(cat.descricao)}
                    </span></td>`;
            meses.forEach(m => {
                const v = cat.valores[String(m)] || 0;
                html += `<td>${v ? colorVal(v, classeValor) : '<span class="val-neutral">—</span>'}</td>`;
            });
            const totalCat = Object.values(cat.valores).reduce((a, b) => a + b, 0);
            html += `<td class="val-total">${totalCat ? colorVal(totalCat, classeValor) : '<span class="val-neutral">—</span>'}</td>`;
            html += '</tr>';

            // Entidades/fornecedores (nível 2)
            cat.entidades.forEach(ent => {
                const eId = `${cId}-e-${entIdx++}`;
                html += `<tr class="row-entidade" id="row-${eId}" data-cat="${cId}" data-grupo="${gId}">`;
                html += `<td>${escHtml(ent.nome || ent.cod_entidade || '—')}</td>`;
                meses.forEach(m => {
                    const v = ent.valores[String(m)] || 0;
                    html += `<td>${v ? colorVal(v, classeValor) : '<span class="val-neutral">—</span>'}</td>`;
                });
                const totalEnt = Object.values(ent.valores).reduce((a, b) => a + b, 0);
                html += `<td class="val-total">${totalEnt ? colorVal(totalEnt, classeValor) : '<span class="val-neutral">—</span>'}</td>`;
                html += '</tr>';
            });
        });
    });

    return html;
}

// ── Toggle expand/collapse ───────────────────────────────────────────────────

function toggleGrupo(gId) {
    const arrow = document.getElementById(`arrow-${gId}`);
    const isOpen = arrow.classList.contains('open');
    arrow.classList.toggle('open', !isOpen);

    // Esconde/exibe categorias filhas e seus descendentes
    document.querySelectorAll(`[data-grupo="${gId}"]`).forEach(row => {
        row.style.display = isOpen ? 'none' : '';
        // Se colapsando o grupo, recolhe também as categorias
        if (isOpen) {
            const cId = row.id.replace('row-', '');
            const catArrow = document.getElementById(`arrow-${cId}`);
            if (catArrow) catArrow.classList.remove('open');
        }
    });
}

function toggleCat(cId) {
    const arrow = document.getElementById(`arrow-${cId}`);
    const isOpen = arrow.classList.contains('open');
    arrow.classList.toggle('open', !isOpen);

    document.querySelectorAll(`[data-cat="${cId}"]`).forEach(row => {
        row.style.display = isOpen ? 'none' : '';
    });
}

function expandirTudo() {
    document.querySelectorAll('.arrow').forEach(a => a.classList.add('open'));
    document.querySelectorAll('[data-grupo],[data-cat]').forEach(r => r.style.display = '');
}

function recolherTudo() {
    document.querySelectorAll('.arrow').forEach(a => a.classList.remove('open'));
    document.querySelectorAll('[data-grupo],[data-cat]').forEach(r => r.style.display = 'none');
}

// ── Helpers de UI ────────────────────────────────────────────────────────────

function mostrarSpinner() {
    const wrapper = document.getElementById('table-wrapper');
    wrapper.innerHTML = '<div class="state-overlay"><div class="spinner"></div><p>Carregando DRE...</p></div>';
}

function ocultarSpinner() {
    const wrapper = document.getElementById('table-wrapper');
    const overlay = wrapper.querySelector('.state-overlay');
    if (overlay) overlay.remove();
}

function mostrarErro(msg) {
    document.getElementById('error-container').innerHTML =
        `<div class="error-msg">${escHtml(msg)}</div>`;
}

function limparErro() {
    document.getElementById('error-container').innerHTML = '';
}

function escHtml(str) {
    if (!str) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}
</script>
</body>
</html>"""
