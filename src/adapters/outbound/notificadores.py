from typing import Dict, List

from src.ports.interfaces import NotificadorPort


class EmailNotificador(NotificadorPort):
    """Adaptador secundário de produção para envio de notificações via SMTP institucional (ASR-01)."""

    def __init__(self, servidor_smtp: str = "smtp.ufpr.br", exibir_log: bool = True):
        self.servidor_smtp = servidor_smtp
        self.exibir_log = exibir_log

    def notificar(self, destinatario: str, assunto: str, mensagem: str) -> None:
        if self.exibir_log:
            print(
                f"[SMTP:{self.servidor_smtp}] Para: {destinatario} | "
                f"Assunto: {assunto} | Mensagem: {mensagem}"
            )


class NotificadorFake(NotificadorPort):
    """Adaptador secundário de teste (Test Double / Spy) em memória para validação determinística (ASR-01 / ASR-03)."""

    def __init__(self):
        self.mensagens_enviadas: List[Dict[str, str]] = []

    def notificar(self, destinatario: str, assunto: str, mensagem: str) -> None:
        self.mensagens_enviadas.append(
            {
                "destinatario": destinatario,
                "assunto": assunto,
                "mensagem": mensagem,
            }
        )
