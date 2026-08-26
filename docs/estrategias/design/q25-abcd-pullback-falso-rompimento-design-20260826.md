# Q25 — ABCD pullback com falso rompimento

## Origem

Análise derivada da transcrição do vídeo **"Como fazer Day Trade em Cripto (Estratégia Simples e Lucrativa)"**, do canal **Fabrício Lorenz - Trader e Investidor**.

## Resumo executivo

A estratégia apresentada no vídeo é uma estratégia de **continuação de tendência por pullback/correção complexa**, combinando:

- tendência/inércia a favor
- padrão harmônico **ABCD**
- **falso rompimento / manipulação**
- gatilho por **candle de força**
- **média móvel de 21 períodos** como filtro
- **timeframe principal de 15 minutos**
- foco em horários de maior **liquidez/volume**

Nome técnico sugerido:

- **ABCD pullback com falso rompimento a favor da tendência**
- ou **continuação de tendência após correção ABCD com sweep do fundo/topo anterior**

---

## Componentes centrais da estratégia

### 1. Contexto primeiro

O vídeo enfatiza que o setup depende de contexto favorável, não de entradas aleatórias.

Critérios destacados:

- operar em horários de maior volume
  - aproximadamente **10h**: sobreposição Europa + EUA
  - aproximadamente **21h**: abertura Ásia
- evitar ativos sem liquidez
- priorizar movimentos mais limpos e previsíveis

Conclusão: **não é um setup para qualquer horário**.

### 2. Timeframe preferido

O prazo operacional defendido no vídeo é:

- **gráfico de 15 minutos**

A argumentação é que timeframes muito curtos, como 1m, 2m e 5m, tendem a ser mais erráticos e menos confiáveis.

### 3. Viés direcional: operar com a inércia

A base do racional é operar a favor da direção dominante:

- em **tendência de alta**, procurar **compras**
- em **tendência de baixa**, procurar **vendas**

A ideia central é evitar operar contra a inércia do mercado. O trader deve buscar correções dentro de uma tendência, e não tentar antecipar topos e fundos.

### 4. Padrão principal: ABCD

O vídeo chama o setup de **estratégia N**, mas a estrutura técnica descrita é a de um **padrão harmônico ABCD**.

Em tendência de alta, a leitura proposta é:

- **A → B**: primeira perna de queda
- **B → C**: respiro/reação
- **C → D**: segunda perna de queda
- condição importante: **AB ≈ CD**

Quando as duas pernas corretivas têm amplitudes semelhantes, o movimento é interpretado como **correção complexa**, e não necessariamente como reversão.

### 5. Verdadeira vantagem do setup: falso rompimento em D

O gatilho principal não é apenas a conclusão geométrica do ABCD.

O vídeo procura o seguinte comportamento em **D**:

- o mercado está em tendência de alta
- a correção forma um ABCD
- a segunda perna pode **perder o fundo anterior**
- logo depois aparece uma reação forte
- o preço rompe a máxima do candle que sinalizou a rejeição da queda

Isso caracteriza:

- **falso rompimento de fundo**
- **varrida de liquidez (sweep)**
- **bear trap / spring**
- retomada da tendência principal

Assim, a entrada não acontece apenas porque o preço “chegou no ponto D”, mas porque o ponto D **falha como reversão** e se converte em armadilha para participantes contra a tendência.

---

## Regras operacionais descritas no vídeo

### Setup de compra

1. Identificar **tendência de alta**
   - topos e fundos ascendentes
   - média móvel de 21 períodos ainda apontando para cima

2. Esperar uma **correção complexa**
   - duas pernas contra a tendência
   - padrão **ABCD**

3. Verificar se:
   - **AB ≈ CD**
   - a segunda perna pode inclusive **violar o fundo anterior**

4. Esperar o **candle de força comprador**
   - candle que rejeita a continuação da queda
   - frustra a tentativa de rompimento baixista
   - sinaliza retomada compradora

5. **Entrada**
   - no **rompimento da máxima** do candle de sinal / candle que rejeitou a perda do fundo

6. **Stop**
   - **abaixo da mínima** do candle de sinal
   - ou da região do sweep, dependendo do refinamento operacional

7. **Alvo**
   - alvo clássico do padrão no **topo A**
   - isto é, retorno à origem da correção

### Setup de venda (simetria)

Embora o vídeo enfatize o lado comprador, a lógica espelhada seria:

1. tendência de baixa
2. correção ABCD para cima
3. **AB ≈ CD**
4. falso rompimento de topo
5. candle forte vendedor
6. entrada na perda da mínima do candle de sinal
7. stop acima da máxima do sinal
8. alvo no fundo anterior / origem da correção

---

## Indicadores e filtros explícitos

Pelos trechos analisados, os filtros explícitos são:

- **média móvel de 21 períodos**
- **estrutura de tendência**
- **equivalência aproximada AB = CD**
- **volume/liquidez por horário**
- **leitura de candle**
- **falso rompimento em suporte/resistência**

Observação: a média de 21 parece funcionar mais como **filtro de tendência/inércia** do que como gatilho principal.

---

## Tradução para linguagem de price action

Em linguagem mais objetiva, o setup pode ser descrito como:

- **trend pullback**
- **ABCD correction**
- **support/resistance sweep**
- **false breakout**
- **continuation entry on momentum candle**

---

## Hipótese de edge

A vantagem operacional sugerida pelo vídeo está na combinação de fatores:

- tendência dominante já estabelecida
- correção em duas pernas (ABCD)
- entrada tardia dos traders no rompimento da correção
- falha desse rompimento
- retomada rápida do fluxo a favor da tendência principal

Em resumo, a edge proposta não está só no ABCD, mas em:

**tendência + correção ABCD + sweep + candle de força + MM21**

---

## Formulação curta da estratégia

> Entrar a favor da tendência principal em um pullback ABCD no gráfico de 15 minutos, após um falso rompimento do fundo/topo da correção, confirmado por candle forte e média móvel de 21 ainda inclinada na direção da tendência.

---

## Limitações e pontos de subjetividade

A ideia geral da estratégia está clara, mas o vídeo, pela transcrição analisada, deixa pontos subjetivos que exigiriam definição adicional para implementação sistemática ou backtest:

- o que define objetivamente uma **tendência**
- qual a tolerância aceitável para **AB ≈ CD**
- como medir um **candle forte**
- quando invalidar o setup
- como tratar situações em que o alvo no topo A gera relação risco/retorno insuficiente
- como filtrar consolidações e regimes de baixa direcionalidade

---

## Especificação quantitativa pré-registrada

> Status: **documento de design pré-registrado**. Esta seção congela uma primeira formulação objetiva da hipótese antes de olhar resultado do backtest.

### 1. Escopo desta rodada

- universo inicial: **BTCUSDT spot 15m**;
- período alvo: **2017-08-17 → execução atual**;
- lados operados: **long e short**;
- custo explícito: **10bp round-trip**;
- nada vai para paper/live.

Esta rodada não tenta provar a melhor parametrização do padrão. Ela apenas responde se uma formulação razoável, causal e congelada do setup possui edge líquido suficientemente robusta para continuar viva na trilha.

### 2. Regras causais e filosofia de implementação

- toda leitura do setup acontece no fechamento de `t-1`;
- a entrada só pode acontecer em `t`;
- pivots só podem ser considerados depois de confirmados;
- nenhuma decisão pode depender do futuro;
- não haverá grid search nem múltiplas variantes nesta primeira execução.

### 3. Componentes congelados do setup

#### 3.1. Filtro de tendência/inércia

A tendência será considerada **bullish** quando, no candle de sinal:

- `close > EMA_21`;
- `EMA_21 > EMA_21.shift(1)`;
- a estrutura recente de swings mostrar **higher high + higher low**.

A tendência será considerada **bearish** quando:

- `close < EMA_21`;
- `EMA_21 < EMA_21.shift(1)`;
- a estrutura recente de swings mostrar **lower low + lower high**.

#### 3.2. Pivots e estrutura

A detecção de swing usará pivots confirmados com janela simétrica fixa:

- `lookback = 2`
- `lookforward = 2`

Portanto, um pivot só é conhecido duas velas depois de se formar. Isso atrasa o reconhecimento estrutural, mas preserva causalidade.

#### 3.3. Definição do padrão ABCD

No lado comprador, o algoritmo buscará a sequência estrutural:

- `A`: último swing high relevante antes da correção;
- `B`: primeiro swing low corretivo;
- `C`: swing high intermediário abaixo de `A`;
- `D`: segundo swing low corretivo.

No lado vendedor, a lógica será espelhada.

A correção será aceita como ABCD quando:

- `AB` e `CD` tiverem a **mesma direção corretiva**;
- a amplitude relativa obedecer a:
  - `0.80 <= |CD| / |AB| <= 1.20`
- `C` não violar estruturalmente `A`;
- `D` ocorrer depois de `C`, sem reorder artificial.

A tolerância de **±20%** para `AB ≈ CD` fica congelada nesta rodada.

#### 3.4. Sweep / falso rompimento

No long, exige-se que `D`:

- viole a mínima de `B` por qualquer margem positiva;
- mas não produza continuação limpa imediata;
- seja seguido por um candle de força que recupere o terreno da armadilha.

No short, exige-se que `D`:

- viole a máxima de `B`;
- mas fracasse em continuar;
- seja seguido por candle de força vendedor.

Isso traduz objetivamente a ideia de **rompimento falso / manipulação / varrida de liquidez**.

#### 3.5. Candle de força

O candle gatilho será considerado forte no lado comprador quando:

- `close > open`;
- `body / range >= 0.50`;
- `close_location = (close - low) / range >= 0.66`;
- `close > high` do candle que fez o sweep;
- `volume >= média das últimas 20 velas`.

No lado vendedor:

- `close < open`;
- `body / range >= 0.50`;
- `close_location <= 0.34`;
- `close < low` do candle que fez o sweep;
- `volume >= média das últimas 20 velas`.

### 4. Regras operacionais congeladas

#### Entrada long

Entrar comprado em `t` quando, em `t-1`, todos os critérios abaixo forem verdadeiros:

1. tendência/inércia bullish;
2. sequência estrutural ABCD confirmada;
3. `AB ≈ CD` dentro da tolerância fixa;
4. `D` fez sweep da mínima de `B`;
5. candle de força comprador confirmou o fracasso da quebra.

#### Entrada short

Entrar vendido em `t` quando, em `t-1`, todos os critérios abaixo forem verdadeiros:

1. tendência/inércia bearish;
2. sequência estrutural ABCD espelhada;
3. `AB ≈ CD` dentro da mesma tolerância;
4. `D` fez sweep da máxima de `B`;
5. candle de força vendedor confirmou o fracasso da quebra.

#### Stop

- long: abaixo da mínima do candle de sweep/sinal, usando a mínima mais extrema entre `D` e o candle gatilho;
- short: acima da máxima mais extrema entre `D` e o candle gatilho.

#### Alvo

O alvo-base será o retorno à origem da correção:

- long: região de `A`;
- short: região de `A` espelhado.

Se a projeção até `A` gerar risco-retorno muito comprimido, isso será medido no resultado, mas **não será reotimizado depois**.

#### Saída adicional

Se nem stop nem alvo forem atingidos, será aplicado um **time stop fixo** para evitar trades indefinidos em consolidação. A primeira formulação usará:

- `MAX_HOLD_BARS = 16` velas (4h)

### 5. Regras de execução e medição

- o trade entra na abertura de `t` depois do sinal fechado em `t-1`;
- durante a vida do trade, o backtest observará stop/alvo pela faixa `high/low` de cada vela;
- quando stop e alvo forem tocados na mesma vela, o backtest adotará uma convenção conservadora fixa, documentada no script;
- custos só entram quando houver abertura/fechamento efetivo da posição.

### 6. O que será medido

A rodada deve produzir, no mínimo:

- número de trades long e short;
- win rate;
- payoff;
- profit factor;
- curva de equity;
- CAGR líquido e bruto;
- vol anualizada;
- Sharpe;
- Sortino;
- max drawdown;
- duração do drawdown;
- retorno total;
- retornos por ano;
- robustez por sub-janelas.

Benchmark: **buy-and-hold BTCUSDT spot** no mesmo intervalo.

### 7. Veredito pré-registrado

A hipótese Q25 só **sobrevive como candidata** se, na janela cheia:

1. `CAGR líquido >= 30%` do CAGR do buy-and-hold;
2. `max drawdown <= 70%` do maxDD do buy-and-hold;
3. nenhum único ano responder por `>= 55%` do retorno total;
4. comportamento líquido positivo em:
   - pelo menos `1/2` das metades;
   - pelo menos `2/3` dos ciclos amplos;
5. o custo não explicar sozinho o resultado:
   - `CAGR bruto - CAGR líquido <= 1.5pp`;
6. haver amostra suficiente para leitura:
   - pelo menos `30 trades` no total.

Sub-janelas pré-registradas:

- primeira metade vs segunda metade;
- `2017-08 → 2019-12`;
- `2020-01 → 2022-12`;
- `2023-01 → execução atual`.

### 8. O que esta rodada NÃO autoriza

Mesmo se a Q25 sobreviver:

- não é promoção para paper/live;
- não autoriza retune pós-fato de pivots, tolerância de amplitude ou candle de força;
- não prova robustez fora de BTC spot 15m;
- apenas mantém a hipótese viva para validação/refino posterior.

---

## Conclusão

A estratégia usada no vídeo pode ser classificada com boa confiança como uma estratégia de:

**continuação de tendência via correção ABCD com falso rompimento e retomada por candle de força**.

Nesta rodada, ela fica congelada como uma hipótese objetiva de **ABCD pullback + sweep + candle de força + EMA 21**, aplicável em **BTCUSDT spot 15m**, com validação exclusivamente histórica e causal.
