# Validação Q17 — taker flow imbalance — 2026-08-22

> Pré-registro: [q17-taker-flow-imbalance-design-20260822.md](q17-taker-flow-imbalance-design-20260822.md)
> Script: `backend/scripts/experiment_q17_taker_flow_imbalance.py`
> Task de execução: `bb69x7aea` (exit code 0, output completo lido)

## Veredito final

**❌ REPROVADA — E1 e E2**

Nenhum dos dois braços passou os guardrails pré-registrados. Ambos falharam
em sinal, magnitude, fatias e coerência cross-horizonte simultaneamente.

---

## Dataset

- `208.601` velas M15, `2020-09-01 00:00 → 2026-08-21 23:45` (idêntico à Q16-longa — confirma reuso correto da ingestão)
- Funding: `6.544` linhas
- Eventos E1 (`taker_pct >= 0.90`): `32.098`
- Eventos E2 (`taker_pct <= 0.10`): `19.640`

## E1 — taker buy imbalance extremo → continuação de alta (sinal pedido +1)

- Episódios (gap<24h) = 26, maior episódio = 13.553 eventos (**42,2%** do raw)

| Horizonte | n_indep | gross | net | ctrl_net | marginal_net | WR | t |
|---|---|---|---|---|---|---|---|
| 4h | 8.278 | +0,00003 | -0,00097 | -0,00078 | **-0,00019** | 51,0% | +0,27 |
| 8h (primário) | 4.979 | +0,00007 | -0,00093 | -0,00056 | **-0,00037** | 51,2% | +0,30 |
| 24h | 1.972 | +0,00107 | +0,00007 | +0,00033 | **-0,00026** | 51,6% | +1,63 |

Fatias 8h (6x ~363d), `marginal_net`:
`-0,00097 / -0,00011 / -0,00014 / -0,00083 / -0,00019 / +0,00013` → só **1/6** no sentido pedido (positivo).

**Veredito:** `n_ok=True sign_ok=False mag_ok=False conc_ok=True slice_ok=False cross_ok=False` → **❌ FALHA**
`n_indep=4979 marginal_net=-3,7bp conc_ep=42,2% fatias=1/6`

## E2 — taker sell imbalance extremo → continuação de baixa (sinal pedido -1)

- Episódios (gap<24h) = 27, maior episódio = 2.244 eventos (**11,4%** do raw)

| Horizonte | n_indep | gross | net | ctrl_net | marginal_net | WR | t |
|---|---|---|---|---|---|---|---|
| 4h | 7.435 | +0,00024 | -0,00076 | -0,00078 | **+0,00002** | 48,7% | +1,74 |
| 8h (primário) | 4.573 | +0,00051 | -0,00049 | -0,00056 | **+0,00007** | 49,0% | +2,04 |
| 24h | 1.840 | +0,00186 | +0,00086 | +0,00033 | **+0,00053** | 47,5% | +2,62 |

Fatias 8h (6x ~363d), `marginal_net`:
`+0,00061 / +0,00005 / +0,00031 / -0,00037 / -0,00066 / +0,00009` → **2/6** no sentido pedido.

**Veredito:** `n_ok=True sign_ok=False mag_ok=False conc_ok=True slice_ok=False cross_ok=False` → **❌ FALHA**
`n_indep=4573 marginal_net=+0,7bp conc_ep=11,4% fatias=2/6`

> Nota sobre E2: `sign_ok=False` porque o sinal pedido era **-1** (continuação de baixa) e
> `marginal_net` saiu **positivo** — ou seja, o resultado é literalmente o oposto do que a
> hipótese pedia, ainda que a magnitude (`+0,7bp`) seja irrelevante frente ao custo.

---

## Leitura

1. **Amostra não é o problema.** `n_indep` no primário ficou em 4.979 (E1) e 4.573 (E2) —
   muito acima do piso de 20. A reprovação é estrutural, não por falta de dado.
2. **Sinal isolado de taker flow não carrega informação direcional útil.** Mesmo sem
   exigir confirmação de OI/funding/premium (deliberadamente, para isolar a variável),
   o efeito ficou próximo de zero e instável entre fatias — ambos os braços tiveram
   coerência cross-horizonte nula (`cross_ok=False` nos dois).
3. **E1 é o mais claramente morto**: 5/6 fatias fora do sentido pedido, `marginal_net`
   negativo em 4h e 8h.
4. **E2 é ruído, não squeeze.** O sinal (`+0,7bp` em 8h) é economicamente irrelevante —
   muito abaixo do custo de 10bp — e não deve ser lido como confirmação da hipótese de
   squeeze da [Q18](q18-squeeze-crowded-side-design-20260822.md); aquele pré-registro
   continua bloqueado e usa uma definição de evento diferente (combinação de
   `ret_lb`+OI+funding+premium, não taker flow isolado).
5. **Consequência para a trilha:** confirma a leitura do mapa de decisões — preço,
   funding, basis, OI público **e agora também taker flow público**, isolados, não bastam
   para gerar edge líquido robusto neste setup. Reforça o peso das fronteiras que exigem
   informação genuinamente nova (Camada B independente, outro venue/universo).

## O que isso NÃO significa

- Não invalida a Q18 (squeeze) — evento e amostra diferentes, ainda não testada.
- Não é evidência de que taker flow seja inútil combinado com outras variáveis —
  apenas que, isolado e nesta forma de evento (percentil extremo rolante de 4 dias),
  não sobrevive aos guardrails.
- Nada muda quanto a paper/live: continua nada indo para lá.
