# Q16 rerun — série longa (Binance Vision) — veredito — 2026-08-22

> Design pré-registrado: `q16-rerun-serie-longa-design-20260822.md` (travado
> **antes** de rodar).
> Script: `backend/scripts/experiment_q16_oi_crowded_continuation_long.py`.
> Escopo: **Camada A** histórica (2020-09-01 → 2026-08-21, ~6 anos), mesmos
> parâmetros de evento da Q16 original — só mudou fonte/profundidade dos
> dados, conforme travado no pré-registro.
> Execução: rodada duas vezes de forma independente (`bhjp5s1ni` e
> `btc0lmn3w`), resultado **idêntico** nas duas — descarta corrida de dados
> ou não-determinismo no pipeline.

## 1. Dataset

- `208.601` velas M15, `2020-09-01 00:00 → 2026-08-21 23:45`
- Funding: `6.544` linhas, mesmo range
- Fonte: Binance Vision `monthly` (klines/premiumIndexKlines/fundingRate) para
  meses fechados + API para o mês corrente parcial (2026-08); OI/ratios via
  `daily/metrics` (backfill de 2.181 dias, 0 erros)

Isso resolve, sem dado pago, o gargalo que deixou a Q16 original inconclusa.

## 2. Resultado E1 — crowded long → continuação (sinal pedido: +1)

- `n_raw = 3.783` eventos | episódios (`gap<24h`) = `538` | maior episódio =
  `47` (**1,2%** do raw, `ret_ep_maior = -0,533%`)

| Horizonte | n_indep | gross | net | ctrl_net | **marginal_net** | WR | t |
|---|---|---|---|---|---|---|---|
| 4h | 1010 | +0,018% | -0,082% | -0,078% | **-0,005%** | 47,1% | +0,41 |
| 8h (primário) | 860 | +0,034% | -0,066% | -0,056% | **-0,010%** | 49,5% | +0,53 |
| 24h | 656 | +0,144% | +0,044% | +0,033% | **+0,012%** | 49,8% | +1,16 |

Fatias (6× ~363d, primário 8h): `+0,08bp / -9,6bp / -16,5bp / +9,9bp / +0,3bp / +3,9bp`
→ 4/6 no mesmo sinal do agregado (mas o agregado é levemente negativo, então
"confirmar" aqui não confirma a hipótese pedida).

**Guardrails:** `n_ok=True` `sign_ok=False` `mag_ok=False` `conc_ok=True`
`slice_ok=True (4/6)` `cross_ok=False`

**Veredito E1: ❌ FALHA**

## 3. Resultado E2 — crowded short → continuação (sinal pedido: −1)

- `n_raw = 347` eventos | episódios (`gap<24h`) = `106` | maior episódio =
  `21` (**6,1%** do raw, `ret_ep_maior = -1,565%`)

| Horizonte | n_indep | gross | net | ctrl_net | **marginal_net** | WR | t |
|---|---|---|---|---|---|---|---|
| 4h | 130 | +0,086% | -0,014% | -0,078% | **+0,064%** | 46,9% | +0,57 |
| 8h (primário) | 124 | +0,199% | +0,099% | -0,056% | **+0,155%** | 44,4% | +1,00 |
| 24h | 111 | +0,968% | +0,868% | +0,033% | **+0,836%** | 39,6% | +2,96 |

Fatias (6× ~363d, primário 8h): `+49,7bp / +27,5bp / +2,9bp / -19,6bp / +55,9bp / -0,2bp`
→ apenas **2/6** confirmam (precisa `≥4/6`).

**Guardrails:** `n_ok=True` `sign_ok=False` `mag_ok=True (15,5bp>10bp custo)`
`conc_ok=True` `slice_ok=False (2/6)` `cross_ok=False`

**Veredito E2: ❌ FALHA**

## 4. Leitura do resultado

Com `n_indep = 860` (E1) e `n_indep = 124` (E2) — ambos muito acima do piso de
20 — este não é mais um caso de "amostra insuficiente". Conforme travado no
pré-registro, isso passa a ser **reprovação por insuficiência estrutural da
hipótese**, não mais "aguardando dado":

1. **E1 (crowded long → continuação) simplesmente não se sustenta.** O
   `+92,8bp` que apareceu na Q16 original com `n_indep=11` **não sobreviveu**
   ao aumento de amostra — no agregado de 6 anos o efeito é ~0 e sem
   coerência de sinal entre 4h/8h/24h. Isto é exatamente o tipo de falso
   positivo que a régua (`n_indep>=20`) existe para evitar, e a disciplina
   funcionou: a Q16 original corretamente recusou-se a aprovar com amostra
   pequena, e agora a amostra grande mostra que o instinto estava certo.

2. **E2 (crowded short) produziu um efeito estatisticamente chamativo — mas
   na direção contrária ao pedido.** `+83,6bp` em 24h com `t=2,96` é forte no
   sentido de "crowded short → preço **sobe**" (squeeze), não desce
   (continuação). Isso ecoa o achado original da Q15 (crowded long também
   "continuou" para cima em vez de fazer unwind) — sugerindo um padrão mais
   geral de **squeeze do lado apinhado**, independente da direção do
   crowding.

3. **Mas essa leitura de squeeze em E2 não passa nos próprios guardrails da
   trilha:** só `2/6` fatias confirmam, ou seja, o efeito agregado é
   dominado por 2-3 janelas específicas (prováveis squeezes de bull run
   2024-2026), não é um padrão estável através de regimes. Tratá-lo como
   edge agora, sem pré-registro e teste out-of-sample dedicados, seria
   exatamente o erro que a Q12 já ensinou a não cometer (concentração
   temporal disfarçada de robustez).

## 5. Veredito final

**Q16 (OI crowded continuation) está ❌ REPROVADA**, com amostra grande e
suficiente nos dois braços (E1 e E2). Não há mais bloqueio de dado a
resolver nesta hipótese — a resposta é definitiva na Camada A.

Não é necessário buscar provedor pago de dado histórico: o dump gratuito da
Binance Vision (~6 anos) já foi suficiente para decidir a hipótese com
`n_indep` muito acima do piso da régua.

## 6. Achado incidental (não promovido, só registrado)

O padrão "squeeze do lado crowded" (E2 desta rodada + o achado original da
Q15) é interessante o bastante para virar uma hipótese **nova e
pré-registrada** no futuro — mas com sinal invertido do que Q15/Q16 testaram
(squeeze, não continuação) e com um desenho que penalize concentração
temporal antes de rodar (ex.: exigir `≥4/6` fatias já no pré-registro, ou
excluir explicitamente o horizonte 24h que é o mais sujeito a picos de
regime). Isso é trabalho para uma eventual Q17, não uma reabertura da Q16.

## 7. Consequência prática

- A frente **"OI crowded continuation"** está encerrada — mesma sorte de Q5,
  Q6, Q7, Q8, Q9, Q10, Q11, Q12, Q14 e (na formulação original) Q15.
- A Camada B (`collect_snapshot.py`, cron 15min) **continua rodando**: não
  como bloqueio de amostra para a Q16 (que já foi resolvida na Camada A),
  mas como canal independente/out-of-sample para validar qualquer hipótese
  nova que a Camada A histórica sugerir daqui pra frente (inclusive a
  possível Q17 de squeeze).
- **Nada vai para paper/live.** Nenhum parâmetro do evento foi re-tunado
  após ver o resultado — o pré-registro foi seguido à risca.
