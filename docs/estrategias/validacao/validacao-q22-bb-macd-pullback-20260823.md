# Validação Q22 — pullback em tendência com BB + MACD — 2026-08-23

> Pré-registro: [q22-bb-macd-pullback-design-20260822.md](q22-bb-macd-pullback-design-20260822.md)
> Script: `backend/scripts/experiment_q22_bb_macd_pullback.py`
> Task de execução: `bhadlgpsc` (exit code 0, output completo lido)

## Veredito final

**❌ REPROVADA — 0/3 variantes sobreviveram**

A leitura visual foi convertida honestamente para regras objetivas de pullback +
retomada com BB/MACD, mas a família falhou de forma ainda mais dura do que Q19:

1. o sinal bruto é inexistente ou fraco;
2. a formulação em 15m ficou **hiper-rotativa**;
3. o custo destrói completamente a curva.

---

## Dataset

- `315.549` velas 15m spot BTCUSDT, `2017-08-17 04:00 → 2026-08-22 23:30`.

## Benchmark — buy & hold (mesmo período)

| Métrica | Valor |
|---|---|
| CAGR | **+37,87%** |
| Vol anualizada | +73,99% |
| Sharpe | +2,41 |
| Sortino | +2,92 |
| Total | +1.707,68% |
| Max drawdown | **83,97%** |
| Duração do drawdown | 1.079 dias |

## Variantes testadas

| Métrica | P1 — Midline Reclaim | P2 — Trend Pullback | P3 — Exhaustion Exit |
|---|---|---|---|
| CAGR líquido | **-71,98%** | **-58,91%** | **-12,63%** |
| CAGR bruto | -14,81% | -1,28% | +1,41% |
| Vol anualizada | +21,80% | +13,55% | +6,75% |
| Sharpe | -17,20 | -19,51 | -5,91 |
| Sortino | -8,89 | -7,68 | -1,23 |
| Max drawdown | 100,00% | 99,97% | 71,08% |
| Duração do drawdown | 3.292 dias | 3.289 dias | 3.033 dias |
| Retorno total | -100,00% | -99,97% | -70,39% |
| Tempo em mercado | 9,9% | 4,6% | 1,4% |
| Flips | **20.040** | **15.794** | **2.686** |
| gross − net (pp) | **57,17** | **57,62** | **14,04** |
| Ano-máx / total | 0,0% | 0,0% | 0,0% |
| Metades positivas | 0/2 | 0/2 | 0/2 |
| Ciclos positivos | 0/3 | 0/3 | 0/3 |

## Leitura honesta do resultado

### 1. O problema principal não é “quase passou e o custo matou”

Aqui a mensagem é mais dura do que em Q5/Q9/Q19.

- **P1**: nem bruto funciona (`CAGR_gross = -14,81%`)
- **P2**: bruto quase zera (`CAGR_gross = -1,28%`)
- **P3**: bruto mal fica positivo (`CAGR_gross = +1,41%`)

Ou seja: mesmo **antes** do custo, a formulação objetiva da leitura visual não gera
continuação forte e limpa o bastante para sustentar uma estratégia real.

### 2. O custo torna tudo catastrófico

A família ficou **hiper-rotativa** em 15m:

- P1: `20.040` flips
- P2: `15.794` flips
- P3: `2.686` flips

Com custo de 10bp round-trip por flip, isso cria erosão gigantesca:

- P1: `gross − net = 57,17pp`
- P2: `gross − net = 57,62pp`
- P3: `gross − net = 14,04pp`

A leitura visual parecia selecionar poucos pontos bonitos. A regra objetiva, na série
longa, acabou entrando em milhares de **micro-retomadas locais** que não têm margem
suficiente para pagar 15m + custo.

### 3. A banda média e o MACD não estão isolando um regime “limpo”

O que a imagem mostrava como:
- pullback controlado,
- retomada limpa,
- saída por exaustão,

na prática vira, na amostra longa:
- muita rotação em chop;
- muita retomada fraca que não evolui;
- muitas saídas curtas demais;
- alto número de reentradas.

Em outras palavras: a leitura visual pode funcionar em alguns trechos selecionados, mas
**não se traduz em regra robusta** com esta formulação objetiva.

---

## Conclusão estrutural para a trilha

A Q22 fecha uma porta importante:

- Q19 já havia mostrado que **BB squeeze + MACD** não sobrevive;
- Q22 agora mostra que a leitura alternativa mais generosa para o setup visual —
  **pullback + midline reclaim + reaceleração de MACD** — também não sobrevive,
  e morre de forma pior: sem alpha bruto relevante e com custo devastador.

Isso reforça uma conclusão dura mas honesta:

> na superfície pública de preço de BTC, em 15m, **nem squeeze/expansão nem
> pullback/retomada com BB + MACD** conseguiram produzir edge líquido robusto.

## O que isso NÃO significa

- Não significa que ninguém nunca consiga ganhar dinheiro olhando um gráfico.
- Significa que **a tradução objetiva e replicável** dessa leitura visual **não passou**.
- Não autoriza re-tune de thresholds, banda, MACD ou filtros na mesma amostra.
- Não muda o fato de que nada vai para paper/live.

## O que aprendemos com a imagem do usuário

A imagem foi útil. Ela não revelou edge, mas revelou uma coisa metodologicamente
importante:

- a leitura visual do usuário **não era** “squeeze puro”;
- era “**retomada após reset local**”.

Isso merecia teste separado, e agora foi testado. O resultado foi **negativo**.

## Próximo passo honesto

Registrar ❌ no mapa e no resumo. Depois de Q20, Q21 e Q22, a trilha já espremeu:

- trend-following diário por timing;
- sizing por volatilidade;
- tática 15m por BB + MACD em squeeze;
- tática 15m por BB + MACD em pullback/retomada.

A próxima frente séria precisa de **informação nova**, não de mais variações sobre a
mesma superfície pública de preço do BTC.
