from datetime import datetime
from enum import Enum
from typing import Optional

from excecoes import *


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
    def __init__(self, id: str, servico_id: str, inicio: datetime, fim: datetime, status: StatusSlot = StatusSlot.LIVRE):
        self.id = id
        self.servico_id = servico_id
        self.inicio = inicio
        self.fim = fim
        self.status = status

    def esta_livre(self) -> bool:
        return self.status == StatusSlot.LIVRE

    def reservar(self) -> None:
        if not self.esta_livre():
            raise SlotIndisponivelError()
        self.status = StatusSlot.RESERVADO

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
            
    def adicionar_slot(self, inicio: datetime, fim: datetime) -> SlotDisponibilidade:
        numero_slot = len(self.slots) + 1
        novo_id = f"slot-{numero_slot}"
        
        novo_slot = SlotDisponibilidade(id = novo_id, servico_id = self.id, inicio = inicio, fim = fim, status = StatusSlot.LIVRE)
        self.slots.append(novo_slot)
        return novo_slot

    def buscar_slot(self, slot_id: str) -> SlotDisponibilidade:
        for slot in self.slots:
            if slot.id == slot_id:
                return slot
        raise ErroDominio(f"Slot '{slot_id}' não encontrado no serviço '{self.id}'.")

    def obter_slots_livres(self) -> list:
        slots_livres = []
        for slot in self.slots:
            if slot.esta_livre():
                slots_livres.append(slot)
        return slots_livres

    def validar_contratante(self, solicitante_id: str) -> None:
        if solicitante_id == self.prestador_id:
            raise AutoContratacaoError()


class Avaliacao:
    def __init__(self, id: str, contratacao_id: str, nota: int, comentario: str, criado_em: datetime = datetime.now(),):
        self.id = id
        self.contratacao_id = contratacao_id
        self.nota = nota
        self.comentario = comentario.strip()
        self.criado_em = criado_em
        self.validar_nota()

    def validar_nota(self) -> None:
        if self.nota < 1 or self.nota > 5:
            raise NotaInvalidaError()
        if self.comentario == "":
            raise NotaInvalidaError()


class Contratacao:
    def __init__(self, id: str, servico_id: str, slot_id: str, solicitante_id: str, prestador_id: str, status: StatusContratacao = StatusContratacao.CONFIRMADA, criado_em: datetime = datetime.now(), avaliacao: Optional[Avaliacao] = None):
        self.id = id
        self.servico_id = servico_id
        self.slot_id = slot_id
        self.solicitante_id = solicitante_id
        self.prestador_id = prestador_id
        self.status = status
        self.criado_em = criado_em
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
        nova_avaliacao = Avaliacao(id = id_avaliacao, contratacao_id = self.id, nota = nota, comentario = comentario)
        self.avaliacao = nova_avaliacao
        return self.avaliacao