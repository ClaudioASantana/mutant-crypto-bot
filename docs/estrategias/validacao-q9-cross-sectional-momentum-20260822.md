# Q9 — Cross-sectional momentum — veredito do event study — 2026-08-22

> Design pré-registrado: `q9-cross-sectional-momentum-design-20260822.md`.
> Script: `backend/scripts/experiment_q9_cross_sectional_momentum.py`.
> Hipótese: extremos cross-sectional de premium/basis não revertem; eles
> **continuam** relativamente ao basket.

## 1. Resultado do par primário (RICH/CHEAP × 4h × M15)

Amostra:
- basket: BTCUSDT, ETHUSDT, SOLUSDT, BNBUSDT, XRPUSDT, DOGEUSDT, ADAUSDT, LINKUSDT
- candles alinhados: `12.480`
- eventos RICH: `2.668`
- eventos CHEAP: `2.654`

Par primário — 4h:
- **RICH**:
  - `n = 2.663`
  - retorno relativo médio: `+0,00005`
  - marginal vs controle: `+0,00005`
  - **sinal correto** para a hipótese de momentum
- **CHEAP**:
  - `n = 2.647`
  - retorno relativo médio: `-0,00020`
  - marginal vs controle: `-0,00020`
  - **sinal correto** para a hipótese de momentum

Controle relativo incondicional:
- aproximadamente `0`, como esperado por construção market-neutral.

## 2. Veredito pré-registrado

**❌ FALHA.**

Motivos:
1. `n_ok = True` — amostra grande e estável.
2. `sign_ok = True` — desta vez a direção do efeito bateu com a hipótese no par primário.
3. `mag_ok = False` — **as magnitudes ficaram muito abaixo do custo piso de 20bp**.

Em outras palavras:
- a Q9 foi melhor que a Q8 em qualidade de sinal;
- mas ainda **não chegou perto de virar edge líquido operável**.

## 3. O que torna Q9 diferente das rodadas anteriores

Q9 é a primeira hipótese da trilha que mostrou algo mais interessante:
- não foi refutada por sinal contrário no par primário;
- não morreu por falta de amostra;
- morreu porque o **efeito é pequeno demais**.

Isso a aproxima mais da Q5 do que das demais:
- **Q5**: havia efeito direcional real em basis extremo, mas pequeno demais para o custo.
- **Q9**: há um indício de continuidade cross-sectional, mas pequeno demais para o custo.

A leitura econômica continua a mesma:
> **efeito estatístico pequeno não é edge líquido real.**

## 4. Estrutura temporal do sinal

- **1h**: RICH falhou no sinal; CHEAP acertou.
- **4h**: ambos acertaram o sinal.
- **8h**: ambos acertaram o sinal.
- **24h**: ambos acertaram o sinal, e CHEAP ficou mais forte em magnitude.

Ou seja:
- a hipótese de momentum cross-sectional parece mais plausível em horizontes
  **4h+**, especialmente no lado CHEAP;
- mas mesmo em 24h, o efeito ainda não supera com folga o custo piso de 20bp.

## 5. Heterogeneidade por símbolo

O split por símbolo em 4h mostrou que o resultado é desigual:
- BTCUSDT e BNBUSDT dominaram muitos eventos RICH com efeito quase nulo;
- DOGEUSDT e ADAUSDT dominaram muitos eventos CHEAP com efeito levemente negativo;
- XRPUSDT puxou em direção oposta em alguns cortes;
- não há um padrão limpo e homogêneo no basket inteiro.

Isso enfraquece a leitura de uma regra simples, universal e robusta para todos os
nomes do cesto.

## 6. Encerramento

Q9 está encerrada como **reprovada**.
Nada vai para paper/live.
Nenhuma estratégia é promovida.

## 7. Placar consolidado

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

## 8. Leitura final desta rodada

Q9 foi a melhor versão cross-sectional testada até agora:
- a hipótese estava alinhada com o que a Q8 sugeriu;
- o sinal apareceu no sentido certo em 4h/8h/24h;
- mas o tamanho do efeito continuou insuficiente para pagar a estrutura.

Portanto, o próximo avanço real só deve acontecer se mudarmos pelo menos uma
coisa estrutural:
- reduzir custo de implementação;
- trocar o universo de ativos;
- mudar o horizonte para algo ainda mais longo;
- ou adicionar outra camada de filtro que aumente a magnitude sem destruir a
  amostra.

Sem isso, insistir seria só fabricar convicção em cima de um alpha pequeno demais.