from datetime import datetime, timedelta

import pytest

from src.adapters.outbound.memoria_repositorios import (
    InMemoryContratacaoRepository,
    InMemoryServicoRepository,
)
from src.adapters.outbound.notificadores import NotificadorFake
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
from src.domain.entidades import Servico, StatusContratacao, StatusSlot
from src.domain.excecoes import (
    AutoContratacaoError,
    NotaInvalidaError,
    SlotIndisponivelError,
    TransicaoEstadoInvalidaError,
)

def criar_servico_exemplo(servico_id: str = "serv-01", prestador_id: str = "prestador-1") -> Servico:
    inicio = datetime.now() + timedelta(days=1)
    fim = inicio + timedelta(hours=1)
    servico = Servico(
        id=servico_id,
        prestador_id=prestador_id,
        titulo="Revisão de Artigo em LaTeX",
        descricao="Formatação e revisão ortográfica.",
        categoria="Revisão",
        valor=50.0,
    )
    servico.adicionar_slot(inicio, fim)
    return servico

# SolicitarContratacaoUseCase
def test_solicitar_contratacao_use_case():
    servico_repo = InMemoryServicoRepository()
    contratacao_repo = InMemoryContratacaoRepository()
    notificador = NotificadorFake()

    servico = criar_servico_exemplo()
    slot = servico.slots[0]
    servico_repo.salvar(servico)

    use_case = SolicitarContratacaoUseCase(servico_repo, contratacao_repo, notificador)

    # contratacao valida reserva o slot, persiste e notifica o prestador
    contratacao = use_case.executar(
        servico_id=servico.id,
        slot_id=slot.id,
        solicitante_id="solicitante-1",
    )

    assert contratacao.status == StatusContratacao.CONFIRMADA
    assert contratacao_repo.buscar_por_id(contratacao.id) is not None

    servico_atualizado = servico_repo.buscar_por_id(servico.id)
    assert servico_atualizado.buscar_slot(slot.id).status == StatusSlot.RESERVADO

    assert len(notificador.mensagens_enviadas) == 1
    assert notificador.mensagens_enviadas[0]["destinatario"] == "prestador-1"

    # impede dupla contratacao no mesmo slot
    with pytest.raises(SlotIndisponivelError):
        use_case.executar(
            servico_id=servico.id,
            slot_id=slot.id,
            solicitante_id="solicitante-2",
        )

    # impede auto contratacao pelo proprio prestador
    novo_slot = servico_atualizado.adicionar_slot(
        datetime.now() + timedelta(days=2),
        datetime.now() + timedelta(days=2, hours=1),
    )
    servico_repo.salvar(servico_atualizado)

    with pytest.raises(AutoContratacaoError):
        use_case.executar(
            servico_id=servico.id,
            slot_id=novo_slot.id,
            solicitante_id="prestador-1",
        )

# ConsultarServicosUseCase
def test_consultar_servicos_use_case():
    servico_repo = InMemoryServicoRepository()
    contratacao_repo = InMemoryContratacaoRepository()
    notificador = NotificadorFake()

    servico_com_vaga = criar_servico_exemplo(servico_id="serv-01", prestador_id="prestador-1")
    servico_esgotado = criar_servico_exemplo(servico_id="serv-02", prestador_id="prestador-2")
    servico_repo.salvar(servico_com_vaga)
    servico_repo.salvar(servico_esgotado)

    # reserva o unico slot do serv-02
    solicitar_uc = SolicitarContratacaoUseCase(servico_repo, contratacao_repo, notificador)
    solicitar_uc.executar(
        servico_id="serv-02",
        slot_id=servico_esgotado.slots[0].id,
        solicitante_id="solicitante-1",
    )

    consultar_uc = ConsultarServicosUseCase(servico_repo)

    # filtro padrao (apenas_com_slots_livres=True) retorna apenas serv-01
    disponiveis = consultar_uc.executar(apenas_com_slots_livres=True)
    assert len(disponiveis) == 1
    assert disponiveis[0].id == "serv-01"

    # sem filtro (apenas_com_slots_livres=False) retorna ambos os servicos cadastrados
    todos = consultar_uc.executar(apenas_com_slots_livres=False)
    assert len(todos) == 2

# ConcluirEAvaliarUseCase
def test_concluir_e_avaliar_use_case():
    servico_repo = InMemoryServicoRepository()
    contratacao_repo = InMemoryContratacaoRepository()
    notificador = NotificadorFake()

    servico = criar_servico_exemplo()
    servico_repo.salvar(servico)

    solicitar_uc = SolicitarContratacaoUseCase(servico_repo, contratacao_repo, notificador)
    contratacao = solicitar_uc.executar(
        servico_id=servico.id,
        slot_id=servico.slots[0].id,
        solicitante_id="solicitante-1",
    )

    concluir_avaliar_uc = ConcluirEAvaliarUseCase(contratacao_repo, notificador)

    # nao permite avaliar antes da contratacao ser concluida
    with pytest.raises(TransicaoEstadoInvalidaError):
        concluir_avaliar_uc.avaliar(contratacao.id, nota=5, comentario="Excelente!")

    # conclusao altera status, persiste e notifica o solicitante
    contratacao_concluida = concluir_avaliar_uc.concluir(contratacao.id)
    assert contratacao_concluida.status == StatusContratacao.CONCLUIDA
    assert notificador.mensagens_enviadas[-1]["destinatario"] == "solicitante-1"

    # valida nota e comentario nao vazio
    with pytest.raises(NotaInvalidaError):
        concluir_avaliar_uc.avaliar(contratacao.id, nota=6, comentario="Nota fora do limite")

    # avaliacao valida eh registrada, persistida e bloqueia avaliacao duplicada
    avaliacao = concluir_avaliar_uc.avaliar(
        contratacao.id, nota=5, comentario="Pontual e muito claro nas explicações."
    )
    assert avaliacao.nota == 5
    assert contratacao_repo.buscar_por_id(contratacao.id).avaliacao is not None

    with pytest.raises(TransicaoEstadoInvalidaError):
        concluir_avaliar_uc.avaliar(contratacao.id, nota=4, comentario="Segunda avaliação")


# Integracao com adaptadores SQLite (ASR-02 e ASR-03)
def test_fluxo_completo_com_sqlite():
    conn = criar_conexao_sqlite(":memory:")
    servico_repo = SqliteServicoRepository(conn)
    contratacao_repo = SqliteContratacaoRepository(conn)
    notificador = NotificadorFake()

    servico = criar_servico_exemplo()
    slot = servico.slots[0]
    servico_repo.salvar(servico)

    solicitar_uc = SolicitarContratacaoUseCase(servico_repo, contratacao_repo, notificador)
    contratacao = solicitar_uc.executar(
        servico_id=servico.id,
        slot_id=slot.id,
        solicitante_id="solicitante-1",
    )

    # confirma persistencia do slot como RESERVADO no SQLite
    servico_db = servico_repo.buscar_por_id(servico.id)
    assert servico_db is not None
    assert servico_db.buscar_slot(slot.id).status == StatusSlot.RESERVADO

    # confirma filtro de consulta sobre o SQLite
    consultar_uc = ConsultarServicosUseCase(servico_repo)
    assert len(consultar_uc.executar(apenas_com_slots_livres=True)) == 0
    assert len(consultar_uc.executar(apenas_com_slots_livres=False)) == 1

    # conclui e avalia persistindo no SQLite
    concluir_avaliar_uc = ConcluirEAvaliarUseCase(contratacao_repo, notificador)
    concluir_avaliar_uc.concluir(contratacao.id)
    concluir_avaliar_uc.avaliar(contratacao.id, nota=5, comentario="Ótimo atendimento!")

    contratacao_db = contratacao_repo.buscar_por_id(contratacao.id)
    assert contratacao_db is not None
    assert contratacao_db.status == StatusContratacao.CONCLUIDA
    assert contratacao_db.avaliacao is not None
    assert contratacao_db.avaliacao.nota == 5
