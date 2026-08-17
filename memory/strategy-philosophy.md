---
name: strategy-philosophy
description: "A estratégia de 3 candles no mutant-crypto-bot deve ser operada com confluência (contexto), nunca isolada."
metadata:
  type: project
---
A estratégia de 3 candles no [[mutant-crypto-bot]] evoluiu de uma detecção puramente estrutural para uma abordagem baseada em contexto e confluência, seguindo a wiki [[3-candle-pattern-wiki]].

**Why:** Sinais isolados de padrões de velas (como *Three White Soldiers*, *Three Black Crows* ou *3 Bar Play*) em gráficos de 5 minutos geram ruído excessivo em ativos cripto. A wiki e os backtests mostram que operar padrões de 3 velas isoladamente produz overtrading e PnL negativo.

**How to apply:**
1. **Confluência de Suporte/Resistência:** O sinal só é válido se ocorrer próximo a zonas estruturais (Bandas de Bollinger, Canais de Donchian, EMAs 20/50). O nível estrutural fornece o *motivo*, o padrão fornece o *timing*.
2. **Filtro de Momentum:** RSI em exaustão (sobrevendido para reversão de alta, sobrecomprado para reversão de baixa) e MACD favorável (cruzamento/histograma) para continuações.
3. **Volume Institucional:** Pico de volume na terceira vela de confirmação (> 1.0x a média de 20 períodos, idealmente > 1.5x). Preço avançando com volume caindo = fakeout.
4. **Alinhamento MTF:** Sinal em tempo gráfico menor (ex: M1/M5) alinhado com a tendência das EMAs (9/20/21/50) do tempo gráfico maior (M15/H4).
5. **Break-and-Retest:** Após a 3ª vela romper uma resistência, aguardar o reteste do nível antes da entrada para evitar armadilhas de liquidez.
6. **Alvos com Fibonacci:** Projetar a amplitude da vela de ignição com razões de Fibonacci (100%, 161.8%, 200%) para definir take-profit.

O filtro de volume + EMA20 já está implementado em `backend/app/engines/technical_analysis.py`.
