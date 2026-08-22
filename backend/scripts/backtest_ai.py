#!/usr/bin/env python3
"""Aviso de descontinuação do backtest legado do AIFilter.

Este script ficou incompatível com a arquitetura atual por depender de peças
legadas ou já aposentadas:

- `app.engines.technical_analysis`
- `app.engines.ai_filter`
- `scripts.backtester.download_history`

Além dos imports quebrados, ele misturava várias responsabilidades em um único
arquivo:

- coleta assíncrona de decisões de IA com cache em JSON;
- aplicação offline de filtros técnicos/padrões;
- simulação própria de SL/TP e time-stop;
- dependência indireta de um downloader legado já aposentado.

A trilha atual recomendada é separar essas preocupações sobre os módulos
vigentes do projeto:

- histórico/cache local: `scripts/optimizer.py`
- harnesses de benchmark/backtest: `scripts/benchmark_all.py`
  e `scripts/deep_backtest.py`
- indicadores atuais: `app/application/services/technical_analysis.py`
- lifecycle/simulação compatível com o runtime: `PaperTrader` +
  `BacktestSimulatorImpl`

Se for necessário retomar um estudo específico de IA offline, o ideal é criar
um novo harness em cima desses módulos atuais, em vez de manter este script
legado funcional.
"""

from __future__ import annotations


def main() -> int:
    print("Este script legado foi descontinuado.")
    print("Use os harnesses atuais de research/backtest e os módulos vigentes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
