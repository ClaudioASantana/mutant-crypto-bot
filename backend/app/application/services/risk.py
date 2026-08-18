"""
Re-exporta evaluate_risk do domínio para manter compatibilidade com imports antigos.

A lógica real vive em app.domain.services.risk_service — este módulo
existe apenas como alias de transição.
"""
from app.domain.services.risk_service import evaluate_risk  # noqa: F401
