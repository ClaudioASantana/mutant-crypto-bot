# Validação Q19 — volatility compression breakout (BB squeeze + MACD) — 2026-08-22

> Pré-registro: [q19-volatility-compression-breakout-design-20260822.md](q19-volatility-compression-breakout-design-20260822.md)
> Script: `backend/scripts/experiment_q19_volatility_compression_breakout.py`
> Task de execução: `btrxrrhzw` (exit code 0, output completo lido)

## Veredito final

**❌ REPROVADA — E1 e E2**

Nenhum dos dois braços passou os guardrails pré-registrados. E1 morreu por sinal
na direção errada; E2 mostrou um efeito *fraco* e direcionalmente consistente no
curto prazo, mas abaixo do custo e sem coerência cross-horizonte.

---

## Dataset

- `58.223` velas H1, `2020-01-01 00:00 → 2026-08-22 22:00` (~6,7 anos — inclui
  2020-01→2020-09, amostra nunca usada pelos experimentos ancorados no `metrics_long.csv`).
- Eventos E1 (compressão + MACD positivo): `3.217`
- Eventos E2 (compressão + MACD negativo): `3.532`

## E1 — compressão + MACD positivo → expansão de alta (sinal pedido +1)

- Episódios (gap<24h) = 385, maior = 1,2% do raw (concentração ok)

| Horizonte | n_indep | gross | net | ctrl_net | marginal_net | WR | t |
|---|---|---|---|---|---|---|---|
| 4h | 1.083 | -0,00023 | -0,00123 | -0,00075 | **-0,00048** | 49,7% | -0,80 |
| 8h (primário) | 733 | -0,00023 | -0,00123 | -0,00051 | **-0,00072** | 50,1% | -0,40 |
| 24h | 473 | +0,00043 | -0,00057 | +0,00047 | **-0,00104** | 49,9% | +0,31 |

Fatias 8h (6x ~404d), `marginal_net`:
`-0,00049 / +0,00093 / -0,00255 / -0,00075 / -0,00119 / +0,00025` → **2/6** no sentido pedido.

**Veredito:** `n_ok=True sign_ok=False mag_ok=False conc_ok=True slice_ok=False cross_ok=False` → **❌ FALHA**
`n_indep=733 marginal_net=-7,2bp conc_ep=1,2% fatias=2/6`

> Leitura: compressão com MACD positivo foi seguida de retorno forward **levemente
> negativo** vs. controle em todos os horizontes. Não é ausência de efeito — é efeito
> na direção **oposta** à hipótese.

## E2 — compressão + MACD negativo → expansão de baixa (sinal pedido -1)

- Episódios (gap<24h) = 417, maior = 1,2% do raw (concentração ok)

| Horizonte | n_indep | gross | net | ctrl_net | marginal_net | WR | t |
|---|---|---|---|---|---|---|---|
| 4h | 1.170 | +0,00003 | -0,00097 | -0,00075 | **-0,00021** | 46,1% | +0,11 |
| 8h (primário) | 775 | -0,00000 | -0,00100 | -0,00051 | **-0,00049** | 47,6% | -0,01 |
| 24h | 515 | +0,00211 | +0,00111 | +0,00047 | **+0,00064** | 44,9% | +1,71 |

Fatias 8h (6x ~404d), `marginal_net`:
`-0,00032 / -0,00007 / -0,00051 / -0,00062 / -0,00210 / +0,00045` → **5/6** no sentido pedido.

**Veredito:** `n_ok=True sign_ok=True mag_ok=False conc_ok=True slice_ok=True cross_ok=False` → **❌ FALHA**
`n_indep=775 marginal_net=-4,9bp conc_ep=1,2% fatias=5/6`

> Leitura honesta: E2 tem o sinal certo em 4h/8h e **5/6 fatias** no primário, mas a
> magnitude é de **-4,9bp vs. controle**, metade do custo de 10bp — e inverte no 24h
> (`+6,4bp`), quebrando a coerência cross-horizonte. É o mesmo padrão já visto em Q5/Q9:
> **sinal real, pequeno demais para virar edge líquido**.

---

## Conclusão para a trilha

1. A formulação mais limpa de **BB squeeze + MACD** não sobreviveu aos guardrails.
2. E1 refuta a direção "compressão + momentum positivo → alta": o efeito veio fraco e
   levemente contrário.
3. E2 confirma um efeito **direcional de baixa** após compressão com MACD negativo, mas
   de magnitude insuficiente (`~5bp < 10bp`) e não persistente no horizonte mais longo.
4. Isso reforça — agora também para a família clássica de TA em superfície de preço
   pública — a conclusão central da trilha: **sinal estatístico ≠ edge líquido**.

## O que isso NÃO significa

- Não invalida a Camada B (que segue como canal independente para hipóteses futuras).
- Não autoriza re-tune de `COMPRESSION_Q`/`PCT_WINDOW` na mesma amostra (seria p-hacking).
- Não muda o fato de que nada vai para paper/live.

## Próximo passo pré-combinado

Conforme o plano: registrar ❌ e, se for retomar a família de TA, abrir a formulação de
**pullback em tendência** (Q20) — trend filter + entrada na banda — em vez de insistir em
variar limiar de percentil da mesma amostra.
