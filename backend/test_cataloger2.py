#!/usr/bin/env python3
"""Aviso de descontinuação — segundo teste legado de cataloger.

Este arquivo era um script ad-hoc fora da suíte principal e dependia de
componentes removidos, especialmente `BotInstance` e `app.engines.cataloger`.

Ele foi preservado apenas como aviso explícito para evitar que alguém tente
executá-lo assumindo que ainda valida o runtime atual.

Para validação real, use:

- testes versionados em `backend/tests/`
- `app/application/services/cataloger.py`
- harnesses modernos de backtest/research em `backend/scripts/`
"""

from __future__ import annotations


def main() -> int:
    print("Script legado descontinuado.")
    print("Use a suíte oficial em `backend/tests/`.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())