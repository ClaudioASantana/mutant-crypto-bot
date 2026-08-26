# Q9 — Cross-sectional momentum (basis/premium) — design pré-registrado — 2026-08-22

> Status: **documento de design**. Nada implementado como estratégia, nada em
> paper/live. Hipótese nova, **derivada diretamente do resultado da Q8**:
> ativos "cheap" (premium relativo baixo) não rebateram — tenderam a continuar
> piores que o basket. Aqui invertemos a direção da aposta e testamos
> **continuação**, não reversão.

---

## 1. Hipótese

> Em um basket de perps USDT-M da Binance, quando o premium/basis relativo de um
> ativo está num extremo (rich ou cheap), o retorno forward **relativo ao basket**
> tende a **continuar na mesma direção**: ativo rich **continua a subperformar?**
> — não. Racional derivado da Q8:
> - **CHEAP** (premium relativo baixo / funding relativo baixo) → tendência de
>   **continuação para baixo** (relativo ao basket) nos horizontes curtos;
> - **RICH** (premium relativo alto) → sem sinal claro de reversão, possivelmente
>   continuação para cima em horizontes mais longos.

**Isso é exatamente o oposto da Q8**: a Q8 apostava em reversão (rich → subperform,
cheap → outperform). A Q9 aposta em **continuar o deslocamento**.

## 2. Por que continuar (em vez de reverter)

Resultado da Q8 (M15, 4h):
- RICH médio: `+0,00005` (subia, contrariando reversão)
- CHEAP médio: `-0,00020` (caía, contrariando reversão)

Se isso não for ruído, o deslocamento de premium relativo extremo **segue**. A
Q8 foi desenhada com uma SINAL-PREDIÇÃO fixa (reversão) e por isso o mesmo estudo
não pode ser re-lido como prova de momentum — precisamos de outra rodada,
pré-registrada, com a previsão correta.

## 3. Definição causal de evento

- **Basket fixo (mesma régua da Q8)**: BTCUSDT, ETHUSDT, SOLUSDT, BNBUSDT,
  XRPUSDT, DOGEUSDT, ADAUSDT, LINKUSDT.
- `premium_rel(s,t) = premium_close(s,t) / perp_close(s,t)`.
- **Rank normalizado** por timestamp: `rn(s,t) = (rank − 1)/(n − 1)` entre os 8.
- **Evento RICH**: `rn(s,t) >= 0.75` → o mesmo da Q8.
- **Evento CHEAP**: `rn(s,t) <= 0.25` → o mesmo da Q8.
- Entrada: close do candle de evento.
- Cooldown: 8 candles por símbolo/lado (como Q8).

## 4. SINAL-PREDIÇÃO (pré-registrado)

- **RICH → retorno relativo forward POSITIVO** (continuação de alta relativa).
- **CHEAP → retorno relativo forward NEGATIVO** (continuação de baixa relativa).

## 5. Retorno e custo

- Relativo ao basket (equiponderado dos outros 7), horizontes 1h/4h/8h/24h.
- Controle: retorno relativo incondicional de todos os pares.
- Custo piso: `20bp` (2 patas × 10bp round-trip por pata).
- Reportar PnL bruto relativo separadamente do líquido.

## 6. Veredito pré-registrado (falsificável)

Par primário: **RICH e CHEAP × 4h × M15**.

- **Falha** se `n < 30` por lado, OU o efeito marginal tiver sinal contrário ao
  previsto, OU `|marginal|` não superar o custo piso de 20bp.
- **Sobrevive** se `n ≥ 30` nos dois lados, sinal previsto consistente em
  1h/4h/8h, e `|marginal| > custo`.

Leituras de robustez (reportar, não admitir sozinhas):
- t-stat por lado;
- win rate;
- estabilidade por símbolo;
- comparação direta com o resultado da Q8 (mesmo cálculo, hipótese oposta).

## 7. Se sobreviver

Fase seguinte (SÓ então): transformar em regra operacional (entrar top/bottom
cross-sectional, sair por horizonte) com a régua completa — walk-forward 90d,
≥5/8 janelas, PnL > 0, PF > 1,3, custo real por pata. **Nada disso nesta
rodada.**

## 8. Distinção metodológica com Q8

Q8 predisse reversão; Q9 prediz momentum. Isto **não é** ajustar a mesma hipótese
até encontrar um resultado — é uma hipótese **distinta**, motivada por um
resultado empiricamente observado, e será reportada como tal (risco de
data-snooping declarado e aceito porque a pergunta é nova e a régua é rígida).