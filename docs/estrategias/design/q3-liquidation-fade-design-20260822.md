# Q3 — Post-liquidation fade (event study) — design pré-registrado — 2026-08-22

> Status: **documento de design**. Nada implementado como estratégia, nada em
> paper/live. Define hipótese, definição causal de evento, dados, controle e
> regra de veredito ANTES de rodar — para não virar teste-pesca.
> Fonte de pesquisa de mercado: pesquisador (levantamento 2026-08-22),
> notadamente Garcia Seuma (early-warning heterogêneo entre cascatas), Cheng et
> al. (liquidações forçadas ~3,5% longs / 1,9% shorts do book), e o esforço do
> projeto em P1/P2 (TA clássica não sobrevive à régua OOS).

---

## 1. Hipótese

> Após um **flush** (movimento de queda rápido, com excesso mecânico típico de
> liquidações forçadas) **sem notícia fundamental**, parte do movimento tende a
> reverter em janelas de horas — o impacto mecânico da venda forçada é
> transitório.

Isso se manifesta em dois padrões de vela **fechada** (causais):

- **Evento A — `climatic_drop`**: vela bearish com corpo ≥ 2,5×ATR(14) e volume
  ≥ 2×média(50). Proxy de cascata de liquidação long side: queda veloz com
  absorção de volume.
- **Evento B — `wick_reclaim`**: vela com pavio inferior (low − min(open,close))
  ≥ 2×ATR(14) **e** fechamento bullish (close > open). Proxy de stop-run/flush
  que foi comprado de volta no mesmo candle.

Ambos só usam dados conhecidos no fechamento do candle — sem lookahead.

## 2. Por que este racional (e não TA clássica)

- Liquidação forçada tem impacto de preço **mecânico** distinto do informacional
  (Cheng et al.); parte dele reverte.
- As rodadas P1/P2 mostraram que sinais de preço sozinhos morrem sob a régua
  OOS. Este estudo separa **primeiro** a medição do efeito (event study) da
  transformação em regra de trading — se não houver assimetria aqui, morre
  antes e barato.
- A pesquisa de mercado alertou que sinais de liquidação não generalizam entre
  eventos (Garcia Seuma); portanto o evento **não** será medido sobre poucas
  cascatas famosas, e sim como padrão estatístico sobre 90 dias contínuos.

## 3. Dados

| Dado | Fonte | Disponibilidade anônima | Uso |
|---|---|---|---|
| OHLCV BTCUSDT M15 e H1 | `fapi/v1/klines` | ✅ | preço/evento |
| Funding rate histórico | `fapi/v1/fundingRate` | ✅ | contexto de posicionamento |
| Long/short account ratio (15m) | `futures/data/globalLongShortAccountRatio` | ✅ | (exploratório, não no veredito primário) |
| Open interest histórico | `fapi/v1/futures/data/openInterestHist` | ❌ requer API key | fora do escopo desta rodada |
| Liquidações oficiais | — | ❌ indisponível | fora do escopo |

**Limitação declarada:** o estudo usa proxy de flush por price action + volume,
não dados reais de liquidação/OI. Isso enfraquece a atribuição causal específica
"liquidação forçada"; o que se mede é o **comportamento pós-dislocação de
preço** de forma geral. Se o efeito existir e for forte, a hipótese sobrevive
para a próxima rodada com dados melhores.

## 4. Protocolo

- Período: 130 dias de histórico, dos quais **90 dias** (os últimos) como janela
  de evento; 40 dias de warmup para ATR e médias.
- Ativos/TFs: BTCUSDT **M15 (primário)** e BTCUSDT H1 (secundário).
- Custo por round-trip (entrada+saída): `2×(fee 0,0004 + slippage 1bp)` =
  **0,0010 = 10bp**.
- Entrada hipotética: no fechamento do candle de evento.
- Horizontes de retorno forward: **1h, 4h, 8h, 24h** — de `close[t]` a
  `close[t+h]`.
- **Controle obrigatório**: retorno forward médio incondicional sobre TODAS as
  velas (mesma janela), para subtrair o drift do mercado. Sem isso, "comprar
  queda" parece bom em bull market.
- **Cooldown** para não contar a mesma cascata repetidamente: após um evento do
  mesmo tipo, ignorar outros por 4h (16 velas M15 / 4 velas H1).
- Splits de contexto (pré-registrados, não varridos): funding no momento do
  evento (positivo vs negativo/neutro) e regime ADX (trend ≥25 vs range <25).

## 5. Veredito pré-registrado (falsificável)

Para o **par primário Evento B × horizonte 4h** em BTC M15:

- **Falha** se: `n_eventos < 20`, ou retorno forward médio **líquido ≤ 0**, ou
  o retorno líquido não supera o controle líquido.
- **Sobrevive à fase de event study** se: `n_eventos ≥ 20` **e** retorno líquido
  médio > 0 **e** retorno líquido médio > controle líquido, com win rate e
  t-stat reportados (leitura conservadora, não p < 0,05 mecânico).

Demais combinações (Evento A, outros horizontes, H1) são **exploratórias** e
não admitem a hipótese — servem apenas para dimensionar se vale reabrir.

## 6. Critério de admissão (fase seguinte, SÓ se o event study sobreviver)

Se o padrão primário sobreviver, aí (e apenas aí) vira regra operacional e passa
pela réguanormal de walk-forward: ≥5/8 janelas OOS positivas + PnL agregado > 0
+ PF > 1,3, com custos reais. **Nada disso acontece nesta rodada.**