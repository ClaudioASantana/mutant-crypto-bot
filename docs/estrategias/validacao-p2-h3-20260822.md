# Validação P2 — H3 (funding rate como filtro direcional) — 2026-08-22

> Status: **H3 reprovada**. O filtro de funding melhora a poda em M15, mas não
> converte o sinal base em edge robusto; em H1, piora até o pequeno agregado de H2.

## 1. Hipótese testada

> "Funding rate como filtro long/short de microestrutura melhora a seleção de
> direção sobre o breakout de regime de H2."

Regras implementadas, sem lookahead:

- **PUT/short** só com funding **positivo e crescendo**;
- **CALL/long** só com funding **negativo** ou **neutro decrescente**;
- estado de funding causal: para cada candle, usa-se apenas o **último evento de
  funding conhecido até aquele timestamp** (`funding_state_at`).

H3 foi aplicada como **overlay direcional** sobre H2 (breakout de regime), não
como sinal isolado.

Fonte: `backend/scripts/experiment_h3_funding.py`.

## 2. Protocolo

Mesmo protocolo das frentes anteriores:

- BTCUSDT;
- timeframes: M15 e H1;
- 90 dias de preço;
- funding histórico Binance Futures (`/fapi/v1/fundingRate`), 360 eventos;
- 8 janelas OOS de 7 dias, passo 7 dias, warmup 30 dias;
- custos: `fee_rate=0.0004`, `slippage_bps=1.0`;
- critério de admissão: **≥5/8 janelas positivas + PnL agregado > 0 + PF > 1,3**.

## 3. Resultado

| TF | H2 puro folds+ | H2 puro PnL | H3 folds+ | H3 PnL | H3 PF | H3 trades | Veredito |
|---|---:|---:|---:|---:|---:|---:|---|
| M15 | 3/8 | −77,21 | 3/8 | −5,39 | 0,75 | 12 | ❌ reprovada |
| H1 | 2/8 | +1,31 | 1/8 | −0,65 | 0,93 | 2 | ❌ reprovada |

## 4. Leitura

1. **Em M15, o funding ajuda a podar os piores trades**, reduzindo a perda de
   −77,21 para −5,39 e cortando a amostra de 48 para 12 trades. Mas isso ainda
   não chega a edge: PF continua < 1 e o número de janelas positivas não sobe.
2. **Em H1, o filtro destrói a pouca amostra restante.** O H2 puro já era fraco,
   mas ainda tinha +1,31 em 4 trades; com funding, cai para −0,65 em 2 trades.
3. **O funding funciona como seletor, não como gerador de edge.** Ele melhora a
   higiene direcional de uma base ruim, mas não cria robustez estatística quando
   o sinal subjacente já não sobrevive ao walk-forward.
4. O padrão da trilha inteira se mantém: filtros externos conseguem reduzir dano,
   porém não produzir o tripé exigido (frequência suficiente + PnL agregado + PF).

## 5. Veredito

**H3 está reprovada.** Nenhum timeframe atende o critério mínimo de admissão:

- M15 continua com PnL agregado negativo e PF abaixo de 1,3;
- H1 perde janelas positivas, vira negativo e fica com amostra ínfima.

## 6. Fechamento da frente P2

Com H3 reprovada, a trilha P2 fica **inteiramente encerrada como não validada**:

- H1: filtros de sessão/ATR/ADX não salvam o zoo atual;
- H2: breakout de regime não sobrevive como sinal novo;
- H3: funding melhora a poda, mas não cria edge robusto.

**Nada vai para paper/live.** A conclusão mais forte desta rodada é
metodológica: quando a régua OOS é honesta, filtros e overlays reduzem dano,
mas não substituem a ausência de edge estrutural no sinal base.
