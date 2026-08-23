# Q10 — Cross-sectional momentum com funding confirmation — veredito do event study — 2026-08-22

> Design pré-registrado: `q10-funding-confirmed-momentum-design-20260822.md`.
> Script: `backend/scripts/experiment_q10_funding_confirmed_momentum.py`.
> Hipótese: adicionar confirmação de funding ao momentum cross-sectional da Q9
> aumentaria a magnitude do efeito, preservando o sinal direcional.

## 1. Resultado do par primário (RICH_F/CHEAP_F × 4h × M15)

Amostra:
- sem funding (Q9 baseline):
  - `RICH_Q9 = 2.668`
  - `CHEAP_Q9 = 2.653`
- com funding confirmation:
  - `RICH_F = 128`
  - `CHEAP_F = 203`

Par primário — 4h:
- **RICH_F**:
  - `n = 128`
  - retorno relativo médio: `+0,00037`
  - marginal vs controle: `+0,00037`
  - sinal **correto**
  - magnitude **maior que Q9** no lado RICH (`+0,00037` vs `+0,00004`)
- **CHEAP_F**:
  - `n = 203`
  - retorno relativo médio: `-0,00010`
  - marginal vs controle: `-0,00010`
  - sinal **correto**
  - magnitude **menor que Q9** no lado CHEAP (`-0,00010` vs `-0,00020`)

## 2. Veredito pré-registrado

**❌ FALHA.**

Critérios:
- `n_ok = True`
- `sign_ok = True`
- `mag_ok = False`
- `bigger_than_q9 = False`

A hipótese caiu por dois motivos principais:

1. **Magnitude ainda muito abaixo do custo piso de 20bp**
   - RICH_F: `+3,7bp`
   - CHEAP_F: `-1,0bp`
   - custo relativo mínimo: `20bp`

2. **O filtro não melhorou os dois lados**
   - melhorou bem o lado **RICH**;
   - piorou o lado **CHEAP**;
   - portanto não entregou um ganho estrutural limpo sobre a Q9.

## 3. Leitura correta

Q10 é uma refutação útil porque separa dois efeitos:

### A. Funding confirmation parece **ajudar** no lado RICH
Sem funding:
- RICH Q9 em 4h: `+0,00004`

Com funding confirmado:
- RICH_F em 4h: `+0,00037`

Isso sugere que quando o nome está rich **e** pagando funding positivo, a leitura
"crowding que continua empurrando" faz mais sentido.

### B. Funding confirmation **não ajuda** no lado CHEAP
Sem funding:
- CHEAP Q9 em 4h: `-0,00020`

Com funding confirmado:
- CHEAP_F em 4h: `-0,00010`

Além disso, o lado CHEAP confirmado ficou inconsistente em outros horizontes:
- em **1h**, sinal contrário;
- em **8h**, sinal contrário;
- em **24h**, volta a ficar levemente negativo, mas ainda pequeno demais.

Ou seja:
> o filtro de funding **não generaliza** simetricamente entre crowded longs e
> crowded shorts.

## 4. Interpretação econômica

Q10 não zerou a hipótese — ela a **particionou**:
- "momentum com funding confirmation" como regra geral falha;
- mas o subcaso **RICH + funding positivo** parece mais promissor do que o resto.

Mesmo esse subcaso, porém, continua economicamente insuficiente:
- o efeito sobe de ~0,4bp para ~3,7bp em 4h;
- ainda assim fica muito abaixo dos `20bp` exigidos pela estrutura relativa.

Então a conclusão metodologicamente correta é:
> existe possivelmente um **sinal mais concentrado do lado crowded-long**,
> mas ainda não existe **edge líquido robusto**.

## 5. Encerramento

Q10 está encerrada como **reprovada**.
Nada vai para paper/live.
Nenhuma estratégia é promovida.

## 6. Placar consolidado

- P1: reprovada
- H1: reprovada
- H2: reprovada
- H3: reprovada
- Q3: reprovada
- Q5: reprovada
- Q6: reprovada
- Q7: reprovada
- Q8: reprovada
- Q9: reprovada
- Q10: reprovada

## 7. O que aprendemos com Q10

Q10 não entregou edge, mas refinou bastante o mapa:
- a família cross-sectional parece **mais promissora no lado rich/crowded-long**;
- o lado cheap/crowded-short é mais instável;
- se houver algo a perseguir nessa família, faz mais sentido focar em:
  - apenas o lado **RICH**;
  - horizontes mais longos (8h/24h);
  - ou um universo onde o crowding positivo seja mais pronunciado.

Mas isso já seria uma hipótese nova, não continuação automática desta.