from typing import List

from src.domain.entidades import Contratacao
from src.ports.interfaces import ContratacaoRepository


class ConsultarContratacoesUseCase:
    """Consulta: contratações em que o usuário é solicitante ou prestador (mais antigas primeiro)."""

    def __init__(self, contratacao_repo: ContratacaoRepository):
        self.contratacao_repo = contratacao_repo

    def executar(self, usuario_id: str) -> List[Contratacao]:
        contratacoes = self.contratacao_repo.listar_por_usuario(usuario_id)
        return sorted(contratacoes, key=lambda c: c.criado_em)
