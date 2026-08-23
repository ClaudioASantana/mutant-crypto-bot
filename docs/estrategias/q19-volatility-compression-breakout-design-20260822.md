# Q19 — volatility compression breakout (BB squeeze + MACD) — design pré-registrado — 2026-08-22

> Status: **documento de design**. Nada implementado como estratégia, nada em
> paper/live.

---

## 1. Por que esta rodada existe

A trilha já reprovou a maior parte da superfície pública em perguntas do tipo:

- basis/premium extremo;
- funding/carry;
- OI crowding/unwind/continuation;
- taker flow isolado;
- e também o zoo legado de TA clássica e o breakout de regime com Donchian/ADX.

Ainda assim, existe uma pergunta **que nunca foi feita honestamente** dentro do
framework atual de event study com controle:

> compressão de volatilidade + confirmação de momentum carregam expansão
> direcional do preço acima do baseline?

Esta rodada existe para testar a formulação mais defensável da família que o
usuário explicitamente pediu para revisitar: **Bollinger Bands + MACD**.

## 2. O que esta rodada NÃO é

Isto **não** é uma reabertura de P1/H2 disfarçada.

- P1/H2 foram backtests de estratégia com TP/SL e lógica operacional;
- aqui a pergunta é de **event study**:
  - dado um evento bem definido,
  - o retorno forward fica melhor que o controle incondicional?

Também **não** é a Q18:

- na Q18, "squeeze" significa o lado crowded de OI/funding/premium sendo
  espremido;
- aqui, "squeeze" significa **compressão de volatilidade** em Bollinger Bands.

## 3. Hipótese desta rodada

### E1 — compressão + momentum comprador

> Quando a largura das Bollinger Bands entra em compressão extrema e o histograma
> do MACD está positivo, o BTC tende a romper/expandir **para cima** acima do
> controle incondicional.

### E2 — compressão + momentum vendedor

> Quando a largura das Bollinger Bands entra em compressão extrema e o histograma
> do MACD está negativo, o BTC tende a romper/expandir **para baixo** acima do
> controle incondicional.

## 4. Definição do evento

- BTCUSDT
- timeframe **H1**
- `bb_width` = Bollinger Bandwidth de `BBANDS(20, 2)`
- `macd_hist` = histograma de `MACD(12, 26, 9)`
- `bb_width_pct` = percentil causal de `bb_width` em `PCT_WINDOW = 384` barras H1
  (~16 dias)

### E1 — squeeze direcional de alta
- `bb_width_pct <= 0.10`
- `macd_hist > 0`

### E2 — squeeze direcional de baixa
- `bb_width_pct <= 0.10`
- `macd_hist < 0`

### O que esta rodada deliberadamente NÃO exige
- não exige OI/funding/premium
- não exige `ret_lb`
- não exige volume
- não exige filtro de EMA/ADX

Isto é intencional: o objetivo é testar a família **BB + MACD** em sua forma
mais limpa, sem reembalar hipóteses públicas já reprovadas por outras vias.

## 5. Fonte de dados

- Binance Vision `monthly/klines/BTCUSDT/1h`
- API do mês corrente para completar o mês em andamento
- faixa alvo: **2020-01-01 → execução atual**

Esta rodada **não** depende de `BTCUSDT_metrics_long.csv` e não usa Camada B.

## 6. Custos

- `10bp round-trip` (`COST = 0.0010`)

## 7. Horizontes e primário

- **4h**
- **8h** (primário)
- **24h**

## 8. Regras causais

- `bb_width_pct` usa apenas a janela até a barra fechada em `t`
- `macd_hist` é lido no fechamento da própria barra do evento
- retornos forward (4h/8h/24h) só medem o desfecho
- nenhum threshold será re-tunado depois do resultado

## 9. Guardrails

Mesma disciplina da Q17:

1. **Coerência cross-horizonte obrigatória:** o `marginal_net` precisa ter o
   mesmo sinal da hipótese em **4h E 8h E 24h**.
2. **Amostra independente:** `n_indep >= 20` no primário 8h.
3. **Magnitude:** `|marginal_net| > 10bp` no primário.
4. **Episódios:** concentração do maior episódio `< 50%` dos eventos brutos.
5. **Fatias:** `>= 2/3` das 6 fatias temporais com `marginal_net` no sentido da
   hipótese.
6. **Dominância de episódio:** reportar retorno médio por episódio no primário.
7. **Se `n_indep < 20`: o veredito é INCONCLUSO**, não aprovado.

## 10. Veredito pré-registrado

### E1 — compressão + momentum comprador
- **Falha** se qualquer guardrail não passar.
- **INCONCLUSO** se `n_indep < 20`.
- **Sobrevive (candidato Camada A)** somente com TODOS os guardrails passando
  e coerência em 4h/8h/24h.

### E2 — compressão + momentum vendedor
- Mesma lógica, espelhada.

## 11. O que NÃO significa sobreviver

Mesmo sobrevivendo na Camada A:
- é só um **candidato**, não um edge;
- exige revalidação séria antes de qualquer promoção;
- nada vai para paper/live nesta rodada.

## 12. Consequências possíveis

Se Q19 falhar:
- reforça a leitura de que nem mesmo uma formulação limpa de **BB + MACD**
  sobrevive aos guardrails;
- reduz ainda mais o espaço para insistir em TA pública clássica sobre a mesma
  superfície.

Se Q19 sobreviver:
- vira o primeiro candidato real dessa família;
- mas continua bloqueado para paper/live até revalidação posterior.
