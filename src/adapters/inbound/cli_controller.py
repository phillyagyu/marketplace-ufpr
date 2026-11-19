"""Adaptador primário (inbound) — CLI.

Traduz chamadas da linha de comando em chamadas aos Casos de Uso e converte
respostas/erros em texto legível. Não contém regra de negócio: as validações
(RES01, RES02/ASR-02, RES03) vivem no domínio.

Direção das dependências (sempre para dentro):
    adapters.inbound -> application -> ports / domain
"""
from typing import List, Optional

from src.application.casos_de_uso import (
    ConcluirEAvaliarUseCase,
    ConsultarServicosUseCase,
    SolicitarContratacaoUseCase,
)
from src.application.consultar_contratacoes import ConsultarContratacoesUseCase
from src.domain.entidades import Avaliacao, Contratacao, Servico
from src.domain.excecoes import ErroDominio


class MarketplaceController:
    """GRASP Controller da camada de apresentação; recebe os casos de uso por injeção."""

    def __init__(
        self,
        consultar_servicos: ConsultarServicosUseCase,
        solicitar_contratacao: SolicitarContratacaoUseCase,
        concluir_e_avaliar: ConcluirEAvaliarUseCase,
        consultar_contratacoes: Optional[ConsultarContratacoesUseCase] = None,
    ):
        self._consultar = consultar_servicos
        self._solicitar = solicitar_contratacao
        self._concluir_e_avaliar = concluir_e_avaliar
        self._consultar_contratacoes = consultar_contratacoes

    # consulta (somente leitura)
    def listar_servicos_disponiveis(self, exibir: bool = True) -> List[Servico]:
        servicos = self._consultar.executar(apenas_com_slots_livres=True)
        if not exibir:
            return servicos
        if not servicos:
            print("  (nenhum serviço com horário livre no momento)")
            return []

        for servico in servicos:
            print(
                f"  • [{servico.id}] {servico.titulo} ({servico.categoria}) "
                f"— R$ {servico.valor:.2f} — prestador: {servico.prestador_id}"
            )
            for slot in servico.obter_slots_livres():
                print(
                    f"      {slot.id}: {slot.inicio:%d/%m %H:%M} → {slot.fim:%H:%M}"
                )
        return servicos

    def listar_minhas_contratacoes(
        self, usuario_id: str, exibir: bool = True
    ) -> List[Contratacao]:
        if self._consultar_contratacoes is None:
            return []
        contratacoes = self._consultar_contratacoes.executar(usuario_id)
        if not exibir:
            return contratacoes
        if not contratacoes:
            print("  (você ainda não tem contratações)")
            return []

        titulos = {
            s.id: s.titulo for s in self._consultar.executar(apenas_com_slots_livres=False)
        }
        for c in contratacoes:
            papel = "prestador" if c.prestador_id == usuario_id else "solicitante"
            nota = f" | nota {c.avaliacao.nota}" if c.avaliacao else ""
            print(
                f"  • {c.id} — {titulos.get(c.servico_id, c.servico_id)} / {c.slot_id} "
                f"— você é {papel} — {c.status.name}{nota}"
            )
        return contratacoes

    # comandos (alteram estado); ErroDominio vira mensagem, não derruba o programa
    def solicitar_contratacao(
        self, servico_id: str, slot_id: str, solicitante_id: str
    ) -> Optional[Contratacao]:
        print(f"  → {solicitante_id} solicita {servico_id} / {slot_id}")
        try:
            contratacao = self._solicitar.executar(servico_id, slot_id, solicitante_id)
        except ErroDominio as erro:
            self._exibir_bloqueio(erro)
            return None

        print(
            f"  ✔ Contratação {contratacao.id} criada "
            f"(status: {contratacao.status.name})"
        )
        return contratacao

    def concluir_servico(self, contratacao_id: str) -> Optional[Contratacao]:
        print(f"  → Concluindo contratação {contratacao_id}")
        try:
            contratacao = self._concluir_e_avaliar.concluir(contratacao_id)
        except ErroDominio as erro:
            self._exibir_bloqueio(erro)
            return None

        print(f"  ✔ Contratação {contratacao.id} agora está {contratacao.status.name}")
        return contratacao

    def avaliar_servico(
        self, contratacao_id: str, nota: int, comentario: str
    ) -> Optional[Avaliacao]:
        print(f"  → Avaliando contratação {contratacao_id} com nota {nota}")
        try:
            avaliacao = self._concluir_e_avaliar.avaliar(contratacao_id, nota, comentario)
        except ErroDominio as erro:
            self._exibir_bloqueio(erro)
            return None

        print(f"  ✔ Avaliação registrada: nota {avaliacao.nota} — “{avaliacao.comentario}”")
        return avaliacao

    @staticmethod
    def _exibir_bloqueio(erro: ErroDominio) -> None:
        print(f"  ✖ BLOQUEADO [{type(erro).__name__}]: {erro.mensagem}")
