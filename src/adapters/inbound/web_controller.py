import json
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, urlparse
import webbrowser

from src.adapters.outbound.notificadores import EmailNotificador, NotificadorFake
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
from src.domain.excecoes import ErroDominio
from src.ports.interfaces import NotificadorPort


class NotificadorCompostoWeb(NotificadorPort):
    """
    Adaptador de Notificação que despacha no log SMTP do terminal (EmailNotificador)
    e simultaneamente armazena o histórico em memória (NotificadorFake) para exibição na UI Web.
    """

    def __init__(self, servidor_smtp: str = "smtp.ufpr.br"):
        self.email_notificador = EmailNotificador(servidor_smtp=servidor_smtp, exibir_log=True)
        self.fake_notificador = NotificadorFake()

    def notificar(self, destinatario: str, assunto: str, mensagem: str) -> None:
        self.email_notificador.notificar(destinatario, assunto, mensagem)
        self.fake_notificador.notificar(destinatario, assunto, mensagem)
        self.fake_notificador.mensagens_enviadas[-1]["horario"] = datetime.now().strftime("%H:%M:%S")
        self.fake_notificador.mensagens_enviadas[-1]["canal"] = f"SMTP ({self.email_notificador.servidor_smtp})"


class CampusHubWebContext:
    """Mantém as instâncias injetadas (Composition Root) para o Adaptador Primário Web."""

    def __init__(self, caminho_banco: str = "campushub.db"):
        self.caminho_banco = caminho_banco
        self.membros: List[MembroComunidade] = []
        self.conn = None
        self.servico_repo: Optional[SqliteServicoRepository] = None
        self.contratacao_repo: Optional[SqliteContratacaoRepository] = None
        self.notificador: Optional[NotificadorCompostoWeb] = None
        self.solicitar_uc: Optional[SolicitarContratacaoUseCase] = None
        self.consultar_uc: Optional[ConsultarServicosUseCase] = None
        self.concluir_avaliar_uc: Optional[ConcluirEAvaliarUseCase] = None
        self.inicializar_sistema(resetar_banco=True)

    def inicializar_sistema(self, resetar_banco: bool = False) -> None:
        if self.conn is not None:
            try:
                self.conn.close()
            except Exception:
                pass

        arquivo_db = Path(self.caminho_banco)
        if resetar_banco and self.caminho_banco != ":memory:" and arquivo_db.exists():
            arquivo_db.unlink()

        self.conn = criar_conexao_sqlite(self.caminho_banco)
        self.servico_repo = SqliteServicoRepository(self.conn)
        self.contratacao_repo = SqliteContratacaoRepository(self.conn)
        self.notificador = NotificadorCompostoWeb(servidor_smtp="smtp.ufpr.br")

        self.solicitar_uc = SolicitarContratacaoUseCase(
            servico_repo=self.servico_repo,
            contratacao_repo=self.contratacao_repo,
            notificador=self.notificador,
        )
        self.consultar_uc = ConsultarServicosUseCase(servico_repo=self.servico_repo)
        self.concluir_avaliar_uc = ConcluirEAvaliarUseCase(
            contratacao_repo=self.contratacao_repo,
            notificador=self.notificador,
        )

        self._popular_dados_iniciais()

    def _popular_dados_iniciais(self) -> None:
        self.membros = [
            MembroComunidade(
                id="usr-lucas-solicitante",
                nome="Lucas Martins (Graduando BCC)",
                email="lucas.martins@ufpr.br",
                registro_academico="GRR20241234",
            ),
            MembroComunidade(
                id="usr-bruna-solicitante",
                nome="Bruna Souza (Graduanda Estatística)",
                email="bruna.souza@ufpr.br",
                registro_academico="GRR20239876",
            ),
            MembroComunidade(
                id="usr-ana-prestadora",
                nome="Ana Clara (Mestranda PPGInf)",
                email="ana.clara@ufpr.br",
                registro_academico="GRR20220001",
            ),
            MembroComunidade(
                id="usr-carlos-docente",
                nome="Prof. Carlos Eduardo (Docente DInf)",
                email="carlos.eduardo@ufpr.br",
                registro_academico="SIAPE112233",
            ),
        ]

        assert self.servico_repo is not None
        if len(self.servico_repo.listar_disponiveis()) > 0:
            return

        s1 = Servico(
            id="serv-01",
            prestador_id="usr-ana-prestadora",
            titulo="Revisão e Formatação de TCC em LaTeX / ABNT",
            descricao="Ajuste completo do template oficial da UFPR, referências BibTeX e revisão textual.",
            categoria="Revisão Acadêmica",
            valor=60.0,
        )
        s1.adicionar_slot(datetime(2026, 11, 25, 14, 0), datetime(2026, 11, 25, 15, 30))
        s1.adicionar_slot(datetime(2026, 11, 26, 10, 0), datetime(2026, 11, 26, 11, 30))

        s2 = Servico(
            id="serv-02",
            prestador_id="usr-ana-prestadora",
            titulo="Mentoria de Design e Arquitetura de Software",
            descricao="Sessão prática sobre padrões GRASP, princípios SOLID, Clean e Arquitetura Hexagonal.",
            categoria="Mentoria",
            valor=45.0,
        )
        s2.adicionar_slot(datetime(2026, 11, 27, 16, 0), datetime(2026, 11, 27, 17, 0))
        s2.adicionar_slot(datetime(2026, 11, 28, 9, 0), datetime(2026, 11, 28, 10, 0))

        s3 = Servico(
            id="serv-03",
            prestador_id="usr-carlos-docente",
            titulo="Consultoria em Análise Estatística com Python / R",
            descricao="Apoio na validação de hipóteses, testes estatísticos e gráficos para artigos científicos.",
            categoria="Pesquisa & Dados",
            valor=80.0,
        )
        s3.adicionar_slot(datetime(2026, 11, 29, 14, 0), datetime(2026, 11, 29, 16, 0))

        self.servico_repo.salvar(s1)
        self.servico_repo.salvar(s2)
        self.servico_repo.salvar(s3)

    def listar_todas_contratacoes(self) -> List[Dict[str, Any]]:
        assert self.conn is not None and self.contratacao_repo is not None and self.servico_repo is not None
        cursor = self.conn.execute("SELECT id FROM contratacoes ORDER BY criado_em DESC;")
        ids = [row["id"] for row in cursor.fetchall()]
        nomes_membros = {m.id: m.nome for m in self.membros}

        resultado = []
        for cid in ids:
            c = self.contratacao_repo.buscar_por_id(cid)
            if c is None:
                continue
            servico = self.servico_repo.buscar_por_id(c.servico_id)
            horario_str = c.slot_id
            if servico is not None:
                try:
                    slot = servico.buscar_slot(c.slot_id)
                    horario_str = f"{slot.inicio.strftime('%d/%m/%Y %H:%M')} - {slot.fim.strftime('%H:%M')}"
                except ErroDominio:
                    pass

            resultado.append(
                {
                    "id": c.id,
                    "servico_id": c.servico_id,
                    "servico_titulo": servico.titulo if servico else c.servico_id,
                    "slot_id": c.slot_id,
                    "horario": horario_str,
                    "solicitante_id": c.solicitante_id,
                    "solicitante_nome": nomes_membros.get(c.solicitante_id, c.solicitante_id),
                    "prestador_id": c.prestador_id,
                    "prestador_nome": nomes_membros.get(c.prestador_id, c.prestador_id),
                    "status": c.status.value,
                    "criado_em": c.criado_em.strftime("%d/%m/%Y %H:%M:%S"),
                    "avaliacao": (
                        {
                            "id": c.avaliacao.id,
                            "nota": c.avaliacao.nota,
                            "comentario": c.avaliacao.comentario,
                        }
                        if c.avaliacao
                        else None
                    ),
                }
            )
        return resultado


HTML_PAGINA = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>CampusHub UFPR — Marketplace de Serviços no Campus (Tema 11)</title>
  <style>
    :root {
      --bg: #0f172a;
      --panel: #1e293b;
      --panel-alt: #334155;
      --border: #475569;
      --text: #f8fafc;
      --muted: #94a3b8;
      --primary: #3b82f6;
      --primary-hover: #2563eb;
      --success: #10b981;
      --danger: #ef4444;
      --warning: #f59e0b;
      --purple: #a855f7;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Segoe UI', system-ui, -apple-system, sans-serif; }
    body { background: var(--bg); color: var(--text); min-height: 100vh; padding-bottom: 40px; }
    header {
      background: linear-gradient(135deg, #1e3a8a 0%, #0f172a 100%);
      border-bottom: 1px solid var(--border);
      padding: 18px 28px;
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
    }
    .brand h1 { font-size: 1.35rem; font-weight: 700; display: flex; align-items: center; gap: 10px; }
    .badge-arch {
      font-size: 0.72rem;
      background: rgba(59, 130, 246, 0.2);
      border: 1px solid #60a5fa;
      color: #93c5fd;
      padding: 3px 10px;
      border-radius: 999px;
      font-weight: 600;
    }
    .brand p { font-size: 0.85rem; color: var(--muted); margin-top: 4px; }
    .user-bar {
      display: flex;
      align-items: center;
      gap: 12px;
      background: rgba(15, 23, 42, 0.75);
      padding: 10px 16px;
      border-radius: 10px;
      border: 1px solid var(--border);
    }
    .user-bar label { font-size: 0.82rem; color: var(--muted); font-weight: 600; }
    select, input, textarea {
      background: var(--panel);
      color: var(--text);
      border: 1px solid var(--border);
      padding: 8px 12px;
      border-radius: 6px;
      font-size: 0.88rem;
    }
    button {
      cursor: pointer;
      border: none;
      border-radius: 6px;
      padding: 8px 14px;
      font-size: 0.85rem;
      font-weight: 600;
      transition: all 0.15s;
    }
    .btn-primary { background: var(--primary); color: white; }
    .btn-primary:hover { background: var(--primary-hover); }
    .btn-success { background: var(--success); color: #052e16; }
    .btn-success:hover { filter: brightness(1.1); }
    .btn-danger { background: rgba(239, 68, 68, 0.18); color: #fca5a5; border: 1px solid var(--danger); }
    .btn-danger:hover { background: rgba(239, 68, 68, 0.3); }
    .btn-warning { background: var(--warning); color: #451a03; }
    .btn-outline { background: transparent; color: var(--muted); border: 1px solid var(--border); }
    .btn-outline:hover { color: white; border-color: white; }

    .container {
      max-width: 1400px;
      margin: 22px auto;
      padding: 0 20px;
      display: grid;
      grid-template-columns: 1.35fr 1fr;
      gap: 22px;
    }
    @media (max-width: 1024px) { .container { grid-template-columns: 1fr; } }

    .alert-box {
      max-width: 1400px;
      margin: 16px auto 0;
      padding: 0 20px;
    }
    .toast {
      padding: 14px 18px;
      border-radius: 10px;
      margin-bottom: 10px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-size: 0.92rem;
      animation: fadeIn 0.2s ease;
    }
    .toast-error {
      background: rgba(127, 29, 29, 0.85);
      border: 2px solid var(--danger);
      color: #fecaca;
    }
    .toast-success {
      background: rgba(6, 78, 59, 0.85);
      border: 2px solid var(--success);
      color: #a7f3d0;
    }
    @keyframes fadeIn { from { opacity: 0; transform: translateY(-5px); } to { opacity: 1; transform: translateY(0); } }

    .card-panel {
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 20px;
      margin-bottom: 22px;
    }
    .panel-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 16px;
      padding-bottom: 12px;
      border-bottom: 1px solid var(--border);
      flex-wrap: wrap;
      gap: 10px;
    }
    .panel-header h2 { font-size: 1.1rem; display: flex; align-items: center; gap: 8px; }
    .tag-usecase {
      font-size: 0.72rem;
      font-family: monospace;
      background: rgba(168, 85, 247, 0.2);
      color: #d8b4fe;
      border: 1px solid var(--purple);
      padding: 2px 8px;
      border-radius: 4px;
    }

    .service-card {
      background: rgba(15, 23, 42, 0.65);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 16px;
      margin-bottom: 14px;
    }
    .service-top {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 12px;
      margin-bottom: 8px;
    }
    .service-title { font-size: 1.02rem; font-weight: 700; color: #60a5fa; }
    .service-price {
      font-size: 1rem;
      font-weight: 700;
      color: var(--success);
      background: rgba(16, 185, 129, 0.12);
      padding: 4px 10px;
      border-radius: 6px;
      white-space: nowrap;
    }
    .service-meta { font-size: 0.82rem; color: var(--muted); margin-bottom: 10px; }
    .slots-grid {
      display: flex;
      flex-direction: column;
      gap: 8px;
      margin-top: 12px;
      padding-top: 10px;
      border-top: 1px dashed var(--border);
    }
    .slot-item {
      display: flex;
      justify-content: space-between;
      align-items: center;
      background: var(--panel);
      padding: 8px 12px;
      border-radius: 8px;
      border: 1px solid var(--border);
      flex-wrap: wrap;
      gap: 8px;
    }
    .status-pill {
      font-size: 0.73rem;
      font-weight: 700;
      padding: 2px 8px;
      border-radius: 999px;
      text-transform: uppercase;
    }
    .pill-livre { background: rgba(16, 185, 129, 0.2); color: #34d399; border: 1px solid var(--success); }
    .pill-reservado { background: rgba(239, 68, 68, 0.2); color: #f87171; border: 1px solid var(--danger); }
    .pill-confirmada { background: rgba(59, 130, 246, 0.2); color: #60a5fa; border: 1px solid var(--primary); }
    .pill-concluida { background: rgba(16, 185, 129, 0.2); color: #34d399; border: 1px solid var(--success); }

    .contratacao-item {
      background: rgba(15, 23, 42, 0.65);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 14px;
      margin-bottom: 12px;
    }
    .contratacao-actions {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 12px;
      padding-top: 10px;
      border-top: 1px solid var(--border);
    }
    .notif-item {
      background: rgba(15, 23, 42, 0.8);
      border-left: 4px solid var(--warning);
      padding: 10px 12px;
      border-radius: 6px;
      margin-bottom: 10px;
      font-size: 0.83rem;
    }
    .guide-bar {
      max-width: 1400px;
      margin: 18px auto 0;
      padding: 0 20px;
    }
    .guide-inner {
      background: rgba(30, 58, 138, 0.35);
      border: 1px solid #3b82f6;
      border-radius: 10px;
      padding: 12px 18px;
      font-size: 0.85rem;
      display: flex;
      flex-wrap: wrap;
      gap: 16px;
      align-items: center;
      justify-content: space-between;
    }
    .eval-form {
      margin-top: 10px;
      background: var(--panel);
      padding: 10px;
      border-radius: 8px;
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: center;
    }
  </style>
</head>
<body>

  <header>
    <div class="brand">
      <h1>
        CampusHub UFPR
        <span class="badge-arch">Monolito Modular + Ports &amp; Adapters (Hexagonal)</span>
      </h1>
      <p>Tema 11 — Marketplace de Serviços no Campus | Persistência: SQLite (campushub.db) | Porta Externa: NotificadorPort</p>
    </div>

    <div class="user-bar">
      <label for="usuarioAtivo">Ator Logado na Sessão:</label>
      <select id="usuarioAtivo" onchange="atualizarDicaAtor()"></select>
      <button class="btn-outline" onclick="resetarBanco()" title="Restaura os dados originais da demonstração">
        Resetar Demo (SQLite)
      </button>
    </div>
  </header>

  <div class="guide-bar">
    <div class="guide-inner">
      <div id="dicaRoteiro">
        <strong>Roteiro Rápido para a Defesa:</strong>
        1) Com <b>Lucas</b> selecionado, contrate um horário LIVRE.
        2) Mude para <b>Bruna</b> e tente contratar o mesmo horário (testa <code>SlotIndisponivelError - ASR-02</code>).
        3) Mude para <b>Ana Clara</b> e tente contratar o próprio serviço dela (testa <code>AutoContratacaoError - RES01</code>).
        4) Conclua e avalie a contratação!
      </div>
    </div>
  </div>

  <div class="alert-box" id="alertContainer"></div>

  <div class="container">
    <!-- COLUNA ESQUERDA: CATALOGO E SLOTS -->
    <div>
      <div class="card-panel">
        <div class="panel-header">
          <div>
            <h2>Catálogo de Serviços e Agenda de Slots</h2>
            <span class="tag-usecase">ConsultarServicosUseCase + SolicitarContratacaoUseCase</span>
          </div>
          <label style="font-size: 0.84rem; display: flex; align-items: center; gap: 6px; cursor: pointer;">
            <input type="checkbox" id="filtroSlotsLivres" checked onchange="carregarEstado()" />
            Apenas serviços com slots livres
          </label>
        </div>

        <div id="listaServicos">Carregando serviços...</div>
      </div>

      <!-- CADASTRAR NOVO SERVICO / SLOT (RF01 / RF02) -->
      <div class="card-panel">
        <div class="panel-header">
          <h2>Cadastrar Nova Oferta de Serviço com Slot (RF01 / RF02)</h2>
          <span class="tag-usecase">Servico.adicionar_slot() [Creator GRASP]</span>
        </div>
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px;">
          <input type="text" id="novoTitulo" placeholder="Título do serviço (ex: Aula de Cálculo II)" />
          <input type="text" id="novaCategoria" placeholder="Categoria (ex: Mentoria, Revisão, Lab)" />
          <input type="text" id="novaDescricao" placeholder="Descrição do serviço oferecido" style="grid-column: span 2;" />
          <input type="number" id="novoValor" placeholder="Valor (R$)" value="50" />
          <button class="btn-primary" onclick="criarServico()">+ Publicar Oferta como Usuário Logado</button>
        </div>
      </div>
    </div>

    <!-- COLUNA DIREITA: CONTRATACOES, AVALIACOES E LOG DE NOTIFICACOES -->
    <div>
      <div class="card-panel">
        <div class="panel-header">
          <div>
            <h2>Contratações Persistidas no SQLite &amp; Avaliações</h2>
            <span class="tag-usecase">ConcluirEAvaliarUseCase [RF06 / RF07 / RES03]</span>
          </div>
        </div>
        <div id="listaContratacoes">Nenhuma contratação registrada ainda.</div>
      </div>

      <div class="card-panel">
        <div class="panel-header">
          <div>
            <h2>Monitor da Dependência Externa (NotificadorPort)</h2>
            <span class="tag-usecase">EmailNotificador / NotificadorFake [ASR-01 / Seção 8]</span>
          </div>
        </div>
        <div id="listaNotificacoes">Nenhuma notificação disparada ainda.</div>
      </div>
    </div>
  </div>

  <script>
    let estadoAtual = { membros: [], servicos: [], contratacoes: [], notificacoes: [] };

    function mostrarAlerta(tipo, titulo, detalhe) {
      const container = document.getElementById('alertContainer');
      const div = document.createElement('div');
      div.className = 'toast ' + (tipo === 'erro' ? 'toast-error' : 'toast-success');
      div.innerHTML = `
        <div>
          <strong>${titulo}</strong><br/>
          <span>${detalhe}</span>
        </div>
        <button class="btn-outline" style="color:white;border-color:rgba(255,255,255,0.4)" onclick="this.parentElement.remove()">Fechar</button>
      `;
      container.prepend(div);
      setTimeout(() => { if (div.parentElement) div.remove(); }, 9000);
    }

    function obterUsuarioLogado() {
      return document.getElementById('usuarioAtivo').value;
    }

    function atualizarDicaAtor() {
      renderizarServicos();
    }

    async function carregarEstado() {
      const apenasLivres = document.getElementById('filtroSlotsLivres').checked;
      const resp = await fetch(`/api/estado?apenas_livres=${apenasLivres}`);
      estadoAtual = await resp.json();

      const select = document.getElementById('usuarioAtivo');
      const valorAnterior = select.value;
      if (select.options.length === 0) {
        estadoAtual.membros.forEach(m => {
          const opt = document.createElement('option');
          opt.value = m.id;
          opt.textContent = `${m.nome} [${m.registro_academico}]`;
          select.appendChild(opt);
        });
        if (valorAnterior) select.value = valorAnterior;
      }

      renderizarServicos();
      renderizarContratacoes();
      renderizarNotificacoes();
    }

    function renderizarServicos() {
      const container = document.getElementById('listaServicos');
      const usuarioLogado = obterUsuarioLogado();

      if (estadoAtual.servicos.length === 0) {
        container.innerHTML = '<p style="color:var(--muted)">Nenhum serviço disponível para este filtro.</p>';
        return;
      }

      container.innerHTML = estadoAtual.servicos.map(s => {
        const ehProprioPrestador = (s.prestador_id === usuarioLogado);
        const slotsHtml = s.slots.map(slot => {
          const livre = slot.status === 'livre';
          let botaoTexto = livre ? 'Contratar Horário (RF04)' : 'Tentar Contratar (Testar Anti-Overbooking RES02)';
          if (ehProprioPrestador && livre) {
            botaoTexto = 'Tentar Auto-Contratação (Testar Bloqueio RES01)';
          }
          const btnClass = (livre && !ehProprioPrestador) ? 'btn-success' : 'btn-danger';

          return `
            <div class="slot-item">
              <div>
                <span class="status-pill ${livre ? 'pill-livre' : 'pill-reservado'}">${slot.status}</span>
                <strong style="margin-left:8px; font-size:0.88rem;">${slot.inicio} às ${slot.fim}</strong>
                <span style="color:var(--muted); font-size:0.78rem; margin-left:6px;">(${slot.id})</span>
              </div>
              <button class="${btnClass}" onclick="solicitarContratacao('${s.id}', '${slot.id}')">
                ${botaoTexto}
              </button>
            </div>
          `;
        }).join('');

        return `
          <div class="service-card">
            <div class="service-top">
              <div>
                <div class="service-title">${s.titulo}</div>
                <div class="service-meta">
                  Categoria: <b>${s.categoria}</b> | Prestador: <b>${s.prestador_nome}</b>
                  ${ehProprioPrestador ? '<span style="color:#fbbf24; font-weight:700;"> (Você é o prestador)</span>' : ''}
                </div>
              </div>
              <div class="service-price">R$ ${s.valor.toFixed(2)}</div>
            </div>
            <p style="font-size:0.86rem; color:#cbd5e1;">${s.descricao}</p>
            <div class="slots-grid">${slotsHtml}</div>
          </div>
        `;
      }).join('');
    }

    function renderizarContratacoes() {
      const container = document.getElementById('listaContratacoes');
      if (estadoAtual.contratacoes.length === 0) {
        container.innerHTML = '<p style="color:var(--muted); font-size:0.88rem;">Nenhuma contratação realizada ainda. Clique em "Contratar Horário" em um slot ao lado!</p>';
        return;
      }

      container.innerHTML = estadoAtual.contratacoes.map(c => {
        const confirmada = c.status === 'confirmada';
        const avalHtml = c.avaliacao
          ? `<div style="margin-top:10px; background:rgba(16,185,129,0.12); border:1px solid var(--success); padding:8px 12px; border-radius:6px; font-size:0.84rem;">
               <strong>Avaliação Registrada (${c.avaliacao.id}):</strong>
               <span style="color:#fbbf24; font-weight:700;">${'★'.repeat(c.avaliacao.nota)}${'☆'.repeat(5 - c.avaliacao.nota)} (${c.avaliacao.nota}/5)</span>
               — <em>"${c.avaliacao.comentario}"</em>
             </div>`
          : '';

        return `
          <div class="contratacao-item">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
              <strong>Contrato <code>${c.id}</code> — ${c.servico_titulo}</strong>
              <span class="status-pill ${confirmada ? 'pill-confirmada' : 'pill-concluida'}">${c.status}</span>
            </div>
            <div style="font-size:0.82rem; color:var(--muted);">
              Horário: <b>${c.horario}</b> (${c.slot_id})<br/>
              Solicitante: <b>${c.solicitante_nome}</b> | Prestador: <b>${c.prestador_nome}</b>
            </div>
            ${avalHtml}
            <div class="contratacao-actions">
              ${confirmada
                ? `<button class="btn-primary" onclick="concluirServico('${c.id}')">1. Concluir Serviço (RF06)</button>`
                : `<button class="btn-outline" onclick="concluirServico('${c.id}')">Tentar Concluir Novamente (Testar Erro)</button>`
              }
              <button class="btn-warning" onclick="toggleFormAvaliacao('${c.id}')">
                ${confirmada ? 'Tentar Avaliar Antes de Concluir (Testar Bloqueio RES03)' : '2. Registrar Avaliação (RF07)'}
              </button>
            </div>
            <div class="eval-form" id="form-aval-${c.id}" style="display:none;">
              <label style="font-size:0.8rem;">Nota:</label>
              <select id="nota-${c.id}">
                <option value="5">5 ★ (Excelente)</option>
                <option value="4">4 ★ (Muito Bom)</option>
                <option value="3">3 ★ (Regular)</option>
                <option value="2">2 ★ (Ruim)</option>
                <option value="1">1 ★ (Péssimo)</option>
                <option value="6">6 ★ (Nota Inválida > 5 - Testar NotaInvalidaError)</option>
              </select>
              <input type="text" id="comentario-${c.id}" placeholder="Comentário sobre o serviço..." value="Atendimento excelente e muito pontual!" style="flex:1;" />
              <button class="btn-success" onclick="avaliarServico('${c.id}')">Enviar Avaliação</button>
            </div>
          </div>
        `;
      }).join('');
    }

    function renderizarNotificacoes() {
      const container = document.getElementById('listaNotificacoes');
      if (estadoAtual.notificacoes.length === 0) {
        container.innerHTML = '<p style="color:var(--muted); font-size:0.88rem;">Nenhuma notificação externa disparada ainda.</p>';
        return;
      }

      container.innerHTML = estadoAtual.notificacoes.slice().reverse().map(n => `
        <div class="notif-item">
          <div style="display:flex; justify-content:space-between; color:#fbbf24; font-weight:700; margin-bottom:4px;">
            <span>[${n.canal}] Para: ${n.destinatario}</span>
            <span>${n.horario}</span>
          </div>
          <div><strong>Assunto:</strong> ${n.assunto}</div>
          <div style="color:#cbd5e1; margin-top:2px;">${n.mensagem}</div>
        </div>
      `).join('');
    }

    function toggleFormAvaliacao(id) {
      const el = document.getElementById(`form-aval-${id}`);
      el.style.display = (el.style.display === 'none') ? 'flex' : 'none';
    }

    async function solicitarContratacao(servico_id, slot_id) {
      const solicitante_id = obterUsuarioLogado();
      const resp = await fetch('/api/contratar', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ servico_id, slot_id, solicitante_id })
      });
      const dados = await resp.json();
      if (!resp.ok) {
        mostrarAlerta('erro', `Regra de Negócio Protegida pelo Domínio (${dados.erro_tipo})`, dados.mensagem);
      } else {
        mostrarAlerta('sucesso', `Contratação Confirmada e Persistida no SQLite (${dados.contratacao_id})`, dados.mensagem);
      }
      await carregarEstado();
    }

    async function concluirServico(contratacao_id) {
      const resp = await fetch('/api/concluir', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ contratacao_id })
      });
      const dados = await resp.json();
      if (!resp.ok) {
        mostrarAlerta('erro', `Transição Inválida Bloqueada (${dados.erro_tipo})`, dados.mensagem);
      } else {
        mostrarAlerta('sucesso', 'Serviço Concluído com Sucesso (RF06)', dados.mensagem);
      }
      await carregarEstado();
    }

    async function avaliarServico(contratacao_id) {
      const nota = parseInt(document.getElementById(`nota-${contratacao_id}`).value, 10);
      const comentario = document.getElementById(`comentario-${contratacao_id}`).value;
      const resp = await fetch('/api/avaliar', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ contratacao_id, nota, comentario })
      });
      const dados = await resp.json();
      if (!resp.ok) {
        mostrarAlerta('erro', `Invariante de Avaliação Protegida (${dados.erro_tipo})`, dados.mensagem);
      } else {
        mostrarAlerta('sucesso', 'Avaliação Registrada com Sucesso (RF07 / Creator GRASP)', dados.mensagem);
      }
      await carregarEstado();
    }

    async function criarServico() {
      const titulo = document.getElementById('novoTitulo').value.trim();
      const categoria = document.getElementById('novaCategoria').value.trim();
      const descricao = document.getElementById('novaDescricao').value.trim();
      const valor = parseFloat(document.getElementById('novoValor').value || '50');
      const prestador_id = obterUsuarioLogado();

      if (!titulo || !categoria) {
        mostrarAlerta('erro', 'Campos Obrigatórios', 'Informe ao menos o título e a categoria da oferta.');
        return;
      }

      const resp = await fetch('/api/criar_servico', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prestador_id, titulo, categoria, descricao, valor })
      });
      const dados = await resp.json();
      if (resp.ok) {
        document.getElementById('novoTitulo').value = '';
        document.getElementById('novaCategoria').value = '';
        document.getElementById('novaDescricao').value = '';
        mostrarAlerta('sucesso', 'Nova Oferta Publicada no SQLite (RF01 / RF02)', dados.mensagem);
        await carregarEstado();
      }
    }

    async function resetarBanco() {
      await fetch('/api/resetar', { method: 'POST' });
      mostrarAlerta('sucesso', 'Banco SQLite Restaurado', 'Os serviços e slots iniciais da demonstração foram recarregados.');
      await carregarEstado();
    }

    carregarEstado();
  </script>
</body>
</html>
"""


def criar_handler_web(contexto: CampusHubWebContext):
    class CampusHubHTTPHandler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:
            pass

        def _enviar_json(self, status_code: int, payload: Dict[str, Any]) -> None:
            corpo = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(corpo)))
            self.end_headers()
            self.wfile.write(corpo)

        def _ler_json(self) -> Dict[str, Any]:
            tamanho = int(self.headers.get("Content-Length", 0))
            if tamanho == 0:
                return {}
            dados = self.rfile.read(tamanho).decode("utf-8")
            return json.loads(dados)

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/":
                corpo = HTML_PAGINA.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(corpo)))
                self.end_headers()
                self.wfile.write(corpo)
                return

            if parsed.path == "/api/estado":
                qs = parse_qs(parsed.query)
                apenas_livres = qs.get("apenas_livres", ["true"])[0].lower() == "true"
                assert contexto.consultar_uc is not None and contexto.notificador is not None

                servicos = contexto.consultar_uc.executar(apenas_com_slots_livres=apenas_livres)
                nomes_membros = {m.id: m.nome for m in contexto.membros}

                servicos_json = [
                    {
                        "id": s.id,
                        "prestador_id": s.prestador_id,
                        "prestador_nome": nomes_membros.get(s.prestador_id, s.prestador_id),
                        "titulo": s.titulo,
                        "descricao": s.descricao,
                        "categoria": s.categoria,
                        "valor": s.valor,
                        "slots": [
                            {
                                "id": slot.id,
                                "inicio": slot.inicio.strftime("%d/%m/%Y %H:%M"),
                                "fim": slot.fim.strftime("%H:%M"),
                                "status": slot.status.value,
                            }
                            for slot in s.slots
                        ],
                    }
                    for s in servicos
                ]

                self._enviar_json(
                    200,
                    {
                        "membros": [
                            {
                                "id": m.id,
                                "nome": m.nome,
                                "email": m.email,
                                "registro_academico": m.registro_academico,
                            }
                            for m in contexto.membros
                        ],
                        "servicos": servicos_json,
                        "contratacoes": contexto.listar_todas_contratacoes(),
                        "notificacoes": contexto.notificador.fake_notificador.mensagens_enviadas,
                    },
                )
                return

            self._enviar_json(404, {"erro": "Rota não encontrada"})

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            dados = self._ler_json()

            try:
                if parsed.path == "/api/contratar":
                    assert contexto.solicitar_uc is not None
                    contratacao = contexto.solicitar_uc.executar(
                        servico_id=dados["servico_id"],
                        slot_id=dados["slot_id"],
                        solicitante_id=dados["solicitante_id"],
                    )
                    self._enviar_json(
                        200,
                        {
                            "contratacao_id": contratacao.id,
                            "mensagem": (
                                f"Slot '{contratacao.slot_id}' alterado para RESERVADO no SQLite e "
                                f"notificação enviada ao prestador '{contratacao.prestador_id}'!"
                            ),
                        },
                    )
                    return

                if parsed.path == "/api/concluir":
                    assert contexto.concluir_avaliar_uc is not None
                    contratacao = contexto.concluir_avaliar_uc.concluir(dados["contratacao_id"])
                    self._enviar_json(
                        200,
                        {
                            "mensagem": (
                                f"Contratação '{contratacao.id}' alterada para CONCLUIDA e "
                                f"notificação disparada para '{contratacao.solicitante_id}'."
                            )
                        },
                    )
                    return

                if parsed.path == "/api/avaliar":
                    assert contexto.concluir_avaliar_uc is not None
                    avaliacao = contexto.concluir_avaliar_uc.avaliar(
                        contratacao_id=dados["contratacao_id"],
                        nota=int(dados["nota"]),
                        comentario=str(dados["comentario"]),
                    )
                    self._enviar_json(
                        200,
                        {
                            "mensagem": (
                                f"Avaliação '{avaliacao.id}' (Nota {avaliacao.nota}/5) instanciada por "
                                "Contratacao.registrar_avaliacao() e salva no SQLite!"
                            )
                        },
                    )
                    return

                if parsed.path == "/api/criar_servico":
                    assert contexto.servico_repo is not None
                    existentes = contexto.servico_repo.listar_disponiveis()
                    novo_id = f"serv-0{len(existentes) + 1}"
                    novo_servico = Servico(
                        id=novo_id,
                        prestador_id=dados["prestador_id"],
                        titulo=dados["titulo"],
                        descricao=dados.get("descricao") or "Atendimento acadêmico no campus.",
                        categoria=dados["categoria"],
                        valor=float(dados.get("valor", 50.0)),
                    )
                    novo_servico.adicionar_slot(
                        datetime(2026, 11, 30, 14, 0),
                        datetime(2026, 11, 30, 15, 30),
                    )
                    contexto.servico_repo.salvar(novo_servico)
                    self._enviar_json(
                        200,
                        {"mensagem": f"Serviço '{novo_servico.titulo}' ({novo_id}) criado com slot inicial LIVRE!"},
                    )
                    return

                if parsed.path == "/api/resetar":
                    contexto.inicializar_sistema(resetar_banco=True)
                    self._enviar_json(200, {"mensagem": "Banco SQLite reinicializado."})
                    return

                self._enviar_json(404, {"erro": "Rota não encontrada"})

            except ErroDominio as erro:
                self._enviar_json(
                    400,
                    {
                        "erro_tipo": erro.__class__.__name__,
                        "mensagem": erro.mensagem,
                    },
                )

    return CampusHubHTTPHandler


def iniciar_servidor_web(porta: int = 8000, caminho_banco: str = "campushub.db", abrir_navegador: bool = True) -> None:
    contexto = CampusHubWebContext(caminho_banco=caminho_banco)
    handler = criar_handler_web(contexto)
    servidor = HTTPServer(("127.0.0.1", porta), handler)
    url = f"http://localhost:{porta}"

    print("=" * 88)
    print(f" CAMPUSHUB UFPR (TEMA 11) — FRONT-END WEB INTERATIVO RODANDO EM: {url}")
    print(" Pressione Ctrl+C a qualquer momento para encerrar o servidor.")
    print("=" * 88)

    if abrir_navegador:
        try:
            webbrowser.open(url)
        except Exception:
            pass

    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor Web encerrado.")
        servidor.server_close()
