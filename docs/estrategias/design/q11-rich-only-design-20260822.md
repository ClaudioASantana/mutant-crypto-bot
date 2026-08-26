# Q11 — RICH-only cross-sectional continuation — design pré-registrado — 2026-08-22

> Status: **documento de design**. Nada implementado como estratégia, nada em
> paper/live. Hipótese: o único pedaço que restou minimamente promissor na família
> cross-sectional foi o lado **RICH + funding positivo**. Aqui abandonamos a
> simetria artificial e testamos **somente** esse subcaso.

---

## 1. Hipótese

> Em um basket de perps USDT-M, ativos com premium relativo alto **e** funding
> positivo suficientemente forte tendem a **continuar outperformando** o basket
> por alguns horizontes (especialmente 8h/24h), antes de eventual mean reversion.

Isto é uma hipótese mais estreita que Q9/Q10:
- Q9: rich e cheap, sem funding.
- Q10: rich e cheap, com funding.
- Q11: **apenas rich**, com funding positivo, porque foi o único lado que
  realmente melhorou quando adicionamos confirmação.

## 2. Definição causal de evento

- Basket fixo: BTCUSDT, ETHUSDT, SOLUSDT, BNBUSDT, XRPUSDT, DOGEUSDT,
  ADAUSDT, LINKUSDT.
- `premium_rel(s,t) = premium_close(s,t) / perp_close(s,t)`.
- `rn(s,t)` = rank normalizado cross-sectional no timestamp t.
- `funding(s,t)` = último funding conhecido até t (sem lookahead).

Evento único desta rodada:
- **RICH+**: `rn(s,t) >= 0.75` **e** `funding(s,t) > +0.0001`.

Entrada: close do candle de evento.
Cooldown: 8 candles por símbolo.

## 3. SINAL-PREDIÇÃO (pré-registrado)

- **RICH+ → retorno relativo forward POSITIVO**.

Horizontes a medir:
- 1h
- 4h
- **8h (primário)**
- **24h (secundário forte)**

A mudança do horizonte primário é intencional e declarada: em Q9/Q10 o lado rich
pareceu ganhar força em horizontes mais longos; aqui não faz sentido insistir em
4h como centro absoluto se a própria exploração honesta mostrou outro perfil.

## 4. Retorno e custo

- Retorno relativo ao basket (média equiponderada dos outros 7 ativos).
- Controle: retorno relativo incondicional de todos os pares (≈0 por construção).
- Custo piso: 20bp (2 patas × 10bp round-trip por pata).

## 5. Veredito pré-registrado (falsificável)

Par primário: **RICH+ × 8h × M15**.

- **Falha** se `n < 30`, OU sinal contrário, OU `marginal <= 20bp`.
- **Sobrevive** se `n ≥ 30`, sinal positivo em 4h/8h/24h, e `marginal > 20bp`
  no horizonte primário de 8h.

Leituras de robustez:
- t-stat;
- win rate;
- split por símbolo;
- comparação com Q10 RICH_F em 8h/24h.

## 6. Disciplina metodológica

Esta rodada **não** está buscando um lado que funcione “de qualquer jeito”.
Ela existe porque a própria Q10 sugeriu assimetria clara entre os lados. Se o
subcaso RICH+ ainda falhar mesmo isolado, então a conclusão correta é que a
família cross-sectional de momentum provavelmente não paga a conta neste setup.