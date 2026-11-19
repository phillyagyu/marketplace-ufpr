"""Adaptador primário (inbound) — menu interativo e navegável no terminal.

Segundo adaptador de entrada sobre os MESMOS casos de uso: só cuida de
navegação, numeração de opções e leitura de teclado. Toda regra de negócio
continua no domínio; erros chegam já tratados pelo MarketplaceController.

A leitura de teclado é injetável (`entrada`) para permitir testes automatizados.
"""
from typing import Callable, Dict, List, Optional

from src.adapters.inbound.cli_controller import MarketplaceController
from src.domain.entidades import StatusContratacao

Notificacoes = Callable[[str], List[Dict[str, str]]]


class MenuInterativo:
    def __init__(
        self,
        controller: MarketplaceController,
        usuarios: Dict[str, str],
        ler_notificacoes: Optional[Notificacoes] = None,
        entrada: Callable[[str], str] = input,
    ):
        self._c = controller
        self._usuarios = usuarios            # id -> nome
        self._ler_notificacoes = ler_notificacoes
        self._entrada = entrada

    # ---------------------------------------------------------------- navegação
    def executar(self) -> None:
        print("\n╔══════════════════════════════════════════╗")
        print("║   CampusHub — Marketplace de Serviços    ║")
        print("╚══════════════════════════════════════════╝")
        try:
            usuario = self._escolher_usuario()
            while usuario is not None:
                usuario = self._menu_principal(usuario)
        except (EOFError, KeyboardInterrupt):
            print()
        print("\nAté logo!")

    def _escolher_usuario(self) -> Optional[str]:
        ids = list(self._usuarios)
        i = self._escolher("Quem é você? (login simulado)", [f"{self._usuarios[u]} ({u})" for u in ids], "Sair")
        return None if i is None else ids[i]

    def _menu_principal(self, usuario: str) -> Optional[str]:
        """Retorna o usuário ativo (pode ser outro) ou None para encerrar."""
        opcoes = [
            "Ver serviços disponíveis",
            "Contratar um serviço",
            "Minhas contratações",
            "Concluir um serviço que prestei",
            "Avaliar um serviço que contratei",
        ]
        if self._ler_notificacoes:
            opcoes.append("Minhas notificações")
        opcoes.append("Trocar de usuário")

        i = self._escolher(f"Menu — {self._usuarios[usuario]}", opcoes, "Sair")
        if i is None:
            return None
        escolhida = opcoes[i]

        if escolhida.startswith("Ver"):
            self._c.listar_servicos_disponiveis()
        elif escolhida.startswith("Contratar"):
            self._fluxo_contratar(usuario)
        elif escolhida.startswith("Minhas contr"):
            self._c.listar_minhas_contratacoes(usuario)
        elif escolhida.startswith("Concluir"):
            self._fluxo_concluir(usuario)
        elif escolhida.startswith("Avaliar"):
            self._fluxo_avaliar(usuario)
        elif escolhida.startswith("Minhas not"):
            self._mostrar_notificacoes(usuario)
        elif escolhida.startswith("Trocar"):
            return self._escolher_usuario()
        return usuario

    # ------------------------------------------------------------------- fluxos
    def _fluxo_contratar(self, usuario: str) -> None:
        servicos = self._c.listar_servicos_disponiveis(exibir=False)
        if not servicos:
            print("  (nenhum serviço com horário livre)")
            return
        i = self._escolher(
            "Qual serviço?",
            [f"{s.titulo} — R$ {s.valor:.2f} — prestador {s.prestador_id}" for s in servicos],
        )
        if i is None:
            return
        servico = servicos[i]
        livres = servico.obter_slots_livres()
        j = self._escolher(
            f"Qual horário de “{servico.titulo}”?",
            [f"{s.inicio:%d/%m %H:%M} → {s.fim:%H:%M}  [{s.id}]" for s in livres],
        )
        if j is None:
            return
        # sem pré-validação aqui: quem decide é o domínio (RES01 / RES02)
        self._c.solicitar_contratacao(servico.id, livres[j].id, usuario)

    def _fluxo_concluir(self, usuario: str) -> None:
        # filtro de apresentação: mostra só o que faz sentido para o prestador
        pendentes = [
            c for c in self._c.listar_minhas_contratacoes(usuario, exibir=False)
            if c.prestador_id == usuario and c.status == StatusContratacao.CONFIRMADA
        ]
        if not pendentes:
            print("  (nenhuma contratação confirmada aguardando conclusão)")
            return
        i = self._escolher(
            "Qual contratação concluir?",
            [f"{c.id} — {c.slot_id} — solicitante {c.solicitante_id}" for c in pendentes],
        )
        if i is not None:
            self._c.concluir_servico(pendentes[i].id)

    def _fluxo_avaliar(self, usuario: str) -> None:
        avaliaveis = [
            c for c in self._c.listar_minhas_contratacoes(usuario, exibir=False)
            if c.solicitante_id == usuario
            and c.status == StatusContratacao.CONCLUIDA
            and c.avaliacao is None
        ]
        if not avaliaveis:
            print("  (nenhum serviço concluído aguardando sua avaliação)")
            return
        i = self._escolher(
            "Qual serviço avaliar?",
            [f"{c.id} — {c.slot_id} — prestador {c.prestador_id}" for c in avaliaveis],
        )
        if i is None:
            return
        try:
            nota = int(self._entrada("  Nota (1 a 5): ").strip())
        except ValueError:
            print("  ✖ Digite um número inteiro.")
            return
        comentario = self._entrada("  Comentário: ")
        # nota fora de 1..5 / comentário vazio: o domínio recusa (NotaInvalidaError)
        self._c.avaliar_servico(avaliaveis[i].id, nota, comentario)

    def _mostrar_notificacoes(self, usuario: str) -> None:
        msgs = self._ler_notificacoes(usuario)
        if not msgs:
            print("  (nenhuma notificação)")
        for m in msgs:
            print(f"  ✉ {m['assunto']}\n      {m['mensagem']}")

    # ------------------------------------------------------------------ helpers
    def _escolher(self, titulo: str, opcoes: List[str], rotulo_zero: str = "Voltar") -> Optional[int]:
        """Mostra opções numeradas; 0 = voltar/sair. Repete até receber entrada válida."""
        while True:
            print(f"\n{titulo}")
            for n, texto in enumerate(opcoes, 1):
                print(f"  {n}) {texto}")
            print(f"  0) {rotulo_zero}")
            bruto = self._entrada("> ").strip()
            if bruto == "0":
                return None
            if bruto.isdigit() and 1 <= int(bruto) <= len(opcoes):
                return int(bruto) - 1
            print("  ✖ Opção inválida, tente novamente.")
