"""Adaptador primário (inbound) — interface Web (HTML renderizado no servidor + API JSON).

Terceiro adaptador de entrada sobre os MESMOS casos de uso (CLI, menu e web).
Só traduz HTTP <-> casos de uso; nenhuma regra de negócio mora aqui (RES01,
RES02/ASR-02 e RES03 continuam no domínio e chegam como mensagens).

  WebApp.tratar(...)  : roteador puro (método, caminho, corpo, cookie) -> resposta;
                        testável sem abrir socket.
  servir(...)         : casca fina sobre http.server (biblioteca padrão, RES05).

Padrão Post/Redirect/Get: toda mutação redireciona de volta com uma mensagem.
Login simulado por cookie (escopo de protótipo; sem senha nem CSRF).
"""
import json
from html import escape
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Callable, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, quote, urlsplit

from src.application.casos_de_uso import (
    ConcluirEAvaliarUseCase,
    ConsultarServicosUseCase,
    SolicitarContratacaoUseCase,
)
from src.application.consultar_contratacoes import ConsultarContratacoesUseCase
from src.domain.entidades import StatusContratacao
from src.domain.excecoes import ErroDominio

Resposta = Tuple[int, List[Tuple[str, str]], bytes]

CSS = """
:root{--bg:#f6f7f9;--fg:#1c1f24;--card:#fff;--bd:#dde1e7;--ac:#1f6feb;--ok:#1a7f37;--er:#cf222e;--mut:#667085}
@media (prefers-color-scheme:dark){:root{--bg:#13161a;--fg:#e6e8eb;--card:#1c2026;--bd:#2d333b;--ac:#58a6ff;--ok:#3fb950;--er:#ff7b72;--mut:#9aa4b2}}
*{box-sizing:border-box}body{margin:0;font:16px/1.5 system-ui,sans-serif;background:var(--bg);color:var(--fg)}
header{display:flex;flex-wrap:wrap;gap:12px;align-items:center;justify-content:space-between;padding:12px 20px;background:var(--card);border-bottom:1px solid var(--bd)}
nav a{margin-right:14px;color:var(--ac);text-decoration:none;font-weight:600}main{max-width:820px;margin:0 auto;padding:20px}
.card{background:var(--card);border:1px solid var(--bd);border-radius:10px;padding:14px 16px;margin-bottom:14px}
.mut{color:var(--mut);font-size:.9em}.msg{padding:10px 14px;border-radius:8px;margin-bottom:14px;border:1px solid}
.msg.ok{color:var(--ok);border-color:var(--ok)}.msg.er{color:var(--er);border-color:var(--er)}
.slot{display:flex;justify-content:space-between;align-items:center;padding:6px 0;border-top:1px solid var(--bd)}
button,.btn{font:inherit;padding:6px 14px;border-radius:8px;border:1px solid var(--ac);background:var(--ac);color:#fff;cursor:pointer;text-decoration:none}
select,input[type=text]{font:inherit;padding:5px 8px;border-radius:8px;border:1px solid var(--bd);background:var(--bg);color:var(--fg)}
.tag{font-size:.8em;padding:2px 8px;border-radius:99px;border:1px solid var(--bd)}form{margin:0;display:inline-flex;gap:8px;align-items:center;flex-wrap:wrap}
""".strip()


class WebApp:
    def __init__(
        self,
        consultar_servicos: ConsultarServicosUseCase,
        solicitar_contratacao: SolicitarContratacaoUseCase,
        concluir_e_avaliar: ConcluirEAvaliarUseCase,
        consultar_contratacoes: ConsultarContratacoesUseCase,
        usuarios: Dict[str, str],
        ler_notificacoes: Optional[Callable[[str], List[Dict[str, str]]]] = None,
    ):
        self._servicos = consultar_servicos
        self._solicitar = solicitar_contratacao
        self._concluir_avaliar = concluir_e_avaliar
        self._contratacoes = consultar_contratacoes
        self._usuarios = usuarios
        self._ler_notificacoes = ler_notificacoes

    # ------------------------------------------------------------------ roteador
    def tratar(self, metodo: str, alvo: str, corpo: bytes = b"", cookie: str = "") -> Resposta:
        url = urlsplit(alvo)
        caminho, consulta = url.path, parse_qs(url.query)
        form = parse_qs(corpo.decode("utf-8")) if metodo == "POST" else {}
        pegar = lambda d, k: (d.get(k) or [""])[0]
        usuario = self._usuario_do_cookie(cookie)

        if caminho == "/login" and metodo == "GET":
            uid = pegar(consulta, "u")
            if uid in self._usuarios:
                return self._redirecionar("/", [("Set-Cookie", f"usuario={uid}; Path=/; SameSite=Lax")])
            return self._redirecionar("/")
        if caminho == "/logout":
            return self._redirecionar("/", [("Set-Cookie", "usuario=; Path=/; Max-Age=0")])
        if caminho == "/api/servicos" and metodo == "GET":
            return self._json(self._api_servicos())
        if usuario is None:
            return self._html(self._pagina_login())

        if metodo == "GET":
            msg = (pegar(consulta, "msg"), pegar(consulta, "ok") == "1")
            if caminho == "/":
                return self._html(self._pagina(usuario, "Serviços", self._corpo_servicos(usuario), msg))
            if caminho == "/minhas":
                return self._html(self._pagina(usuario, "Minhas contratações", self._corpo_minhas(usuario), msg))
            if caminho == "/notificacoes" and self._ler_notificacoes:
                return self._html(self._pagina(usuario, "Notificações", self._corpo_notificacoes(usuario), msg))
            return self._html(self._pagina(usuario, "Não encontrado", "<p>Página inexistente.</p>"), 404)

        if metodo == "POST":
            try:
                if caminho == "/contratar":
                    c = self._solicitar.executar(pegar(form, "servico_id"), pegar(form, "slot_id"), usuario)
                    return self._voltar("/minhas", f"Contratação {c.id} confirmada!", True)
                if caminho == "/concluir":
                    c = self._concluir_avaliar.concluir(pegar(form, "contratacao_id"))
                    return self._voltar("/minhas", f"Contratação {c.id} concluída.", True)
                if caminho == "/avaliar":
                    try:
                        nota = int(pegar(form, "nota"))
                    except ValueError:
                        nota = 0  # o domínio recusa (NotaInvalidaError)
                    self._concluir_avaliar.avaliar(pegar(form, "contratacao_id"), nota, pegar(form, "comentario"))
                    return self._voltar("/minhas", "Avaliação registrada. Obrigado!", True)
            except ErroDominio as erro:
                destino = "/" if caminho == "/contratar" else "/minhas"
                return self._voltar(destino, f"{type(erro).__name__}: {erro.mensagem}", False)
        return self._html("<h1>405</h1>", 405)

    # ------------------------------------------------------------------ páginas
    def _corpo_servicos(self, usuario: str) -> str:
        servicos = self._servicos.executar(apenas_com_slots_livres=True)
        if not servicos:
            return '<p class="mut">Nenhum serviço com horário livre.</p>'
        blocos = []
        for s in servicos:
            meu = ' <span class="tag">seu serviço</span>' if s.prestador_id == usuario else ""
            linhas = "".join(
                f'<div class="slot"><span>{sl.inicio:%d/%m %H:%M} → {sl.fim:%H:%M} '
                f'<span class="mut">[{escape(sl.id)}]</span></span>'
                f'<form method="post" action="/contratar">'
                f'<input type="hidden" name="servico_id" value="{escape(s.id)}">'
                f'<input type="hidden" name="slot_id" value="{escape(sl.id)}">'
                f"<button>Contratar</button></form></div>"
                for sl in s.obter_slots_livres()
            )
            blocos.append(
                f'<div class="card"><strong>{escape(s.titulo)}</strong>{meu}'
                f'<div class="mut">{escape(s.categoria)} · R$ {s.valor:.2f} · '
                f'prestador {escape(self._nome(s.prestador_id))}</div>'
                f'<p>{escape(s.descricao)}</p>{linhas}</div>'
            )
        return "".join(blocos)

    def _corpo_minhas(self, usuario: str) -> str:
        contratacoes = self._contratacoes.executar(usuario)
        if not contratacoes:
            return '<p class="mut">Você ainda não tem contratações.</p>'
        titulos = {s.id: s.titulo for s in self._servicos.executar(apenas_com_slots_livres=False)}
        blocos = []
        for c in contratacoes:
            papel = "prestador" if c.prestador_id == usuario else "solicitante"
            acao = ""
            if papel == "prestador" and c.status == StatusContratacao.CONFIRMADA:
                acao = (f'<form method="post" action="/concluir">'
                        f'<input type="hidden" name="contratacao_id" value="{escape(c.id)}">'
                        f"<button>Marcar como concluído</button></form>")
            elif papel == "solicitante" and c.status == StatusContratacao.CONCLUIDA and c.avaliacao is None:
                acao = (f'<form method="post" action="/avaliar">'
                        f'<input type="hidden" name="contratacao_id" value="{escape(c.id)}">'
                        f'<select name="nota">{"".join(f"<option>{n}</option>" for n in range(5, 0, -1))}</select>'
                        f'<input type="text" name="comentario" placeholder="Comentário">'
                        f"<button>Avaliar</button></form>")
            nota = f' · nota {c.avaliacao.nota}: “{escape(c.avaliacao.comentario)}”' if c.avaliacao else ""
            blocos.append(
                f'<div class="card"><strong>{escape(titulos.get(c.servico_id, c.servico_id))}</strong> '
                f'<span class="tag">{c.status.name}</span>'
                f'<div class="mut">{escape(c.id)} · {escape(c.slot_id)} · você é {papel}{nota}</div>'
                f"<div style='margin-top:8px'>{acao}</div></div>"
            )
        return "".join(blocos)

    def _corpo_notificacoes(self, usuario: str) -> str:
        msgs = self._ler_notificacoes(usuario)
        if not msgs:
            return '<p class="mut">Nenhuma notificação.</p>'
        return "".join(
            f'<div class="card"><strong>{escape(m["assunto"])}</strong>'
            f'<div class="mut">{escape(m["mensagem"])}</div></div>' for m in msgs
        )

    def _pagina_login(self) -> str:
        botoes = " ".join(
            f'<a class="btn" href="/login?u={quote(uid)}">{escape(nome)}</a>'
            for uid, nome in self._usuarios.items()
        )
        corpo = f'<div class="card"><h2>Quem é você?</h2><p class="mut">Login simulado (protótipo).</p><p>{botoes}</p></div>'
        return self._layout("CampusHub", f"<main>{corpo}</main>", "")

    def _pagina(self, usuario: str, titulo: str, corpo: str, msg=("", False)) -> str:
        aviso = ""
        if msg[0]:
            aviso = f'<div class="msg {"ok" if msg[1] else "er"}">{escape(msg[0])}</div>'
        notif = '<a href="/notificacoes">Notificações</a>' if self._ler_notificacoes else ""
        topo = (f'<header><nav><strong>CampusHub</strong> &nbsp; <a href="/">Serviços</a>'
                f'<a href="/minhas">Minhas contratações</a>{notif}</nav>'
                f'<span>{escape(self._nome(usuario))} · <a href="/logout">trocar</a></span></header>')
        return self._layout(titulo, f"{topo}<main><h1>{escape(titulo)}</h1>{aviso}{corpo}</main>", "")

    @staticmethod
    def _layout(titulo: str, corpo: str, _: str) -> str:
        return (f'<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">'
                f'<meta name="viewport" content="width=device-width,initial-scale=1">'
                f"<title>{escape(titulo)} — CampusHub</title><style>{CSS}</style></head><body>{corpo}</body></html>")

    # ---------------------------------------------------------------------- API
    def _api_servicos(self) -> list:
        return [
            {"id": s.id, "titulo": s.titulo, "categoria": s.categoria, "valor": s.valor,
             "prestador_id": s.prestador_id,
             "slots_livres": [{"id": x.id, "inicio": x.inicio.isoformat(), "fim": x.fim.isoformat()}
                              for x in s.obter_slots_livres()]}
            for s in self._servicos.executar(apenas_com_slots_livres=True)
        ]

    # ------------------------------------------------------------------ helpers
    def _nome(self, uid: str) -> str:
        return self._usuarios.get(uid, uid)

    def _usuario_do_cookie(self, cabecalho: str) -> Optional[str]:
        jar = SimpleCookie()
        try:
            jar.load(cabecalho or "")
        except Exception:
            return None
        uid = jar["usuario"].value if "usuario" in jar else ""
        return uid if uid in self._usuarios else None

    @staticmethod
    def _html(texto: str, status: int = 200) -> Resposta:
        return status, [("Content-Type", "text/html; charset=utf-8")], texto.encode("utf-8")

    @staticmethod
    def _json(dados) -> Resposta:
        return 200, [("Content-Type", "application/json; charset=utf-8")], json.dumps(dados, ensure_ascii=False).encode("utf-8")

    @staticmethod
    def _redirecionar(destino: str, extras=None) -> Resposta:
        return 303, [("Location", destino)] + (extras or []), b""

    def _voltar(self, destino: str, msg: str, ok: bool) -> Resposta:
        return self._redirecionar(f"{destino}?msg={quote(msg)}&ok={'1' if ok else '0'}")


def servir(app: WebApp, host: str = "127.0.0.1", porta: int = 8000) -> None:
    """Casca HTTP fina. Servidor de thread única: o SQLite fica numa só thread."""

    class Handler(BaseHTTPRequestHandler):
        def _responder(self, metodo: str) -> None:
            tamanho = int(self.headers.get("Content-Length") or 0)
            corpo = self.rfile.read(tamanho) if tamanho else b""
            status, cabecalhos, dados = app.tratar(metodo, self.path, corpo, self.headers.get("Cookie", ""))
            self.send_response(status)
            for k, v in cabecalhos:
                self.send_header(k, v)
            self.send_header("Content-Length", str(len(dados)))
            self.end_headers()
            self.wfile.write(dados)

        def do_GET(self): self._responder("GET")
        def do_POST(self): self._responder("POST")
        def log_message(self, fmt, *args): print(f"  [{self.command}] {self.path} → {args[1] if len(args) > 1 else ''}")

    servidor = HTTPServer((host, porta), Handler)
    print(f"CampusHub Web em http://{host}:{porta}  (Ctrl+C para parar)")
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor encerrado.")
    finally:
        servidor.server_close()
