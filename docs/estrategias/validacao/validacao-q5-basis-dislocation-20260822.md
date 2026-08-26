# Q5 — Basis/premium dislocation — veredito do event study — 2026-08-22

> Design pré-registrado: `q5-basis-event-study-design-20260822.md`.
> Script: `backend/scripts/experiment_q5_basis_dislocation.py`.
> Fonte: `fapi/v1/premiumIndexKlines` + `fapi/v1/klines` (Binance Futures, mesma
> fonte validada no backbone Q4). BTCUSDT, 130 dias buscados, janela de evento
> nos últimos 90 dias, percentil causal em janela rolante de 384 candles.

## 1. Resultado do par primário (P+/P− × 4h × M15)

| Lado | n   | net médio | ctrl_net | marginal | sinal previsto? |
|------|-----|-----------|----------|----------|------------------|
| P+   | 217 | -0,0016   | -0,0010  | **-0,0007** | ✅ sim |
| P−   | 207 | -0,0007   | -0,0010  | **+0,0002** | ✅ sim |

**Veredito pré-registrado: ❌ FALHA.**
- `n_ok = True` (ambos os lados ≥ 50, muito acima do mínimo).
- `sign_ok = True` (o sinal do efeito marginal bate com a hipótese em ambos os lados).
- `mag_ok = False` — **os dois efeitos marginais (7bp e 2bp) são menores que o
  custo round-trip de 10bp**. A regra de falsificação pré-registrada
  (`|marginal| <= custo → falha`) é objetiva e o resultado cai exatamente nela.

## 2. Leitura honesta — não é "sem sinal", é "sinal real, mas pequeno demais"

Isso é diferente dos vereditos de H1/H2/H3/Q3, que não mostraram nem
direção nem magnitude. Aqui:

- **P+ (basis extremo alto) tem sinal direcional negativo consistente** em
  TODOS os horizontes testados em M15 (1h, 4h, 8h, 24h), com t-stat do próprio
  retorno líquido decrescendo de -3,54 (1h) a -1,25 (24h) — o efeito é mais
  forte perto do evento e decai, como se espera de uma dislocação de curto
  prazo se normalizando.
- **P− (basis extremo baixo) tem sinal direcional positivo apenas em 1h/4h**,
  e inverte de sinal em 8h/24h — menos robusto que P+.
- Em **H1** o padrão não se sustenta: P+ inverte de sinal em 8h/24h; P− só é
  consistente até 8h e inverte em 24h. A confluência com funding (P+ com
  funding>0 vs funding≤0) não mostra diferença de magnitude relevante.

Conclusão: existe uma micro-mean-reversion real e estatisticamente detectável
em torno de extremos de basis intradiário, mas sua magnitude (na casa de
2-7bp) é **menor que o próprio custo de transação de ida-e-volta (10bp)**.
Operar isso direcionalmente, pagando spread/fee/slippage duas vezes por
trade, **queima exatamente o tamanho do efeito**. Não é uma estratégia
viável nesse desenho.

## 3. O que isso NÃO invalida

O event study testou uma hipótese específica: **aposta direcional no
underlying condicionada a extremo de basis, pagando custo de round-trip
completo**. Isso é diferente de:

- **Carry delta-neutral**: coletar o funding sem tomar risco direcional
  (long spot / short perp ou vice-versa) — aqui o "prêmio" capturado é o
  próprio funding pago pela contraparte, não uma aposta em reversão de preço.
  Essa estrutura tem custo de round-trip **diferente** (não precisa fechar
  posição a cada extremo, mantém-se enquanto o carry for favorável) e não foi
  testada aqui.
- Isso é uma hipótese **nova e distinta**, não um reteste com threshold
  ajustado da mesma hipótese — portanto não é elegível a ser tratada como
  continuação desta rodada. Se o usuário quiser persegui-la, ela precisa do
  mesmo tratamento: design pré-registrado e regra de falsificação próprios,
  numa rodada futura (candidato a "Q6").

## 4. Encerramento desta rodada

Q5, como desenhada (event study direcional de basis/premium), está encerrada
como **reprovada pela régua de custo**. Nenhuma estratégia é promovida.
Nada muda em paper/live.

**Placar agregado da trilha quantitativa até aqui:**
- P1 (zoo de estratégias legado): 4/4 reprovadas.
- H1 (filtros de sessão/ATR/ADX): reprovada.
- H2 (breakout de regime): reprovada.
- H3 (funding como filtro direcional): reprovada.
- Q3 (liquidation fade): reprovada (amostra insuficiente).
- Q5 (basis/premium dislocation direcional): reprovada (efeito real, mas
  menor que o custo).

Seis hipóteses testadas com a mesma régua honesta, seis reprovadas — mas
Q5 é a primeira que mostrou um efeito estatisticamente real e consistente
em direção, só perdendo pela margem de custo. Isso é um resultado
qualitativamente diferente dos anteriores e aponta para onde vale insistir:
estruturas que não pagam round-trip completo por sinal (carry, hedge
estático, ou horizontes mais longos que dilua o custo por unidade de tempo).