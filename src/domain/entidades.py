from datetime import datetime
from enum import Enum
from typing import Optional, List

from src.domain.excecoes import *

class StatusSlot(Enum):
    LIVRE = "livre"
    RESERVADO = "reservado"


class StatusContratacao(Enum):
    CONFIRMADA = "confirmada"
    CONCLUIDA = "concluida"
    CANCELADA = "cancelada"

# qualquer ator universitario (aluno, técnico ou docente)
class MembroComunidade:
    def __init__(self, id: str, nome: str, email: str, registro_academico: str):
        self.id = id
        self.nome = nome
        self.email = email
        self.registro_academico = registro_academico

# controla o estado da janela de horário
class SlotDisponibilidade:
    def __init__(self, id: str, servico_id: str, inicio: datetime, fim: datetime, status=None):
        self.id = id
        self.servico_id = servico_id
        self.inicio = inicio
        self.fim = fim

        if status is not None:
            self.status = status
        else:
            self.status = StatusSlot.LIVRE

    # verifica se o horario esta disponivel para reserva
    def esta_livre(self) -> bool:
        return self.status == StatusSlot.LIVRE

    # bloqueia o horario caso esteja livre, evitando overbooking
    def reservar(self) -> None:
        if not self.esta_livre():
            raise SlotIndisponivelError()
        self.status = StatusSlot.RESERVADO

    # devolve o horario para o estado livre em caso de cancelamento
    def liberar(self) -> None:
        self.status = StatusSlot.LIVRE

# mantem os dados da oferta, gerencia sua lista de horários
class Servico:
    def __init__(self, id: str, prestador_id: str, titulo: str, descricao: str, categoria: str, valor: float, slots=None):
        self.id = id
        self.prestador_id = prestador_id
        self.titulo = titulo
        self.descricao = descricao
        self.categoria = categoria
        self.valor = valor
        
        if slots is not None:
            self.slots = slots
        else:
            self.slots = []

    # cria e adiciona um novo slot de horario na agenda do servico     
    def adicionar_slot(self, inicio: datetime, fim: datetime) -> SlotDisponibilidade:
        numero_slot = len(self.slots) + 1
        novo_id = f"slot-{numero_slot}"
        
        novo_slot = SlotDisponibilidade(novo_id, self.id, inicio, fim)
        self.slots.append(novo_slot)
        return novo_slot

    def buscar_slot(self, slot_id: str) -> SlotDisponibilidade:
        for slot in self.slots:
            if slot.id == slot_id:
                return slot
        raise ErroDominio(f"Slot '{slot_id}' não encontrado no serviço '{self.id}'.")

    # retorna apenas os horarios que ainda estao com status livre
    def obter_slots_livres(self) -> List[SlotDisponibilidade]:
        slots_livres = []
        for slot in self.slots:
            if slot.esta_livre():
                slots_livres.append(slot)
        return slots_livres

    def validar_contratante(self, solicitante_id: str) -> None:
        if solicitante_id == self.prestador_id:
            raise AutoContratacaoError()

# representa a avaliacao do servico e garante nota valida (1 a 5) e comentario preenchido
class Avaliacao:
    def __init__(self, id: str, contratacao_id: str, nota: int, comentario: str, criado_em=None):
        self.id = id
        self.contratacao_id = contratacao_id
        self.nota = nota
        self.comentario = comentario.strip()

        if criado_em is not None:
            self.criado_em = criado_em
        else:
            self.criado_em = datetime.now()

        self.validar_nota()

    def validar_nota(self) -> None:
        if self.nota < 1 or self.nota > 5:
            raise NotaInvalidaError()
        if self.comentario == "":
            raise NotaInvalidaError()

# governa o ciclo de vida do contrato (confirmada, concluida, cancelada) e cria a avaliacao
class Contratacao:
    def __init__(self, id: str, servico_id: str, slot_id: str, solicitante_id: str, prestador_id: str, status=None, criado_em=None, avaliacao: Optional[Avaliacao]=None):
        self.id = id
        self.servico_id = servico_id
        self.slot_id = slot_id
        self.solicitante_id = solicitante_id
        self.prestador_id = prestador_id

        if status is not None:
            self.status = status
        else:
            self.status = StatusContratacao.CONFIRMADA

        if criado_em is not None:
            self.criado_em = criado_em
        else:
            self.criado_em = datetime.now()

        self.avaliacao = avaliacao

    def concluir(self) -> None:
        if self.status != StatusContratacao.CONFIRMADA:
            raise TransicaoEstadoInvalidaError("Apenas contratações CONFIRMADAS podem ser concluídas.")
        self.status = StatusContratacao.CONCLUIDA

    def cancelar(self) -> None:
        if self.status == StatusContratacao.CONCLUIDA:
            raise TransicaoEstadoInvalidaError("Não é possível cancelar uma contratação já CONCLUÍDA.")
        self.status = StatusContratacao.CANCELADA

    def registrar_avaliacao(self, nota: int, comentario: str) -> Avaliacao:
        if self.status != StatusContratacao.CONCLUIDA:
            raise TransicaoEstadoInvalidaError("A avaliação só pode ser registrada para contratações CONCLUÍDAS.")
        if self.avaliacao is not None:
            raise TransicaoEstadoInvalidaError("Esta contratação já possui uma avaliação registrada.")

        id_avaliacao = f"aval-{self.id}"
        nova_avaliacao = Avaliacao(id_avaliacao, self.id, nota, comentario)
        self.avaliacao = nova_avaliacao
        return self.avaliacao