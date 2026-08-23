# Q5 — Basis/premium dislocation — event study — design pré-registrado — 2026-08-22

> Status: **documento de design**. Nada implementado como estratégia, nada em
> paper/live. Define hipótese, definição causal de evento, SINAL-PREDIÇÃO e
> regra de falsificação ANTES de rodar — para não virar teste-pesca.
> Baseia-se no backbone Q4 (dados base já validados).

---

## 1. Hipótese

> Em BTCUSDT perpétuo, quando o **basis/premium** (mark − index, normalizado pelo
> preço) atinge um extremo histórico em janela rolante, a curto prazo o sinal é
> **contrária ao extremo**: basis muito positivo prenuncia queda de preço; basis
> muito negativo prenuncia alta.

Racional de microestrutura:
- basis extremo positivo = demanda long alavancada pressionando o perp acima do
  index (crowded long) → maior probabilidade de squeeze/fade.
- basis extremo negativo = vendas forçadas/hedge pressionando o perp abaixo do
  index → maior probabilidade de recuperação do index.

Isso **não é** "o basis reverte para a média" (fato estrutural documentado) — é
a afirmação mais forte e testável de que o basis extremo tem conteúdo preditivo
para o **preço futuro do underlying**, além do drift incondicional.

## 2. Definição causal de evento

- **Normalização**: `premium_rel(t) = premium_close(t) / perp_close(t)` — basis
  relativo ao preço, com `premium_close` da série `premiumIndexKlines` e
  `perp_close` da série de klines do perp.
- **Distribuição causal**: `pct(t)` = percentil empírico de `premium_rel(t)`
  dentro da janela rolante dos **últimos 384 candles** (≈ 4 dias em M15),
  computado só com dados até `t` (sem lookahead).
- **Evento P+**: `pct(t) >= 0.95` — basis extremamente positivo.
- **Evento P−**: `pct(t) <= 0.05` — basis extremamente negativo.
- **Entrada hipotética**: close do candle de evento.
- **SINAL-PREDIÇÃO (pré-registrado)**: P+ → retorno forward **negativo além do
  controle**; P− → retorno forward **positivo além do controle**.
- **Cooldown**: após evento P+ (ou P−), ignora novos eventos do mesmo sinal por
  16 candles (4h em M15) — evita contar a mesma dislocação repetidamente.

## 3. Protocolo

- Dados: BTCUSDT **M15 (primário)** e BTCUSDT H1 (secundário), 130 dias,
  dos quais 90 dias de janela; 40 dias de warmup.
  Fonte: `fapi/v1/premiumIndexKlines` + `fapi/v1/klines` (mesma fronte do Q4,
  já validada).
- Horizonte primário: **4h** forward. Secundários: 1h, 8h, 24h.
- Custo round-trip: `2×(fee 0,0004 + slippage 1bp)` = **10bp**.
- **Controle obrigatório**: retorno forward médio incondicional de TODAS as
  velas da janela, mesmo horizonte — para subtrair o drift.
- Contexto exploratório (não decide veredito): split por funding no momento do
  evento (causal), e P+/P− com funding também extremo (confluência).

## 4. Veredito pré-registrado (falsificável)

Para o **par primário P+ (e P−) × horizonte 4h × M15**, com evento definido em
percêntil ≥ 0,95 / ≤ 0,05:

- **Falha** se `n < 50` por lado, ou o efeito marginal
  `(mean_event_{net} − mean_control_{net})` tiver **sinal contrário ao
  previsto** (P+ marginal ≥ 0, ou P− marginal ≤ 0), ou o efeito marginal for
  `≈ 0` (não distinto de zero com magnitude > custo, leitura conservadora).
- **Sobrevive à fase de event study** se, em ambos os lados,
  `n ≥ 50` **e** o efeito marginal tiver o **sinal previsto** consistentemente
  nos horizontes 1h/4h/8h (não só num único).

Leitura de robustez (sempre reportada, não usada para admitir sozinha):
t-stat do efeito marginal, win rate, e a diferença P+ vs P− (o "spread" direcional).

## 5. Se sobreviver

Fase seguinte (SÓ então): transformar em regra operacional (ex.: baseboard=+,
fade de basis extremo) com a régua completa — walk-forward 90d, ≥5/8 janelas
positivas, PnL agregado > 0, PF > 1,3, custos reais. **Nada disso nesta
rodada.**