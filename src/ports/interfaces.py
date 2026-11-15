from abc import ABC, abstractmethod
from typing import List, Optional

from src.domain.entidades import Contratacao, Servico

class ServicoRepository(ABC):
    @abstractmethod
    def salvar(self, servico: Servico) -> None:
        pass

    @abstractmethod
    def buscar_por_id(self, servico_id: str) -> Optional[Servico]:
        pass

    @abstractmethod
    def listar_disponiveis(self) -> List[Servico]:
        pass


class ContratacaoRepository(ABC):
    @abstractmethod
    def salvar(self, contratacao: Contratacao) -> None:
        pass

    @abstractmethod
    def buscar_por_id(self, contratacao_id: str) -> Optional[Contratacao]:
        pass

    @abstractmethod
    def listar_por_usuario(self, usuario_id: str) -> List[Contratacao]:
        pass


class NotificadorPort(ABC):
    @abstractmethod
    def notificar(self, destinatario: str, assunto: str, mensagem: str) -> None:
        pass