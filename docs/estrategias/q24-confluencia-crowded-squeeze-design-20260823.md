# Q24 — confluência total de crowded squeeze — design pré-registrado — 2026-08-23

> Status: **documento de design / viabilidade apenas**.
> Esta hipótese **não será validada hoje**.
>
> ⚠️ **Aviso metodológico central:** a hipótese nasce como refinamento da Q18
> (que por sua vez nasceu do achado incidental da Q16 longa). Portanto, a janela
> histórica da Camada A que gerou o achado (`2020-09-01 → 2026-08-21`) está
> **contaminada para validação**. Hoje só é permitido:
>
> 1. congelar a hipótese;
> 2. medir **viabilidade de frequência** (contagem de eventos);
> 3. começar a acumular amostra genuinamente nova.

---

## 1. Por que esta rodada existe

A Q16 longa mostrou que a narrativa de **continuação do lado crowded** falhou,
mas o braço de **crowded short** sugeriu um comportamento diferente:

- não continuação para baixo;
- e sim **squeeze para cima** contra o lado apinhado.

A Q18 preservou essa hipótese sem executá-la, porque a própria amostra que a
sugeriu não pode confirmá-la honestamente.

A Q24 é um refinamento lógico e mais exigente:

> talvez o squeeze só apareça quando o estado crowded não é apenas
> `preço + OI + funding + premium`, mas uma **confluência extrema completa**,
> incluindo **taker flow** no mesmo lado.

Ou seja: não basta crowding de estrutura. Exigimos também crowding de fluxo.

---

## 2. Hipótese desta rodada

### E1 — crowded long squeeze com confluência total

> Quando o BTC entra em estado de **crowded long extremo e convergente**
> (preço subindo, OI crescendo forte, funding positivo e extremo, premium rich,
> taker buy imbalance extremo), o retorno forward tende a ser **mais negativo**
> que o controle — squeeze contra o lado crowded.

### E2 — crowded short squeeze com confluência total

> Quando o BTC entra em estado de **crowded short extremo e convergente**
> (preço caindo, OI crescendo forte, funding negativo e extremo, premium cheap,
> taker sell imbalance extremo), o retorno forward tende a ser **mais positivo**
> que o controle — squeeze de alta contra o lado crowded.

---

## 3. O que esta rodada É e NÃO É

### É
- uma hipótese nova, mais específica que a Q18;
- um refinamento que adiciona **fluxo agressor extremo** à leitura de crowding;
- um pré-registro com teste de **frequência** apenas.

### NÃO É
- validação de edge hoje;
- backtest de retorno na mesma amostra histórica que gerou a hipótese;
- reabertura da Q16/Q18 sob outro nome;
- autorização para paper/live.

---

## 4. Fonte de dados permitida nesta rodada

### 4.1. Camada A histórica (permitida apenas para viabilidade)

- `BTCUSDT_metrics_long.csv`
- monthly futures Binance Vision:
  - klines
  - premiumIndexKlines
  - fundingRate

Uso permitido hoje:
- **contagem de eventos por mês**;
- distribuição de frequência;
- estimativa de tempo de espera para atingir `n_indep` fora-da-amostra.

Uso proibido hoje:
- qualquer cálculo de retorno forward para decidir se a hipótese “funciona”.

### 4.2. Amostra válida futura para o veredito

A Q24 só pode ser validada em:
1. **meses novos da Camada A** posteriores ao cutoff da Q16 longa; ou
2. **Camada B** quando a série própria maturar.

---

## 5. Variáveis da hipótese

Todas causais, conhecidas no instante do evento:

- `ret_lb`: retorno trailing de `LOOKBACK_BARS = 16` velas (4h)
- `oi_chg`: variação de OI no mesmo lookback
- `oi_pct`: percentil causal de `oi_chg` em `PCT_WINDOW = 384`
- `premium_rel`: `premium_close / close`
- `prem_pct`: percentil causal de `premium_rel` em `PCT_WINDOW = 384`
- `taker_ls`: `sum_taker_long_short_vol_ratio`
- `taker_pct`: percentil causal de `taker_ls` em `PCT_WINDOW = 384`
- funding state causal em `ts` via último funding conhecido (`rate`, `rising`)
- `funding_abs_pct`: percentil causal do valor absoluto do funding nas últimas
  observações realizadas

---

## 6. Definição do evento (congelada)

### Parâmetros fixos

- `LOOKBACK_BARS = 16` (4h)
- `PCT_WINDOW = 384` (4 dias em M15)
- `OI_PCT_HIGH = 0.90`
- `PREMIUM_RICH_Q = 0.75`
- `PREMIUM_CHEAP_Q = 0.25`
- `TAKER_HIGH_Q = 0.90`
- `TAKER_LOW_Q = 0.10`
- `FUNDING_ABS_Q = 0.80`

### E1 — crowded long squeeze com confluência total

Evento dispara quando **todos** valem:
- `ret_lb > 0`
- `oi_pct >= 0.90`
- `funding_rate > 0`
- `funding_abs_pct >= 0.80`
- `prem_pct >= 0.75`
- `taker_pct >= 0.90`

### E2 — crowded short squeeze com confluência total

Evento dispara quando **todos** valem:
- `ret_lb < 0`
- `oi_pct >= 0.90`
- `funding_rate < 0`
- `funding_abs_pct >= 0.80`
- `prem_pct <= 0.25`
- `taker_pct <= 0.10`

---

## 7. Sinal pedido (para a futura validação)

- `SIGN_REQUESTED["E1"] = -1`
- `SIGN_REQUESTED["E2"] = +1`

Ou seja, é uma hipótese de **squeeze contra o lado crowded**, não de
continuação.

---

## 8. O que será medido HOJE (e somente hoje)

### 8.1. Viabilidade de frequência

Para a janela histórica contaminada, medir apenas:
- número bruto de eventos E1 e E2;
- número por mês;
- número de eventos independentes por mês (gap = horizonte primário futuro);
- maior episódio por share de observações;
- estimativa de meses necessários para acumular `n_indep >= 20` fora-da-amostra.

### 8.2. Sem retorno, sem t-stat, sem marginal

Hoje é **proibido** calcular:
- retorno 4h / 8h / 24h;
- média líquida vs controle;
- t-stat;
- win rate;
- qualquer veredito econômico.

Se o script imprimir retorno, o script está metodologicamente errado.

---

## 9. Critério de utilidade desta rodada

A Q24 só é útil hoje se responder:

> "A confluência total é frequente o bastante para merecer esperar amostra nova,
> ou é tão rara que a hipótese fica operacionalmente inviável?"

### Interpretação

- se a frequência implícita sugerir `n_indep >= 20` em horizonte razoável,
  a hipótese merece ficar viva aguardando amostra nova;
- se for rara demais, a hipótese pode ser arquivada por inviabilidade prática,
  mesmo antes da validação econômica.

---

## 10. Como a futura validação deverá acontecer

Quando houver amostra nova suficiente, a Q24 deverá herdar a lógica da Q16/Q18:

- horizontes: `4h / 8h (primário) / 24h`
- custo: `10bp round-trip`
- `n_indep >= 20`
- maior episódio `< 50%`
- `>= 2/3` das 6 fatias confirmando
- coerência cross-horizonte obrigatória
- comparação contra controle do BTC no mesmo período

Mas **isso não será rodado hoje**.

---

## 11. O que a Q24 ensina mesmo se nunca validar

Mesmo que a hipótese se revele rara demais, a rodada ainda serve para uma coisa:

- responder se o próximo passo sério da trilha deve ser
  **esperar dado novo** para a fronteira crowded-squeeze,
  ou **abandoná-la por inviabilidade de frequência**.

---

## 12. O que esta hipótese NÃO autoriza

- não autoriza reabrir Q16/Q18 com flip pós-hoc na amostra velha;
- não autoriza calcular retorno hoje “só para ver”;
- não autoriza paper/live;
- não autoriza retune posterior dos limiares depois de ver a frequência.
