#!/usr/bin/env python3
"""Aviso de descontinuação do script legado de varredura TP x SL.

Este script de pesquisa dependia de peças já aposentadas:

- `app.engines.technical_analysis`
- `scripts.backtester.download_history`

Além dos imports quebrados, sua lógica (simulação própria de SL/TP com loops
sobre candles e fees simplificadas) foi substituída pelos harnesses que usam
o lifecycle real do `PaperTrader` com `RiskManager`.

Para estudos de relações de risco:retorno, use as trilhas atuais:

- `scripts/optimizer.py`
- `scripts/fine_tune_*` / `scripts/tune_risk_parameters.py`
- `scripts/benchmark_all.py`
- `scripts/analyze_strategies_30d.py`

Se for necessário retomar a varredura de multiplicadores TP x SL, o ideal é
instrumentar `RiskManager`/`PaperTrader` nos harnesses atuais em vez de manter
este script legado funcional.
"""

from __future__ import annotations


def main() -> int:
    print("Este script legado foi descontinuado.")
    print("Use os harnesses atuais de research/backtest para estudos de TP/SL.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())