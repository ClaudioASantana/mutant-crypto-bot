"""
Registro centralizado para estratégias de trading.
Permite o registro dinâmico de novas estratégias utilizando decorators.
"""
from typing import Callable, Dict, Any
import logging

logger = logging.getLogger(__name__)

class StrategyRegistry:
    _strategies: Dict[str, Callable] = {}

    @classmethod
    def register(cls, name: str):
        """Decorator para registrar uma função de estratégia."""
        def decorator(func: Callable):
            cls._strategies[name] = func
            logger.info(f"Estratégia '{name}' registrada com sucesso.")
            return func
        return decorator

    @classmethod
    def get(cls, name: str) -> Callable:
        """Recupera uma estratégia registrada pelo nome."""
        return cls._strategies.get(name)

    @classmethod
    def list_all(cls) -> Dict[str, Callable]:
        """Retorna todas as estratégias registradas."""
        return cls._strategies

# Alias para facilitar o uso (syntactic sugar)
register_strategy = StrategyRegistry.register
