from typing import List, Optional

from src.domain.entidades import Contratacao, Servico
from src.ports.interfaces import ContratacaoRepository, ServicoRepository


# repositorio em memoria para guardar e buscar servicos
class InMemoryServicoRepository(ServicoRepository):
    def __init__(self):
        self.servicos = {}

    def salvar(self, servico: Servico) -> None:
        self.servicos[servico.id] = servico

    def buscar_por_id(self, servico_id: str) -> Optional[Servico]:
        if servico_id in self.servicos:
            return self.servicos[servico_id]
        else:
            return None

    def listar_disponiveis(self) -> List[Servico]:
        disponiveis = []
        for servico in self.servicos.values():
            slots_livres = servico.obter_slots_livres()
            if len(slots_livres) > 0:
                disponiveis.append(servico)
        return disponiveis


# repositorio em memoria para guardar e buscar contratacoes
class InMemoryContratacaoRepository(ContratacaoRepository):
    def __init__(self):
        self.contratacoes = {}

    def salvar(self, contratacao: Contratacao) -> None:
        self.contratacoes[contratacao.id] = contratacao

    def buscar_por_id(self, contratacao_id: str) -> Optional[Contratacao]:
        if contratacao_id in self.contratacoes:
            return self.contratacoes[contratacao_id]
        else:
            return None

    def listar_por_usuario(self, usuario_id: str) -> List[Contratacao]:
        resultado = []
        for contratacao in self.contratacoes.values():
            if contratacao.solicitante_id == usuario_id or contratacao.prestador_id == usuario_id:
                resultado.append(contratacao)
        return resultado