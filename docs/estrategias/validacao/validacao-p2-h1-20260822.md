# Validação P2 — H1 (filtros de sessão/ATR/regime) — 2026-08-22

> Status: **H1 reprovada**. Nenhuma estratégia admitida. Segue para H2
> (breakout de regime), conforme ordem de execução em
> [recomendacoes-p2-crypto-20260822.md](recomendacoes-p2-crypto-20260822.md).

## 1. Hipótese testada

> "Se o prejuízo vem de operar horas mortas e volatilidade comprimida,
> restrita a M15 e janelas de liquidez, as estratégias existentes deveriam
> melhorar."

Overlay puro sobre o zoo já reprovado em P1 (Exaustão, ABCD, 3 Velas,
VWAP Z-Score), sem alterar o sinal:

- `filter_session_utc` — só permite entrada no overlap Londres/NY (12h–17h UTC);
- `filter_atr_percentile` — exige ATR no percentil [0.40, 0.90] das últimas 100 velas;
- `filter_regime_adx` — exige `ADX_14 >= 25` (regime de tendência).

Protocolo idêntico ao que refutou P1: BTCUSDT M15, walk-forward de 90 dias,
8 janelas OOS de 7 dias (passo 7d), warmup 30d, custos
`fee_rate=0.0004 + slippage_bps=1.0`. Critério de admissão: ≥5/8 janelas OOS
positivas **e** PnL agregado > 0 **e** PF > 1,3.

Fonte: `backend/scripts/experiment_h1_filters.py`.

## 2. Resultado

| Estratégia | baseline (sem H1) folds+ | baseline PnL | com H1 folds+ | com H1 PnL | com H1 PF | com H1 trades | Veredito |
|---|---:|---:|---:|---:|---:|---:|---|
| Exaustão | 3/8 | −20,00 | 0/8 | 0,00 | 0,00 | **0** | ❌ reprovada |
| ABCD | 1/8 | −283,24 | 2/8 | −14,67 | 0,26 | 7 | ❌ reprovada |
| 3 Velas | 1/8 | −132,70 | 1/8 | −2,48 | 0,67 | 3 | ❌ reprovada |
| VWAP Z-Score | 3/8 | −30,33 | 1/8 | +3,40 | 99,00 | **1** | ❌ reprovada |

(PF "99,00" é a sentinela do módulo de métricas para "sem perdedor na
amostra" — não profit factor real; a amostra é de 1 trade.)

## 3. Leitura

1. **Os filtros não resgatam edge — eles removem amostra.** A janela de
   sessão (12h–17h UTC) sozinha já corta a maior parte dos candles elegíveis
   em M15; somada a ADX≥25 e ATR em banda média, a interseção é rara. Exaustão
   (que já era seletiva) foi a **zero trades** nas 8 janelas OOS inteiras.
2. **PnL "menos negativo" é operar menos, não operar melhor.** ABCD e 3 Velas
   passam de centenas de trades ruins para poucos trades também ruins (PF
   ainda < 1). Não há nenhum caso em que os filtros viraram PF de perdedor
   para consistentemente vencedor.
3. **VWAP Z-Score com H1 deu +3,40 em 1 trade** — não é evidência de nada;
   é ruído de amostra ínfima, exatamente o mesmo erro metodológico que a
   régua de walk-forward foi desenhada para evitar (ver P1, seção 4).
4. Nenhuma candidata chega perto de 5/8 janelas positivas — o número máximo
   observado com H1 ligado foi 2/8 (ABCD).

## 4. Veredito

**H1 morre com evidência**, conforme previsto no documento de recomendação:
> "Se nada melhorar, o problema é o sinal, não o horário."

O prejuízo das candidatas P1 não vem de operar em horário/regime/volatilidade
errados — vem do próprio sinal de entrada não ter edge líquido depois de
custos. Filtrar sessão/ATR/ADX sobre um sinal sem edge produz **menos trades
sem edge**, não trades com edge.

## 5. Próximo passo

Conforme a ordem de execução aprovada: implementar **H2** (breakout de
regime — Donchian 55 + ADX + banda de ATR) do zero em M15/H1, com o mesmo
protocolo de validação. H3 (funding rate) só entra se H2 sobreviver ao
walk-forward.

**Nada promovido para paper/live nesta rodada.**
