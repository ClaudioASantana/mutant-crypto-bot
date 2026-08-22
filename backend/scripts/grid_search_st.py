#!/usr/bin/env python3
"""Aviso de descontinuação do script legado de grid search de SuperTrend.

Este arquivo dependia de imports de uma estrutura antiga que não existe mais,
incluindo:

- `backend.app.services.binance_client`
- `backend.app.engines.technical_analysis`

O projeto já possui trilhas mais atuais para research/backtest, como:

- `scripts/deep_backtest.py`
- `scripts/benchmark_all.py`
- `scripts/optimizer.py`
- `scripts/analyze_strategies_30d.py`

Se for necessário retomar uma busca de hiperparâmetros para SuperTrend, o ideal
é reimplementar este estudo sobre os módulos vigentes em
`app/application/services/technical_analysis.py` e os harnesses modernos de
backtest/research, em vez de tentar manter este script legado funcional.
"""

from __future__ import annotations


def main() -> int:
    print("Este script legado foi descontinuado.")
    print("Use os harnesses atuais de research/backtest para novos estudos.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
