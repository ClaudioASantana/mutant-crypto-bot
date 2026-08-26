# Q13 — Swing horizon study (48h / 72h / 7d) — design pré-registrado — 2026-08-22

> Status: **documento de design**. Nada implementado como estratégia, nada em
> paper/live. Esta rodada não cria uma família nova; ela testa uma hipótese
> estrutural derivada do mapa final:
>
> **talvez alguns sinais reais que morreram em horizontes curtos não sejam falsos
> positivos — apenas pequenos demais para um round-trip intraday.**
>
> Se o alpha for capturado num hold mais longo, o custo piso de 10–20bp pode se
> diluir o bastante para o efeito aparecer líquido.

---

## 1. Hipótese

> Alguns sinais da trilha mostraram direção estatística correta, mas ficaram
> abaixo do custo em 1h–24h. Se o mesmo deslocamento persistir em horizontes
> swing (48h, 72h, 7d), a magnitude líquida pode superar o custo e revelar edge
> econômico que estava sendo esmagado pelo curto prazo.

## 2. Sinais elegíveis (pré-seleção justificada)

Esta rodada **não** vai reabrir tudo. Só entram sinais que já mostraram algum
conteúdo informacional verdadeiro, ainda que insuficiente economicamente.

### S1 — BTC basis extremo positivo (Q5 lado P+)
- definição mantida da Q5:
  - BTCUSDT M15
  - `premium_pct >= 0.95`
- leitura anterior: basis muito positivo → retorno futuro **negativo**
- 4h: ~`-7bp` marginal (real, mas < custo)

### S2 — RICH+ cross-sectional com funding positivo (Q11/Q12)
- definição mantida da Q11:
  - basket fixo: BTCUSDT, ETHUSDT, SOLUSDT, BNBUSDT, XRPUSDT, DOGEUSDT,
    ADAUSDT, LINKUSDT
  - `rn(s,t) >= 0.75`
  - funding > `+0.0001`
- leitura anterior: rich+ → retorno relativo **positivo**
- 8h: ~`+15,2bp`; 24h: ~`+30,6bp`, mas concentrado em BNB e sem repetibilidade

Esses são os dois únicos casos em que já vimos:
- direção coerente;
- magnitude não desprezível;
- mas ainda sem edge líquido promovível.

## 3. O que Q13 mede

Horizontes fixos:
- **48h**
- **72h**
- **7d**

Para cada sinal:
- retorno forward bruto;
- retorno líquido após custo piso;
- controle incondicional equivalente;
- t-stat do retorno bruto/líquido;
- win rate;
- amostra útil (`n`) por horizonte.

## 4. Custos

### S1 — BTC direcional
- custo piso: `10bp` round-trip total
  - mesma régua usada em Q5/Q6/Q7

### S2 — Cross-sectional relative trade
- custo piso: `20bp`
  - 2 patas × 10bp por pata
  - mesma régua usada em Q8–Q12

## 5. Regras causais

Nada usa futuro para definir evento:
- premium percentil / rank são observados no candle fechado do evento;
- funding usa o último valor conhecido até `t`;
- os horizontes futuros só servem para medir resultado.

## 6. Guardrails metodológicos

### A. Não reinterpretar Q12 como prova
Q12 mostrou que o caso RICH+ estava concentrado em BNB e não replicou nas fatias.
Logo, Q13 **não** pode concluir "S2 funciona" só porque 7d sobe. Ele precisa:
- superar custo;
- e não depender de um único subperíodo.

### B. Não trocar janela
A janela continua a mesma da trilha:
- 130 dias buscados
- 90 dias de estudo
- 40 dias de warmup implícitos

### C. Sobreposição de eventos
Horizontes longos fazem eventos se sobrepor naturalmente. Isso infla `n` se não
formos honestos. Portanto reportaremos:
- `n_raw` = todos os eventos
- `n_indep` = eventos após aplicar um **cooldown igual ao horizonte** (48h, 72h,
  7d) — leitura mais conservadora de independência

O veredito se apoia em `n_indep`, não em `n_raw`.

## 7. Veredito pré-registrado (falsificável)

### S1 — BTC basis extremo positivo
Par primário: **48h**.
- **Falha** se `n_indep < 20`, OU sinal não negativo vs controle, OU
  `|marginal_net| <= 10bp`.
- **Sobrevive** se `n_indep >= 20`, sinal negativo coerente em 48h/72h,
  e `|marginal_net| > 10bp` no primário.

### S2 — RICH+ cross-sectional com funding
Par primário: **72h**.
- **Falha** se `n_indep < 20`, OU sinal não positivo vs controle, OU
  `marginal_net <= 20bp`, OU concentração de símbolo continuar extrema
  (≥60% dos eventos independentes vindos de um só ativo).
- **Sobrevive** se `n_indep >= 20`, sinal positivo em 48h/72h/7d,
  `marginal_net > 20bp` no primário, e a concentração por símbolo cair abaixo
  de 60%.

## 8. Interpretação correta

Se sobreviver:
- ainda não é estratégia pronta;
- significa só que a hipótese **de horizonte mais longo** merece walk-forward
  próprio.

Se falhar:
- encerra-se a leitura de que "o problema era só custo de curto prazo";
- e a trilha deve migrar com prioridade para OI/fluxo real ou outra classe de
  informação.

**Nada vai para paper/live.**