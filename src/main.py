from datetime import datetime
from pathlib import Path

from src.adapters.inbound.cli_controller import MarketplaceController
from src.adapters.outbound.notificadores import EmailNotificador
from src.adapters.outbound.sqlite_repositorios import (
    SqliteContratacaoRepository,
    SqliteServicoRepository,
    criar_conexao_sqlite,
)
from src.application.casos_de_uso import (
    ConcluirEAvaliarUseCase,
    ConsultarServicosUseCase,
    SolicitarContratacaoUseCase,
)
from src.domain.entidades import MembroComunidade, Servico


def popular_dados_iniciais(servico_repo: SqliteServicoRepository) -> tuple[MembroComunidade, MembroComunidade, MembroComunidade]:
    """Cadastra membros da comunidade UFPR e serviços iniciais no banco SQLite."""
    prestador_ana = MembroComunidade(
        id="usr-ana-prestadora",
        nome="Ana Clara (Mestranda PPGInf)",
        email="ana.clara@ufpr.br",
        registro_academico="GRR20220001",
    )
    solicitante_lucas = MembroComunidade(
        id="usr-lucas-solicitante",
        nome="Lucas Martins (Graduando BCC)",
        email="lucas.martins@ufpr.br",
        registro_academico="GRR20241234",
    )
    solicitante_bruna = MembroComunidade(
        id="usr-bruna-solicitante",
        nome="Bruna Souza (Graduanda Estatística)",
        email="bruna.souza@ufpr.br",
        registro_academico="GRR20239876",
    )

    servico_latex = Servico(
        id="serv-01",
        prestador_id=prestador_ana.id,
        titulo="Revisão e Formatação de TCC em LaTeX/ABNT",
        descricao="Ajuste completo de template UFPR, referências BibTeX e revisão técnica.",
        categoria="Revisão Acadêmica",
        valor=60.0,
    )
    servico_latex.adicionar_slot(
        inicio=datetime(2026, 11, 25, 14, 0),
        fim=datetime(2026, 11, 25, 15, 30),
    )
    servico_latex.adicionar_slot(
        inicio=datetime(2026, 11, 26, 10, 0),
        fim=datetime(2026, 11, 26, 11, 30),
    )

    servico_mentoria = Servico(
        id="serv-02",
        prestador_id=prestador_ana.id,
        titulo="Mentoria de Design e Arquitetura de Software",
        descricao="Auxílio prático em padrões GRASP, princípios SOLID e Arquitetura Hexagonal.",
        categoria="Mentoria",
        valor=45.0,
    )
    servico_mentoria.adicionar_slot(
        inicio=datetime(2026, 11, 27, 16, 0),
        fim=datetime(2026, 11, 27, 17, 0),
    )

    servico_repo.salvar(servico_latex)
    servico_repo.salvar(servico_mentoria)

    return prestador_ana, solicitante_lucas, solicitante_bruna


def executar_demonstracao_fatia_vertical(caminho_banco: str = "campushub.db") -> None:
    """
    Composition Root e Roteiro Executável da Fatia Vertical (Seções 7 e 8 do Edital).
    Demonstra a coerência entre Arquitetura Hexagonal, Modelo de Domínio Rico, Persistência SQLite e Notificador.
    """
    print("=" * 88)
    print(" CAMPUSHUB (TEMA 11) — PROTÓTIPO FUNCIONAL DA FATIA VERTICAL (MONOLITO MODULAR HEXAGONAL)")
    print("=" * 88)

    # Limpa banco anterior de demonstracao para garantir execucao deterministica e reprodutivel
    arquivo_db = Path(caminho_banco)
    if caminho_banco != ":memory:" and arquivo_db.exists():
        arquivo_db.unlink()

    # 1. Inicializacao da Infraestrutura (Adaptadores Secundarios / Outbound)
    conn = criar_conexao_sqlite(caminho_banco)
    servico_repo = SqliteServicoRepository(conn)
    contratacao_repo = SqliteContratacaoRepository(conn)
    notificador = EmailNotificador(servidor_smtp="smtp.ufpr.br")

    # 2. Injecao de Dependencia nos Casos de Uso (Camada de Aplicacao - DIP)
    solicitar_uc = SolicitarContratacaoUseCase(
        servico_repo=servico_repo,
        contratacao_repo=contratacao_repo,
        notificador=notificador,
    )
    consultar_uc = ConsultarServicosUseCase(servico_repo=servico_repo)
    concluir_avaliar_uc = ConcluirEAvaliarUseCase(
        contratacao_repo=contratacao_repo,
        notificador=notificador,
    )

    # 3. Inicializacao do Adaptador Primario (Inbound CLI Controller)
    controller = MarketplaceController(
        solicitar_uc=solicitar_uc,
        consultar_uc=consultar_uc,
        concluir_avaliar_uc=concluir_avaliar_uc,
    )

    prestador_ana, solicitante_lucas, solicitante_bruna = popular_dados_iniciais(servico_repo)

    # -------------------------------------------------------------------------
    # PASSO 1: CONSULTA DE SERVICOS DISPONIVEIS (RF03 / Item 2 da Secao 7)
    # -------------------------------------------------------------------------
    print("\n[PASSO 1] Consulta inicial de serviços com horários (slots) livres no campus:")
    controller.listar_servicos_disponiveis(apenas_com_slots_livres=True)

    # -------------------------------------------------------------------------
    # PASSO 2: CONTRATACAO VALIDA + PERSISTENCIA + NOTIFICACAO (RF04, RF08 / ASR-01, ASR-02)
    # -------------------------------------------------------------------------
    print(
        f"\n[PASSO 2] Solicitante '{solicitante_lucas.nome}' solicita contratação do serviço "
        "'serv-01' no horário 'slot-1':"
    )
    contratacao = controller.solicitar_contratacao(
        servico_id="serv-01",
        slot_id="slot-1",
        solicitante_id=solicitante_lucas.id,
    )

    # -------------------------------------------------------------------------
    # PASSO 3: FLUXO DE ERRO 1 — PROIBICAO DE AUTO-CONTRATACAO (RES01)
    # -------------------------------------------------------------------------
    print(
        f"\n[PASSO 3] Fluxo Alternativo/Erro (RES01): Prestadora '{prestador_ana.nome}' "
        "tenta contratar o próprio serviço 'serv-01' ('slot-2'):"
    )
    controller.solicitar_contratacao(
        servico_id="serv-01",
        slot_id="slot-2",
        solicitante_id=prestador_ana.id,
    )

    # -------------------------------------------------------------------------
    # PASSO 4: FLUXO DE ERRO 2 — PREVENCAO DE OVERBOOKING DE HORARIO (RES02 / ASR-02)
    # -------------------------------------------------------------------------
    print(
        f"\n[PASSO 4] Fluxo Alternativo/Erro (RES02 / ASR-02): Solicitante '{solicitante_bruna.nome}' "
        "tenta contratar o 'slot-1' do 'serv-01' que já foi reservado no Passo 2:"
    )
    controller.solicitar_contratacao(
        servico_id="serv-01",
        slot_id="slot-1",
        solicitante_id=solicitante_bruna.id,
    )

    # -------------------------------------------------------------------------
    # PASSO 5: CONCLUSAO DO SERVICO E AVALIACAO (RF06, RF07, RES03)
    # -------------------------------------------------------------------------
    if contratacao is not None:
        print(
            f"\n[PASSO 5] Tentativa inválida de avaliar a contratação '{contratacao.id}' "
            "ANTES da conclusão do serviço (RES03):"
        )
        controller.avaliar_servico(
            contratacao_id=contratacao.id,
            nota=5,
            comentario="Tentando avaliar antes de concluir.",
        )

        print(f"\n[PASSO 6] Conclusão do serviço referente à contratação '{contratacao.id}' (RF06):")
        controller.concluir_servico(contratacao_id=contratacao.id)

        print(f"\n[PASSO 7] Registro de avaliação válida (nota 5) após conclusão (RF07 / RES03):")
        controller.avaliar_servico(
            contratacao_id=contratacao.id,
            nota=5,
            comentario="Revisão impecável do TCC em LaTeX, entregou antes do prazo!",
        )

    # -------------------------------------------------------------------------
    # PASSO 8: NOVA CONSULTA COMPROVANDO A PERSISTENCIA NO SQLITE
    # -------------------------------------------------------------------------
    print("\n[PASSO 8] Nova consulta ao banco SQLite confirmando o slot-1 como RESERVADO:")
    controller.listar_servicos_disponiveis(apenas_com_slots_livres=True)

    conn.close()
    print("\n" + "=" * 88)
    print(f" Demonstração concluída com sucesso! Dados persistidos em '{arquivo_db.resolve()}'.")
    print("=" * 88)


if __name__ == "__main__":
    import sys

    if "--web" in sys.argv:
        from src.adapters.inbound.web_controller import iniciar_servidor_web

        iniciar_servidor_web(porta=8000)
    else:
        executar_demonstracao_fatia_vertical()
        print("\n[DICA] Para abrir a interface gráfica Web interativa no navegador, execute:")
        print("       python -m src.main --web")
