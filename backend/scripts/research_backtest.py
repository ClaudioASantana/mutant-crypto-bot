#!/usr/bin/env python3
"""Aviso de descontinuação do harness legado `research_backtest.py`.

Este script ainda representa uma trilha antiga de pesquisa, apesar de parte dos
imports já apontarem para módulos vigentes. O problema não é só import path:

- ele implementa um motor de backtest próprio, paralelo ao stack atual;
- recalcula lifecycle, fees, trailing e R-multiple fora de `PaperTrader` /
  `BacktestSimulatorImpl`;
- mantém um contrato de pesquisa isolado, difícil de comparar com os resultados
  dos harnesses modernos do projeto.

Substitutos atuais mais alinhados com a arquitetura vigente:

- `scripts/benchmark_all.py`
- `scripts/deep_backtest.py`
- `scripts/optimizer.py`
- `scripts/analyze_strategies_30d.py`

Se a pesquisa destas estratégias candidatas precisar continuar, o ideal é
migrá-las para um harness novo apoiado nos componentes canônicos de backtest,
em vez de manter este motor paralelo.
"""

from __future__ import annotations


def main() -> int:
    print("Este script legado foi descontinuado.")
    print("Use os harnesses atuais de benchmark/backtest da arquitetura vigente.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
