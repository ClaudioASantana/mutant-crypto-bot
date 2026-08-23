# Q16 rerun — série longa (Binance Vision) — pré-registro — 2026-08-22

## Motivação

A Q16 (`validacao-q16-oi-crowded-continuation-20260822.md`) ficou **🔵 INCONCLUSA**
por um único guardrail: `n_indep = 11 < 20` no horizonte primário (8h). Todos os
outros guardrails passaram (sinal, magnitude, concentração de episódio, fatias,
coerência cross-horizonte 4h/8h/24h). O gargalo era puramente **amostra**, não
hipótese.

O plano original era esperar a série própria (`collect_snapshot.py`, Camada B)
acumular ~60 dias (previsão ~2026-10-21). Durante a investigação de como acelerar
essa fase, descobrimos que a Binance Vision publica um dump diário gratuito de
`daily/metrics` (OI + ratios, granularidade ~5min) cobrindo **2020-09-01 até
hoje** (~2181 dias, ~6 anos) para `BTCUSDT`. Esse backfill foi concluído nesta
sessão: `2178 dias baixados, 0 erros, 627.489 linhas` em
`data/derivatives/binance_vision/metrics/BTCUSDT_metrics_long.csv`.

Isso remove o gargalo de amostra sem esperar 60 dias e sem comprar dado pago —
mas continua sendo **Camada A** (dado público da Binance), só que histórico em
vez de janela recente de 30 dias. **Não é a Camada B** (nossa série própria,
que continua rodando em paralelo via cron como canal de validação independente
e out-of-sample).

## O que muda vs. Q16 original

Apenas a **fonte e a profundidade dos dados**. Nenhum parâmetro de definição de
evento é re-tunado:

| Parâmetro | Q16 original | Q16 rerun | Mudou? |
|---|---|---|---|
| Fonte do OI | REST `/futures/data/openInterestHist` (paginado, ~30d) | CSV `BTCUSDT_metrics_long.csv` (`sum_open_interest`, ~5min, 2020-09-01→hoje) | ✅ só a fonte |
| Fonte klines/premium | REST `/fapi/v1/klines` e `/premiumIndexKlines` (paginado, ~30d) | Binance Vision **monthly** zips (`klines`, `premiumIndexKlines`) para meses fechados + API para o mês corrente parcial, mesmo intervalo 15m | ✅ só a fonte |
| Fonte funding | REST `/fapi/v1/fundingRate` | Binance Vision **monthly** `fundingRate` para meses fechados + API para o mês corrente parcial | ✅ só a fonte |
| `LOOKBACK_BARS` | 16 | 16 | não |
| `PCT_WINDOW` | 384 | 384 | não |
| `OI_PCT_HIGH` | 0.90 | 0.90 | não |
| `PREMIUM_RICH_Q` / `PREMIUM_CHEAP_Q` | 0.75 / 0.25 | 0.75 / 0.25 | não |
| `HORIZONS_HOURS` / primário | [4,8,24] / 8h | [4,8,24] / 8h | não |
| `COST` | 10bp | 10bp | não |
| `MIN_N_INDEP` | 20 | 20 | não |
| `MAX_EPISODE_CONCENTRATION` | 0.50 | 0.50 | não |
| `EPISODE_GAP_HOURS` | 24 | 24 | não |
| Janela avaliada | ~30 dias | **2020-09-01 → hoje** (janela cheia disponível, ~2181d) | ✅ intencional, é o objetivo do rerun |
| `N_SLICES` | 3 (~10d cada) | **6** (~1 ano cada) | ✅ decidido agora, antes do resultado — ver justificativa abaixo |
| `MIN_SLICE_CONFIRM_FRAC` | 2/3 | 2/3 (ou seja, ≥4/6) | não (mesma fração) |

### Justificativa do único parâmetro novo (`N_SLICES=6`)

Com 3 fatias de ~10 dias cada, a fatia era curta demais para significar "regime
de mercado" — mal servia de proxy de repetibilidade temporal. Com ~6 anos de
janela, 3 fatias virariam ~2 anos cada — ainda aceitável, mas 6 fatias (~1 ano
cada) dá uma leitura mais fina de robustez através de regimes de mercado bem
diferentes (2020 mania, 2021 topo, 2022 bear, 2023 lateral, 2024 bull, 2025-26
atual), sem reduzir a fração de confirmação exigida (mantém 2/3). Essa decisão
é sobre **granularidade do guardrail de robustez**, não sobre o evento em si —
e está travada **antes** de rodar o experimento.

## Risco reconhecido e não escondido

- Os primeiros meses de futuros perpétuos de BTC na Binance (2020) tinham
  liquidez/OI muito menor que hoje — isso pode ser ruído ou pode ser um regime
  legítimo. Não vamos excluir esse período a priori (seria p-hacking pós-hoc);
  vamos **reportar os resultados por fatia** para que qualquer efeito
  concentrado num regime específico fique visível, não escondido.
- Klines/premium/funding via Binance Vision **monthly** dumps são o mesmo dado
  que a API serve (fonte oficial da Binance), só que arquivado — não há
  diferença de conteúdo esperada, apenas de meio de acesso. Como o bucket
  monthly não publica o mês corrente ainda aberto, o mês corrente será
  completado pela API; isso não muda o desenho do evento, só fecha a borda
  operacional da janela.
- OI da Binance Vision (`daily/metrics`, ~5min) é reamostrado (merge_asof
  causal, `direction="backward"`) para o grid M15 dos klines — igual ao método
  já usado para os outros ratios no harness original.

## Critério de aprovação (idêntico ao Q16 original)

Continua sendo o pré-registro da Q16: `n_indep >= 20`, sinal na direção
pedida (`E1:+1`, `E2:-1`), `|marginal_net| > custo (10bp)`, concentração de
episódio `< 50%`, `>= 2/3` das fatias confirmando, coerência cross-horizonte
obrigatória (4h **E** 8h **E** 24h no mesmo sinal). Se `n_indep` ainda ficar
abaixo de 20 mesmo com 6 anos de dados, o veredito passa a ser **reprovado por
insuficiência estrutural do evento** (não mais "aguardando amostra") — não
existe mais próxima fonte gratuita de mais profundidade de Camada A.

Se sobreviver: **ainda não é edge**. Precisa ser revalidado na Camada B (série
própria, independente) antes de qualquer promoção — regra que já valia no Q16
original e continua valendo.

Nada vai para paper/live nesta rodada, independente do resultado.
