# Q6 — Carry / funding capture — design pré-registrado — 2026-08-22

> Status: **documento de design**. Nada implementado como estratégia, nada em
> paper/live. Esta rodada testa uma hipótese diferente da Q5: não direção
> outright do underlying, e sim captura de carry/funding em estrutura
> **delta-neutral idealizada**.

---

## 1. Hipótese

> Em BTCUSDT perpétuo, quando o funding entra em faixa extrema e com o mesmo
> sinal do basis/premium, existe um regime de carry suficientemente persistente
> para que uma posição **delta-neutral** mantida até o próximo funding capture
> valor líquido positivo.

Estrutura conceitual:
- funding **positivo** e basis/premium **positivo** → crowded long no perp;
  o short perp recebe funding.
- funding **negativo** e basis/premium **negativo** → crowded short no perp;
  o long perp recebe funding.

A aposta aqui **não é** que o preço vá reverter. A tese é outra:
- se o crowding persiste tempo suficiente,
- o fluxo de funding pago pela ponta pressionada pode superar o custo de entrar
  e sair de uma estrutura hedgeada.

## 2. Unidade de estudo

Vamos modelar uma estrutura idealizada delta-neutral:
- **Regime C+**: funding > 0 e basis extremo positivo.
  Estrutura hipotética: **short perp / long spot**.
- **Regime C−**: funding < 0 e basis extremo negativo.
  Estrutura hipotética: **long perp / short spot**.

Como esta base de dados não inclui custo realista de borrow/short spot nem
slippage multi-venue, a métrica desta rodada será tratada como **upper bound
research-only**.

## 3. Definição causal de evento

Dados:
- `fundingRate` histórico Binance Futures;
- `premiumIndexKlines`;
- `klines` do perp;
- BTCUSDT em M15 (primário) e H1 (secundário).

Definições:
- `premium_rel(t) = premium_close(t) / perp_close(t)`.
- `premium_pct(t)` = percentil causal de `premium_rel` numa janela rolante de
  384 candles em M15 (ou janela temporal equivalente em H1), usando só dados
  até `t`.
- `funding_state_at(t)` = último funding conhecido até `t`, sem lookahead.

Eventos primários:
- **C+**: `premium_pct >= 0.95` **e** `funding_rate > 0`
- **C−**: `premium_pct <= 0.05` **e** `funding_rate < 0`

Cooldown:
- 8 horas entre eventos do mesmo tipo.

## 4. Regra de holding e payoff idealizado

Holding rule primária:
- entrada no close do candle de evento;
- saída no **próximo funding event conhecido após a entrada**.

Payoff idealizado por unidade de notional:
- `carry_gross = abs(next_funding_rate)`
- `carry_net = carry_gross - cost_roundtrip`

Onde:
- `cost_roundtrip = 10 bp` como proxy conservadora mínima de ida-e-volta.

Observação importante:
- esta rodada **não** modela PnL de basis convergence/divergence durante o hold;
- mede apenas se o funding por si só já seria grande o bastante para compensar
  um custo mínimo de execução.
- portanto é um teste propositalmente conservador sobre a componente de carry
  mais limpa e causal.

## 5. Protocolo

- Horizonte econômico: hold até o próximo funding conhecido.
- Timeframes: M15 primário; H1 secundário.
- Janela de dados: 130 dias buscados, 90 dias de evento, 40 dias de warmup.
- Controle obrigatório:
  - média incondicional de `abs(next_funding_rate) - cost_roundtrip` em todos os
    candles elegíveis da janela.
- Leituras auxiliares:
  - distribuição do tempo até o próximo funding;
  - split por intensidade do funding (`|rate|` acima/abaixo da mediana dos eventos);
  - frequência de eventos por lado.

## 6. Regra de falsificação

Par primário:
- **C+ e C− em M15**, hold até próximo funding.

Falha se qualquer uma ocorrer:
- `n < 30` em qualquer lado;
- `mean(carry_net) <= 0` em qualquer lado;
- `mean(carry_net) <= mean(control_net)` em qualquer lado.

Sobrevive ao event study se:
- `n >= 30` em ambos os lados;
- `mean(carry_net) > 0` em ambos os lados;
- `mean(carry_net) > control_net` em ambos os lados.

## 7. Interpretação correta

Se sobreviver:
- **não** significa que existe estratégia pronta;
- significa apenas que vale a pena modelar uma versão mais realista, incluindo:
  - custo de hedge/borrow;
  - venue real do spot;
  - risco de basis convergir contra a estrutura antes do funding;
  - múltiplos funding intervals.

Se falhar:
- encerra-se a hipótese de que "só capturar o próximo funding" já basta.
- isso não mata outras hipóteses de carry mais longas, mas mata esta versão
  simples e causal.
