# Q11 — RICH-only cross-sectional continuation — veredito do event study — 2026-08-22

> Design pré-registrado: `q11-rich-only-design-20260822.md`.
> Script: `backend/scripts/experiment_q11_rich_only.py`.
> Hipótese: o subcaso mais promissor da família cross-sectional é o lado **RICH + funding positivo**; isolando apenas esse lado, talvez a magnitude finalmente fique suficiente.

## 1. Resultado do par primário (RICH+ × 8h × M15)

Amostra:
- baseline RICH sem funding: `2.669` eventos
- RICH+ com funding confirmado: `120` eventos

Par primário — 8h:
- **RICH baseline**:
  - `n = 2.659`
  - marginal vs controle: `+0,00023`
- **RICH+**:
  - `n = 120`
  - marginal vs controle: `+0,00152`
  - sinal **correto**
  - magnitude **muito maior** que o baseline sem funding

Horizonte 24h:
- **RICH+**:
  - `n = 113`
  - marginal vs controle: `+0,00306`

## 2. Veredito pré-registrado

**❌ FALHA.**

Critérios do par primário (8h):
- `n_ok = True`
- `sign_ok = True`
- `mag_ok = False`

Motivo direto da reprovação:
- o horizonte **primário** exigia `marginal > 20bp`;
- em 8h, o resultado foi **+15,2bp**;
- portanto a hipótese **não cruzou a barra econômica** que ela própria precisava cruzar.

## 3. O que torna Q11 importante

Q11 é, até aqui, **o melhor resultado da família cross-sectional**.

Ela mostrou três coisas relevantes:

1. **Isolar o lado RICH fez sentido**
   - o sinal ficou correto em 4h/8h/24h;
   - a magnitude aumentou bastante em relação a Q9/Q10.

2. **Funding confirmation realmente concentrou algo**
   - baseline rich em 8h: `+2,3bp`
   - rich+ em 8h: `+15,2bp`
   - rich+ em 24h: `+30,6bp`

3. **Mesmo assim, o primário não passou**
   - 15,2bp ainda é menor que o custo piso de 20bp.

Ou seja:
> esta é a primeira hipótese da família cross-sectional que ficou relativamente
> perto da barreira econômica, mas ainda **não passou com a régua pré-registrada**.

## 4. A ressalva crítica: concentração extrema em BNBUSDT

O split por símbolo em 8h foi decisivo:
- **todos os eventos RICH+ vieram de BNBUSDT** (`n=120`)
- os demais símbolos não contribuíram materialmente

Isso muda a interpretação do estudo:
- Q11 **não descobriu um padrão universal do basket**;
- Q11 encontrou algo que, nesta janela, é essencialmente um **fenômeno de BNBUSDT**.

Então mesmo o bom resultado relativo de 24h (`+30,6bp`) não pode ser lido como
"a família toda funciona". A leitura correta é:
- **há um possível micro-edge específico em BNBUSDT quando ele está rich e com funding positivo**;
- mas isso ainda não foi mostrado como regra geral cross-sectional nem como edge robusto multiativo.

## 5. Encerramento

Q11 está encerrada como **reprovada**.
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
- Q11: reprovada

## 7. O que aprendemos de verdade com Q11

Q11 afinou o mapa de forma muito valiosa:
- a simetria rich/cheap era mesmo enganosa;
- o lado **rich + funding positivo** é o único pedaço que merece alguma atenção adicional;
- mas o sinal ainda não é amplo o bastante nem limpo o bastante para ser promovido;
- e, principalmente, ele parece **concentrado em BNBUSDT**, não no basket todo.

A continuação lógica, se quisermos insistir de forma honesta, já não é "mais uma hipótese geral". O próximo passo correto teria que ser muito mais específico, por exemplo:
- estudo **single-name** em BNBUSDT rich+;
- ou checar se o mesmo fenômeno aparece em outros períodos / outros baskets;
- ou admitir que a cross-section ampla falhou e que o que sobrou é apenas uma
  curiosidade local, não uma estratégia escalável.