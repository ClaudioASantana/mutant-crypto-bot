# Q12 — BNBUSDT single-name rich+ study — design pré-registrado — 2026-08-22

> Status: **documento de design**. Nada implementado como estratégia, nada em
> paper/live.
>
> **Este é o teste mais perigoso da trilha por risco de data-snooping**: a Q11
> "descobriu" BNB sobre os dados; agora estou olhando especificamente para BNB.
> A régua precisa ser correspondentemente mais dura, e há guardrails explícitos
> abaixo para não transformar uma curiosidade de janela em estratégia.

---

## 1. Hipótese

> O efeito visto na Q11 — **BNBUSDT rich no basket + funding positivo → BNB
> continua outperformando o basket** — é real e **repetível dentro da mesma
> janela**, e não apenas um artefato de um único episódio ou subperíodo.

A pergunta que Q12 responde **não** é "BNB funciona?" (viés de confirmação).
A pergunta é:

> **Se eu corto a janela em subperíodos e separo episódios distintos, o efeito
> sobrevive? Ou ele era só um pump contínuo de BNB no meio da janela?**

## 2. Por que Q12 existe (e o risco que corrige)

Q11, em 8h:
- BNBUSDT contribuiu com **todos** os eventos RICH+ (`n=120`);
- marginal `+15,2bp`, sinal correto, caminho para positivo em 24h (`+30,6bp`).

Um cético corretíssimo responderia:
1. "Se todos os eventos vêm de um só ativo, é um estudo de **1 ativo** com
   amostra inflada por repetições de um mesmo movimento.";
2. "Se BNB subiu muito nessa janela, você só descobriu que comprar um ativo
   que sobe continua subindo — isso é momentum de um trending asset, não edge
   de microestrutura.";
3. "O efeito pode ser **um episódio único de várias horas** que gera dezenas de
   eventos correlacionados e nãos independentes."

Q12 existe para testar (1), (2) e (3) de forma direta.

## 3. Definição causal de evento (mantida da Q11)

- **Ativo estudado**: BNBUSDT.
- **Basket de referência para o rank** (o sinal continua cross-sectional):
  BTCUSDT, ETHUSDT, SOLUSDT, BNBUSDT, XRPUSDT, DOGEUSDT, ADAUSDT, LINKUSDT.
- `premium_rel(s,t) = premium_close(s,t) / perp_close(s,t)` em M15.
- `rn(s,t)` = rank normalizado cross-sectional do premium_rel no timestamp t.
- `funding(s,t)` = último funding conhecido até t (sem lookahead).
- **Evento BNB RICH+**: `rn(BNB,t) >= 0.75` **e** `funding(BNB,t) > +0.0001`.
- Entrada: close do candle de evento.
- Cooldown: 8 candles (2h), como antes.

## 4. Guardrails anti-snooping (pré-registrados)

### A. Independência temporal — "episódios" não "candles repetidos"
O `n` da Q11 (`120`) **não** mede independência. Um único movimento de BNB
sustentado por 2 dias gera dezenas de eventos correlacionados.

Definição de **episódio**:
- agrupar eventos consecutivos do mesmo sinal separados por **menos de 24h**
  (que o cooldown de 2h não captura);
- cada cluster = 1 episódio.

**Regra pré-registrada:**
- se o efeito for explicado por **1 único episódio** (≥ 60% dos eventos em 1
  episódio), a Q12 é **declarada vazia independentemente do PnL** — porque não
  há evidência de repetibilidade.

### B. Subperíodos
Cortar os 90 dias de janela em **3 fatias de 30 dias** (cada uma com ~30
eventos esperados se o efeito for estável).

**Regra pré-registrada:**
- o efeito **deve ter sinal positivo em pelo menos 2 das 3 fatias**;
- se o sinal vier de uma única fatia, é rejeitado como janela-dependente.

### C. Comparação contra "momentum-ingênuo"
Para descartar (2) — "BNB estava só subindo":
- medir o efeito **relativo ao basket** (não absoluto) — já é o que fazemos;
- além disso, reportar o **retorno absoluto do BNB** na janela: se BNB subiu
  tanto que até o controle relativo é forte, exige-se que o efeito RICH+
  **supere** o controle relativo condicional (retorno relativo médio do BNB em
  qualquer timestamp, não só nos eventos).

### D. Independência da janela
- Testar o efeito nas **3 fatias** descritas acima já é uma mini-validação
  out-of-sample temporal;
- não vamos "esticar" 130 dias adicionais; a janela é a mesma das rodadas
  anteriores, para não mudar a régua.

## 5. Medidas principais

Por horizonte (1h/4h/8h/24h), para BNB RICH+:
- n e número de **episódios**;
- marginal vs controle **relativo condicional** (média do retorno relativo do
  BNB em todos os timestamps da janela);
- win rate;
- por fatia de 30 dias;
- máximo de concentração de eventos em um episódio (%).

## 6. Veredito pré-registrado (falsificável)

Par primário: **BNB RICH+ × 8h × M15**.

**Falha** (qualquer uma):
- `n < 30`;
- **1 episódio domina ≥ 60% dos eventos** (repetição, não repetibilidade);
- sinal marginal **≤** controle relativo condicional (não supera momentum-ingênuo);
- efeito positivo em **menos de 2 das 3 fatias** de 30 dias;
- marginal **≤ 20bp** de custo piso.

**Sobrevive** somente se:
- `n ≥ 30`;
- max concentração episódio **< 60%**;
- efeito positivo em **≥ 2/3 fatias**;
- marginal em 8h **> 20bp**;
- e marginal **> controle condicional**.

## 7. Conclusão honesta antecipada

Dado que na Q11 todos os eventos vieram de BNB, a probabilidade a priori de que
a régua A. (concentração de episódio) já derrube a hipótese é alta. Esse é o
resultado esperado e aceitável: se o efeito morre aqui, a família cross-sectional
está encerrada como explorada — sem viés de sobrevivência do "último vencedor".

**Nada vai para paper/live.**