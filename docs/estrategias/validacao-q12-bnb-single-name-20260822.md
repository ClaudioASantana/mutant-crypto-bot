# Q12 — BNBUSDT single-name rich+ study — veredito do event study — 2026-08-22

> Design pré-registrado: `q12-bnb-single-name-design-20260822.md`.
> Script: `backend/scripts/experiment_q12_bnb_single_name.py`.
> Hipótese: o resultado da Q11 talvez fosse um micro-edge real de **BNBUSDT rich + funding positivo**, e não apenas uma curiosidade do basket.

## 1. Resultado bruto

Amostra total:
- eventos BNB RICH+: `128`
- episódios (gap <24h): `12`
- distribuição por episódio: `[21, 17, 15, 13, 12, 12, 8, 8, 8, 5, 5, 4]`
- concentração do maior episódio: `16,4%`

Isso já resolveu a primeira dúvida importante:
- **não** era um único episódio dominando toda a amostra.

## 2. Par primário (BNB RICH+ × 8h × M15)

- controle relativo condicional do BNB: `-0,00006`
- retorno relativo médio dos eventos: `+0,00109`
- marginal vs controle condicional: `+0,00115`
- `n = 128`

Leitura:
- o sinal é **positivo** como previsto;
- supera o controle relativo condicional;
- mas o marginal de `+11,5bp` ainda fica **abaixo** do piso de custo de `20bp`.

## 3. Guardrails anti-snooping

### A. Episódios
**Passou.**
- o maior episódio responde por apenas `16,4%` dos eventos;
- portanto não dá para dizer que era apenas um único pump concentrado.

### B. Fatias de 30 dias
**Falhou.**

Em 8h:
- **fatia 1**: `+0,01949` (muito forte)
- **fatia 2**: `-0,00049`
- **fatia 3**: `-0,00166`

Regra pré-registrada exigia efeito positivo em **≥2 das 3 fatias**.
Resultado:
- só **1 de 3** fatias foi positiva.

Esse foi o golpe decisivo.

## 4. Veredito pré-registrado

**❌ FALHA.**

Critérios:
- `n_ok = True`
- `ep_ok = True`
- `ctrl_ok = True`
- `slices_ok = False`
- `mag_ok = False`

A hipótese morreu por duas razões independentes:
1. **não replicou temporalmente** dentro da própria janela (só a primeira fatia funcionou);
2. **não superou o custo piso de 20bp** no horizonte primário de 8h.

## 5. Leitura correta

Q12 foi o teste mais importante para evitar autoengano, e ele cumpriu esse papel.

O que ele mostrou:
- havia, sim, algo real na leitura de Q11 — não era puro artefato de um único episódio;
- mas esse algo estava **concentrado em um subperíodo específico**;
- fora daquela fatia, o efeito não só enfraqueceu como ficou negativo.

Em linguagem simples:
> **não descobrimos um edge estável de BNB rich+; descobrimos um subperíodo muito
> favorável que não se repetiu no restante da janela.**

Isso é exatamente o tipo de achado que engana quando a pesquisa não tem
safeguards temporais.

## 6. Encerramento metodológico da família

Com Q12, a família cross-sectional fica praticamente encerrada da forma honesta:
- Q8: reversão relativa simples falhou;
- Q9: momentum relativo funcionou no sentido, mas pequeno demais;
- Q10: funding confirmation ajudou só no lado rich;
- Q11: rich+ aproximou-se mais, mas dependia de BNB;
- Q12: o caso BNB não replicou nas fatias e não bateu custo no primário.

Logo, a conclusão correta é:
> **não há evidência robusta de edge cross-sectional implementável neste setup,
> nem mesmo no subcaso mais promissor (BNB rich+).**

## 7. Encerramento

Q12 está encerrada como **reprovada**.
Nada vai para paper/live.
Nenhuma estratégia é promovida.

## 8. Placar consolidado

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
- Q11: reprovada
- Q12: reprovada

## 9. O que sobra agora

Depois de Q12, insistir em microvariações desta família seria provavelmente só
procurar um jeito de salvar o que já não passou. A trilha cross-sectional de
premium/funding, do jeito atual, está honestamente **esgotada**.

Se o projeto continuar buscando edge real, o próximo salto precisa vir de outra
fonte de informação, por exemplo:
- OI real acumulado da nossa série própria;
- eventos de fluxo/liquidação melhores;
- horizontes mais longos e outra estrutura de custo;
- ou outro mercado/venue/universo.