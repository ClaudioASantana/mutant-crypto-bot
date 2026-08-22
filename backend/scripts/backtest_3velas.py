#!/usr/bin/env python3
"""Aviso de descontinuação do comparativo legado `backtest_3velas.py`.

Este script era um comparativo ad-hoc da estratégia "3 Velas" contra outras
estratégias antigas, mas dependia de namespaces removidos:

- `app.models.market`
- `app.engines.cataloger`
- `app.engines.technical_analysis`

Além disso, ele já foi superado por harnesses mais novos que usam os módulos
vigentes do projeto e conseguem produzir comparações mais confiáveis.

Substitutos recomendados:

- `scripts/benchmark_all.py`
- `scripts/analyze_strategies_30d.py`
- `scripts/deep_backtest.py`
- `app/application/services/cataloger.py`

Se a comparação específica da estratégia "3 Velas" ainda for desejada, o ideal
é reintroduzi-la em um harness atual, em vez de manter este script legado.
"""

from __future__ import annotations


def main() -> int:
    print("Este script legado foi descontinuado.")
    print("Use os harnesses atuais para comparar estratégias, incluindo 3 Velas.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
