from extractors.categorias import CategoriasExtractor
from extractors.departamentos import DepartamentosExtractor
from extractors.clientes import ClientesExtractor
from extractors.contas_correntes import ContasCorrentesExtractor
from extractors.contas_pagar import ContasPagarExtractor
from extractors.contas_receber import ContasReceberExtractor
from extractors.lancamentos_cc import LancamentosCCExtractor

# Mapeamento do nome do ETL para a respectiva classe extratora
EXTRACTOR_MAPPING = {
    "categorias": CategoriasExtractor,
    "departamentos": DepartamentosExtractor,
    "clientes": ClientesExtractor,
    "contas_correntes": ContasCorrentesExtractor,
    "contas_pagar": ContasPagarExtractor,
    "contas_receber": ContasReceberExtractor,
    "lancamentos_cc": LancamentosCCExtractor
}
