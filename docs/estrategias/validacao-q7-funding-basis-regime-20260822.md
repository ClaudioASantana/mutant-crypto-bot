# Q7 — Funding / basis regime persistence — veredito do study — 2026-08-22

> Design pré-registrado: `q7-funding-basis-regime-design-20260822.md`.
> Script: `backend/scripts/experiment_q7_regime_persistence.py`.
> Hipótese: regimes persistentes de funding + basis no mesmo lado poderiam
> carregar informação econômica útil além de um evento isolado.

## 1. Resultado bruto

### M15 (primário)
- funding events na janela: `270`
- regimes válidos R+: `4`
- regimes válidos R−: `1`

#### R+
- duração mediana: `4` funding events
- carry bruto médio: `+0,00022`
- carry líquido upper-bound: `-0,00078`
- retorno underlying por regime: média `-0,0081`
- retorno por 8h: `-0,00272` vs controle `+0,00015`

#### R−
- duração mediana: `3` funding events
- carry bruto médio: `+0,00008`
- carry líquido upper-bound: `-0,00092`
- retorno underlying por regime: `-0,0218`
- retorno por 8h: `-0,00727` vs controle `+0,00015`

### H1 (secundário)
- regimes válidos R+: `2`
- regimes válidos R−: `1`

Também aqui o carry líquido upper-bound permanece negativo.

## 2. Veredito pré-registrado

**❌ FALHA.**

A hipótese caiu por dois motivos independentes:

1. **Amostra muito pequena**
   - critério exigia `n >= 30` regimes por lado;
   - observamos apenas `4` regimes R+ e `1` regime R− em M15.

2. **Carry líquido ainda negativo**
   - mesmo quando o regime persiste por 3–4 fundings,
   - o funding acumulado médio continua muito menor que o custo mínimo de 10bp.

## 3. Leitura correta

Isso é um resultado útil:
- existe, sim, ocorrência de períodos persistentes de crowding no mesmo lado;
- mas eles são **raros** na janela observada;
- e, mesmo quando aparecem, o carry acumulado simples ainda não paga a conta.

No lado R+, o retorno do underlying durante o regime foi negativo em média, o
que é coerente com a intuição de crowded longs perdendo ar. Mas isso por si só
não salva a hipótese, porque:
- a amostra é pequena demais para promover robustez;
- e o componente de carry continua economicamente insuficiente.

## 4. Encerramento

Q7 está encerrada como **reprovada**.
Nada vai para paper/live.
Nenhuma estratégia é promovida.

## 5. Placar consolidado

- P1: reprovada
- H1: reprovada
- H2: reprovada
- H3: reprovada
- Q3: reprovada
- Q5: reprovada
- Q6: reprovada
- Q7: reprovada

A mensagem agregada até aqui é forte:
- nem TA clássica,
- nem basis extremo direcional,
- nem carry curto,
- nem regime persistente simples

mostraram edge líquido robusto neste setup.

Isso é duro, mas extremamente valioso: estamos fechando portas erradas rápido e
com honestidade metodológica.