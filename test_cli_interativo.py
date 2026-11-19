"""Testa a navegação do menu interativo com entradas roteirizadas (sem teclado)."""
import io
from contextlib import redirect_stdout

from src.adapters.inbound.cli_interativo import MenuInterativo
from src.adapters.outbound import NotificadorFake
from src.main import USUARIOS, montar, popular_dados


def rodar(roteiro):
    controller, notificador, conexao, servico_repo = montar(":memory:")
    popular_dados(servico_repo)
    assert isinstance(notificador, NotificadorFake)
    entradas = iter(roteiro)
    ler = lambda uid: [m for m in notificador.mensagens_enviadas if m["destinatario"] == uid]
    saida = io.StringIO()
    with redirect_stdout(saida):
        MenuInterativo(controller, USUARIOS, ler, entrada=lambda _="": next(entradas)).executar()
    conexao.close()
    return saida.getvalue()


def test_fluxo_completo_navegando_pelo_menu():
    # usuários: 1=Ana 2=Bruno 3=Carla | menu: 1 ver 2 contratar 3 minhas 4 concluir 5 avaliar 6 notif 7 trocar
    texto = rodar([
        "2",                    # entra como Bruno
        "2", "1", "1",          # contrata Monitoria (serv-001), slot-1
        "3",                    # minhas contratações
        "7", "3",               # troca para Carla
        "2", "3", "1",          # Carla contrata “Design de slides” (serv-003, de Bruno)
        "7", "1",               # troca para Ana (prestadora)
        "6",                    # notificações de Ana
        "4", "1",               # conclui a 1ª contratação
        "2", "1", "1",          # Ana escolhe a própria Monitoria (slot-2 livre) -> bloqueio RES01
        "7", "2",               # volta como Bruno
        "5", "1", "9", "x",     # nota 9: a UI não valida, o domínio recusa
        "5", "1", "5", "Ótimo!",# avalia corretamente
        "3",                    # confere nota nas contratações
        "0",                    # sair do menu principal
    ])
    assert "Contratação cont-" in texto and "CONFIRMADA" in texto
    assert "Nova Contratação Confirmada" in texto            # notificação lida por Ana
    assert "BLOQUEADO [AutoContratacaoError]" in texto        # RES01 pelo menu
    assert "BLOQUEADO [NotaInvalidaError]" in texto           # nota 9 recusada pelo domínio
    assert "Avaliação registrada: nota 5" in texto
    assert "você é solicitante — CONCLUIDA | nota 5" in texto   # persistido e exibido
    assert "Até logo!" in texto


def test_entrada_invalida_nao_quebra_e_eof_encerra():
    texto = rodar(["abc", "99", "2", "9", "0"])  # inválidas, depois Bruno, opção inválida, sair
    assert texto.count("Opção inválida") == 3
    assert "Até logo!" in texto


if __name__ == "__main__":
    test_fluxo_completo_navegando_pelo_menu(); print("[OK] fluxo completo pelo menu")
    test_entrada_invalida_nao_quebra_e_eof_encerra(); print("[OK] entradas inválidas")
