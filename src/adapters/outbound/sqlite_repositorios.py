import sqlite3
from datetime import datetime
from typing import List, Optional, Union

from src.domain.entidades import (
    Avaliacao,
    Contratacao,
    Servico,
    SlotDisponibilidade,
    StatusContratacao,
    StatusSlot,
)
from src.ports.interfaces import ContratacaoRepository, ServicoRepository


def criar_conexao_sqlite(destino: Union[sqlite3.Connection, str] = ":memory:") -> sqlite3.Connection:
    """Retorna uma conexão SQLite configurada e inicializa o esquema relacional caso necessário."""
    if isinstance(destino, sqlite3.Connection):
        conn = destino
    else:
        conn = sqlite3.connect(destino)

    conn.row_factory = sqlite3.Row
    with conn:
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS servicos (
                id TEXT PRIMARY KEY,
                prestador_id TEXT NOT NULL,
                titulo TEXT NOT NULL,
                descricao TEXT NOT NULL,
                categoria TEXT NOT NULL,
                valor REAL NOT NULL
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS slots (
                id TEXT NOT NULL,
                servico_id TEXT NOT NULL,
                inicio TEXT NOT NULL,
                fim TEXT NOT NULL,
                status TEXT NOT NULL,
                PRIMARY KEY (id, servico_id),
                FOREIGN KEY (servico_id) REFERENCES servicos (id) ON DELETE CASCADE
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS contratacoes (
                id TEXT PRIMARY KEY,
                servico_id TEXT NOT NULL,
                slot_id TEXT NOT NULL,
                solicitante_id TEXT NOT NULL,
                prestador_id TEXT NOT NULL,
                status TEXT NOT NULL,
                criado_em TEXT NOT NULL
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS avaliacoes (
                id TEXT PRIMARY KEY,
                contratacao_id TEXT NOT NULL UNIQUE,
                nota INTEGER NOT NULL,
                comentario TEXT NOT NULL,
                criado_em TEXT NOT NULL,
                FOREIGN KEY (contratacao_id) REFERENCES contratacoes (id) ON DELETE CASCADE
            );
            """
        )
    return conn


class SqliteServicoRepository(ServicoRepository):
    """Adaptador secundário de persistência SQLite para a Raiz de Agregado Servico e seus Slots (ASR-02 / ASR-03)."""

    def __init__(self, conn: Union[sqlite3.Connection, str] = ":memory:"):
        self.conn = criar_conexao_sqlite(conn)

    def salvar(self, servico: Servico) -> None:
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO servicos (id, prestador_id, titulo, descricao, categoria, valor)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    prestador_id = excluded.prestador_id,
                    titulo = excluded.titulo,
                    descricao = excluded.descricao,
                    categoria = excluded.categoria,
                    valor = excluded.valor;
                """,
                (
                    servico.id,
                    servico.prestador_id,
                    servico.titulo,
                    servico.descricao,
                    servico.categoria,
                    float(servico.valor),
                ),
            )

            self.conn.execute("DELETE FROM slots WHERE servico_id = ?;", (servico.id,))
            for slot in servico.slots:
                self.conn.execute(
                    """
                    INSERT INTO slots (id, servico_id, inicio, fim, status)
                    VALUES (?, ?, ?, ?, ?);
                    """,
                    (
                        slot.id,
                        servico.id,
                        slot.inicio.isoformat(),
                        slot.fim.isoformat(),
                        slot.status.value,
                    ),
                )

    def buscar_por_id(self, servico_id: str) -> Optional[Servico]:
        cursor = self.conn.execute(
            "SELECT id, prestador_id, titulo, descricao, categoria, valor FROM servicos WHERE id = ?;",
            (servico_id,),
        )
        row = cursor.fetchone()
        if row is None:
            return None

        return self._reconstruir_servico(row)

    def listar_disponiveis(self) -> List[Servico]:
        cursor = self.conn.execute(
            "SELECT id, prestador_id, titulo, descricao, categoria, valor FROM servicos ORDER BY id;"
        )
        rows = cursor.fetchall()
        return [self._reconstruir_servico(row) for row in rows]

    def _reconstruir_servico(self, row: sqlite3.Row) -> Servico:
        cursor_slots = self.conn.execute(
            """
            SELECT id, servico_id, inicio, fim, status
            FROM slots
            WHERE servico_id = ?
            ORDER BY inicio;
            """,
            (row["id"],),
        )
        slots = [
            SlotDisponibilidade(
                id=slot_row["id"],
                servico_id=slot_row["servico_id"],
                inicio=datetime.fromisoformat(slot_row["inicio"]),
                fim=datetime.fromisoformat(slot_row["fim"]),
                status=StatusSlot(slot_row["status"]),
            )
            for slot_row in cursor_slots.fetchall()
        ]

        return Servico(
            id=row["id"],
            prestador_id=row["prestador_id"],
            titulo=row["titulo"],
            descricao=row["descricao"],
            categoria=row["categoria"],
            valor=float(row["valor"]),
            slots=slots,
        )


class SqliteContratacaoRepository(ContratacaoRepository):
    """Adaptador secundário de persistência SQLite para a Raiz de Agregado Contratacao e sua Avaliacao (ASR-02 / ASR-03)."""

    def __init__(self, conn: Union[sqlite3.Connection, str] = ":memory:"):
        self.conn = criar_conexao_sqlite(conn)

    def salvar(self, contratacao: Contratacao) -> None:
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO contratacoes (id, servico_id, slot_id, solicitante_id, prestador_id, status, criado_em)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    servico_id = excluded.servico_id,
                    slot_id = excluded.slot_id,
                    solicitante_id = excluded.solicitante_id,
                    prestador_id = excluded.prestador_id,
                    status = excluded.status,
                    criado_em = excluded.criado_em;
                """,
                (
                    contratacao.id,
                    contratacao.servico_id,
                    contratacao.slot_id,
                    contratacao.solicitante_id,
                    contratacao.prestador_id,
                    contratacao.status.value,
                    contratacao.criado_em.isoformat(),
                ),
            )

            if contratacao.avaliacao is not None:
                aval = contratacao.avaliacao
                self.conn.execute(
                    """
                    INSERT INTO avaliacoes (id, contratacao_id, nota, comentario, criado_em)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        nota = excluded.nota,
                        comentario = excluded.comentario,
                        criado_em = excluded.criado_em;
                    """,
                    (
                        aval.id,
                        aval.contratacao_id,
                        int(aval.nota),
                        aval.comentario,
                        aval.criado_em.isoformat(),
                    ),
                )

    def buscar_por_id(self, contratacao_id: str) -> Optional[Contratacao]:
        cursor = self.conn.execute(
            """
            SELECT id, servico_id, slot_id, solicitante_id, prestador_id, status, criado_em
            FROM contratacoes
            WHERE id = ?;
            """,
            (contratacao_id,),
        )
        row = cursor.fetchone()
        if row is None:
            return None

        return self._reconstruir_contratacao(row)

    def listar_por_usuario(self, usuario_id: str) -> List[Contratacao]:
        cursor = self.conn.execute(
            """
            SELECT id, servico_id, slot_id, solicitante_id, prestador_id, status, criado_em
            FROM contratacoes
            WHERE solicitante_id = ? OR prestador_id = ?
            ORDER BY criado_em;
            """,
            (usuario_id, usuario_id),
        )
        return [self._reconstruir_contratacao(row) for row in cursor.fetchall()]

    def _reconstruir_contratacao(self, row: sqlite3.Row) -> Contratacao:
        cursor_aval = self.conn.execute(
            """
            SELECT id, contratacao_id, nota, comentario, criado_em
            FROM avaliacoes
            WHERE contratacao_id = ?;
            """,
            (row["id"],),
        )
        aval_row = cursor_aval.fetchone()
        avaliacao = None
        if aval_row is not None:
            avaliacao = Avaliacao(
                id=aval_row["id"],
                contratacao_id=aval_row["contratacao_id"],
                nota=int(aval_row["nota"]),
                comentario=aval_row["comentario"],
                criado_em=datetime.fromisoformat(aval_row["criado_em"]),
            )

        return Contratacao(
            id=row["id"],
            servico_id=row["servico_id"],
            slot_id=row["slot_id"],
            solicitante_id=row["solicitante_id"],
            prestador_id=row["prestador_id"],
            status=StatusContratacao(row["status"]),
            criado_em=datetime.fromisoformat(row["criado_em"]),
            avaliacao=avaliacao,
        )
