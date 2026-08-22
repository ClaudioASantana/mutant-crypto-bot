#!/usr/bin/env python3
"""Aviso de descontinuação do script legado de simulação 24h.

Este arquivo dependia do namespace antigo `app.engines.*` (`simulator`,
`ai_filter`, `candle_builder`, `technical_analysis`), que não existe mais no
runtime atual.

Além disso, ele pressupunha contratos legados que deixaram de ser verdade após
as rodadas de hardening e unificação de persistência:

- `PaperTrader` em um módulo legado fora da arquitetura atual;
- estado mutável direto em atributos como `history_trades` e `open_positions`;
- fluxo de backtest/simulação acoplado a imports antigos e não versionados.

Use em vez deste script:

- os backtests/research scripts que já apontam para os módulos vigentes;
- os testes de integração em `backend/tests/` para validar persistência e
  lifecycle canônico;
- `docs/guides/cutover_persistencia_canonica_sqlite.md` para o procedimento
  operacional de storage canônico.
"""

from __future__ import annotations


def main() -> int:
    print("Este script legado foi descontinuado.")
    print("Ele dependia de `app.engines.*`, namespace removido do runtime atual.")
    print("Use os testes/backtests compatíveis com a arquitetura vigente.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
