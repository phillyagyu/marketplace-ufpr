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
  <title>CampusHub UFPR — Marketplace de Serviços Acadêmicos</title>
  <style>
    :root {
      --bg: #f6f8fc;
      --surface: #ffffff;
      --surface-soft: #f8fafc;
      --border: #e2e8f0;
      --border-soft: #edf2f7;
      --text: #1e293b;
      --text-muted: #64748b;

      /* Paleta Pastel Suave */
      --indigo-pastel: #e0e7ff;
      --indigo-border: #c7d2fe;
      --indigo-text: #4338ca;
      --indigo-btn: #6366f1;
      --indigo-btn-hover: #4f46e5;

      --mint-pastel: #dcfce7;
      --mint-border: #bbf7d0;
      --mint-text: #15803d;
      --mint-btn: #34d399;

      --rose-pastel: #ffe4e6;
      --rose-border: #fecdd3;
      --rose-text: #be123c;

      --amber-pastel: #fef3c7;
      --amber-border: #fde68a;
      --amber-text: #b45309;

      --lavender-pastel: #f3e8ff;
      --lavender-border: #e9d5ff;
      --lavender-text: #6b21a8;

      --sky-pastel: #e0f2fe;
      --sky-border: #bae6fd;
      --sky-text: #0369a1;
    }

    * {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
      font-family: 'Inter', 'Segoe UI', system-ui, -apple-system, sans-serif;
    }

    body {
      background-color: var(--bg);
      color: var(--text);
      min-height: 100vh;
      padding-bottom: 48px;
      line-height: 1.5;
    }

    /* Top Navbar de Aplicacao Real */
    .navbar {
      background: var(--surface);
      border-bottom: 1px solid var(--border);
      padding: 14px 32px;
      position: sticky;
      top: 0;
      z-index: 50;
      box-shadow: 0 2px 10px rgba(15, 23, 42, 0.03);
    }
    .navbar-inner {
      max-width: 1360px;
      margin: 0 auto;
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
    }
    .brand {
      display: flex;
      align-items: center;
      gap: 12px;
    }
    .brand-logo {
      width: 42px;
      height: 42px;
      border-radius: 12px;
      background: linear-gradient(135deg, #c7d2fe 0%, #e9d5ff 100%);
      color: var(--indigo-text);
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: 800;
      font-size: 1.15rem;
      border: 1px solid var(--indigo-border);
    }
    .brand-text h1 {
      font-size: 1.22rem;
      font-weight: 700;
      color: #0f172a;
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .campus-tag {
      font-size: 0.72rem;
      background: var(--lavender-pastel);
      color: var(--lavender-text);
      border: 1px solid var(--lavender-border);
      padding: 2px 10px;
      border-radius: 999px;
      font-weight: 600;
    }
    .brand-text p {
      font-size: 0.8rem;
      color: var(--text-muted);
    }

    /* Seletor de Perfil na Navbar */
    .profile-switcher {
      display: flex;
      align-items: center;
      gap: 10px;
      background: var(--surface-soft);
      padding: 6px 12px;
      border-radius: 12px;
      border: 1px solid var(--border);
    }
    .avatar-circle {
      width: 32px;
      height: 32px;
      border-radius: 50%;
      background: var(--indigo-pastel);
      color: var(--indigo-text);
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: 700;
      font-size: 0.82rem;
    }
    .profile-switcher label {
      font-size: 0.75rem;
      color: var(--text-muted);
      font-weight: 600;
      display: block;
    }
    select, input, textarea {
      background: var(--surface);
      color: var(--text);
      border: 1px solid var(--border);
      padding: 8px 12px;
      border-radius: 8px;
      font-size: 0.86rem;
      outline: none;
      transition: border-color 0.15s, box-shadow 0.15s;
    }
    select:focus, input:focus, textarea:focus {
      border-color: var(--indigo-btn);
      box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.12);
    }
    .profile-select {
      border: none;
      background: transparent;
      font-weight: 600;
      color: var(--text);
      padding: 2px 4px;
      font-size: 0.88rem;
      cursor: pointer;
    }

    /* Botoes Suaves */
    button {
      cursor: pointer;
      border: none;
      border-radius: 8px;
      padding: 8px 14px;
      font-size: 0.84rem;
      font-weight: 600;
      transition: all 0.15s ease;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 6px;
    }
    .btn-primary {
      background: var(--indigo-btn);
      color: #ffffff;
      box-shadow: 0 2px 5px rgba(99, 102, 241, 0.22);
    }
    .btn-primary:hover { background: var(--indigo-btn-hover); transform: translateY(-1px); }

    .btn-mint {
      background: var(--mint-pastel);
      color: var(--mint-text);
      border: 1px solid var(--mint-border);
    }
    .btn-mint:hover { background: #bbf7d0; transform: translateY(-1px); }

    .btn-rose-soft {
      background: var(--rose-pastel);
      color: var(--rose-text);
      border: 1px solid var(--rose-border);
    }
    .btn-rose-soft:hover { background: #fecdd3; }

    .btn-amber-soft {
      background: var(--amber-pastel);
      color: var(--amber-text);
      border: 1px solid var(--amber-border);
    }
    .btn-amber-soft:hover { background: #fde68a; }

    .btn-ghost {
      background: var(--surface);
      color: var(--text-muted);
      border: 1px solid var(--border);
    }
    .btn-ghost:hover { background: var(--surface-soft); color: var(--text); }

    /* Hero Banner / Barra de Busca e Filtros */
    .hero-wrap {
      max-width: 1360px;
      margin: 22px auto 0;
      padding: 0 24px;
    }
    .hero-banner {
      background: linear-gradient(120deg, #eef2ff 0%, #fdf4ff 50%, #f0fdf4 100%);
      border: 1px solid var(--indigo-border);
      border-radius: 16px;
      padding: 20px 26px;
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
    }
    .hero-left h2 {
      font-size: 1.25rem;
      color: #1e1b4b;
      margin-bottom: 4px;
    }
    .hero-left p {
      font-size: 0.88rem;
      color: #475569;
    }
    .filter-bar {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 10px;
    }
    .cat-pill {
      padding: 6px 14px;
      border-radius: 999px;
      font-size: 0.8rem;
      font-weight: 600;
      background: rgba(255, 255, 255, 0.85);
      color: var(--text-muted);
      border: 1px solid var(--border);
      cursor: pointer;
    }
    .cat-pill.active {
      background: var(--indigo-btn);
      color: white;
      border-color: var(--indigo-btn);
    }

    /* Alertas / Notificacoes Flutuantes */
    .alert-box {
      max-width: 1360px;
      margin: 14px auto 0;
      padding: 0 24px;
    }
    .toast {
      padding: 14px 20px;
      border-radius: 12px;
      margin-bottom: 10px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 14px;
      font-size: 0.9rem;
      box-shadow: 0 4px 12px rgba(15, 23, 42, 0.06);
      animation: slideDown 0.22s ease;
    }
    .toast-error {
      background: #fff1f2;
      border: 1px solid #fda4af;
      border-left: 5px solid #e11d48;
      color: #881337;
    }
    .toast-success {
      background: #f0fdf4;
      border: 1px solid #86efac;
      border-left: 5px solid #16a34a;
      color: #14532d;
    }
    @keyframes slideDown {
      from { opacity: 0; transform: translateY(-6px); }
      to { opacity: 1; transform: translateY(0); }
    }

    /* Layout Principal */
    .main-grid {
      max-width: 1360px;
      margin: 22px auto 0;
      padding: 0 24px;
      display: grid;
      grid-template-columns: 1.45fr 1fr;
      gap: 24px;
    }
    @media (max-width: 1024px) {
      .main-grid { grid-template-columns: 1fr; }
    }

    .section-card {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 16px;
      padding: 22px;
      margin-bottom: 22px;
      box-shadow: 0 2px 8px rgba(15, 23, 42, 0.02);
    }
    .section-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 10px;
      margin-bottom: 18px;
      padding-bottom: 12px;
      border-bottom: 1px solid var(--border-soft);
    }
    .section-title {
      font-size: 1.06rem;
      font-weight: 700;
      color: #0f172a;
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .count-badge {
      background: var(--indigo-pastel);
      color: var(--indigo-text);
      font-size: 0.76rem;
      padding: 2px 9px;
      border-radius: 999px;
      font-weight: 700;
    }

    /* Cards de Servico do Marketplace */
    .service-card {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 18px 20px;
      margin-bottom: 16px;
      transition: box-shadow 0.18s ease, border-color 0.18s ease;
    }
    .service-card:hover {
      border-color: var(--indigo-border);
      box-shadow: 0 6px 18px rgba(99, 102, 241, 0.06);
    }
    .service-header {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 12px;
      margin-bottom: 8px;
    }
    .cat-tag {
      display: inline-block;
      font-size: 0.72rem;
      font-weight: 700;
      padding: 3px 10px;
      border-radius: 999px;
      background: var(--sky-pastel);
      color: var(--sky-text);
      border: 1px solid var(--sky-border);
      margin-bottom: 6px;
    }
    .service-title {
      font-size: 1.08rem;
      font-weight: 700;
      color: #1e293b;
    }
    .price-badge {
      background: var(--mint-pastel);
      color: var(--mint-text);
      border: 1px solid var(--mint-border);
      padding: 6px 12px;
      border-radius: 10px;
      font-size: 1rem;
      font-weight: 800;
      white-space: nowrap;
    }
    .provider-row {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 0.83rem;
      color: var(--text-muted);
      margin-bottom: 10px;
    }
    .provider-dot {
      width: 24px;
      height: 24px;
      border-radius: 50%;
      background: var(--lavender-pastel);
      color: var(--lavender-text);
      display: inline-flex;
      align-items: center;
      justify-content: center;
      font-weight: 700;
      font-size: 0.72rem;
    }
    .own-badge {
      background: var(--amber-pastel);
      color: var(--amber-text);
      border: 1px solid var(--amber-border);
      font-size: 0.72rem;
      font-weight: 700;
      padding: 1px 8px;
      border-radius: 999px;
    }
    .service-desc {
      font-size: 0.88rem;
      color: #475569;
      margin-bottom: 14px;
    }

    /* Slots de Horario */
    .slots-box {
      background: var(--surface-soft);
      border: 1px solid var(--border-soft);
      border-radius: 12px;
      padding: 12px;
    }
    .slots-label {
      font-size: 0.76rem;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.03em;
      color: var(--text-muted);
      margin-bottom: 8px;
    }
    .slot-row {
      display: flex;
      justify-content: space-between;
      align-items: center;
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 8px 12px;
      margin-bottom: 8px;
      flex-wrap: wrap;
      gap: 8px;
    }
    .slot-row:last-child { margin-bottom: 0; }
    .slot-info {
      display: flex;
      align-items: center;
      gap: 10px;
    }
    .status-badge {
      font-size: 0.72rem;
      font-weight: 700;
      padding: 3px 10px;
      border-radius: 999px;
      text-transform: capitalize;
    }
    .badge-livre {
      background: var(--mint-pastel);
      color: var(--mint-text);
      border: 1px solid var(--mint-border);
    }
    .badge-reservado {
      background: var(--rose-pastel);
      color: var(--rose-text);
      border: 1px solid var(--rose-border);
    }
    .badge-confirmada {
      background: var(--sky-pastel);
      color: var(--sky-text);
      border: 1px solid var(--sky-border);
    }
    .badge-concluida {
      background: var(--mint-pastel);
      color: var(--mint-text);
      border: 1px solid var(--mint-border);
    }

    /* Contratacoes e Avaliacoes */
    .booking-card {
      background: var(--surface-soft);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 16px;
      margin-bottom: 12px;
    }
    .booking-top {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 8px;
      margin-bottom: 6px;
    }
    .booking-title {
      font-size: 0.95rem;
      font-weight: 700;
      color: #0f172a;
    }
    .booking-meta {
      font-size: 0.82rem;
      color: var(--text-muted);
      line-height: 1.45;
    }
    .booking-actions {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 12px;
      padding-top: 10px;
      border-top: 1px dashed var(--border);
    }
    .review-box {
      margin-top: 10px;
      background: var(--amber-pastel);
      border: 1px solid var(--amber-border);
      color: #78350f;
      padding: 10px 12px;
      border-radius: 10px;
      font-size: 0.84rem;
    }
    .eval-drawer {
      margin-top: 10px;
      background: var(--surface);
      border: 1px solid var(--border);
      padding: 12px;
      border-radius: 10px;
      display: flex;
      flex-direction: column;
      gap: 8px;
    }

    /* Caixa de E-mails / Notificacoes */
    .email-card {
      background: var(--surface-soft);
      border: 1px solid var(--border);
      border-left: 4px solid #818cf8;
      border-radius: 10px;
      padding: 12px 14px;
      margin-bottom: 10px;
      font-size: 0.83rem;
    }
    .email-header {
      display: flex;
      justify-content: space-between;
      color: var(--indigo-text);
      font-weight: 700;
      margin-bottom: 4px;
      font-size: 0.78rem;
    }
    .empty-state {
      text-align: center;
      padding: 24px 12px;
      color: var(--text-muted);
      font-size: 0.88rem;
    }
  </style>
</head>
<body>

  <!-- NAVBAR -->
  <nav class="navbar">
    <div class="navbar-inner">
      <div class="brand">
        <div class="brand-logo">CH</div>
        <div class="brand-text">
          <h1>
            CampusHub UFPR
            <span class="campus-tag">Comunidade Acadêmica</span>
          </h1>
          <p>Marketplace de mentorias, revisões e serviços especializados dentro do campus</p>
        </div>
      </div>

      <div style="display: flex; align-items: center; gap: 12px; flex-wrap: wrap;">
        <div class="profile-switcher">
          <div class="avatar-circle" id="avatarIniciais">LM</div>
          <div>
            <label for="usuarioAtivo">Acessando como:</label>
            <select id="usuarioAtivo" class="profile-select" onchange="trocarUsuario()"></select>
          </div>
        </div>

        <button class="btn-ghost" onclick="resetarBanco()" title="Restaura os serviços e horários iniciais">
          Restaurar Dados Iniciais
        </button>
      </div>
    </div>
  </nav>

  <!-- HERO & FILTROS -->
  <div class="hero-wrap">
    <div class="hero-banner">
      <div class="hero-left">
        <h2>Encontre ou ofereça apoio acadêmico na UFPR</h2>
        <p>Agende horários livres com estudantes e docentes, acompanhe suas solicitações e avalie os atendimentos.</p>
      </div>

      <div class="filter-bar">
        <input type="text" id="buscaTexto" placeholder="Buscar por título ou área..." oninput="renderizarServicos()" style="min-width: 220px;" />
        <label style="font-size: 0.84rem; color: #334155; font-weight: 600; display: flex; align-items: center; gap: 6px; cursor: pointer; background: rgba(255,255,255,0.8); padding: 7px 12px; border-radius: 8px; border: 1px solid var(--border);">
          <input type="checkbox" id="filtroSlotsLivres" checked onchange="carregarEstado()" />
          Somente com horários livres
        </label>
      </div>
    </div>
  </div>

  <!-- TOAST ALERTS -->
  <div class="alert-box" id="alertContainer"></div>

  <!-- CONTEUDO PRINCIPAL -->
  <div class="main-grid">
    <!-- COLUNA ESQUERDA: SERVICOS E PUBLICACAO -->
    <div>
      <div class="section-card">
        <div class="section-header">
          <div class="section-title">
            Serviços Disponíveis no Campus
            <span class="count-badge" id="contadorServicos">0</span>
          </div>
          <div style="display: flex; gap: 6px; flex-wrap: wrap;" id="filtrosCategoria">
            <span class="cat-pill active" onclick="selecionarCategoria('TODAS', this)">Todas</span>
            <span class="cat-pill" onclick="selecionarCategoria('Revisão Acadêmica', this)">Revisão Acadêmica</span>
            <span class="cat-pill" onclick="selecionarCategoria('Mentoria', this)">Mentoria</span>
            <span class="cat-pill" onclick="selecionarCategoria('Pesquisa & Dados', this)">Pesquisa &amp; Dados</span>
          </div>
        </div>

        <div id="listaServicos">Carregando serviços...</div>
      </div>

      <!-- PUBLICAR NOVA OFERTA -->
      <div class="section-card">
        <div class="section-header">
          <div class="section-title">Oferecer um Novo Serviço no Campus</div>
          <span style="font-size: 0.78rem; color: var(--text-muted);">Publica um serviço vinculado ao seu perfil atual</span>
        </div>
        <div style="display: grid; grid-template-columns: 1.5fr 1fr; gap: 10px;">
          <input type="text" id="novoTitulo" placeholder="Título do serviço (ex: Monitoria de Cálculo II)" />
          <input type="text" id="novaCategoria" placeholder="Categoria (ex: Mentoria, Revisão)" />
          <input type="text" id="novaDescricao" placeholder="Descreva como funciona o atendimento..." style="grid-column: span 2;" />
          <div style="display: flex; align-items: center; gap: 8px;">
            <span style="font-size: 0.85rem; color: var(--text-muted); font-weight: 600;">Valor (R$):</span>
            <input type="number" id="novoValor" value="50" style="width: 110px;" />
          </div>
          <button class="btn-primary" onclick="criarServico()">Publicar Oferta com Horário Livre</button>
        </div>
      </div>
    </div>

    <!-- COLUNA DIREITA: MINHAS CONTRATACOES E E-MAILS -->
    <div>
      <div class="section-card">
        <div class="section-header">
          <div class="section-title">
            Contratações &amp; Avaliações
            <span class="count-badge" id="contadorContratacoes">0</span>
          </div>
          <span style="font-size: 0.76rem; color: var(--text-muted);">Salvo em SQLite</span>
        </div>
        <div id="listaContratacoes"></div>
      </div>

      <div class="section-card">
        <div class="section-header">
          <div class="section-title">
            Notificações Enviadas (@ufpr.br)
            <span class="count-badge" id="contadorNotificacoes">0</span>
          </div>
          <span style="font-size: 0.76rem; color: var(--text-muted);">Via NotificadorPort</span>
        </div>
        <div id="listaNotificacoes"></div>
      </div>
    </div>
  </div>

  <script>
    let estadoAtual = { membros: [], servicos: [], contratacoes: [], notificacoes: [] };
    let categoriaSelecionada = 'TODAS';

    function mostrarAlerta(tipo, titulo, detalhe) {
      const container = document.getElementById('alertContainer');
      const div = document.createElement('div');
      div.className = 'toast ' + (tipo === 'erro' ? 'toast-error' : 'toast-success');
      div.innerHTML = `
        <div>
          <strong>${titulo}</strong>
          <div style="font-size: 0.85rem; margin-top: 2px;">${detalhe}</div>
        </div>
        <button class="btn-ghost" style="padding: 4px 10px; font-size: 0.78rem;" onclick="this.parentElement.remove()">Fechar</button>
      `;
      container.prepend(div);
      setTimeout(() => { if (div.parentElement) div.remove(); }, 8000);
    }

    function obterUsuarioLogado() {
      return document.getElementById('usuarioAtivo').value;
    }

    function iniciaisNome(nome) {
      const partes = nome.split(' ');
      if (partes.length >= 2) return (partes[0][0] + partes[1][0]).toUpperCase();
      return nome.substring(0, 2).toUpperCase();
    }

    function trocarUsuario() {
      const uid = obterUsuarioLogado();
      const membro = estadoAtual.membros.find(m => m.id === uid);
      if (membro) {
        document.getElementById('avatarIniciais').textContent = iniciaisNome(membro.nome);
      }
      renderizarServicos();
    }

    function selecionarCategoria(cat, el) {
      categoriaSelecionada = cat;
      document.querySelectorAll('#filtrosCategoria .cat-pill').forEach(p => p.classList.remove('active'));
      el.classList.add('active');
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
          opt.textContent = `${m.nome} (${m.registro_academico})`;
          select.appendChild(opt);
        });
        if (valorAnterior) select.value = valorAnterior;
      }

      trocarUsuario();
      renderizarContratacoes();
      renderizarNotificacoes();
    }

    function renderizarServicos() {
      const container = document.getElementById('listaServicos');
      const usuarioLogado = obterUsuarioLogado();
      const termo = (document.getElementById('buscaTexto').value || '').toLowerCase().trim();

      const filtrados = estadoAtual.servicos.filter(s => {
        const bateCategoria = (categoriaSelecionada === 'TODAS') || (s.categoria === categoriaSelecionada);
        const bateTexto = !termo || s.titulo.toLowerCase().includes(termo) || s.descricao.toLowerCase().includes(termo) || s.categoria.toLowerCase().includes(termo);
        return bateCategoria && bateTexto;
      });

      document.getElementById('contadorServicos').textContent = filtrados.length;

      if (filtrados.length === 0) {
        container.innerHTML = '<div class="empty-state">Nenhum serviço encontrado para os filtros selecionados.</div>';
        return;
      }

      container.innerHTML = filtrados.map(s => {
        const ehProprioPrestador = (s.prestador_id === usuarioLogado);
        const slotsHtml = s.slots.map(slot => {
          const livre = slot.status === 'livre';
          const btnClass = livre ? 'btn-mint' : 'btn-rose-soft';
          const btnTexto = livre ? 'Agendar Horário' : 'Horário Reservado';

          return `
            <div class="slot-row">
              <div class="slot-info">
                <span class="status-badge ${livre ? 'badge-livre' : 'badge-reservado'}">
                  ${livre ? 'Disponível' : 'Reservado'}
                </span>
                <strong style="font-size: 0.87rem; color: #1e293b;">${slot.inicio} às ${slot.fim}</strong>
                <span style="color: var(--text-muted); font-size: 0.76rem;">(${slot.id})</span>
              </div>
              <button class="${btnClass}" onclick="solicitarContratacao('${s.id}', '${slot.id}')">
                ${btnTexto}
              </button>
            </div>
          `;
        }).join('');

        return `
          <div class="service-card">
            <div class="service-header">
              <div>
                <span class="cat-tag">${s.categoria}</span>
                <div class="service-title">${s.titulo}</div>
              </div>
              <div class="price-badge">R$ ${s.valor.toFixed(2)}</div>
            </div>

            <div class="provider-row">
              <span class="provider-dot">${iniciaisNome(s.prestador_nome)}</span>
              <span>Oferecido por <strong>${s.prestador_nome}</strong></span>
              ${ehProprioPrestador ? '<span class="own-badge">Seu anúncio</span>' : ''}
            </div>

            <p class="service-desc">${s.descricao}</p>

            <div class="slots-box">
              <div class="slots-label">Horários na Agenda</div>
              ${slotsHtml}
            </div>
          </div>
        `;
      }).join('');
    }

    function renderizarContratacoes() {
      const container = document.getElementById('listaContratacoes');
      document.getElementById('contadorContratacoes').textContent = estadoAtual.contratacoes.length;

      if (estadoAtual.contratacoes.length === 0) {
        container.innerHTML = '<div class="empty-state">Nenhuma contratação realizada ainda.<br/>Escolha um horário disponível ao lado para agendar!</div>';
        return;
      }

      container.innerHTML = estadoAtual.contratacoes.map(c => {
        const confirmada = c.status === 'confirmada';
        const avalHtml = c.avaliacao
          ? `<div class="review-box">
               <div style="font-weight: 700; margin-bottom: 2px;">
                 Avaliação do Solicitante: ${'★'.repeat(c.avaliacao.nota)}${'☆'.repeat(5 - c.avaliacao.nota)} (${c.avaliacao.nota}/5)
               </div>
               <div>"${c.avaliacao.comentario}"</div>
             </div>`
          : '';

        return `
          <div class="booking-card">
            <div class="booking-top">
              <div class="booking-title">${c.servico_titulo}</div>
              <span class="status-badge ${confirmada ? 'badge-confirmada' : 'badge-concluida'}">
                ${confirmada ? 'Confirmada' : 'Concluída'}
              </span>
            </div>
            <div class="booking-meta">
              <div><strong>Horário:</strong> ${c.horario}</div>
              <div><strong>Solicitante:</strong> ${c.solicitante_nome}</div>
              <div><strong>Prestador:</strong> ${c.prestador_nome}</div>
              <div style="font-size: 0.75rem; margin-top: 2px;">Código: <code>${c.id}</code></div>
            </div>
            ${avalHtml}
            <div class="booking-actions">
              <button class="${confirmada ? 'btn-primary' : 'btn-ghost'}" onclick="concluirServico('${c.id}')">
                ${confirmada ? 'Marcar como Concluído' : 'Concluído'}
              </button>
              <button class="btn-amber-soft" onclick="toggleFormAvaliacao('${c.id}')">
                Avaliar Atendimento
              </button>
            </div>
            <div class="eval-drawer" id="form-aval-${c.id}" style="display:none;">
              <div style="display: flex; gap: 8px; align-items: center; flex-wrap: wrap;">
                <label style="font-size: 0.8rem; font-weight: 600;">Nota:</label>
                <select id="nota-${c.id}" style="flex: 1;">
                  <option value="5">★★★★★ (5 - Excelente)</option>
                  <option value="4">★★★★☆ (4 - Muito Bom)</option>
                  <option value="3">★★★☆☆ (3 - Regular)</option>
                  <option value="2">★★☆☆☆ (2 - Insatisfatório)</option>
                  <option value="1">★☆☆☆☆ (1 - Ruim)</option>
                  <option value="6">Nota 6 (Testar Validação de Nota Inválida)</option>
                </select>
              </div>
              <input type="text" id="comentario-${c.id}" placeholder="Escreva seu comentário sobre o serviço..." value="Excelente atendimento, muito didático e pontual!" />
              <button class="btn-primary" onclick="avaliarServico('${c.id}')">Confirmar Avaliação</button>
            </div>
          </div>
        `;
      }).join('');
    }

    function renderizarNotificacoes() {
      const container = document.getElementById('listaNotificacoes');
      document.getElementById('contadorNotificacoes').textContent = estadoAtual.notificacoes.length;

      if (estadoAtual.notificacoes.length === 0) {
        container.innerHTML = '<div class="empty-state">Nenhum alerta institucional enviado ainda.</div>';
        return;
      }

      container.innerHTML = estadoAtual.notificacoes.slice().reverse().map(n => `
        <div class="email-card">
          <div class="email-header">
            <span>Para: ${n.destinatario}</span>
            <span>${n.horario} • ${n.canal}</span>
          </div>
          <div style="font-weight: 600; color: #1e293b; margin-bottom: 2px;">${n.assunto}</div>
          <div style="color: var(--text-muted);">${n.mensagem}</div>
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
        mostrarAlerta('erro', `Não foi possível agendar (${dados.erro_tipo})`, dados.mensagem);
      } else {
        mostrarAlerta('sucesso', `Agendamento Confirmado (${dados.contratacao_id})`, dados.mensagem);
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
        mostrarAlerta('erro', `Operação não permitida (${dados.erro_tipo})`, dados.mensagem);
      } else {
        mostrarAlerta('sucesso', 'Serviço Concluído', dados.mensagem);
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
        mostrarAlerta('erro', `Avaliação recusada (${dados.erro_tipo})`, dados.mensagem);
      } else {
        mostrarAlerta('sucesso', 'Avaliação Registrada com Sucesso!', dados.mensagem);
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
        mostrarAlerta('erro', 'Campos obrigatórios', 'Preencha o título e a categoria para publicar sua oferta.');
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
        mostrarAlerta('sucesso', 'Oferta Publicada no CampusHub!', dados.mensagem);
        await carregarEstado();
      }
    }

    async function resetarBanco() {
      await fetch('/api/resetar', { method: 'POST' });
      mostrarAlerta('sucesso', 'Dados Iniciais Restaurados', 'A agenda e os serviços foram reiniciados com sucesso.');
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
