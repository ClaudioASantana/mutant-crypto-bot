# Validação Q20 — trend participation lenta em BTC (long/flat diário) — 2026-08-22

> Pré-registro: [q20-trend-participation-design-20260822.md](q20-trend-participation-design-20260822.md)
> Script: `backend/scripts/experiment_q20_trend_participation.py`
> Tasks de execução: `b3hp26lp7` (exit 1 — bug de parse), `bxpslm7gy` (exit 0 — dataset truncado), `b2kd03iy6` (exit 0 — válida)

## Veredito final

**❌ REPROVADA — 0/3 regras sobreviveram**

As três regras passam em **participação**, **robustez temporal** e **custo** — e as
três morrem no **mesmo critério**: preservação de drawdown.

---

## Dataset

- `3.293` velas 1d spot BTCUSDT, `2017-08-17 → 2026-08-22` (~9 anos, 3 ciclos
  bull/bear completos).

## Bug corrigido antes do veredito (registro de honestidade)

A primeira execução (`b3hp26lp7`) morreu com `OutOfBoundsDatetime`, e a segunda
(`bxpslm7gy`) terminou "bem" mas com dataset truncado (`599` velas a partir de
`2025-01-01`). Causa: os arquivos mensais de klines spot da Binance Vision mudaram
o formato de timestamp em **2025-01**:

- `<= 2024-12` → `open_time` em **milissegundos** (13 dígitos, ex. `1502928000000`);
- `>= 2025-01` → `open_time` em **microssegundos** (16 dígitos, ex. `1735689600000000`).

O parse por magnitude foi corrigido (detecção de unidade por arquivo) antes da
execução válida. **Nenhuma regra, janela, custo ou critério foi alterado.** As duas
execuções anteriores foram descartadas por não representarem a amostra pré-registrada.

---

## Benchmark — buy & hold (mesmo período)

| Métrica | Valor |
|---|---|
| CAGR | **+37,79%** |
| Vol anualizada | +67,08% |
| Sharpe | +2,45 |
| Sortino | +3,31 |
| Total | +1.697,82% |
| Max drawdown | **83,19%** |
| Duração do drawdown | 1.073 dias |

## Regras (todas long/flat, custo 10bp round-trip por flip)

| Métrica | R1 — SMA200 | R2 — Golden Cross | R3 — TSMOM 12-1 |
|---|---|---|---|
| CAGR líquido | +24,92% | +17,82% | +33,27% |
| CAGR bruto | +25,37% | +17,93% | +33,55% |
| Vol anualizada | +41,56% | +46,20% | +48,37% |
| Sharpe | +2,23 | +1,78 | +2,52 |
| Sortino | +2,22 | +1,65 | +2,58 |
| Max drawdown | 63,69% | 66,75% | 63,34% |
| Duração do drawdown | 1.050 dias | 1.050 dias | 731 dias |
| Retorno total | +642,97% | +338,31% | +1.230,97% |
| Tempo em mercado | 48,5% | 48,7% | 57,9% |
| Flips | 65 | 18 | 38 |
| gross − net (pp) | 0,45 | 0,12 | 0,28 |
| Ano-máx / total | 27,2% | 32,3% | 14,6% |
| Metades positivas | 2/2 | 2/2 | 2/2 |
| Ciclos positivos | 3/3 | 3/3 | 2/3 |

## Análise contra os critérios pré-registrados

| Critério | Limiar | R1 | R2 | R3 |
|---|---|---|---|---|
| **C1** CAGR ≥ 40% do B&H | ≥ 15,12% | ✅ 24,92% | ✅ 17,82% | ✅ 33,27% |
| **C2** MaxDD ≤ 60% do B&H | ≤ 49,91% | ❌ 63,69% | ❌ 66,75% | ❌ 63,34% |
| **C3a** ano-máx < 50% do total | — | ✅ 27,2% | ✅ 32,3% | ✅ 14,6% |
| **C3b** ≥1 metade e ≥2 ciclos | — | ✅ 2/2, 3/3 | ✅ 2/2, 3/3 | ✅ 2/2, 2/3 |
| **C4** gross − net ≤ 1,0 pp | — | ✅ 0,45 | ✅ 0,12 | ✅ 0,28 |

**Veredito por regra:** ❌ ❌ ❌ — **todas falham exclusivamente no critério C2.**

## Leitura honesta do resultado

Este é o resultado mais informativo da trilha até aqui, porque é **limpo e
direcionalmente específico**:

1. **Participação funciona.** As três regras preservaram entre 47% e 88% do CAGR do
   buy-and-hold (R3 TSMOM ficou em +33,27% vs +37,79% — 88% do upside), com vol menor
   e Sharpe comparável ou melhor (R3: 2,52 vs 2,45).

2. **Robustez temporal funciona.** Todas as regras foram positivas nas duas metades e
   em ≥2/3 dos ciclos; nenhum ano responde por mais de 33% do retorno. Não é
   fenômeno de janela única.

3. **Custo é irrelevante.** O custo por flip drena no máximo 0,45pp de CAGR — a
   rotatividade baixa faz exatamente o que foi previsto.

4. **Mas a promessa central — corte de drawdown — não se cumpre.** O max drawdown
   caiu de 83,19% para 63–67%, ou seja, as regras só reduziram ~19–24% da profundidade
   do drawdown, muito longe dos 40% exigidos. O SMA200 e o Golden Cross deixam o
   drawdown **também** durar ~1.050 dias, praticamente igual ao buy-and-hold (1.073).

A conclusão estrutural é esta: **trend-following clássico em BTC, na granularidade
diária e com regras padrão da literatura, não entrega o seu benefício-assinatura** —
que é evitar o drawdown catastrófico. O que ele entrega é uma *suavização parcial da
volatilidade* (vol cai, Sharpe sobe levemente), mas o investidor continua exposto a um
drawdown de ~64% no pior momento. Para uma regra que exige aceitar CAGR menor, essa
troca não fecha pelos critérios pré-registrados.

---

## Conclusão para a trilha

1. A mudança de lente (event study → curva de equity) foi **metodologicamente
   correta e produtiva**: produziu um veredito nítido, não uma nebulosa de `bp`.
2. A hipótese "regras lentas e públicas de tendência preservam upside e cortam
   drawdown materialmente" está **refutada** para este setup (BTC spot 1d, long/flat,
   sem short, sem stop otimizado, sem grid de parâmetros).
3. O fracasso é **específico**: não é "trend-following não funciona", é "a versão
   clássica diária não corta drawdown o suficiente em BTC para justificar abrir mão de
   CAGR". Isso é informação nova e útil.

## O que isso NÃO significa

- Não invalida a Camada B (segue como canal independente para hipóteses futuras).
- Não autoriza re-tune de SMA50/SMA200/12-1, nem adicionar stop/trailing/short pós-hoc
  na mesma amostra (seria p-hacking sobre o resultado).
- Não muda o fato de que nada vai para paper/live.
- Não diz que o momentum de cripto é inexistente — diz que, nesta régua de
  *preservação de capital*, a formulação diária long/flat não passa.

## Próximo passo pré-combinado

Registrar ❌ no mapa e no resumo, e manter a disciplina: só abrir uma nova frente se
ela trouxer **informação nova** (OI/flow próprios, squeeze em amostra nova, outro
venue/universo) — em vez de reinterpretar o mesmo resultado ou retunar a mesma regra.
