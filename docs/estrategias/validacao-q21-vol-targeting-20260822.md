# Validação Q21 — exposição calibrada à volatilidade (vol-targeting) — 2026-08-22

> Pré-registro: [q21-vol-targeting-design-20260822.md](q21-vol-targeting-design-20260822.md)
> Script: `backend/scripts/experiment_q21_vol_targeting.py`
> Task de execução: `blt71ilkp` (exit code 0, output completo lido)

## Veredito final

**❌ REPROVADA — 0/3 variantes sobreviveram**

As três variantes passam em **participação**, **robustez temporal** e **custo** — e as
três falham no **mesmo critério** que já tinha reprovado a Q20: **preservação de
drawdown**.

---

## Dataset

- `3.293` velas 1d spot BTCUSDT, `2017-08-17 → 2026-08-22` (mesma base da Q20).
- Parse de timestamp com detecção de unidade (ms ≤ 2024-12, us ≥ 2025-01), já corrigido
  na Q20.

## Benchmark — buy & hold (mesmo período)

| Métrica | Valor |
|---|---|
| CAGR | **+37,79%** |
| Vol anualizada | +67,08% |
| Sharpe | +2,45 |
| Sortino | +3,31 |
| Total | +1.697,96% |
| Max drawdown | **83,19%** |
| Duração do drawdown | 1.073 dias |

## Variantes (sizing por vol-alvo, sem alavancagem, sem previsão direcional)

| Métrica | V1 — W30/T40 | V2 — W60/T40 | V3 — W30/T30 |
|---|---|---|---|
| CAGR líquido | +29,42% | +26,92% | +25,10% |
| CAGR bruto | +29,75% | +27,10% | +25,44% |
| Vol anualizada | +43,01% | +42,23% | +34,14% |
| Sharpe | +2,45 | +2,33 | +2,48 |
| Sortino | +3,31 | +3,11 | +3,37 |
| Max drawdown | 64,97% | 61,07% | **53,75%** |
| Duração do drawdown | 839 dias | 784 dias | 790 dias |
| Retorno total | +922,00% | +757,42% | +652,69% |
| Exposição média | 72,1% | 69,7% | 57,6% |
| Notional trocado | 46,28× | 25,64× | 49,47× |
| gross − net (pp) | 0,33 | 0,18 | 0,34 |
| Ano-máx / total | 15,9% | 18,9% | 18,5% |
| Metades positivas | 2/2 | 2/2 | 2/2 |
| Ciclos positivos | 3/3 | 3/3 | 3/3 |

## Análise contra os critérios pré-registrados

| Critério | Limiar | V1 | V2 | V3 |
|---|---|---|---|---|
| **C1** CAGR ≥ 40% do B&H | ≥ 15,12% | ✅ 29,42% | ✅ 26,92% | ✅ 25,10% |
| **C2** MaxDD ≤ 60% do B&H | ≤ 49,91% | ❌ 64,97% | ❌ 61,07% | ❌ 53,75% |
| **C3a** ano-máx < 50% do total | — | ✅ 15,9% | ✅ 18,9% | ✅ 18,5% |
| **C3b** ≥1 metade e ≥2 ciclos | — | ✅ 2/2, 3/3 | ✅ 2/2, 3/3 | ✅ 2/2, 3/3 |
| **C4** gross − net ≤ 1,0 pp | — | ✅ 0,33 | ✅ 0,18 | ✅ 0,34 |

**Veredito por variante:** ❌ ❌ ❌ — **todas falham exclusivamente no critério C2.**

## Leitura honesta do resultado

Este resultado é o mais informativo de toda a trilha, porque **confirma o mesmo gargalo
da Q20 com um mecanismo ortogonal** — e o ataca melhor, sem ainda passar:

1. **Vol-targeting reduz drawdown mais que trend-following.** O melhor trend (Q20 R3
   TSMOM) derrubou o MaxDD para 63,34%; a V3 (alvo 30%) chegou a **53,75%**. Ou seja,
   o mecanismo de *sizing* é estruturalmente mais eficaz que o de *timing* para este
   objetivo — exatamente o que a Q20 sugeria.

2. **Mas nem o alvo mais conservador passa a barra.** A V3 corta o MaxDD de 83,19% para
   53,75%, ficando ainda **3,8pp acima** do teto de 49,91%. Com exposição média de
   57,6%, continuar metade-investido num ativo que cai 73% (2018) e 64% (2022) ainda
   produz um drawdown de pico acima de 50%.

3. **A duração do drawdown quase não melhora.** B&H fica 1.073 dias debaixo d'água; as
   variantes ficam 784–839 dias. O drawdown do BTC não é só fundo — é **longo**, e o
   sizing proporcional não encurta isso de forma material.

4. **O trade-off é real e apertado.** As três variantes preservam Sharpe ≥ B&H (2,33 a
   2,48 vs 2,45) e vol muito menor (34–43% vs 67%), mas o CAGR cai para 66–78% do B&H.
   O ponto em que o alvo de vol ficaria baixo o bastante para passar C2 é aquele em que
   o CAGR provavelmente cairia abaixo de C1.

## Conclusão estrutural para a trilha

Juntando Q20 e Q21, o quadro agora é coerente e específico:

- **Timing clássico (Q20):** preserva upside, mas não tira o investidor do crash a
  tempo — MaxDD 63–67%.
- **Sizing por vol (Q21):** tira exposição quando a vol explode, reduz o MaxDD para
  54–65% — melhor que timing, mas ainda acima da barra.
- A conclusão é que **não existe, para BTC long/flat, uma combinação de regras públicas
  simples que entregue simultaneamente ≥40% do CAGR e ≤60% do MaxDD do buy-and-hold**
  na régua pré-registrada. O drawdown de BTC é fundo **e** longo demais; qualquer
  política que fique significativamente investida herda uma fração grande dele, e
  qualquer política que saia o bastante sacrifica o CAGR.

## O que isso NÃO significa

- Não invalida a Camada B (segue como canal independente — agora a única fonte com
  informação genuinamente nova no horizonte).
- Não autoriza re-tune de alvo/janela (ex.: tentar 25% de alvo para "forçar" passar C2)
  na mesma amostra — seria p-hacking explícito sobre o resultado.
- Não autoriza combinar vol-targeting com as regras da Q20 na mesma amostra para
  "achar" uma versão que passa (mesma objeção).
- Não muda o fato de que nada vai para paper/live.

## Próximo passo pré-combinado

Registrar ❌ no mapa e no resumo. A leitura honesta é que as duas famílias de regras
públicas sobre preço (timing e sizing) mapearam a fronteira real `CAGR × drawdown` do
BTC long/flat, e **nenhuma** passa a régua. O próximo passo legítimo é informação
genuinamente nova (Camada B madura, ou outro universo/venue), não mais uma reinterpretação
da mesma superfície de preço.
