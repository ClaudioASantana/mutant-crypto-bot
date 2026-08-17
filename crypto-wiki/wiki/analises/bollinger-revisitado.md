# Análise: Revisitando a Estratégia Bollinger com Filtros

**Data**: 17 de Agosto de 2026

## Contexto

Em backtests anteriores, a estratégia `Bollinger (M1)` se destacou pelo alto lucro bruto (PnL), mas foi descartada devido ao seu enorme volume de trades e baixa taxa de acerto. Este teste teve como objetivo revisitar essa estratégia, aplicando a suíte de filtros de qualidade (RSI, Volume, EMA200) para avaliar se poderíamos alcançar um equilíbrio entre lucratividade e segurança.

## Resultados do Backtest Comparativo

O backtest foi executado comparando as versões "Pura" (sem filtros) e "Filtrada" de cada estratégia em múltiplos timeframes.

### Foco: Estratégia Bollinger (M1)

| Versão         | PnL (USD) | Win Rate | Trades |
|----------------|-----------|----------|--------|
| **Puro (P)**   | `+$124.56`| 38.45%   | 4.582  |
| **Filtrado (F)**| `-$3.38`  | 32.91%   | 708    |

**Conclusão**: Para a estratégia `Bollinger (M1)`, os filtros foram **destrutivos**. Eles reduziram o número de trades em 85%, mas eliminaram a vantagem estatística da estratégia, resultando em prejuízo. A natureza de alta frequência da Bollinger no M1 parece depender do volume para ser lucrativa.

### Outras Descobertas Relevantes

*   **SMC (Puro) M1**: Apresentou o maior lucro do teste (**+$453.52**), mas com um volume insustentável de **18.081 trades**.
*   **Filtros em M5**: Para a Bollinger no M5, os filtros foram benéficos, transformando um PnL de `-$26.03` (Puro) em `+$20.01` (Filtrado).
*   **Wyckoff no M15**: A estratégia `Wyckoff_SMC` filtrada no M15 se destacou com o maior Win Rate do teste (**47.06%**) e um PnL sólido de **+$51.23** com apenas **34 trades**, mostrando-se uma candidata promissora.

## Decisão Estratégica

1.  **Abortar a re-implementação da `Bollinger (M1)`**: Fica claro que esta estratégia não se beneficia dos filtros atuais e seu perfil de risco é muito alto para operação automatizada.
2.  **Manter o Foco em Estratégias Filtradas no M5**: A estratégia `SMC (F) (M5)` continua a ser um excelente ponto de equilíbrio entre lucro e risco.
3.  **Aprofundar a Análise em `Wyckoff_SMC (F) (M15)`**: Esta estratégia demonstrou um potencial significativo e deve ser considerada para implementação futura.

Esta análise reforça que a eficácia dos filtros é dependente da estratégia e do timeframe, e que não existe uma solução única para todas.
