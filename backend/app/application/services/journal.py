"""Shim legado do TradeJournal.

O journal separado em `journal.db` foi absorvido pela tabela canônica `trades`.
Este módulo permanece apenas para preservar imports transitórios durante a
transição e falha de forma explícita se algum caminho antigo ainda tentar usá-lo.
"""


class TradeJournal:
    def __init__(self, *args, **kwargs):
        _ = (args, kwargs)
        raise RuntimeError(
            "TradeJournal legado foi descontinuado. "
            "Use a persistência canônica na tabela `trades` via PaperTrader/TradeRepository."
        )

    def log_entry(self, *args, **kwargs):
        _ = (args, kwargs)
        raise RuntimeError("TradeJournal legado foi descontinuado")

    def log_exit(self, *args, **kwargs):
        _ = (args, kwargs)
        raise RuntimeError("TradeJournal legado foi descontinuado")
