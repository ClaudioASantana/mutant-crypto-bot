# Validação das candidatas P1 — 2026-08-22

> Status: **nenhuma candidata promovida**. Resultado negativo para o edge
> líquido com custos honestos e split out-of-sample. Todas continuam em
> *research*, sem paper e sem live.

Este documento consolida a validação quantitativa da shortlist P1 definida em
[recomendacoes-daytrade-crypto-20260822.md](recomendacoes-daytrade-crypto-20260822.md).
Todas as rodadas usam a régua centralizada:

- custo por ponta: `fee_rate = 0.0004` (0,04%) + `slippage_bps = 1.0`;
- custo aplicado sobre o notional de entrada **e** saída (`TradingCostConfig`);
- métricas do módulo `app/application/services/backtest_metrics.py`.

---

## 1. Benchmark geral (BTC 5m, 30 dias, SL/TP 2:2)

Fonte: `backend/scripts/benchmark_all.py`.

| # | Estratégia | PNL líquido | WR | PF | Trades |
|---:|---|---:|---:|---:|---:|
| 1 | 3 Velas | +2,83 | 52% | 1,35 | 50 |
| 2 | Exaustão | +0,49 | 61% | 1,17 | 18 |
| 3 | RSI+EMA | −1,87 | 50% | 0,77 | 50 |
| 4 | ABCD | −2,51 | 52% | 0,74 | 50 |
| 5 | **VWAP Z-Score** | **−2,56** | **34%** | **0,36** | 50 |
| 6 | SMC | −2,63 | 46% | 0,65 | 50 |
| 7 | Pin Bar | −3,74 | 40% | 0,47 | 50 |
| 8 | SuperTrend | −3,80 | 30% | 0,27 | 50 |
| 9 | VWAP | −4,07 | 46% | 0,38 | 50 |
| 10 | EMA+MACD | −7,68 | 36% | 0,34 | 50 |
| 11 | Bollinger | −9,31 | 38% | 0,32 | 50 |

Somente **3 Velas** e **Exaustão** fecham positivas, e com PnL pequeno
(abaixo de 3 USD sobre capital de 200 USD em 30 dias).

---

## 2. Backtest semanal (BTC, 7 dias, TP=3×ATR / SL=1,5×ATR)

Fonte: `backend/scripts/run_weekly_backtest.py`.

Top 10 geral:

| # | Estratégia (TF) | PNL | WR | PF | Trades |
|---:|---:|---:|---:|---:|---:|
| 1 | ABCD (M15) | +24,18 | 58% | 1,89 | 19 |
| 2 | Exaustão (M5) | +23,95 | 60% | 4,14 | 5 |
| 3 | SMC (M15) | +11,98 | 38% | 2,13 | 8 |
| 6 | **VWAP Z-Score (M15)** | +0,88 | 60% | 1,09 | 10 |

Detalhe da **VWAP Z-Score** por timeframe:

| TF | PNL | Trades | WR | PF |
|---|---:|---:|---:|---:|
| M15 | +0,88 | 10 | 60% | 1,09 |
| M5 | −11,88 | 18 | 22% | 0,33 |
| M1 | −102,09 | 100 | 12% | 0,19 |

A estratégia se degrada com a queda do timeframe: em M1 é francamente
destrutiva (12% de win rate sobre 100 trades).

---

## 3. Sweep da VWAP Z-Score (M15, 30 dias, split 70/30)

Fonte: `backend/scripts/experiment_vwap_zscore.py`.

Thresholds `{1.2, 1.5, 1.8, 2.0}` × alvo `{atr, vwap}`.

| threshold | alvo | treino PnL | teste PnL | teste PF | teste WR | teste n |
|---:|---|---:|---:|---:|---:|---:|
| 1.8 | atr | −55,77 | +9,96 | 3,37 | 86,67% | 15 |
| 1.5 | atr | −64,55 | +9,62 | 2,24 | 78,95% | 19 |
| 2.0 | atr | −49,09 | +4,33 | 2,03 | 80,00% | 10 |
| 1.2 | atr | −83,25 | +1,32 | 1,08 | 66,67% | 24 |
| 2.0 | vwap | −81,75 | −3,33 | 0,38 | 60,00% | 10 |
| 1.8 | vwap | −91,56 | −5,58 | 0,27 | 46,67% | 15 |
| 1.5 | vwap | −115,51 | −6,77 | 0,23 | 38,89% | 18 |
| 1.2 | vwap | −145,42 | −9,91 | 0,17 | 31,82% | 22 |

**Leitura:**

- A hipótese original ("mean reversion sai na VWAP") foi **reprovada**:
  todo `alvo=vwap` é negativo em treino e teste.
- O único OOS positivo (`threshold=1.8, alvo=atr`) tem **treino fortemente
  negativo** (−55,77). Isso é dependência de regime recente, não edge
  estável.
- Conclusão: **VWAP Z-Score não validada** — congelada como hipótese
  aberta para rechecagem futura por regime.

---

## 4. Comparativo das candidatas restantes (30 dias, split 70/30)

Fonte: `backend/scripts/experiment_candidates.py`.

Harness idêntico ao weekly (TP=3×ATR, SL=1,5×ATR, filtros RSI/volume/tendência,
uma posição por vez, time stop 24h).

### M5

| Estratégia | treino PnL | teste PnL | teste PF | teste WR | teste n |
|---|---:|---:|---:|---:|---:|
| Exaustão | −2,14 | +23,95 | 4,14 | 60,00% | 5 |
| 3 Velas | −112,29 | −52,75 | 0,52 | 40,00% | 55 |
| ABCD | −283,39 | −94,60 | 0,46 | 33,96% | 106 |

### M15

| Estratégia | treino PnL | teste PnL | teste PF | teste WR | teste n |
|---|---:|---:|---:|---:|---:|
| Exaustão | −10,57 | +0,71 | 99,00 | 100,00% | 1 |
| 3 Velas | −27,69 | −7,51 | 0,83 | 38,89% | 18 |
| ABCD | −98,63 | +19,81 | 1,56 | 56,52% | 23 |

**Leitura:**

- **Exaustão** é a única positiva OOS nos dois TFs, mas sobre amostra ínfima
  (5 trades em M5, 1 em M15). O resultado coincide com o semanal porque o
  split 70/30 faz o teste ser ~a última semana. Não dá para confiar em 5 trades.
- **3 Velas** é negativa OOS nos dois TFs.
- **ABCD** alterna: OOS positivo em M15 (23 trades, PF 1,56) mas treino muito
  negativo (−98,63) — regime-dependente, não estável.

---

## 4b. Walk-forward 90 dias + split por regime (Exaustão e ABCD)

Fonte: `backend/scripts/experiment_walkforward.py`.

Metodologia: 8 janelas out-of-sample não sobrepostas de 7 dias (passo 7d),
com 30 dias de warmup de indicadores antes de cada uma. Regime por ADX(14)
(≥25 = trend). Mesmo harness e custos.

### M5

| Estratégia | janelas OOS | positivas | PnL total | PF | WR | trades |
|---|---:|---:|---:|---:|---:|---:|
| Exaustão | 8 | 3 | −20,59 | 0,55 | 33% | 24 |
| ABCD | 8 | 0 | −684,01 | 0,39 | 29% | 585 |

### M15

| Estratégia | janelas OOS | positivas | PnL total | PF | WR | trades |
|---|---:|---:|---:|---:|---:|---:|
| Exaustão | 8 | 3 | −20,00 | 0,44 | 38% | 8 |
| ABCD | 8 | 1 | −283,24 | 0,51 | 34% | 189 |

**Leitura:** os OOS positivos recentes (Exaustão M5 +23,95; ABCD M15 +19,81)
eram **sorte de regime da última semana**, não edge. No agregado de 8 semanas
não sobrepostas dos últimos 90 dias, nenhum dos dois sobrevive. O regime não
muda a conclusão: Exaustão concentrou até os trades negativos no regime trend;
ABCD é negativa em trend e range.

---

## 5. Veredito

Nenhuma das quatro candidatas P1 demonstrou **edge líquido robusto** com a
régua honesta (custos reais + split out-of-sample). O resultado confirma a
tese central do documento de recomendação: sem custos modelados e sem validação
fora da amostra, rankings anteriores mascaravam a ausência de edge.

| Candidata | Veredito | Motivo |
|---|---|---|
| VWAP Z-Score | ❌ reprovada | alvo-em-VWAP negativo; único OOS+ tem treino negativo |
| 3 Velas | ❌ negativa OOS | PF < 1 nos dois TFs |
| ABCD | ❌ refutada por walk-forward | só 0/8 (M5) e 1/8 (M15) janelas OOS positivas |
| Exaustão | ❌ refutada por walk-forward | só 3/8 janelas OOS positivas; PnL agregado negativo |

**Nada vai para paper/live.** Com 8 janelas não sobrepostas de 7 dias nos
últimos 90 dias, os OOS positivos vistos nos testes curtos eram sorte de regime
recente. A shortlist P1 está encerrada como não validada.

---

## 6. Próximos passos

1. **Rechecar Exaustão e ABCD com 90 dias + walk-forward** (não apenas 70/30),
   para descartar sorte de regime recente.
2. **Split por regime** (tendência vs. lateralização) nas candidatas ainda vivas.
3. Deixar **VWAP Z-Score e 3 Velas** arquivadas como hipóteses não validadas.
4. Nenhuma alteração em execução live nesta rodada (permanece fail-closed).
