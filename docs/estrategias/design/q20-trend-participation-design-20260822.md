# Q20 — trend participation lenta em BTC (long/flat diário) — design pré-registrado — 2026-08-22

> Status: **documento de design**. Nada implementado como estratégia, nada em
> paper/live.

---

## 1. Por que esta rodada existe

A trilha já espremeu, até aqui, principalmente perguntas do tipo:

- este evento direcional em BTC gera retorno forward acima do controle?
- este indicador público isolado passa custo em 4h/8h/24h?

Essa lente foi útil para matar muita coisa, mas ela é **cega** para o tipo de
edge que mais plausivelmente existe em crypto:

> participar de tendências longas e reduzir drawdowns grandes, em vez de tentar
> adivinhar microdireção de 4h/8h.

Esta rodada existe para fazer a correção metodológica explícita:

- sair do **event study de média por evento**;
- entrar em **curva de equity de estratégia**.

## 2. O que esta rodada NÃO é

Isto **não** é:

- continuação da Q19 em outro threshold;
- re-tune de TA curta;
- estratégia com stop/TP otimizado;
- short sistemático;
- grid-search de parâmetros.

Também não é um teste para paper/live. É uma pergunta de pesquisa:

> regras lentas e públicas de tendência conseguem preservar uma fração relevante
> do upside de BTC enquanto cortam drawdown de forma material?

## 3. Fonte de dados

- **spot BTCUSDT 1d** via Binance Vision monthly klines
- mês corrente completado por API spot da Binance
- faixa alvo: **2017-08-17 → execução atual**

Motivo da escolha:
- é a série mais longa e limpa disponível gratuitamente;
- cobre múltiplos regimes (bull, bear, chop, crash, recuperação).

## 4. Regras pré-registradas

Todas as regras são **long/flat** (`pos ∈ {0, 1}`), sem short.

### R1 — SMA200
- long quando `close > SMA200`
- flat quando `close <= SMA200`

### R2 — Golden Cross
- long quando `SMA50 > SMA200`
- flat quando `SMA50 <= SMA200`

### R3 — Time-Series Momentum 12-1
- long quando o retorno dos últimos 12 meses, excluindo o mês mais recente,
  for positivo
- flat quando for zero ou negativo

## 5. Regras de execução / causalidade

- o sinal é lido no fechamento do dia `t-1`
- a posição vale para o retorno de `t`
- isto é: não há lookahead do fechamento atual para decidir a própria barra
- `ret_t = pos_t * (close_t / close_{t-1} - 1)`

## 6. Custos

- custo total de **10bp round-trip**
- custo cobrado **somente quando há flip** de posição (`0→1` ou `1→0`)
- sem slippage adicional arbitrário além desse custo pré-registrado

## 7. Métricas a reportar

Para cada regra e para o benchmark **buy-and-hold**:

- CAGR líquido
- vol anualizada
- Sharpe
- Sortino
- max drawdown
- duração do drawdown
- percentual do tempo em mercado
- número de flips/trades
- gross vs net
- retorno por ano-calendário
- curva de equity

## 8. Benchmark

O benchmark é **buy-and-hold spot BTCUSDT** no mesmo período.

O objetivo da rodada não é bater buy-and-hold em retorno absoluto puro a qualquer
custo, mas testar o trade-off:

> quanto upside foi preservado em troca de quanto drawdown foi evitado?

## 9. Veredito pré-registrado

Uma regra só **SOBREVIVE como candidata** se, na janela cheia:

1. **Participação:** CAGR líquido ≥ 40% do CAGR do buy-and-hold.
2. **Preservação:** max drawdown ≤ 60% do maxDD do buy-and-hold.
3. **Robustez temporal:**
   - nenhum único ano responde por ≥ 50% do retorno total;
   - comportamento consistente em pelo menos `2/3` das sub-janelas pré-registradas.
4. **Custo não explica tudo:** diferença entre CAGR gross e net ≤ 1,0 ponto percentual.
5. **Concordância de classe:** pelo menos `2/3` regras (isto é, 2 das 3) passam os
   critérios acima.

### Sub-janelas pré-registradas

- primeira metade vs segunda metade da amostra
- regimes amplos por ciclo:
  - 2017-08 → 2019-12
  - 2020-01 → 2022-12
  - 2023-01 → execução atual

## 10. O que NÃO significa sobreviver

Mesmo sobrevivendo:
- ainda não é promoção para paper/live;
- vira apenas **candidato** a validação posterior;
- não autoriza re-tune pós-hoc de janelas 50/200 ou 12-1.

## 11. Consequências possíveis

Se Q20 falhar:
- reforça que nem a formulação mais clássica e robusta de trend-following em BTC,
  com lente correta de equity curve, está entregando o trade-off desejado.

Se Q20 sobreviver:
- vira o primeiro candidato sério da trilha com vocação real de preservação de
  capital + participação em tendência;
- mas continua bloqueado para paper/live até a próxima camada de validação.
