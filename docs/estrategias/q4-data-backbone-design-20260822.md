# Q4 — Data backbone para microestrutura crypto — design — 2026-08-22

> Status: **documento de design com verificação empírica das fontes**.
> Objetivo: decidir e pavimentar o dataset comum para as próximas hipóteses
> (funding+OI, basis/carry, order flow, post-flush), permitindo que futuros
> event studies NÃO esbarrem de novo no problema de "a hipótese morreu só
> porque o dado não existia".
> Nada toca paper/live.

---

## 1. Por que isso é a frentecorreta agora

P1/P2 (sinais) e Q3 (event study) esbarraram, em momentos distintos, no mesmo
teto: **dados fracos**. Em Q3 a hipótese de post-flush falhou por falta de
informações de OI/liquidação reais, forçando um proxy de OHLCV que não trouxe
evidência suficiente. Antes de fechar (ou não) novas hipóteses, precisamos saber
**exatamente o que conseguimos medir** — e o que não conseguimos — com custo
aceitável.

## 2. Fonte de dados verificadas hoje (probe empírico, 2026-08-22)

### 2.1 Binance Futures — endpoints públicos (sem API key)

| Dado | Endpoint | Status | Granularidade | Uso |
|---|---|---|---|---|
| OHLCV futuros | `fapi/v1/klines` | ✅ | 1s–1M | preço de execução |
| Mark price klines | `fapi/v1/markPriceKlines` | ✅ | 1s–1M | mark vs trade |
| **Premium index klines** | `fapi/v1/premiumIndexKlines` | ✅ | 1s–1M | **basis (mark − index) histórico** |
| Funding rate | `fapi/v1/fundingRate` | ✅ | 8h (mais denso em HL) | posicionamento |
| Top long/short ratio | `futures/data/topLongShortAccountRatio` | ✅ | 15m/1h/4h/… | posicionamento top traders |
| Global long/short ratio | `futures/data/globalLongShortAccountRatio` | ✅ | idem | posicionamento agregado |
| **Taker buy/sell ratio** | `futures/data/takerlongshortRatio` | ✅ | idem | **proxy de order flow** |
| Open interest (atual) | `fapi/v1/openInterest` | ⚠️ apenas snapshot atual | — | sem histórico |
| Liquidações (`allForceOrders`) | — | ❌ requer API key | — | forçadas fora |

### 2.2 Binance Vision — bucket público de histórico mensal (sem API key)

Verificado com `HEAD`/listing no bucket `data.binance.vision` (prefixo
`data/futures/um/monthly/`):

- ✅ `klines` — OHLCV mensal, qualquer ativo/TF
- ✅ `markPriceKlines` / `indexPriceKlines` / `premiumIndexKlines` — basis histórico
- ✅ `fundingRate` — CSV mensal com `fundingTime, fundingRate, markPrice`
- ✅ `aggTrades` / `trades` — **fluxo de ordens agregado** (proxy de taker flow)
- ❌ (não existe) open interest histórico

### 2.3 Hyperliquid — API pública (verificada)

- ✅ `fundingHistory` (post `{"type":"fundingHistory","coin":"BTC",...}`) — retorna
  `fundingRate` + `premium` por timestamp
- ⚠️ `openInterest` — snapshot atual; payload ainda a validar
- (alternativas de histórico OI da HL exigem pipeline próprio)

## 3. Arquitetura de dataset proposta

Camada única de ingestão em `backend/scripts/` + outputs versionados:

```
data/derivatives/
  binance_vision/monthly/<YYYY-MM>/
    klines_BTCUSDT_15m.csv.gz
    premiumIndexKlines_BTCUSDT_15m.csv.gz
    fundingRate_BTCUSDT.csv.gz
    aggTrades_BTCUSDT.csv.gz
  live_snapshot/
    oi_funding_ratios_YYYYMMDD.csv     <- coletor nosso (a partir de hoje)
```

Componentes:
1. `download_binance_vision.py` — baixa e normaliza os CSVs mensais.
2. `collect_snapshot.py` — job periódico gravando OI atual + funding + ratios
   (constrói **nosso próprio histórico de OI** a partir de agora).
3. `validate_ds.py` — etapa obrigatória de qualidade (protocolo §4); falha → não
   sobe para nenhum estudo.

## 4. Protocolo de qualidade de dados (obrigatório antes de cada estudo)

1. **Integridade**: contagem de linhas vs esperado; sem valores ausentes em
   `open/close`; `high >= max(open,close)` e `low <= min(open,close)`; sem
   duplicados de timestamp.
2. **Continuidade**: índices temporais sem lacunas maiores que 2× o intervalo;
   funding sem gaps > 3 períodos.
3. **Plausibilidade**: `premium` dentro de faixa sanidade (ex.: |basis| < 1% do
   preço na janela); `funding` dentro de faixa histórica; ratios em [0,1].
4. **Consistência cruzada**: amostra de Binance Vision vs endpoint público atual
   (mesma semana) — devem bater dentro de tolerância pequena.
5. **Documentação**: cada run grava um `ds_report.json` com as verificações.

O dataset **só é consumível por um study se passar em 1–4**.

## 5. Decisão em aberto (custo)

Histórico de **open interest** e **liquidações** têm 3 rotas possíveis:

- **A — 100% gratuito (recomendado daqui em diante)**: começar a coletar OI
  snapshot nós mesmos a partir de hoje; usar proxy de liquidações via eventos de
  OI/preço. Limitação: backtest só ganha OI "real" para períodos futuros.
- **B — fonte paga mínima para backfill**: free tier do CoinAPI (O)riode, ou
  assinatura starter da Coinglass para OI/liquidações históricas. Backtest com
  dados melhores desde já, porém com custo recorrente e (no caso de Coinglass)
  API chave + limites.
- **C — Hybird**: coletar nós o mais cedo possível (A) e comprar apenas o
  **backfill** uma vez (B).

## 6. Quais estudos reabrir depois (Q5), em ordem de prontidão de dados

1. **Basis/carry delta-neutral** — mais pronto: premiumIndexKlines + funding
   já disponíveis gratuitamente. Event study de basis extremo; racional
   estrutural forte (literatura He et al.).
2. **Funding + order flow direcional** — pronto: funding + taker ratio +
   aggTrades. Hipótese: combinar prêmio de alavancagem com vivacidade do fluxo,
   não como "outro indicador".
3. **OI divergence (preço vs OI)** — depende da decisão §5; com snapshot
   próprio, só após acumular semanas; com backfill pago, imediato.
4. **Post-flush com OI/liquidações reais** — reabrir apenas quando tivermos OI
   ou liquidações confiáveis (senão repetimos Q3 com o mesmo teto).

## 7. Fora de escopo desta rodada

- Nenhuma estratégia nova.
- Nenhuma mudança em runtime/executor (continua fail-closed).
- Sem compra de dados sem decisão explícita do usuário (§5).