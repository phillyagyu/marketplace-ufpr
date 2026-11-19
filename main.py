"""Composition Root do CampusHub + demonstração da fatia vertical (Seção 7).

Único ponto que conhece as classes concretas: instancia o SQLite, o notificador,
os casos de uso e o controller, e injeta tudo por construtor.

Executar:
    python -m src.main                  # demonstração automática (Seção 7)
    python -m src.main --interativo     # protótipo navegável (menu no terminal)
    python -m src.main -i --reset       # idem, recomeçando com o banco zerado
    python -m src.main --web            # versão web em http://127.0.0.1:8000
Notificador por SMTP: CAMPUSHUB_NOTIFICADOR=email python -m src.main
"""
import argparse
import os
import tempfile
from datetime import datetime, timedelta

from src.adapters.inbound.cli_controller import MarketplaceController
from src.adapters.inbound.cli_interativo import MenuInterativo
from src.adapters.inbound.web_app import WebApp, servir
from src.adapters.outbound import (
    EmailNotificador,
    NotificadorFake,
    SqliteContratacaoRepository,
    SqliteServicoRepository,
    criar_conexao_sqlite,
)
from src.application.casos_de_uso import (
    ConcluirEAvaliarUseCase,
    ConsultarServicosUseCase,
    SolicitarContratacaoUseCase,
)
from src.application.consultar_contratacoes import ConsultarContratacoesUseCase
from src.domain.entidades import Servico

DB_PATH = os.path.join(tempfile.gettempdir(), "campushub_demo.db")

PRESTADOR_ID = "membro-ana"      # oferece o serviço
SOLICITANTE_ID = "membro-bruno"  # contrata
OUTRO_ID = "membro-carla"        # tenta contratar o slot já reservado

USUARIOS = {PRESTADOR_ID: "Ana", SOLICITANTE_ID: "Bruno", OUTRO_ID: "Carla"}


def titulo(texto: str) -> None:
    print(f"\n{'=' * 72}\n{texto}\n{'=' * 72}")


def criar_notificador():
    """Dependência externa substituível (ASR-01): a escolha acontece só aqui."""
    if os.environ.get("CAMPUSHUB_NOTIFICADOR", "fake").lower() == "email":
        return EmailNotificador()
    return NotificadorFake()


def popular_dados(servico_repo: SqliteServicoRepository) -> Servico:
    """Cadastra serviços de exemplo. Retorna o primeiro (usado na demo automática)."""
    base = datetime.now().replace(minute=0, second=0, microsecond=0) + timedelta(days=1)
    dia2 = base + timedelta(days=1)

    monitoria = Servico("serv-001", PRESTADOR_ID, "Monitoria de Cálculo I",
                        "Reforço individual de limites e derivadas.", "Aulas particulares", 40.0)
    monitoria.adicionar_slot(base.replace(hour=14), base.replace(hour=15))
    monitoria.adicionar_slot(base.replace(hour=15), base.replace(hour=16))

    revisao = Servico("serv-002", OUTRO_ID, "Revisão de TCC",
                      "Revisão ortográfica e de normas ABNT.", "Revisão", 60.0)
    revisao.adicionar_slot(base.replace(hour=10), base.replace(hour=11))
    revisao.adicionar_slot(dia2.replace(hour=10), dia2.replace(hour=11))

    slides = Servico("serv-003", SOLICITANTE_ID, "Design de slides",
                     "Diagramação de apresentações acadêmicas.", "Design", 35.0)
    slides.adicionar_slot(base.replace(hour=16), base.replace(hour=17))

    for servico in (monitoria, revisao, slides):
        servico_repo.salvar(servico)
    return monitoria


def _componentes(db_path: str):
    """Instancia infraestrutura e casos de uso (único lugar que conhece as classes concretas)."""
    conexao = criar_conexao_sqlite(db_path)
    servico_repo = SqliteServicoRepository(conexao)
    contratacao_repo = SqliteContratacaoRepository(conexao)
    notificador = criar_notificador()
    casos = (
        ConsultarServicosUseCase(servico_repo),
        SolicitarContratacaoUseCase(servico_repo, contratacao_repo, notificador),
        ConcluirEAvaliarUseCase(contratacao_repo, notificador),
        ConsultarContratacoesUseCase(contratacao_repo),
    )
    return casos, notificador, conexao, servico_repo


def _caixa_de_entrada(notificador):
    """Leitura de notificações só existe para o NotificadorFake (e-mail apenas imprime log)."""
    if isinstance(notificador, NotificadorFake):
        return lambda uid: [m for m in notificador.mensagens_enviadas if m["destinatario"] == uid]
    return None


def montar(db_path: str):
    """Composition Root da CLI. Retorna (controller, notificador, conexao, servico_repo)."""
    casos, notificador, conexao, servico_repo = _componentes(db_path)
    return MarketplaceController(*casos), notificador, conexao, servico_repo


def montar_web(db_path: str):
    """Composition Root da Web. Retorna (app, conexao, servico_repo)."""
    casos, notificador, conexao, servico_repo = _componentes(db_path)
    return WebApp(*casos, USUARIOS, _caixa_de_entrada(notificador)), conexao, servico_repo


def web(reset: bool, db_path: str, porta: int) -> None:
    if reset and os.path.exists(db_path):
        os.remove(db_path)
    app, conexao, servico_repo = montar_web(db_path)
    if servico_repo.buscar_por_id("serv-001") is None:
        popular_dados(servico_repo)
    print(f"Banco SQLite: {db_path}")
    servir(app, porta=porta)
    conexao.close()


def interativo(reset: bool, db_path: str) -> None:
    if reset and os.path.exists(db_path):
        os.remove(db_path)
    controller, notificador, conexao, servico_repo = montar(db_path)
    if servico_repo.buscar_por_id("serv-001") is None:   # banco novo → semeia
        popular_dados(servico_repo)

    ler = _caixa_de_entrada(notificador)

    print(f"Banco SQLite: {db_path} (os dados persistem entre execuções; use --reset para zerar)")
    print(f"Notificador em uso: {type(notificador).__name__}")
    MenuInterativo(controller, USUARIOS, ler).executar()
    conexao.close()


def main() -> None:
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)   # banco recriado a cada execução: demo reproduzível
    controller, notificador, conexao, servico_repo = montar(DB_PATH)

    servico = popular_dados(servico_repo)
    slot_id = servico.slots[0].id
    print(f"CampusHub — demo da fatia vertical | banco SQLite: {DB_PATH}")
    print(f"Notificador em uso: {type(notificador).__name__}")

    # 1) CONSULTA
    titulo("1) Consulta: serviços e horários livres no campus")
    controller.listar_servicos_disponiveis()

    # 2) MUTAÇÃO + PERSISTÊNCIA + DEPENDÊNCIA EXTERNA
    titulo("2) Contratação válida → grava no SQLite → dispara notificação")
    contratacao = controller.solicitar_contratacao(servico.id, slot_id, SOLICITANTE_ID)
    assert contratacao is not None, "a contratação válida deveria ter sido criada"

    # prova de persistência: conexão e repositório novos, lendo do arquivo
    relido = SqliteContratacaoRepository(DB_PATH)
    recuperada = relido.buscar_por_id(contratacao.id)
    relido.conn.close()
    estado = recuperada.status.name if recuperada else "NÃO ENCONTRADA"
    print(f"  ⛁ Persistência: reabrindo o banco, {contratacao.id} → {estado}")
    if isinstance(notificador, NotificadorFake):
        for msg in notificador.mensagens_enviadas:
            print(f"  ✉ NotificadorFake → {msg['destinatario']} | {msg['assunto']}")

    # 3) ERRO 1 — RES01
    titulo("3) Fluxo de erro 1 (RES01): auto-contratação")
    controller.solicitar_contratacao(servico.id, slot_id, PRESTADOR_ID)

    # 4) ERRO 2 — RES02 / ASR-02
    titulo("4) Fluxo de erro 2 (RES02 / ASR-02): slot já reservado (anti-overbooking)")
    controller.solicitar_contratacao(servico.id, slot_id, OUTRO_ID)

    # 5) CICLO COMPLETO
    titulo("5) Ciclo completo: concluir e avaliar com nota 5")
    controller.concluir_servico(contratacao.id)
    controller.avaliar_servico(contratacao.id, 5, "Explicação clara e pontual!")

    titulo("Fim da demonstração")
    conexao.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="CampusHub — protótipo da fatia vertical")
    ap.add_argument("-i", "--interativo", action="store_true", help="abre o menu navegável")
    ap.add_argument("--reset", action="store_true", help="(interativo/web) apaga o banco antes de iniciar")
    ap.add_argument("--web", action="store_true", help="sobe a versão web")
    ap.add_argument("--porta", type=int, default=8000, help="(modo web) porta HTTP")
    ap.add_argument("--db", default="campushub.db", help="(interativo/web) arquivo SQLite")
    args = ap.parse_args()
    if args.web:
        web(args.reset, args.db, args.porta)
    elif args.interativo:
        interativo(args.reset, args.db)
    else:
        main()
