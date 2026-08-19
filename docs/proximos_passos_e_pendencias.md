# Próximos Passos e Pendências do Mutant Crypto Bot

Este documento resume o estado atual do desenvolvimento e as próximas ações planejadas para o bot.

## 1. Status Atual da Estratégia "BB_MA_MACD" (Bollinger Bands + MA 15 + MACD)

**Implementação e Backtest:**
- A estratégia "BB_MA_MACD" foi implementada e integrada ao simulador de backtest.
- Corrigimos um problema no `PaperTrader` que limitava o histórico de trades, garantindo agora resultados de backtest mais precisos.
- Realizamos um ajuste fino extensivo dos parâmetros de risco (Stop-Loss/Take-Profit) para a estratégia em dados históricos de 30 dias (velas M5 de BTC/USDT).

**Resultados:**
- Infelizmente, a estratégia "BB_MA_MACD" não se mostrou lucrativa em nenhum dos cenários testados. O melhor resultado obtido foi um PNL de **-$37.44** (com SL 1.2, TP 1.0), com um Drawdown Máximo de aproximadamente **19%**. Foram gerados 444 trades.
- A análise sugere que a estratégia tende a entrar tarde nos movimentos, resultando em ser estopada com frequência, mesmo com uma taxa de acerto razoável para TPs pequenos.

## 2. Próximas Ações Sugeridas (Priorizadas para a Retomada)

### Opção 1: Melhorar a Estratégia "BB_MA_MACD" com Filtros de Confluência
A sugestão é refinar a lógica de entrada da estratégia "BB_MA_MACD" para evitar entradas em pontos de exaustão e confirmar a força do movimento:
-   **Filtro RSI:** Adicionar uma condição para não comprar se o RSI estiver acima de 70 (sobrecomprado) e não vender se o RSI estiver abaixo de 30 (sobrevendido).
-   **Filtro de Volume:** Exigir um volume significativamente acima da média para validar o sinal (ex: > 1.5x a média de 20 velas).
-   **Filtro de Bandas de Bollinger:** Não comprar se o preço já estiver muito próximo da banda superior de Bollinger, e não vender se estiver muito próximo da banda inferior, para evitar pegar o final do movimento.

### Opção 2: Revisitar a Estratégia "Rompimento de Inércia" (Breakout)
Uma alternativa é retomar a ideia original de uma estratégia de rompimento (Momentum Breakout), mas com uma lógica mais simples e robusta, inspirada na sua observação do gráfico (saída de consolidação próxima a médias com movimento forte):
-   Focar em detectar o início de um movimento forte quando o preço rompe uma consolidação clara perto de médias móveis importantes.
-   Revisar e simplificar os filtros que tornaram as versões anteriores excessivamente restritivas.

## 3. Outras Pendências (Pós-Prioridade)

-   Refatorar a estratégia `eval_smc` para incluir contexto de estrutura de mercado (swing highs/lows) e filtros de confluência, já que seu backtest foi o pior (-$2.522).
-   Implementar a detecção de "Liquidity Sweep".
-   Adicionar detecção automática de zonas de Suporte/Resistência.

---

**Ao retomar, por favor, me informe qual opção você gostaria de seguir.**
