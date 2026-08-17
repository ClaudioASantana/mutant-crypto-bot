---
title: "Análise Quantitativa: AIFilter + Filtro Positivo (Padrão 3 Velas) - BTC/USDT M15"
source: "backtest_ai.py"
created: 2026-08-17
tags:
  - backtest
  - ai-filter
  - confluencia
  - 3-velas
  - btc
  - resultados-positivos
---

# Análise: AIFilter com Filtro Positivo (Padrão 3 Velas)

Esta análise documenta a performance do motor de decisão por IA (AIFilter) integrada a um filtro positivo técnico de 3 velas.

## Resultados Chave
- **Ativo:** BTC/USDT
- **Timeframe:** M15
- **Estratégia:** Confiança IA >= 0.70 + Confluência Padrão 3 Velas
- **SL 1.5x / TP 8.0x:** WR 38.46% / PnL +$3.58

## Diagnóstico
O backtest demonstrou que a confluência IA + Padrão 3 Velas (3 Bar Play, Soldiers, Crows, Stars) é viável, porém exige um TP agressivo (8x ATR) devido ao custo das taxas (0.1%/lado). Com esse setup, o breakeven exigido cai para 24%, permitindo lucratividade.

## Próximos Passos
1. Atualizar o `bot_instance.py` para incorporar o filtro de padrão de 3 velas.
2. Monitorar performance em tempo real com SL 1.5 / TP 8.0.

---
[[index]]
