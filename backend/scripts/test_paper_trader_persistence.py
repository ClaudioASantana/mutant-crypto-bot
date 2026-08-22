#!/usr/bin/env python3
"""Aviso de descontinuação do script legado de persistência.

Este arquivo existia para validar o antigo caminho de persistência baseado em
JSON do PaperTrader. Após a unificação canônica em SQLite/SQLAlchemy:

- o runtime principal não usa mais JSON como storage default;
- `history_trades` / `open_positions` não vivem mais dentro do snapshot salvo;
- o teste real dessa trilha passou a morar em testes de integração versionados.

Use em vez deste script:

- `venv/bin/python -m pytest tests/integration/scripts/test_migrate_legacy_paper_trader_data.py -q`
- `venv/bin/python -m pytest tests/integration/infrastructure/test_sqlalchemy_trade_repository.py -q`
- `venv/bin/python -m pytest tests/integration/infrastructure/test_sqlalchemy_paper_trader_state_repository.py -q`

Para o procedimento operacional de cutover, consulte:

- `docs/guides/cutover_persistencia_canonica_sqlite.md`
"""

from __future__ import annotations


def main() -> int:
    print("Este script foi descontinuado.")
    print("Use os testes de integração e o guia de cutover documentados no cabeçalho.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
