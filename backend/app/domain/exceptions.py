"""
Exceções puras de Domínio (Domain Exceptions).
Representam violações de regras de negócio independente da infraestrutura.
"""

class DomainException(Exception):
    """Exceção base do Domínio."""
    pass

class RiskLimitExceededException(DomainException):
    """Lançada quando uma operação viola os limites de risco (ex: perda diária máxima)."""
    pass

class InvalidSignalException(DomainException):
    """Lançada quando um sinal de trade for considerado inválido pelo domínio."""
    pass

class TradeExecutionException(DomainException):
    """Lançada quando ocorre um erro lógico na execução de um trade."""
    pass
