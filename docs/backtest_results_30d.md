# 🧬 Relatório Estatístico e Decisões de Engenharia
## Testes Quantitativos de 30 Dias (BTC/USDT)

Este documento registra os resultados dos backtests realizados em dados históricos de 30 dias do par **BTC/USDT** (Binance Futures), detalhando o impacto dos filtros de assertividade e a introdução da lógica de reteste baseada no método de Wyckoff.

---

## 1. Backtest Original (Sem Filtros)
*Realizado na banca simulada de $200.00 com margem fixa de $10.00 (Sem RSI, EMA 200, Volume ou Filtro de MTF).*

| Timeframe | Estratégia | Sinais Gerados | Win Rate (WR) | PnL Acumulado (USD) |
|-----------|------------|----------------|---------------|---------------------|
| **M1**    | Bollinger  | 4.523          | 37.52%        | +$169.97            |
| **M5**    | SMC        | 1.021          | 34.97%        | +$41.92             |
| **M5**    | EMA+MACD   | 363            | 33.88%        | +$14.26             |

* **Diagnóstico:** O robô gerava um volume massivo de sinais (especialmente no M1), mas sofria com muitos falsos rompimentos. O lucro líquido vinha do fator Risco 1:2 com ATR dinâmico, mas o Win Rate flutuava próximo a zona limite de rentabilidade.

---

## 2. Backtest Filtrado (Com Filtros de Qualidade + MTF)
*Com a adição das Fases 1 e 2: Filtro RSI, Volume/Amplitude, Tendência macro (EMA 200) e Multi-Timeframe Confirmation (MACD M5/M15).*

| Timeframe | Estratégia | Sinais Gerados | Win Rate (WR) | PnL Acumulado (USD) |
|-----------|------------|----------------|---------------|---------------------|
| **M5**    | **SMC**    | **355**        | **38.31%**    | **+$61.94**         |
| **M5**    | **EMA+MACD**| **127**       | **43.31%**    | **+$57.39**         |
| **M1**    | Bollinger  | 895            | 35.75%        | +$51.00             |
| **M5**    | Bollinger  | 346            | 38.15%        | +$34.74             |

### Principais Conclusões dos Filtros:
1. **Otimização de Assertividade (Win Rate):** O Win Rate do *EMA+MACD M5* disparou de **33.88% para 43.31%** (+9.43% de precisão). O *SMC M5* subiu de **34.97% para 38.31%**.
2. **Redução de Ruído no M1:** No Bollinger M1, o volume de sinais despencou de 4.523 para 895, filtrando falsas entradas, embora o ganho bruto no M1 tenha sido menor do que a soma das eficiências de M5.
3. **Decisão Técnica:** O robô foi reconfigurado para usar o **M5** como timeframe padrão e o **SMC** como estratégia principal no modo Mutante Global.

---

## 3. Testes da Lógica de Reteste Wyckoff
*Implementação baseada no método de Richard Wyckoff: o bot aguarda o preço romper a estrutura e voltar para retestar a banda/canal antes de acionar o trade.*

| Timeframe | Estratégia | Sinais Gerados | Win Rate (WR) | PnL Acumulado (USD) |
|-----------|------------|----------------|---------------|---------------------|
| **M5**    | Wyckoff SMC| 143            | 38.46%        | +$21.05             |
| **M15**   | Wyckoff SMC| 30             | 36.67%        | +$28.85             |
| **M15**   | Wyckoff Bollinger| 55       | 40.00%        | +$28.26             |
| **M5**    | Wyckoff Bollinger| 141       | 36.88%        | +$1.00              |

### Principais Conclusões do Reteste Wyckoff:
1. **Timeframes Maiores:** Confirmando a literatura do método Wyckoff, a lógica de reteste obteve excelente performance no **M15** (onde o Bollinger com Reteste Wyckoff alcançou **40% de Win Rate**).
2. **Frequência vs Lucro total no M5:** No M5, a estratégia Wyckoff SMC reduziu os trades em mais de 60% em relação ao SMC clássico (143 vs 355), gerando um PnL menor (+$21.05 vs +$61.94), mesmo com assertividade equivalente.
3. **Decisão Técnica:** A estratégia clássica com filtros de qualidade foi mantida como ativa no robô automatizado para garantir capitalização contínua do PnL, mas a lógica de Wyckoff foi integrada ao código-fonte de análise técnica como alternativa robusta para operação em tempos gráficos maiores.

---

## 4. Estrutura do Risco
* **Gestão:** Risco 1:2 Dinâmico
* **Stop Loss (SL):** 1.5x ATR (volatilidade média de 14 períodos)
* **Take Profit (TP):** 3.0x ATR
* **Banca Inicial Simulada:** $200.00
* **Margem por Trade:** $10.00 (Alavancagem 10x)
* **Stop Diário Automático:** -$20.00 (Pausa as operações se perder 10% da banca no dia)
