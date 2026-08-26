# Q8 — Cross-sectional relative value — veredito do event study — 2026-08-22

> Design pré-registrado: `q8-cross-sectional-design-20260822.md`.
> Script: `backend/scripts/experiment_q8_cross_sectional_relative_value.py`.
> Hipótese: um ativo com premium relativo extremo dentro de um basket de perps
> líquidos tenderia a reverter **em relação ao basket** (subperform se rich,
> outperform se cheap).

## 1. Resultado do par primário (RICH/CHEAP × 4h × M15)

Amostra:
- basket: BTCUSDT, ETHUSDT, SOLUSDT, BNBUSDT, XRPUSDT, DOGEUSDT, ADAUSDT, LINKUSDT
- candles alinhados: `12.480`
- eventos RICH: `2.668`
- eventos CHEAP: `2.653`

Par primário — 4h:
- **RICH**:
  - `n = 2.663`
  - retorno relativo médio: `+0,00005`
  - marginal vs controle: `+0,00005`
  - **sinal contrário ao previsto** (deveria ser negativo)
- **CHEAP**:
  - `n = 2.647`
  - retorno relativo médio: `-0,00020`
  - marginal vs controle: `-0,00020`
  - **sinal contrário ao previsto** (deveria ser positivo)

Controle relativo incondicional:
- aproximadamente `0`, como esperado por construção market-neutral.

## 2. Veredito pré-registrado

**❌ FALHA.**

Motivos:
1. `n_ok = True` — amostra muito grande, então não foi problema de escassez.
2. `sign_ok = False` — os dois lados foram contra a hipótese no horizonte primário de 4h.
3. `mag_ok = False` — mesmo ignorando a direção errada, as magnitudes ficaram muito abaixo do piso de custo relativo de 20bp.

Ou seja: a hipótese cross-sectional não só deixou de superar custo — ela errou o
sentido esperado no par primário.

## 3. Leitura útil

Esse resultado é muito informativo, porque elimina uma objeção comum às rodadas
anteriores: "talvez o problema seja usar direção absoluta de BTC".

Q8 testou justamente uma alternativa mais sofisticada:
- neutralizar o drift do mercado;
- usar informação relativa entre ativos;
- apostar em reversão idiossincrática, não direcional.

Mesmo assim, o resultado foi ruim.

### O que os sinais sugerem
- **RICH** não subperforma de forma consistente; em 4h/8h/24h, a média ficou até levemente positiva.
- **CHEAP** foi pior ainda: em 1h/4h/8h/24h, a média relativa ficou negativa.

Em linguagem simples:
> dentro deste basket e desta definição, os ativos "cheap" não rebateram — eles
> tenderam a continuar piores que o basket.

Ou seja, se existe algo aqui, parece mais próximo de **continuação relativa** em
alguns nomes do que de mean reversion cross-sectional simples. Mas essa já seria
**outra hipótese**, não a mesma.

## 4. Robustez por símbolo

O split por símbolo em 4h mostrou heterogeneidade grande:
- BTCUSDT e BNBUSDT dominaram parte relevante dos eventos RICH;
- DOGEUSDT e ADAUSDT dominaram parte relevante dos eventos CHEAP;
- alguns símbolos tiveram poucos eventos e sinais mistos;
- não houve padrão limpo e estável de reversão relativa no basket inteiro.

Isso enfraquece ainda mais a hipótese de uma regra geral simples aplicável ao
conjunto.

## 5. Encerramento

Q8 está encerrada como **reprovada**.
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

A mensagem agregada agora está ainda mais forte:
- nem direção absoluta simples,
- nem carry curto,
- nem persistência de regime simples,
- nem reversão cross-sectional simples

mostraram edge líquido robusto com dados públicos e esta modelagem.

Isso é duro, mas é exatamente o tipo de honestidade que evita construir um bot
em cima de uma miragem estatística.