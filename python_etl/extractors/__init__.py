from extractors.categorias import CategoriasExtractor
from extractors.departamentos import DepartamentosExtractor
from extractors.clientes import ClientesExtractor
from extractors.contas_correntes import ContasCorrentesExtractor
from extractors.contas_pagar import ContasPagarExtractor
from extractors.contas_receber import ContasReceberExtractor
from extractors.lancamentos_cc import LancamentosCCExtractor
from extractors.movimentos import MovimentosExtractor

# Extractors de cadastro (master data) — sempre full reload, são pequenos
CADASTRO_MAPPING = {
    "categorias": CategoriasExtractor,
    "departamentos": DepartamentosExtractor,
    "clientes": ClientesExtractor,
    "contas_correntes": ContasCorrentesExtractor,
}

# Extractors de fato (transações) — suportam carga incremental via watermark
FATO_MAPPING = {
    "contas_pagar": ContasPagarExtractor,
    "contas_receber": ContasReceberExtractor,
    "lancamentos_cc": LancamentosCCExtractor,
}

# Movimentos financeiros — full reload a cada run (não é fato incremental).
# Fornece a data real de baixa (ddtpagamento) por título para a view unificada,
# corrigindo baixas agrupadas. Roda após os títulos.
MOVIMENTOS_MAPPING = {
    "movimentos": MovimentosExtractor,
}

# Mapeamento completo (cadastros primeiro para garantir FK das dims antes dos fatos)
EXTRACTOR_MAPPING = {**CADASTRO_MAPPING, **FATO_MAPPING, **MOVIMENTOS_MAPPING}
