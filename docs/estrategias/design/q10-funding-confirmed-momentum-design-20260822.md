# Q10 — Cross-sectional momentum com funding confirmation — design pré-registrado — 2026-08-22

> Status: **documento de design**. Nada implementado como estratégia, nada em
> paper/live. Hipótese: adicionar **confirmação por funding** ao sinal de
> momentum cross-sectional da Q9, para tentar **aumentar a magnitude do efeito**
> (que na Q9 foi direcionalmente correto, mas pequeno demais para vencer custo).

---

## 1. Hipótese

> Quanto mais **alerrado** (crowded) está um deslocamento, maior a chance de ele
> **continuar**. Um ativo com premium relativo extremo E funding relativo
> confirmando o mesmo lado carrega um deslocamento de posicionamento mais forte
> do que um ativo com premium extremo mas funding neutro/oposto.

Na Q9:
- o sinal cross-sectional de momentum (RICH continua subindo, CHEAP continua
  caindo) esteve correto em 4h/8h/24h;
- mas a magnitude ficou em ~0,5–2bp, muito abaixo do piso de custo de 20bp.

Aqui, adicionamos uma **confirmação independente**: o funding.
- **RICH forte**: premium relativo no topo (≥0.75) **e** funding do ativo acima
  de um limiar positivo (posicionamento long crowded).
- **CHEAP forte**: premium relativo no fundo (≤0.25) **e** funding do ativo
  abaixo de um limiar negativo (posicionamento short crowded).

Racional: se o mercado está pagando funding para segurar aquela direção, há
convicção real por trás — e isto costuma aprofundar/momentum antes de reverter.

## 2. Dados e definição causal

- **Basket fixo**: BTCUSDT, ETHUSDT, SOLUSDT, BNBUSDT, XRPUSDT, DOGEUSDT,
  ADAUSDT, LINKUSDT.
- `premium_rel(s,t) = premium_close(s,t) / perp_close(s,t)` em M15.
- `rn(s,t)` = rank normalizado cross-sectional de `premium_rel` (0 a 1).
- `funding(s,t)` = último funding conhecido até `t` (sem lookahead), via
  `fundingRate` Binance.

Eventos:
- **RICH_F**: `rn(s,t) >= 0.75` **e** `funding(s,t) > +funding_hi_thr`
- **CHEAP_F**: `rn(s,t) <= 0.25` **e** `funding(s,t) < -funding_hi_thr`

Parâmetro pré-registrado:
- `funding_hi_thr` = `0.0001` (1bp) — decadência a funding acima/abaixo de
  1bp absoluto, assumindo que esta é uma cxoração de convicção razoável.

Entrada: close do candle de evento `t`.
Cooldown: 8 candles por símbolo/lado.

## 3. SINAL-PREDIÇÃO (pré-registrado)

- **RICH_F → retorno relativo forward POSITIVO** (continuação de alta com
  confirmação).
- **CHEAP_F → retorno relativo forward NEGATIVO** (continuação de baixa com
  confirmação).

## 4. Retorno e custo

- Relativo ao basket (equiponderado dos outros 7), horizontes 1h/4h/8h/24h.
- Controle: retorno relativo incondicional de todos os pares.
- Custo piso: `20bp` (2 patas × 10bp round-trip por pata).
- Comparação direta com Q9: exigimos **magnitude maior** que o efeito da Q9 no
  mesmo horizonte; apenas manter o sinal não basta.

## 5. Veredito pré-registrado (falsificável)

Par primário: **RICH_F e CHEAP_F × 4h × M15**.

- **Falha** se `n < 30` por lado, OU sinal contrário, OU `|marginal| <= custo 20bp`.
- **Sobrevive** se `n ≥ 30`, sinal previsto consistente em 1h/4h/8h, E
  `|marginal| > custo`, E magnitude maior que a Q9 no mesmo par/horizonte.

Leituras de robustez:
- t-stat por lado;
- win rate;
- estabilidade por símbolo;
- também reportar o mesmo efeito **sem** o filtro de funding (para conferir que o
  filtro realmente aumenta magnitude, não só reduz amostra).

## 6. Se sobreviver

Fase seguinte (SÓ então): transformar em regra operacional completa com
walk-forward 90d, ≥5/8 janelas, PnL > 0, PF > 1,3, custo real por pata.
**Nada disso nesta rodada.**

## 7. Antecipando uma possível trapaça

Não vamos "ajustar o threshold até dar certo":
- o limiar de funding fica fixo em `±1bp` desde o início;
- não vamos varrer `funding_hi_thr`;
- se a magnitude não subir mantendo sinal, a Q10 morre como as anteriores.