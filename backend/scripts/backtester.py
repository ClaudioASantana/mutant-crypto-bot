#!/usr/bin/env python3
"""Aviso de descontinuação do `backtester` legado.

Este arquivo foi o backtest de primeira geração do bot e dependia de módulos
que não existem mais no runtime atual:

- `app.models.market`
- `app.engines.indicators`
- `app.engines.cataloger`

Além dos imports quebrados, o desenho do harness está defasado:

- simulava "2 velas/3 velas consecutivas" com closure trivial no fechamento;
- referia-se a trailing stop / gale, lógica já deprecada no projeto;
- usava `calculate_win_rate` do namespace antigo, com contrato divergente do
  atual em `app/application/services/cataloger.py`.

Para os mesmos objetivos — download de histórico, backtest por estratégia e
métricas de win rate — use os harnesses vigentes:

- download com cache local em `market_history.db`:
  `scripts/optimizer.py` (`download_history`)
- backtest com lifecycle real e risk manager:
  `scripts/benchmark_all.py` (via `BacktestSimulatorImpl` + `PaperTrader`)
- deep backtest multi-timeframe:
  `scripts/deep_backtest.py`
- comparação consolidada de estratégias:
  `scripts/analyze_strategies_30d.py`
"""

from __future__ import annotations


def main() -> int:
    print("Este script legado foi descontinuado.")
    print("Use os harnesses atuais de research/backtest listados no cabeçalho.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())