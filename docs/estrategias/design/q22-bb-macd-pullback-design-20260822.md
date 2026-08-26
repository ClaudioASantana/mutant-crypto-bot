# Q22 — pullback em tendência com BB + MACD — design pré-registrado — 2026-08-22

> Status: **documento de design**. Nada implementado como estratégia, nada em
> paper/live.

---

## 1. De onde esta rodada nasce

A Q19 testou a família **compressão extrema + expansão** com Bollinger bandwidth e
MACD. Resultado: sem edge líquido robusto.

A leitura visual que motivou esta nova frente é diferente. Na imagem fornecida, os
pontos marcados em verde/vermelho parecem refletir não um squeeze puro, mas um
padrão de:

- **retomada após pullback curto**;
- preço trabalhando em torno da **banda média** de Bollinger;
- MACD sendo usado como **filtro de qualidade / reaceleração**, não como gatilho
  cego;
- saída quando o movimento perde qualidade, estica demais ou volta a perder a
  banda média.

Em outras palavras: esta rodada existe porque a leitura visual parece ser uma
**continuação de tendência após reset local**, e não uma mera compressão de
volatilidade.

---

## 2. Hipótese

> Em BTC spot 15m, um setup objetivo de **pullback em tendência + reaceleração de
> momentum** usando Bollinger Bands e MACD consegue capturar continuação curta com
> custo pago e sem depender de squeeze extremo?

Se esta hipótese existir, o que ela procurará não é “adivinhar o fundo”, mas
**comprar a retomada** depois de um recuo controlado e **sair quando a qualidade do
movimento se deteriora**.

---

## 3. O que esta rodada NÃO é

- não é re-tune da Q19;
- não é squeeze clássico;
- não é previsão direcional em regime puro;
- não é longo prazo / trend-following diário;
- não é vol-targeting;
- não é grid-search de parâmetros.

Também não é promoção para paper/live.

---

## 4. Fonte de dados

- **BTCUSDT spot 15m** via Binance Vision monthly klines;
- mês corrente completado por API spot;
- faixa alvo: **2017-08-17 → execução atual**;
- mesma disciplina de parse de timestamps já corrigida na trilha (ms até 2024-12,
  us a partir de 2025-01).

Motivo de manter 15m:
- é o timeframe mais próximo da leitura visual;
- o setup parece ser de **entrada/saída tática** e não de swing diário.

---

## 5. Intuição operacional da leitura visual

A imagem sugere três blocos distintos:

### A. Entrada boa — verde
- preço para de cair e começa a recuperar;
- trabalha perto da banda média ou a recupera;
- MACD deixa de piorar e passa a reacelerar;
- não há esticamento claro ainda.

### B. Saída ruim / evitar continuidade — vermelho
- preço estica em direção à banda superior;
- MACD perde inclinação;
- candles deixam de fazer progresso limpo;
- começa a haver exaustão ou chop.

### C. Consolidação / reset
- o mercado volta a comprimir/respirar;
- o setup ainda não está “limpo” para nova entrada;
- a leitura visual pede paciência.

A hipótese aqui é que o edge não está no squeeze extremo, mas na
**reaceleração após pullback controlado**.

---

## 6. Regras candidatas (pré-registradas como família, não como otimização)

Esta rodada terá uma família pequena de variantes fixas, todas tentando capturar a
mesma ideia:

### Elementos comuns
- Bollinger Bands 20/2 (ou banda equivalente já usada na trilha);
- MACD 12/26/9;
- entrada somente quando houver **pulback + retomada**;
- saída por perda de qualidade, perda da banda média ou exaustão;
- custo explícito;
- sem short sistemático.

### Variantes candidatas

| Variante | Ideia central |
|---|---|
| **P1 — Midline reclaim** | entrar quando o preço recupera a banda média após pullback curto, com MACD melhorando |
| **P2 — Trend pullback continuation** | entrar só se houver viés de tendência local e o pullback retornar à retomada com MACD confirmando |
| **P3 — Exhaustion exit** | mesma entrada da P1/P2, mas com saída mais agressiva quando o preço estica e o MACD perde qualidade |

A implementação posterior deverá escolher uma única regra objetiva por variante,
sem escolher parâmetros depois do resultado.

---

## 7. Regras de causalidade / execução

- o sinal é lido no fechamento de `t-1`;
- a entrada acontece em `t`;
- o setup não pode usar o fechamento de `t` para decidir a própria barra;
- nenhuma decisão pode depender do futuro;
- o custo só incide quando houver mudança de posição.

---

## 8. O que será medido

Como o setup é de trade tático em 15m, a avaliação deve ser por curva de equity,
mas com métricas operacionais mais próximas da execução:

- curva de equity;
- CAGR líquido;
- vol anualizada;
- Sharpe;
- Sortino;
- max drawdown;
- duração do drawdown;
- tempo em mercado;
- turnover / notional trocado;
- retorno por ano;
- robustez temporal em metades e ciclos.

Benchmark: buy-and-hold BTCUSDT spot no mesmo período.

---

## 9. Veredito pré-registrado

Uma variante só **SOBREVIVE como candidata** se, na janela cheia:

1. **Participação:** CAGR líquido ≥ 40% do CAGR do buy-and-hold.
2. **Preservação:** max drawdown ≤ 60% do maxDD do buy-and-hold.
3. **Robustez temporal:**
   - nenhum único ano responde por ≥ 50% do retorno total;
   - comportamento consistente em ≥ 2/3 das sub-janelas pré-registradas.
4. **Custo não explica tudo:** diferença CAGR gross − net ≤ 1,0 ponto percentual.
5. **Concordância de classe:** pelo menos 2 das 3 variantes passam os critérios acima.

Sub-janelas pré-registradas:
- primeira metade vs segunda metade;
- ciclos amplos (2017-08→2019-12, 2020-01→2022-12, 2023-01→execução atual).

---

## 10. O que NÃO significa sobreviver

Mesmo sobrevivendo:

- não é promoção para paper/live;
- vira apenas candidato a validação posterior;
- não autoriza re-tune de janela, banda, MACD ou thresholds depois do fato.

---

## 11. Consequências possíveis

Se a Q22 sobreviver:
- teremos encontrado uma formulação visualmente fiel ao que você marcou na imagem;
- e ela passará a ser a principal candidata tática da trilha para o timeframe 15m.

Se falhar:
- a trilha terá mostrado que mesmo a leitura visual de BB + MACD como pullback/
  retomada não produz edge líquido robusto na amostra longa;
- e isso reforça a necessidade de informação nova (Camada B madura ou outro
  universo/venue).
