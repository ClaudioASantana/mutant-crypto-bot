# Q23 — operador contextual com checklist de entrada/saída — design pré-registrado — 2026-08-23

> Status: **documento de design**. Nada implementado como estratégia, nada em
> paper/live.

---

## 1. De onde esta rodada nasce

Após Q20, Q21 e Q22, a trilha espremeu bem a superfície pública de preço do BTC:

- **Q20:** trend-following diário clássico (timing) preserva upside, mas não corta
o drawdown o suficiente.
- **Q21:** sizing por volatilidade reduz melhor o drawdown do que timing, mas ainda
  não passa a régua de preservação.
- **Q22:** a leitura visual de BB + MACD como pullback/retomada em 15m não se
  traduziu em alpha líquido; virou hiper-rotação e custo destrutivo.

A partir disso, a hipótese de trabalho muda:

> talvez o edge real não esteja em um gatilho isolado, mas em um **processo de
> decisão contextual** — algo mais parecido com o que um operador discricionário
> faz quando diz “este setup vale / este contexto não vale”.

Essa rodada existe para formalizar isso como um experimento testável.

---

## 2. Hipótese

> Um **checklist contextual determinístico** — combinando tendência, localização no
> preço, momentum, volatilidade, qualidade do candle e filtro de regime — consegue
> separar setups “operáveis” de setups “ruins” melhor do que um gatilho isolado?

Esta hipótese não é “o indicador perfeito”. Ela pergunta se um **score de contexto**
pode representar melhor a leitura do operador do que uma regra única de entrada.

---

## 3. O que esta rodada NÃO é

- não é mais uma variação de BB/MACD sozinha;
- não é squeeze puro;
- não é trend diário clássico;
- não é vol-targeting;
- não é IA decidindo sozinha sem controle;
- não é grid-search de thresholds pós-resultado;
- não é uma estratégia para paper/live.

---

## 4. Fonte de dados e separação de proveniência

A trilha já reconhece uma separação importante entre:

- **memória operacional real**;
- **dados simulados/backtest**;
- **documentação/conhecimento narrativo**.

Para esta rodada, essa separação precisa ser respeitada explicitamente:

### 4.1. Dados de preço
- BTCUSDT spot 15m ou 1h (timeframe a definir antes da implementação, sem mudar depois);
- klines públicos Binance Vision / API;
- sem lookahead.

### 4.2. Contexto operacional
- contexto de mercado derivado de preço/indicadores calculados causalmente;
- possíveis campos: tendência, distância de bandas, RSI, ATR, inclinação de média,
  candle atual vs contexto recente, compressão/expansão, regime lateral/tendencial.

### 4.3. Memória de precedentes
- somente histórico operacional real ou memória explicitamente marcada como tal;
- nunca misturar backtest como se fosse trade real;
- nunca deixar memória sintética contaminar o contexto operacional.

Essa separação é coerente com o hardening já reconhecido no projeto: proveniência,
configuração operacional única e contaminação de contexto devem ser controladas.

---

## 5. Forma do operador contextual

O operador não será um “indicador mágico”. Ele será um **score/checklist**.

### 5.1. Estrutura geral
Um setup base gera um candidato, e o checklist decide:

- **ENTER**: contexto forte o bastante;
- **WAIT**: falta contexto ou qualidade;
- **VETO**: contexto ruim / contra-tendência / exaustão / regime desfavorável.

### 5.2. Componentes candidatas do checklist

#### Tendência
- acima/abaixo de EMA200
- EMA20 acima/abaixo de EMA50
- inclinação da média

#### Localização no preço
- perto de banda média / banda superior / banda inferior
- distância relativa ao range recente
- proximidade de máxima/mínima local

#### Momentum
- RSI em faixa favorável
- MACD hist/slope melhorando ou piorando
- candle de retomada ou de exaustão

#### Volatilidade / regime
- ATR alto/baixo vs recente
- compressão vs expansão
- regime de trend vs chop

#### Memória / precedentes
- contexto similar a trades vencedores anteriores?
- contexto similar a trades perdedores anteriores?
- existe forte precedência para WAIT?

---

## 6. Forma testável inicial

Para não cair em ambiguidade, a primeira versão precisa ser **determinística**.

### 6.1. Setup-base
Escolher um setup único para começar, por exemplo:
- pullback em tendência;
- breakout com confirmação;
- exaustão/reversão curta.

### 6.2. Score contextual
Cada componente soma/subtrai pontos:
- +1 tendência alinhada
- +1 momentum melhorando
- +1 preço em zona favorável
- +1 volatilidade/regime favorável
- -1 exaustão
- -1 contra-tendência
- -1 regime lateral ruim

### 6.3. Decisão
- score ≥ limiar → ENTER
- score intermediário → WAIT
- score baixo → VETO

O limiar será fixo antes da execução.

---

## 7. O que esta rodada tenta descobrir de verdade

A pergunta não é “esse score dá lucro?” apenas.
A pergunta maior é:

> o processo de decisão contextual consegue separar o que é **operável** do que é
> **ruído**, melhor do que um gatilho isolado?

Se sim, então a trilha deixa de buscar só “sinais” e passa a modelar um **operador**.

---

## 8. Métricas a reportar

A primeira implementação precisa medir, no mínimo:

- número de oportunidades candidatas;
- taxa ENTER / WAIT / VETO;
- PnL bruto e líquido;
- win rate;
- payoff;
- max drawdown;
- tempo em mercado;
- flips / turnover;
- comparação com setup-base sem checklist;
- comparação com benchmark buy-and-hold (se fizer sentido no timeframe escolhido).

Se o experimento ficar muito tático, também vale medir:
- duração média do trade;
- slippage/custo relativo;
- distribuição dos scores;
- performance por faixa de score.

---

## 9. Critérios de sobrevivência provisórios

Como esta é uma frente nova, os critérios precisam ser honestos mas não ingênuos.

Uma variante só **SOBREVIVE como candidata** se, na janela cheia:

1. **Melhora do processo:** o checklist melhora a qualidade média das entradas vs setup-base.
2. **Custo não explode:** o ganho líquido não some em turnover/custo.
3. **Robustez temporal:** não depende de um único trecho curto.
4. **Pelo menos um dos seguintes:**
   - melhora clara do drawdown;
   - melhora clara do payoff;
   - melhora clara do retorno líquido por trade.

Se isso não acontecer, a hipótese contextual não ajuda o suficiente.

---

## 10. O que NÃO significa sobreviver

Mesmo sobrevivendo:

- não é promoção para paper/live;
- não autoriza transformar o score em “IA livre” sem controle;
- não autoriza misturar backtest com memória operacional real;
- não autoriza retune pós-resultado;
- não autoriza apagar a separação entre contexto real, docs e simulação.

---

## 11. Consequências possíveis

### Se sobreviver
- teremos uma primeira ponte honesta entre a leitura humana do operador e uma regra
  auditável;
- isso abre espaço para um segundo passo com memória operacional real ou IA assistida.

### Se falhar
- significa que, mesmo ao modelar contexto em vez de gatilho isolado, a leitura não
  virou vantagem operacional robusta;
- nesse caso, a trilha deve olhar com mais força para dados realmente novos ou para
  uma forma de decisão ainda mais rica do que checklist.
