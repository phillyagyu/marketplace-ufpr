from typing import List, Optional

from src.application.casos_de_uso import (
    ConcluirEAvaliarUseCase,
    ConsultarServicosUseCase,
    SolicitarContratacaoUseCase,
)
from src.domain.entidades import Avaliacao, Contratacao, Servico
from src.domain.excecoes import ErroDominio


class MarketplaceController:
    """Adaptador primário (Inbound Adapter / Controller GRASP) para interação via CLI."""

    def __init__(
        self,
        solicitar_uc: SolicitarContratacaoUseCase,
        consultar_uc: ConsultarServicosUseCase,
        concluir_avaliar_uc: ConcluirEAvaliarUseCase,
    ):
        self.solicitar_uc = solicitar_uc
        self.consultar_uc = consultar_uc
        self.concluir_avaliar_uc = concluir_avaliar_uc

    def listar_servicos_disponiveis(self, apenas_com_slots_livres: bool = True) -> List[Servico]:
        servicos = self.consultar_uc.executar(apenas_com_slots_livres=apenas_com_slots_livres)
        if not servicos:
            print("  [INFO] Nenhum serviço disponível encontrado para o filtro selecionado.")
            return []

        for servico in servicos:
            slots_livres = servico.obter_slots_livres()
            print(
                f"  • [{servico.id}] {servico.titulo} ({servico.categoria}) "
                f"| Prestador: {servico.prestador_id} | R$ {servico.valor:.2f} "
                f"| Slots livres: {len(slots_livres)}/{len(servico.slots)}"
            )
            for slot in servico.slots:
                horario = f"{slot.inicio.strftime('%d/%m/%Y %H:%M')} às {slot.fim.strftime('%H:%M')}"
                print(f"      - Slot [{slot.id}]: {horario} -> Status: {slot.status.value.upper()}")
        return servicos

    def solicitar_contratacao(
        self,
        servico_id: str,
        slot_id: str,
        solicitante_id: str,
    ) -> Optional[Contratacao]:
        try:
            contratacao = self.solicitar_uc.executar(
                servico_id=servico_id,
                slot_id=slot_id,
                solicitante_id=solicitante_id,
            )
            print(
                f"  [SUCESSO] Contratação '{contratacao.id}' criada com status "
                f"'{contratacao.status.value.upper()}' (Serviço: {servico_id} | Slot: {slot_id} "
                f"| Solicitante: {solicitante_id})."
            )
            return contratacao
        except ErroDominio as erro:
            print(f"  [ERRO DE NEGÓCIO BLOQUEADO PELO DOMÍNIO] {erro.__class__.__name__}: \"{erro.mensagem}\"")
            return None

    def concluir_servico(self, contratacao_id: str) -> Optional[Contratacao]:
        try:
            contratacao = self.concluir_avaliar_uc.concluir(contratacao_id=contratacao_id)
            print(
                f"  [SUCESSO] Contratação '{contratacao.id}' atualizada para "
                f"'{contratacao.status.value.upper()}'."
            )
            return contratacao
        except ErroDominio as erro:
            print(f"  [ERRO DE NEGÓCIO BLOQUEADO PELO DOMÍNIO] {erro.__class__.__name__}: \"{erro.mensagem}\"")
            return None

    def avaliar_servico(
        self,
        contratacao_id: str,
        nota: int,
        comentario: str,
    ) -> Optional[Avaliacao]:
        try:
            avaliacao = self.concluir_avaliar_uc.avaliar(
                contratacao_id=contratacao_id,
                nota=nota,
                comentario=comentario,
            )
            print(
                f"  [SUCESSO] Avaliação '{avaliacao.id}' registrada! "
                f"Nota: {avaliacao.nota}/5 | Comentário: \"{avaliacao.comentario}\""
            )
            return avaliacao
        except ErroDominio as erro:
            print(f"  [ERRO DE NEGÓCIO BLOQUEADO PELO DOMÍNIO] {erro.__class__.__name__}: \"{erro.mensagem}\"")
            return None
