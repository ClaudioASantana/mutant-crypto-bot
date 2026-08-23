# Recomendações P2 — próxima shortlist de pesquisa — 2026-08-22

> Status: **documento de recomendação**. Nada implementado, nada em paper/live.
> Define hipóteses testáveis e o protocolo de validação antes de qualquer código.

---

## 1. O que a rodada P1 provou (e que desqualifica a base atual)

A validação registrada em [validacao-candidatas-p1-20260822.md](validacao-candidatas-p1-20260822.md)
encerrou a shortlist P1 com **4/4 reprovadas** sob custos honestos
(fee 0,04% + slippage 1bp por ponta) e walk-forward de 90 dias em janelas
OOS não sobrepostas de 7 dias:

| Candidata | Resultado no walk-forward |
|---|---|
| VWAP Z-Score | único OOS+ tinha treino negativo; alvo-em-VWAP perdeu em tudo |
| 3 Velas | negativa OOS nos dois TFs |
| Exaustão | 3/8 janelas OOS positivas; PnL agregado negativo |
| ABCD | 0/8 (M5) e 1/8 (M15) janelas OOS positivas |

Três lições estruturais:

1. **Frequência mata**: em M1/M5, o win rate cai para 12–35% e cada trade paga
   fee+slippage nas duas pontas. Estratégia de baixa seletividade no intraday
   curto é um gerador de custo, não de retorno (ABCD: −684 USD em 585 trades).
2. **Payoff mismatch**: o framing "sinal → TP/SL por ATR" assume retorno
   proporcional à volatilidade, mas carrega perdedores de 1,5×ATR contra
   vencedores que pouco recompensam. Mean reversion com alvo na VWAP (payoff
   descentralizado) também não sobreviveu.
3. **Sorte de regime**: OOS positivos em testes curtos (7–30 dias) eram a
   última semana favorável; janelas não sobrepostas devolveram tudo. Regime
   (ADX) não resgatou nenhuma delas.

**Implicação:** a base de sinais atual (crossovers, SMC, Wyckoff, exaustão,
reversão) não deve ser re-iterada com novos indicadores. A próxima frente deve
mudar o **que** é sinalizado e **quando** é permitido operar, não o toolkit.

---

## 2. Hipóteses P2 (testáveis, excludentes)

### H1 — "Filtros de sessão e volatilidade resgatam o zoo atual"
Se o prejuízo vem de operar horas mortas e volatilidade comprimida, **restrita** a
M15 e janelas de liquidez, as estratégias existentes deveriam melhorar. Teste
barato e disentangleable: aplicar os filtros (abaixo) como *wrapper* sobre as
estratégias do zoo, com o mesmo walk-forward. Se nada melhorar, o problema é o
**sinal**, não o horário — e H1 morre com evidência.

### H2 — "Breakout de regime em M15/H1 com filtro de volatilidade"
Donchian de janela longa (ex.: 55 velas) quebrado com:
- regime de tendência (`ADX_14 >= 25`);
- banda de volatilidade (`ATR` no percentil 40–90 da janela — nem morto, nem
  louco);
- alvo/saída por ATR com R:R estruturalmente favorável (ex.: TP/SL assimétrico)
  e **time stop** curto.
Menos trades, maior TF, payoff positivo por desenho.

### H3 — "Funding rate como filtro long/short de microestrutura"
Dados públicos de funding (Binance `fapi/v1/premiumIndex` histórico):
- short só com funding **positivo e crescendo** (posição long sobrecarregada);
- long só com funding **negativo ou neutro decrescente**;
- aplicado como seleção de direção sobre H2 (não como sinal isolado).
É o único "filtro externo" da lista e depende de fonte de dados nova.

### Hipótese que fica fora
**Mean reversion** em qualquer forma, até que haja evidência de que a
autocorrelação intraday do ativo suporta reversão (não testada aqui). M1 fica
fora por construção (frequência + custo).

---

## 3. Filtros reutilizáveis a implementar (research-only)

Estes são pré-requisitos das três hipóteses e servem de overlay para qualquer
sinal futuro:

1. `filter_session_utc(df, signal, sessions)` — só permite entrada em janelas
   de alta liquidez. Sessões-alvo (referência): overlap Londres/NY
   (12h–16h UTC) e NY manhã (13h–17h UTC); a config de janelas deve ser
   **dado do experimento**, não chutada no código.
2. `filter_atr_percentile(df, signal)` — exige `ATR_14` no percentil 40–90 da
   janela das últimas N velas.
3. `filter_regime_adx(df, signal)` — já parametrizável o limiar; reutiliza o
   conceito do walk-forward (ADX ≥ 25 = trend).
4. `funding_direction_filter(df, signal, funding)` — de H3, consome série de
   funding alinhada por timestamp (sem lookahead: funding conhecido só na
   captura).

Todas as funções retornam `bool` e são **puras** — nenhuma toca o executor.

---

## 4. Protocolo de validação (idêntico ao que refutou P1)

Mesma régua, para evitar repetir o erro de julgar com teste curto:

1. Dados: BTCUSDT M15 e H1, **90 dias** (H1: zoo restrito ao M15).
2. Custos: `TradingCostConfig(fee_rate=0.0004, slippage_bps=1.0)`.
3. Walk-forward: janelas OOS de 7 dias, passo 7 dias, warmup 30 dias
   (`experiment_walkforward.py`).
4. Critério de admissão: **≥ 5 de 8 janelas OOS positivas** *e* PnL agregado OOS
   > 0 *e* PF OOS > 1,3 — sem cherry-pick de regime.
5. Só depois disso: split por regime e, se sobreviver, paper trade.

---

## 5. Ordem de execução proposta

1. **H1 primeiro** (mais barato): wrapper de filtros de sessão/ATR/ADX sobre as
   estratégias atuais em M15 + walk-forward.
2. Se H1 morrer com evidência: **H2** (breakout de regime) implementado do zero
   com o protocolo acima.
3. **H3** apenas se H2 sobreviver (adiciona a fonte de dados de funding).

Cada etapa gera um arquivo de experimento em `backend/scripts/` e uma linha no
relatório de validação. **Nada promovido sem passar pelo critério de admissão.**