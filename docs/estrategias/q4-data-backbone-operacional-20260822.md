# Q4 — Data backbone operacional (research-only) — 2026-08-22

> Status: **operacional**. O backbone gratuito para microestrutura crypto saiu do
> papel e já está coletando nossa própria série de snapshot a partir de hoje.
> Nada toca paper/live.

## 1. O que foi colocado de pé

### A. Coletor de snapshot (sem API key)
Arquivo: `backend/scripts/collect_snapshot.py`

Captura por execução:
- `open_interest`
- `mark_price`
- `index_price`
- `last_funding_rate`
- `global_long_short_ratio`
- `top_long_short_ratio`
- `taker_buy_sell_ratio`
- `taker_buy_vol`
- `taker_sell_vol`

Destino append-only:
- `backend/data/derivatives/live_snapshot/oi_funding_ratios.csv`

Primeiro seed gravado em `2026-08-22T15:07:16Z`.

### B. Downloader do Binance Vision (backfill histórico gratuito)
Arquivo: `backend/scripts/download_binance_vision.py`

Baixa para:
- `klines`
- `premiumIndexKlines`
- `fundingRate`

Destino:
- `backend/data/derivatives/binance_vision/monthly/<YYYY-MM>/`

Prova já executada:
- mês `2026-07`
- ativo `BTCUSDT`
- TF `15m`

Arquivos presentes:
- `klines_BTCUSDT_15m.csv`
- `premiumIndexKlines_BTCUSDT_15m.csv`
- `fundingRate_BTCUSDT.csv`

### C. Smoke test do backbone
Arquivo: `backend/scripts/data_sources_smoke.py`

Resultado final: **BACKBONE OK — dataset consumível**

Checks aprovados:
- integridade OHLC
- continuidade temporal
- funding plausível
- basis plausível
- snapshot endpoints públicos disponíveis
- consistência cruzada Vision × endpoint

## 2. O que isso destrava

A partir de agora, o projeto passa a ter duas trilhas de dado utilizáveis:

1. **Histórico gratuito imediato**
   - preço (klines)
   - funding
   - basis / premium index
   - mark/index price histórico

2. **Histórico próprio acumulado a partir de hoje**
   - open interest snapshot
   - ratios de posicionamento
   - taker buy/sell ratio

Isso é suficiente para começar a próxima frente de research **sem depender de TA
clássica**:

- **basis/carry event study** (pronto já)
- **funding + order flow** (pronto já)
- **OI divergence** (precisa acumular série própria)
- **post-flush com OI real** (precisa acumular série própria)

## 3. Próxima trilha recomendada

A próxima hipótese com melhor relação "racional forte × dado já disponível" é:

### Q5 — Basis / carry / premium dislocation

Usar `premiumIndexKlines + fundingRate + klines` para medir:
- se extremos de premium/basis revertêm;
- se basis extremo com funding extremo antecipa mean reversion ou continuação;
- se há edge delta-neutral ou contextual para direção.

Razão da prioridade:
- dado já está pronto **hoje**;
- hipótese tem racional estrutural melhor que candle-pattern;
- não depende de esperar semanas para acumular OI próprio.

## 4. Restrição mantida

**Nada vai para paper/live.** Todo uso deste backbone continua estritamente em
research, com event study / walk-forward e a mesma régua honesta aplicada nas
rodadas anteriores.