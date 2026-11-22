class ErroDominio(Exception):
    # excecao base
    def __init__(self, mensagem: str):
        super().__init__(mensagem)
        self.mensagem = mensagem


class AutoContratacaoError(ErroDominio):
    def __init__(self):
        super().__init__("Prestador não pode contratar o próprio serviço")


class SlotIndisponivelError(ErroDominio):
    def __init__(self):
        super().__init__("Horário selecionado já está reservado")


class TransicaoEstadoInvalidaError(ErroDominio):
    def __init__(self, detalhe: str):
        super().__init__(f"Transição de estado inválida: {detalhe}")


class NotaInvalidaError(ErroDominio):
    def __init__(self):
        super().__init__("A nota deve ser entre 1 e 5 e o comentário não pode ser vazio.")


class PermissaoNegadaError(ErroDominio):
    def __init__(self, detalhe: str):
        super().__init__(f"Permissão negada no domínio: {detalhe}")


class IntervaloHorarioInvalidoError(ErroDominio):
    def __init__(self):
        super().__init__("O horário de término do slot deve ser posterior ao horário de início.")
