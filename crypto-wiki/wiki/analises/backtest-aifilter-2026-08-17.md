---
title: "Análise Quantitativa: AIFilter (Prompt EMA200) - BTC/USDT M15"
source: "backtest_ai.py"
created: 2026-08-17
tags:
  - backtest
  - ai-filter
  - ema200
  - btc
---

# Análise: AIFilter com Filtro de Tendência EMA200

Esta análise documenta a performance do novo motor de decisão por IA, equipado com o filtro rígido de tendência EMA200.

## Dados do Backtest
- **Ativo:** BTC/USDT
- **Timeframe:** M15
- **Janela:** 300 velas (~75 horas)
- **Configuração:** SL 1.5 ATR / TP 3.0 ATR
- **Taxas:** 0.1% por lado (0.2% total)
- **Decisões coletadas:** 269 (avaliação em 69 velas após contexto mínimo)

## Resultados (Confiança >= 0.70)
- **Sinais:** 72
- **Wins:** 26
- **Losses:** 46
- **Win Rate:** 36.11%
- **PnL Líquido:** -$73.24

## Conclusões
A IA mostrou-se muito seletiva, mas o PnL final foi negativo. A taxa de acerto (36%) está acima do ponto de *break-even* para a relação Risco:Retorno de 1:2 (que seria ~33%), porém o custo das taxas em velas de baixa volatilidade está consumindo o lucro dos trades vencedores.

## Lições Aprendidas
1. O filtro de tendência (EMA200) reduz drasticamente o *overtrading*.
2. É necessário filtrar sinais onde o ATR é muito pequeno, para evitar trades cujas taxas superam o alvo de lucro.
3. A IA ainda precisa ser mais precisa em mercados laterais.
4. Respostas vazias do modelo (`mimo-v2.5-pro`) sob carga: mitigadas com retry e `max_tokens=1024`.

---

[[index]]