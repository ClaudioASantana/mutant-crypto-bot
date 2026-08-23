# Q23 — operador contextual para pullback em tendência — design pré-registrado — 2026-08-23

> Status: **documento de design**. Nada implementado como estratégia, nada em
> paper/live.

---

## 1. De onde esta rodada nasce

A trilha já espremeu com rigor três famílias de preço público:

- **Q20:** trend-following diário clássico preserva participação, mas não corta
  drawdown o suficiente.
- **Q21:** sizing por volatilidade melhora o drawdown, mas ainda não passa a régua.
- **Q22:** BB + MACD como pullback/retomada em 15m virou hiper-rotação e custo
  destrutivo.

A resposta que resta não é “mais um indicador”. É tentar modelar o processo que
um operador discricionário realmente usa:

> um **setup-base** que só é operado quando o **contexto** está bom o bastante.

Essa rodada é a primeira versão concreta do **operador contextual**.

---

## 2. Hipótese

> Um **setup-base de pullback em tendência**, combinado com um **checklist
> determinístico de contexto** (tendência, localização, momentum e regime), consegue
> selecionar melhor as oportunidades do que operar o setup-base sozinho?

A pergunta não é se o setup-base existe.
A pergunta é se o **contexto** separa melhor:
- entradas boas;
- entradas medianas;
- entradas ruins / veto.

---

## 3. O que esta rodada NÃO é

- não é IA livre decidindo sozinha;
- não é BB/MACD puro;
- não é squeeze puro;
- não é trend diário clássico;
- não é vol-targeting;
- não é otimização de parâmetros depois do resultado;
- não é promoção para paper/live.

---

## 4. Fonte de dados

- **BTCUSDT spot 15m** via Binance Vision monthly klines;
- mês corrente completado por API spot;
- faixa alvo: **2017-08-17 → execução atual**;
- mesma disciplina causal de parse de timestamp já usada nas Q20–Q22.

Motivo do timeframe:
- o setup-base é tático;
- o checklist contextual precisa ser sensível a pullbacks e retomadas locais;
- 15m é o primeiro intervalo razoável para testar isso sem virar ruído de scalper.

---

## 5. Setup-base escolhido

A primeira versão do operador contextual usa como base um **pullback em tendência**.

### 5.1. Ideia operacional
O operador só procura comprar quando:
- existe uma tendência local de alta;
- o preço fez um pullback controlado;
- o movimento começa a retomar;
- o contexto não está esticado demais.

### 5.2. Variáveis candidatas do setup-base
- EMA20 / EMA50 / EMA200
- Bollinger Bands 20/2
- MACD 12/26/9
- RSI 14
- ATR 14

---

## 6. Checklist contextual (determinístico)

A decisão final é um score simples. O objetivo é ser auditável, não “esperto”.

### 6.1. Blocos de contexto

#### A. Tendência
- +1 se `EMA20 > EMA50`
- +1 se `close > EMA20`
- +1 se `EMA50 > EMA200` (ou equivalente de regime de alta)

#### B. Localização
- +1 se o preço está acima da banda média de Bollinger
- +1 se houve pullback recente até a banda média ou perto dela
- -1 se o preço já encostou na banda superior com pouca progressão

#### C. Momentum
- +1 se `MACD hist > 0`
- +1 se `MACD hist` está subindo por pelo menos 2 barras
- +1 se `RSI` está em faixa de retomada, não de exaustão

#### D. Regime / volatilidade
- +1 se ATR não está em extremo ruim versus o recente
- +1 se o movimento recente não parece chop puro
- -1 se há compressão sem direção ou exaustão evidente

### 6.2. Interpretação do score
- **ENTER**: score alto o suficiente
- **WAIT**: score intermediário
- **VETO**: score baixo / ruim

O limiar precisa ser fixo antes da execução.

---

## 7. Estrutura de teste

A primeira implementação deverá comparar três modos:

1. **Setup-base sozinho**
   - entra quando o pullback em tendência aparece, sem checklist adicional.

2. **Setup-base + checklist contextual**
   - entra só quando o score ultrapassa o limiar.

3. **Veto contextual**
   - mesmo setup-base, mas o checklist pode bloquear entradas ruins.

A hipótese real é que o checklist melhore a qualidade média dos trades e reduza a
taxa de lixo, mesmo que opere menos.

---

## 8. Causalidade / execução

- tudo é decidido com dados até o fechamento da barra anterior;
- nenhuma variável pode usar futuro;
- a entrada ocorre apenas na barra seguinte;
- o custo é cobrado apenas quando houver mudança de posição;
- não existe retune pós-resultado.

---

## 9. Métricas a reportar

Como a rodada é mais de operador do que de gatilho isolado, as métricas precisam
mostrar processo e resultado:

### Métricas do processo
- número de oportunidades candidatas;
- taxa de ENTER / WAIT / VETO;
- distribuição dos scores;
- tempo médio entre oportunidades;
- frequência de reentrada.

### Métricas de performance
- PnL bruto e líquido;
- win rate;
- payoff;
- max drawdown;
- duração do drawdown;
- tempo em mercado;
- turnover / flips;
- retorno por ano;
- comparação com o setup-base sem checklist.

Se fizer sentido, também:
- performance por faixa de score;
- qualidade das entradas aprovadas vs bloqueadas.

---

## 10. Veredito pré-registrado

Uma variante só **SOBREVIVE como candidata** se, na janela cheia:

1. **Melhora do processo:** o checklist melhora a qualidade média das entradas em
   relação ao setup-base sozinho.
2. **Custo não explode:** o ganho líquido não some em turnover/custo.
3. **Robustez temporal:** não depende de um único trecho curto.
4. **Pelo menos um dos seguintes:**
   - melhora clara do drawdown;
   - melhora clara do payoff;
   - melhora clara do retorno líquido por trade.

Se o checklist não melhorar nada de forma consistente, a hipótese do operador
contextual não ajuda o suficiente.

---

## 11. O que NÃO significa sobreviver

Mesmo sobrevivendo:

- não é promoção para paper/live;
- não autoriza virar IA livre sem controle;
- não autoriza misturar backtest com memória operacional real;
- não autoriza retune de thresholds depois do fato.

---

## 12. Consequências possíveis

### Se sobreviver
- teremos uma ponte auditável entre leitura contextual do operador e regra mecânica;
- isso permite evoluir para memória de trades reais / RAG operacional sem contaminação.

### Se falhar
- a leitura contextual não conseguiu superar o setup-base;
- a trilha deve então olhar para informação realmente nova ou para um modelo de
  decisão mais rico do que um checklist simples.

---

## 13. Definição executável pré-registrada (congelada antes da execução)

Esta seção congela todos os números. Nenhum deles pode ser alterado depois do
resultado desta rodada.

### 13.1. Dados, timeframe e custo

- **BTCUSDT spot 15m**, Binance Vision monthly + API do mês corrente (mesmo
  pipeline das Q20–Q22).
- Range: **2017-08-17 → execução atual**.
- **Custo:** `10bp` round-trip por trade (`5bp` por flip). Cada trade fechado
  = `2` flips → custo fixo por trade de `10bp`, consistente com a contagem
  agregada de flips.
- Todas as decisões usam dados até o **fecho da barra `t-1`**; a posição é
  aplicada na barra `t`. Sem lookahead.

### 13.2. Features (fechamento da barra)

- BB 20/2 (`bb_mid`, `bb_upper`, `bb_lower`, `bb_width`)
- EMA 20 / EMA 50 / EMA 200
- MACD 12/26/9 (`macd_hist`, `macd_hist_slope = diff(hist)`)
- RSI 14 (Wilder)
- ATR 14 (Wilder)
- ADX 14 (Wilder)

### 13.3. Setup-base (long) — dispara quando, na barra avaliada:

1. `ema20 > ema50` **e** `close > ema20` (tendência local de alta);
2. `min(close, últimas 6 barras) <= bb_mid` (pullback recente até a zona da média);
3. `close > bb_mid` **e** `close.shift(1) <= bb_mid.shift(1)` (retomada da média);
4. `macd_hist > 0` (momentum positivo).

### 13.4. Saída (idêntica nos três modos — mesma família da Q22)

Sai na barra seguinte quando qualquer um valer:
- `close < bb_mid` (perdeu a banda média); **ou**
- `macd_hist < 0` (momentum virou); **ou**
- `close >= bb_upper` **e** `macd_hist_slope <= 0` (exaustão na banda superior).

### 13.5. Checklist contextual — score determinístico (item inválido/NaN = 0)

| Bloco | Item | Condição | Pontos |
|---|---|---|---|
| A. Tendência | A1 | `ema20 > ema50` | +1 |
| | A2 | `close > ema20` | +1 |
| | A3 | `ema50 > ema200` | +1 |
| B. Localização | B1 | `close > bb_mid` | +1 |
| | B2 | `min(close, últimas 6) <= bb_mid` | +1 |
| | B3 | `close >= bb_upper` e `macd_hist_slope <= 0` | −1 |
| C. Momentum | C1 | `macd_hist > 0` | +1 |
| | C2 | `macd_hist > macd_hist.shift(1) > macd_hist.shift(2)` | +1 |
| | C3 | `40 < rsi14 < 72` | +1 |
| D. Regime/vol | D1 | `atr14 <= quantil(0.95)` do ATR das últimas 200 barras | +1 |
| | D2 | `adx14 >= 18` (não chop puro) | +1 |
| | D3 | `adx14 <= 15` e `bb_width <= quantil(0.25)` dos últimos 100 | −1 |

Faixa do score: **mín −2, máx +10**.

### 13.6. Decisão do checklist (limiares fixos)

- **ENTER:** `score >= 6`
- **WAIT:** `3 <= score <= 5`
- **VETO:** `score <= 2`

### 13.7. Três modos a comparar (mesma entrada-base, mesmo direito de saída)

1. **BASE** — entra em todo setup-base (sem gate).
2. **CHECKLIST** — entra só se `setup` **e** `score >= 6` (só ENTER).
3. **VETO** — entra se `setup` **e** `score >= 3` (bloqueia apenas VETO).

### 13.8. Métricas por modo

- trades por segmento contínuo de posição (`entry_ts`, `score` da decisão,
  `hold_bars`, `gross_return`, `net_return`);
- `avg_trade_gross`, `avg_trade_net`, `win_rate_gross`, `payoff_gross`;
- CAGR bruto/líquido, vol anualizada, Sharpe, Sortino, MaxDD, DD em dias,
  tempo em mercado, flips, `gross−net (pp)`, retorno por ano, metades/ciclos,
  `ano_máx share`;
- benchmark buy-and-hold;
- processo: nº de candidatos do setup-base, distribuição ENTER/WAIT/VETO,
  score médio dos candidatos.

### 13.9. Veredito pré-registrado (codificado no harness)

Para cada variante de checklist (`CHECKLIST`, `VETO`), **“supera a base”** se
**todas** as três condições valerem:

1. **Processo:** `avg_trade_gross` > base **e** `win_rate_gross` > base;
2. **Custo não piora:** `flips` ≤ base **e** `gross−net (pp)` ≤ base;
3. **Pelo menos um:** `max_dd` ≤ base **ou** `avg_trade_net` > base **ou**
   `payoff_gross` > base.

**Classe Q23 sobrevive** se `CHECKLIST` **ou** `VETO` superar a base.

**Sanidade descritiva (não gate):** dentro da BASE, comparar o
`avg_trade_gross` dos trades disparados com `score >= 6` (ENTER) contra os de
`score <= 2` (VETO) — se o checklist discrimina, o grupo ENTER deve vir melhor.

### 13.10. O que a sobrevivência desta classe NÃO autoriza

- não é promoção para paper/live;
- não autoriza retune de qualquer limiar desta seção depois do resultado;
- não autoriza misturar backtest com memória operacional real.
