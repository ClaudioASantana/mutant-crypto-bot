#!/usr/bin/env python3
"""Aviso de descontinuação — teste legado de calibração do cataloger.

Este arquivo vivia solto na raiz do pacote como script de depuração e
dependia de namespaces que não existem mais no runtime atual:

- `app.services.binance_client`
- `app.engines.bot_instance` (`BotInstance` foi removido do projeto)
- `app.engines.cataloger`

Ele não faz parte da suíte oficial de testes (que vive em `backend/tests/`).

Referências atuais para o que ele tentava validar:

- `calculate_win_rate` → `app/application/services/cataloger.py`
- `BinanceClient` → `app/infrastructure/market_data/binance_client.py`
- dados de mercado/fetch → harnesses em `scripts/` (ex.: `optimizer.py`,
  `benchmark_all.py`)
"""

from __future__ import annotations


def main() -> int:
    print("Script legado descontinuado.")
    print("Use `backend/tests/` e os módulos vigentes listados no cabeçalho.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())