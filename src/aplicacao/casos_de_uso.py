from typing import List
from uuid import uuid4

from src.domain.entidades import Avaliacao, Contratacao, Servico, StatusContratacao
from src.domain.excecoes import ErroDominio
from src.ports.interfaces import (
    ContratacaoRepository,
    NotificadorPort,
    ServicoRepository,
)


class SolicitarContratacaoUseCase:
    def __init__(
        self,
        servico_repo: ServicoRepository,
        contratacao_repo: ContratacaoRepository,
        notificador: NotificadorPort,
    ):
        self.servico_repo = servico_repo
        self.contratacao_repo = contratacao_repo
        self.notificador = notificador

    def executar(self, servico_id: str, slot_id: str, solicitante_id: str) -> Contratacao:
        servico = self.servico_repo.buscar_por_id(servico_id)
        if servico is None:
            raise ErroDominio(f"Serviço '{servico_id}' não encontrado.")

        servico.validar_contratante(solicitante_id)

        slot = servico.buscar_slot(slot_id)
        slot.reservar()

        nova_contratacao = Contratacao(
            id=f"cont-{uuid4().hex[:8]}",
            servico_id=servico.id,
            slot_id=slot.id,
            solicitante_id=solicitante_id,
            prestador_id=servico.prestador_id,
            status=StatusContratacao.CONFIRMADA,
        )

        self.servico_repo.salvar(servico)
        self.contratacao_repo.salvar(nova_contratacao)

        self.notificador.notificar(
            destinatario=servico.prestador_id,
            assunto="Nova Contratação Confirmada - CampusHub",
            mensagem=(
                f"O serviço '{servico.titulo}' foi contratado pelo usuário "
                f"'{solicitante_id}' para o horário {slot.inicio.strftime('%d/%m %H:%M')}."
            ),
        )

        return nova_contratacao


class ConsultarServicosUseCase:
    def __init__(self, servico_repo: ServicoRepository):
        self.servico_repo = servico_repo

    def executar(self, apenas_com_slots_livres: bool = True) -> List[Servico]:
        servicos = self.servico_repo.listar_disponiveis()
        if not apenas_com_slots_livres:
            return servicos
        return [s for s in servicos if len(s.obter_slots_livres()) > 0]


class ConcluirEAvaliarUseCase:
    def __init__(
        self,
        contratacao_repo: ContratacaoRepository,
        notificador: NotificadorPort,
    ):
        self.contratacao_repo = contratacao_repo
        self.notificador = notificador

    def concluir(self, contratacao_id: str) -> Contratacao:
        contratacao = self.contratacao_repo.buscar_por_id(contratacao_id)
        if contratacao is None:
            raise ErroDominio(f"Contratação '{contratacao_id}' não encontrada.")

        contratacao.concluir()
        self.contratacao_repo.salvar(contratacao)

        self.notificador.notificar(
            destinatario=contratacao.solicitante_id,
            assunto="Serviço Concluído - CampusHub",
            mensagem=f"A contratação '{contratacao.id}' foi concluída. Você já pode avaliá-la!",
        )
        return contratacao

    def avaliar(self, contratacao_id: str, nota: int, comentario: str) -> Avaliacao:
        contratacao = self.contratacao_repo.buscar_por_id(contratacao_id)
        if contratacao is None:
            raise ErroDominio(f"Contratação '{contratacao_id}' não encontrada.")

        avaliacao = contratacao.registrar_avaliacao(nota=nota, comentario=comentario)
        self.contratacao_repo.salvar(contratacao)
        return avaliacao