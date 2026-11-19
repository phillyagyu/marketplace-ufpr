"""Testa o adaptador web chamando o roteador diretamente (sem abrir socket)."""
from urllib.parse import parse_qs, unquote, urlsplit

from src.main import montar_web, popular_dados


def novo_app():
    app, conexao, repo = montar_web(":memory:")
    popular_dados(repo)
    return app


def seguir(app, resp, cookie):
    """Segue um redirecionamento 303 e devolve (status, html, mensagem)."""
    status, cab, _ = resp
    assert status == 303
    destino = dict(cab)["Location"]
    msg = unquote(parse_qs(urlsplit(destino).query).get("msg", [""])[0])
    s, _, corpo = app.tratar("GET", destino, cookie=cookie)
    return s, corpo.decode(), msg


def test_exige_login_e_lista_servicos():
    app = novo_app()
    assert "Quem é você?" in app.tratar("GET", "/")[2].decode()
    ck = "usuario=membro-bruno"
    status, _, corpo = app.tratar("GET", "/", cookie=ck)
    assert status == 200 and "Monitoria de Cálculo I" in corpo.decode()


def test_fluxo_completo_e_erros_de_dominio():
    app = novo_app()
    bruno, ana = "usuario=membro-bruno", "usuario=membro-ana"
    contratar = lambda ck, sv, sl: app.tratar("POST", "/contratar", f"servico_id={sv}&slot_id={sl}".encode(), ck)

    # contratação válida (persiste e notifica o prestador)
    s, html, msg = seguir(app, contratar(bruno, "serv-001", "slot-1"), bruno)
    assert "confirmada" in msg and "CONFIRMADA" in html
    cid = msg.split()[1]
    assert "Nova Contratação" in app.tratar("GET", "/notificacoes", cookie=ana)[2].decode()

    # RES02 / ASR-02: mesmo slot de novo
    _, _, msg = seguir(app, contratar("usuario=membro-carla", "serv-001", "slot-1"), bruno)
    assert "SlotIndisponivelError" in msg
    # RES01: prestador contratando o próprio serviço
    _, _, msg = seguir(app, contratar(ana, "serv-001", "slot-2"), ana)
    assert "AutoContratacaoError" in msg

    # concluir (prestador) e avaliar (solicitante); nota inválida recusada pelo domínio
    _, html, _ = seguir(app, app.tratar("POST", "/concluir", f"contratacao_id={cid}".encode(), ana), ana)
    assert "CONCLUIDA" in html
    _, _, msg = seguir(app, app.tratar("POST", "/avaliar", f"contratacao_id={cid}&nota=9&comentario=x".encode(), bruno), bruno)
    assert "NotaInvalidaError" in msg
    _, html, msg = seguir(app, app.tratar("POST", "/avaliar", f"contratacao_id={cid}&nota=5&comentario=%C3%93timo".encode(), bruno), bruno)
    assert "registrada" in msg and "nota 5" in html


def test_api_json_e_escape_de_html():
    app = novo_app()
    status, cab, corpo = app.tratar("GET", "/api/servicos")
    assert status == 200 and b'"serv-001"' in corpo and dict(cab)["Content-Type"].startswith("application/json")
    _, _, corpo = app.tratar("GET", "/?msg=%3Cscript%3Ex%3C/script%3E&ok=0", cookie="usuario=membro-ana")
    assert b"<script>x" not in corpo and b"&lt;script&gt;" in corpo


if __name__ == "__main__":
    for t in (test_exige_login_e_lista_servicos, test_fluxo_completo_e_erros_de_dominio, test_api_json_e_escape_de_html):
        t(); print("[OK]", t.__name__)
