# Q8 — Cross-sectional relative value (basis/premium) — design pré-registrado — 2026-08-22

> Status: **documento de design**. Nada implementado como estratégia, nada em
> paper/live. Hipótese nova: em vez de apostar direção de BTCUSDT *outright*,
> comparar **cross-sectionalmente** o basis/premium de um basket de perps e
> testar se extremos relativos revertem *em relação ao basket*.

---

## 1. Hipótese

> Em um basket de perps USDT-M da Binance, quando o premium/basis relativo de um
> ativo está num extremo **em relação aos demais** (rich ou cheap), o retorno
> forward **relativo ao basket** (long cheap / short rich) tende a reverter:
> o ativo rich **subperform** e o ativo cheap **outperform**.

Racional:
- o premium de cada perp reflete seu próprio grau de crowding alavancado;
- comparado ao basket, um premium relativo extremo indica deslocamento de fluxo
  específico do ativo, que tende a normalizar;
- usando **market-neutral relativo**, tira-se o drift comum do crypto e isola-se
  o componente idiossincrático — onde um reach edge teria mais chance de
  sobreviver a custos.

**Isso é diferente das rodadas anteriores**:
- Q5/Q6/Q7 apostavam na direção absoluta do BTCUSDT;
- Q8 não aposta em "o mercado vai subir ou cair", e sim em "qual perna está
  esticada demais *em relação às outras*".

## 2. Definição causal de evento

- **Basket fixo (pré-registrado, 8 símbolos líquidos)**: BTCUSDT, ETHUSDT,
  SOLUSDT, BNBUSDT, XRPUSDT, DOGEUSDT, ADAUSDT, LINKUSDT.
- `premium_rel(s, t) = premium_close(s, t) / perp_close(s, t)` — series
  `premiumIndexKlines` e klines do perp.
- Por timestamp `t` do cruzamento de séries, calcular o **rank normalizado** do
  `premium_rel` entre os 8 símbolos:
  `rn(s,t) = (rank - 1) / (n - 1)` → 0 = mais barato, 1 = mais caro.
- **Evento RICH**: `rn(s,t) >= 0.75` — ativo entre os 25% mais ricos (top 2/8).
- **Evento CHEAP**: `rn(s,t) <= 0.25` — ativo entre os 25% mais baratos (bottom 2/8).
- **Entrada (hipotética)**: close do candle de evento (`t`), executando long na
  perna cheap e short na perna rich.
- **SINAL-PREDIÇÃO (pré-registrado)**: RICH → retorno relativo forward
  **negativo**; CHEAP → retorno relativo forward **positivo**.
- **Cooldown**: por símbolo e por lado, ignora novo evento do mesmo símbolo
  dentro de 8 candles (2h em M15).

## 3. Retorno medido e custo

- **Relativo ao basket**: retorno de `s` menos o retorno médio equiponderado dos
  outros 7 símbolos no mesmo horizonte:
  `rel(s,t→H) = ret(s,t→H) − mean_{j≠s} ret(j,t→H)`.
  Sem lookahead: só usa candles fechados em/antes de `t` para definir o evento;
  o retorno usa candles futuros mas é apenas a *medição* (event study).
- **Horizontes**: 1h, 4h (primário), 8h, 24h.
- **Controle obrigatório**: `rel(s,t→H)` médio incondicional de TODOS os pares
  (símbolo, timestamp) da janela — o drift relativo de cada perna.
- **Custo**: trade relativo = 2 patas × round-trip por pata.
  Em 1 unidade de notional em cada pata, um round-trip por pata = 10bp
  (fee 4bp + slippage 1bp, por ponta). Como o PnL desta estrutura é o retorno
  relativo vezes 1 de notional (long cheap + short rich, neutro), o custo é:
  `cost_rel = 2 × 10bp = 20bp` por reciclagem completa.
  Reportar também o **PnL bruto** para isolar o alpha antes de custos.

## 4. Veredito pré-registrado (falsificável)

Par primário: **RICH e CHEAP × 4h × M15**, eventos por rank ≥ 0.75 / ≤ 0.25.

- **Falha** se `n < 30` por lado, OU o efeito marginal
  `(mean rel_{net} − mean controle_rel_{net})` tiver sinal contrário ao previsto,
  OU `|marginal| <= custo (20bp)`.
- **Sobrevive** se `n ≥ 30` em ambos os lados, sinal previsto consistente
  em 1h/4h/8h, e marginal > custo.

Leituras de robustez (reportar, não admitir sozinhas):
- t-stat do efeito marginal;
- win rate;
- estabilidade do efeito por símbolo (evitar 1 ativo dominar);
- split por regime de funding agregado (exploratório).

## 5. Se sobreviver

Fase seguinte (SÓ então): transformar em regra operacional (ex.: rank-score do
basket como ranking diário, entrar top/bottom cross-sectional, sair por horizonte
fixo) com a régua completa — walk-forward 90d, ≥5/8 janelas, PnL agregado > 0,
PF > 1,3, custos reais por pata. **Nada disso nesta rodada.**

## 6. Limitação declarada

- Volumes de cross-section de 8 ativos dummy-coded: não há component loading de
  risco entre eles (BTC/ETH altamente correlacionados), o que pode inflar n sem
  independência real. O split por símbolo e o controle por par tentam mitigar.
- Os custos de múltiplas patas e o borrow do short perp não são modelados aqui
  (estudo de α relativo bruto), apenas a régua de 20bp como piso.