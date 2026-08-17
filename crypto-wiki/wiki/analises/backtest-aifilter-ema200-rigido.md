---
title: "Análise Quantitativa: AIFilter (Prompt EMA200 Rígido) - BTC/USDT M15"
source: "backtest_ai.py"
created: 2026-08-17
tags:
  - backtest
  - ai-filter
  - ema200
  - btc
  - resultados-negativos
---

# Análise: AIFilter com Filtro de Tendência EMA200 (Prompt Rígido)

Esta análise documenta a performance do motor de decisão por IA após a implementação da regra rígida de tendência EMA200.

## Dados do Backtest
- **Ativo:** BTC/USDT
- **Timeframe:** M15
- **Janela:** 300 velas (~75 horas)
- **Configuração:** SL 1.5 ATR / TP 3.0 ATR
- **Taxas:** 0.1% por lado
- **Execução:** Limpa (sem cache viciado)

## Resultados (Confiança >= 0.70)
- **Sinais:** 8
- **Wins:** 2
- **Losses:** 6
- **Win Rate:** 25.00%
- **PnL Líquido:** -$10.61

## Conclusões
1. **Redução extrema de sinais:** O filtro de tendência reduziu os sinais de 72 para 8, confirmando a alta seletividade.
2. **Degradação de Performance:** O WR caiu de 36.11% para 25.00%.
3. **Diagnóstico:** O modelo está "comprando" correções fracas ou "vendendo" exaustões que falham rapidamente contra a tendência, mesmo dentro da regra da EMA200. A IA está sendo conservadora no volume, mas imprecisa na execução dos sinais filtrados.

## Lições Aprendidas
- A regra rígida EMA200 sozinha não basta. O motor precisa integrar filtros técnicos de confluência (conforme [[strategy-philosophy]]) no `AIFilter` para validar o sinal (ex: RSI + Volume) antes da entrada.

---
[[index]]
