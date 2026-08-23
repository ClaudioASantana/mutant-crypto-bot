# Q7 — Funding / basis regime persistence — design pré-registrado — 2026-08-22

> Status: **documento de design**. Nada implementado como estratégia, nada em
> paper/live. Esta rodada muda o objeto: não um evento único, mas um **regime**
> persistente de funding + basis.

---

## 1. Hipótese

> Em BTCUSDT perpétuo, extremos de funding e basis que permanecem no mesmo lado
> por múltiplos intervalos de funding definem um regime persistente de crowding.
> Nesse regime, uma estrutura hedgeada ou uma posição direcional condicionada
> pelo regime pode ter comportamento estatisticamente distinto do controle.

Esta hipótese é diferente de Q5/Q6:
- Q5: "basis extremo" como **evento único** e aposta direcional curta.
- Q6: "capturar o próximo funding" como **evento único**.
- Q7: **persistência** do regime ao longo do tempo, sem depender de um único
  candle de gatilho.

## 2. Definições

Dados:
- `premium_rel(t) = premium_close(t) / perp_close(t)`
- `premium_pct(t)` = percentil causal rolante de `premium_rel`.
- `funding_state_at(t)` = último funding conhecido até `t`, sem lookahead.

Regime de lado positivo:
- **R+**: `premium_pct >= 0.80` e `funding_rate > 0`

Regime de lado negativo:
- **R−**: `premium_pct <= 0.20` e `funding_rate < 0`

Persistência:
- um regime só conta se se mantiver por pelo menos **3 funding intervals**
  consecutivos (≈ 24h em BTC perp), medidos em pontos de funding sucessivos
  cujo estado continue no mesmo lado.

Entrada e saída do estudo:
- entrada no primeiro candle em que o regime se torna válido;
- saída quando o regime se quebra ou ao completar uma janela fixa de hold.

## 3. What to measure

### A. Persistência do regime
- distribuição do número de funding intervals consecutivos no regime;
- tempo médio e mediano até quebra;
- proporção de regimes que sobrevivem 1, 2, 3, 4+ funding intervals.

### B. Retorno do underlying condicionado ao regime
Para cada regime válido, medir retorno forward do perp em:
- 24h
- 48h
- 72h
- até a quebra do regime

Comparar com:
- controle incondicional
- subamostra de mesma direção sem persistência mínima

### C. Carry bruto acumulado durante o regime
Somar os funding rates observados durante a duração do regime e subtrair um
custo mínimo de round-trip conservador (10bp) apenas para leitura de upper bound.

## 4. Regra causal

Nenhuma variável usa futuro:
- premium/basis é calculado com candle fechado;
- funding é o último evento conhecido até o timestamp;
- persistência é observada somente por funding events já realizados.

## 5. Protocolo

- Mercado: BTCUSDT.
- Timeframes: M15 primário; H1 secundário.
- Janela: 130 dias buscados, 90 dias de análise, 40 dias warmup.
- Critério primário de sobrevivência de regime:
  - n >= 30 regimes por lado;
  - pelo menos 50% dos regimes com duração >= 3 funding intervals.
- Critério de utilidade econômica:
  - retorno forward médio do hold/regime acima do controle;
  - e carry acumulado médio acima do custo mínimo em leitura upper bound.

## 6. Regra de falsificação

A hipótese falha se qualquer uma ocorrer:
- menos de 30 regimes válidos em qualquer lado;
- duração mediana < 3 funding intervals em ambos os lados;
- retorno forward médio condicionado ao regime não supera o controle;
- carry acumulado médio não supera custo mínimo nem em upper bound.

Sobrevive à fase de estudo se:
- n >= 30 em ambos os lados;
- persistência clara (metade ou mais acima de 3 funding intervals);
- algum horizonte mostra desvio consistente do controle;
- carry acumulado tem leitura positiva material.

## 7. Interpretação correta

Se sobreviver:
- ainda não é estratégia pronta;
- apenas indica que existe um regime persistente que merece modelagem mais
  sofisticada (por exemplo, hold multi-funding ou filtro de entrada/saída).

Se falhar:
- encerra-se a família "funding/basis regime persistence" como hipótese simples.

---

**Nada vai para paper/live.**