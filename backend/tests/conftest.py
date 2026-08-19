"""
Configuração global dos testes.

Importa módulos que têm efeitos colaterais de registro (como o
technical_analysis, que registra as estratégias no StrategyRegistry).
"""

# Garante que todas as estratégias reais sejam registradas antes dos testes
import app.application.services.technical_analysis  # noqa: F401