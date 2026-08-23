# Recomendações de Estratégia — Day Trade de Cripto (2026-08-22)

## 1. Contexto e objetivo

Com o hardening operacional (auth, `OperationalConfig`, execução fail-closed, persistência canônica em SQLite/SQLAlchemy) já consolidado, chegou o momento de retomar a trilha quantitativa — mas com disciplina, não com "mais uma estratégia às cegas".

Este documento faz para o crypto o mesmo papel que `docs/estrategias/novas-estrategias-*.md` faz no `mutante-opcoes-acoes`:

1. inventaria o que o motor **já** faz;
2. lê com honestidade o que os backtests atuais **realmente** dizem;
3. propõe famílias de estratégia que **cabem no stack atual**;
4. entrega uma **shortlist priorizada** e um **backlog de experimentos**.

A conclusão mais importante está na seção 3: **o conjunto atual de estratégias ainda não demonstra edge líquido no config padrão**. Portanto, a recomendação central não é "adicionar mais estratégias", e sim **consertar primeiro a régua de medição** e só então testar candidatas com critérios institucionais.

---

## 2. Estado atual do motor (inventário)

### 2.1 Estratégias já implementadas

Em `backend/app/application/services/technical_analysis.py`, registradas via `@register_strategy` (resolvidas por `StrategyRegistry` em `backend/app/domain/services/strategy_registry.py`):

| Estratégia | Lógica | Família |
|---|---|---|
| `EMA+MACD` | cruzamento EMA9×EMA21 + histograma MACD | trend/momentum |
| `Momentum Breakout` | EMA9>EMA21, preço>EMA50, RSI>55 | momentum breakout |
| `Bollinger` | toque/reversão nas bandas (20,2) | mean reversion |
| `VWAP` | cruzamento do preço sobre a VWAP | mean reversion intradiária |
| `SuperTrend` | virada de direção do SuperTrend(10,4) | trend following |
| `SMC` | Fair Value Gap + estrutura de mercado + volume + RSI + EMA20 | smart money |
| `Wyckoff_SMC` | reteste de canal Donchian(20) | breakout retest |
| `Wyckoff_Bollinger` | reteste de banda de Bollinger após rompimento | breakout retest |
| `Pin Bar` | rejeição (pavio) + contexto BB + volume | reversal |
| `ABCD` | stop-run / falso rompimento + EMA21 | smart money |
| `3 Velas` | composto: 3-bar-play, 3 white soldiers, 3 black crows, morning/evening star | candlestick |
| `RSI+EMA` | pullback na tendência (EMA21) com RSI em zona de respiro | trend pullback |
| `Exaustão` | candle climático + RSI extremo + reversão | mean reversion |

### 2.2 Indicadores disponíveis (via `pandas_ta` em `apply_indicators`)

EMA (9/15/20/21/50/200), MACD (12/26/9), Bollinger (20,2), VWAP, ATR(14), Donchian(20), SuperTrend(10,4), RSI(14) + estrutura de mercado custom (swings, HH/HL/LL/LH) e detecção de FVG.

Faltam (fáceis de adicionar por já serem nativas do `pandas_ta`): **Keltner Channels**, **ADX/DI**, **OBV**, **volume profile**, **realized range**, **sessão/regime**.

### 2.3 Harnesses de pesquisa/backtest

| Script | O que faz | Métricas |
|---|---|---|
| `backend/scripts/benchmark_all.py` | ranking de ~10 estratégias, SL/TP fixo 2.0/2.0, 10x | PnL, WR, DD, #trades |
| `backend/scripts/analyze_strategies_30d.py` | 30d via `BacktestService` | sinais, WR, PnL |
| `backend/scripts/deep_backtest.py` | 6 estratégias × M1/M5/M15, SL/TP por ATR | sinais, WR, PnL |
| `backend/scripts/optimizer.py` | grid search 108 configs (3-velas × RSI) | WR, PnL |
| `backend/scripts/fitness_backtest.py` | seletor de personalidade (estático vs dinâmico) | PnL por personalidade |
| `backend/scripts/run_weekly_backtest.py` | relatório semanal mais honesto | **profit factor, max DD%, expectancy**, amostras |

O mais maduro metodologicamente é o `run_weekly_backtest.py`, porque já separa `gross`/`net`, calcula profit factor, drawdown e expectancy por trade — falta Sharpe/Sortino, custos realistas e walk-forward.

### 2.4 Dados, risco e sizing

- **Dados:** Binance OHLCV (ccxt ou `/api/v3/klines`), cache em SQLite `market_history.db`, timeframes M1/M5/M15. Ativo principal `BTC/USDT`.
- **Risco:** `RiskManager` em `backend/app/infrastructure/services/risk_manager.py` — SL/TP por multiplicador de ATR, sizing fixo/volatility_adjusted, leverage, trailing stop, time stop, circuit breaker diário e stop dinâmico.
- **Posição:** `BacktestSimulatorImpl` usa `PaperTrader` real + `RiskManager`, uma posição por vez.

---

## 3. O que os backtests atuais realmente dizem

Ler `backend/strategy_ranking_30d.json` (30 dias, BTC/USDT, M5, config default):

- **Todas as 10 estratégias ficaram negativas no líquido.**
- Melhor: `Exaustão` (−2.01). Depois `RSI+EMA` (−94). As demais perdem entre −206 e −2522.
- `SMC` é a pior (−2522) apesar de 2730 sinais e WR 35.6%: **overtrading puro** — alta frequência com expectancy negativa multiplica a perda.
- WRs vão de 33% a 66%, mas **nenhuma** cobre os custos/assimetria de payoff.

Leitura de `backend/scripts/weekly_backtest_result_*.json` (janela de 7d, com profit factor/expectancy):

- `SMC` M15 chega a net +11.97 (PF 3.62) e `Bollinger` M15 a +4.44 (PF 1.82) — **mas com 9 a 18 trades**, amostra pequena demais para concluir edge.
- `EMA+MACD` M15 fica −12 (PF 0.6).

**Conclusões honestas:**

1. Nenhuma estratégia atual tem edge comprovado no default (SL/TP 2.0/2.0 ou ATR 1.5/3.0, 10x, BTC M5).
2. O ranking por **PnL bruto** premia a estratégia que mais opera (SMC), não a que tem expectancy positiva.
3. Os harnesses não modelam **taxas/slippage** de forma realista e **não separam treino/validação** — risco alto de overfitting.

Isso não significa que as ideias são ruins; significa que **a régua de medição atual não é confiável** para escolher estratégia.

---

## 4. Critérios de avaliação (métrica mínima antes de paper/live)

Para qualquer candidata, exigir **todos** os itens, não só win rate ou PnL:

1. **Expectancy por trade** (`avg_win*win_rate − avg_loss*(1−win_rate)`) > 0, com intervalo de confiança.
2. **Profit factor** ≥ 1.3 (ideal > 1.5).
3. **Payoff ratio** (ganho médio / perda média): se > 2.0, tolera WR de 35–40%.
4. **Max drawdown** (% e R$) dentro do limite da `RiskProfile`.
5. **Sharpe / Sortino** (anualizado) quando a frequência permitir.
6. **Turnover/frequência**: estratégias de alta frequência precisam de expectancy bem maior para pagar custo.
7. **Sensibilidade a custo**: rodar com fee + slippage (ex.: maker/taker ~0.02–0.10%, slippage 0.5–2 bps por lado) e ver se o edge sobrevive.
8. **Walk-forward**: otimizar em janela in-sample (~70%), validar em out-of-sample (~30%) nunca visto.
9. **Split por regime**: separar resultado em trend / chop / alta vol / baixa vol. Uma estratégia só vale se for robusta, não se for a média de um regime favorável.

---

## 5. Famílias de estratégia para day trade de crypto

Legenda de aderência: ✅ = cabe no stack hoje · 🟡 = exige instrumentação leve · 🔴 = exige dados/infra nova.

### 5.1 Momentum / Breakout intradiário ✅

- **Hipótese:** compressão de volatilidade precede expansão direcional; entrar no rompimento confirmado.
- **Já existe (parcial):** `Momentum Breakout`, `SuperTrend`, `Wyckoff_SMC`.
- **O que falta:** filtro de regime (ADX) e confirmação de volume na vela de rompimento; alvo/stop mais assimétrico (TP maior que SL), pois momentum paga com poucos ganhadores grandes.
- **Atenção:** é a família que mais sofre em chop; exige filtro de sessão/regime para não overtrade.

### 5.2 VWAP Pullback / Mean Reversion intradiária ✅

- **Hipótese:** preço esticado demais em relação à VWAP (ou às bandas) tende a reverter à média em day trade de ativo líquido.
- **Já existe:** `VWAP`, `Bollinger`, `Exaustão`.
- **Melhoria de maior alavancagem:** trocar o gatilho binário por **Z-Score da VWAP** (desvio normalizado) — exatamente o padrão do manual de opções (`Z_t = (Close − VWAP) / σ`) — em vez do simples cruzamento. Thresholds mais seletivos (menos trades, mais qualidade), na linha do que o manual de opções já formalizou.
- **Risco:** reverter contra tendência forte; mitigar com filtro de tendência (EMA200) e evitar entrada durante notícia.

### 5.3 Opening Range Breakout (ORB) com referência de sessão 🟡

- **Hipótese:** a faixa inicial de uma sessão define suporte/resistência de referência; o rompimento dessa faixa, com volume, tem continuação.
- **Crypto é 24/7:** não há "abertura" como na B3. A adaptação correta é usar a **sessão UTC** (00:00) ou sessões de liquidez (ex.: abertura de Londres/NY) como "range de abertura" (primeiras 1–2h).
- **Dependência:** já dá para calcular com OHLCV M5; a parte 🟡 é definir sessões de liquidez e sincronizar o conceito de "dia" com o relógio do bot (evitar o bug de virada de dia/fuso).
- **Risco:** rompimentos falsos em liquidez baixa; exige volume filter agressivo e reteste.

### 5.4 Volatility Squeeze (Bollinger dentro de Keltner) 🟡

- **Hipótese:** quando Bollinger(20,2) fica **dentro** do Keltner(20,1.5–2.0), a volatilidade está comprimida ("mola"); a saída do squeeze + momentum dispara a expansão.
- **Já existe:** Bollinger; **falta só adicionar Keltner** (`pandas_ta.kc`), que é trivial.
- **É o análogo direto do "TTM Squeeze" do projeto de opções**, já validado lá como família de rompimento.
- **Risco:** precisa de gatilho de momentum (ex.: histograma MACD, RVOL) para não entrar em squeeze que nunca dispara.

### 5.5 Trend-following com pullback (já existe, precisa calibração) ✅

- `RSI+EMA` e `EMA+MACD` já implementam isso. O problema não é a lógica, é a **calibração de SL/TP e o filtro de regime**.

### 5.6 Pares / stat arb 🟡/🔴

- **Hipótese:** spread cointegrado reverte à média (delta-neutro).
- **No crypto**, é viável com pares tipo `BTC/ETH` ou perps correlacionados, mas **a atomicidade das duas pernas é crítica** (risco já mapeado no projeto de opções: se a perna B falha, a exposição fica desbalanceada).
- **Classificação:** deixar como fase 2, depois que a remediação de execução/atomicidade estiver fechada.

### 5.7 Funding rate / Open Interest / Order flow 🔴

- **Hipótese:** posicionamento extremo (funding muito positivo/negativo, OI em alta com preço caindo, taker buy/sell desequilibrado) antecipa reversão ou continuação.
- **Depende de dados que o bot ainda não consolida** (funding, OI, aggregated trades/liquidações).
- **Classificação:** fase futura — não recomendação principal. Anotar como backlog de instrumentação de dados.

---

## 6. Shortlist priorizada

A prioridade combina: aderência ao stack, clareza de hipótese, facilidade de backtest honesto e robustez esperada em crypto intradiário.

### P0 — Consertar a régua antes de escolher (pré-requisito)

Nenhuma estratégia deve ser promovida a paper/live antes de o harness medir expectancy, profit factor, drawdown e sensibilidade a custo com walk-forward. Sem isso, qualquer shortlist é opinião, não evidência.

### P1 — Candidatas para validar já (stack atual)

1. **VWAP Z-Score Mean Reversion** (evolução da `VWAP` atual) — menor esforço, maior alavancagem de qualidade: trocar cruzamento por desvio normalizado com threshold seletivo + filtro de tendência. É a família que o projeto de opções já trata como estratégia principal.
2. **Volatility Squeeze (BB⊂Keltner) + gatilho de momentum** — análogo direto do TTM Squeeze; só falta adicionar Keltner.
3. **Opening Range Breakout por sessão UTC** — ortogonal às duas acima (captura regime de tendência, não reversão), bom para diversificar.

### P2 — Apostas exploratórias (exigem instrumentação leve)

4. **Momentum Breakout calibrado** (ADX/regime + volume) — recuperar a família já existente com filtros que evitem overtrade.
5. **Funding/OI regime filter** — não como sinal isolado, mas como **filtro de regime** sobre as candidatas P1 (ex.: não fazer mean reversion quando funding está extremo contra).

### Fase 3 — Bloqueadas até remediação operacional

- **Pairs trading** (atomicidade das pernas).
- **Qualquer expansão de automação live** (riscos de AI/RAG/executor ainda abertos — ver `reaudit-2026-08-followup`).

---

## 7. Melhorias críticas no motor de backtest (espelhar o projeto de opções)

O doc `novas-estrategias` do projeto de opções já listou exatamente o que o crypto precisa. Portar os mesmos quatro upgrades:

1. **Saídas dinâmicas por ATR** — já parcial em `deep_backtest.py` e `run_weekly_backtest.py`; padronizar e garantir que o `BacktestSimulatorImpl` use SL/TP por ATR (hoje o `benchmark_all.py` usa 2.0/2.0 fixo).
2. **Custos e fricção** — adicionar taxa + slippage ao PnL (separar `gross`/`net`). Sem isso, estratégia de alta frequência vira falso positivo.
3. **Métricas institucionais** — profit factor, payoff, max drawdown, Sharpe/Sortino, expectancy (o `run_weekly_backtest.py` já tem 3 delas; completar e centralizar).
4. **Walk-forward + split por regime** — obrigatório para evitar overfitting (o `optimizer.py` atual faz grid search sem out-of-sample).

Adicional específico do crypto:
5. **Auditoria anti-lookahead e timing de vela** — confirmar que toda estratégia é avaliada **somente com velas fechadas** (o `eval_smc` usa a última vela como `c3`; ok no backtest, mas exige auditoria no live). E definir o conceito de "sessão/dia" (UTC) para ORB e VWAP reset.

---

## 8. Backlog de execução sugerido

1. **Centralizar métricas de avaliação** num único módulo de métricas (expectancy, profit factor, payoff, drawdown, Sharpe/Sortino) reutilizável por todos os harnesses.
2. **Adicionar modelo de custo** (fee + slippage configurável) ao `BacktestSimulatorImpl` e aos scripts.
3. **Adicionar Keltner** em `apply_indicators` e implementar `eval_squeeze_breakout` registrado.
4. **Implementar `eval_vwap_zscore`** (substitui/evolui `eval_vwap`) com threshold de Z-Score e filtro de tendência.
5. **Implementar ORB** com sessão UTC e volume filter.
6. **Adicionar walk-forward** (ou pelo menos split treino/teste por janela temporal) aos harnesses.
7. **Rodar o ranking honesto** das candidatas P1 e só promover as que baterem as métricas da seção 4.
8. **Paper trading** das vencedoras com o runtime canônico (já pronto), antes de qualquer live.

---

## 9. Guardas e riscos

- **Não promover para live** enquanto os riscos operacionais de AI/RAG/executor da `reaudit-2026-08-followup` não forem remediados. Pesquisa/backtest/paper não têm esse risco; automação live, sim.
- **Evitar concluir por PnL bruto** em janela curta (o caso `SMC` −2522 é o contraexemplo perfeito).
- **Custos mudam o ranking**: re-ranquear sempre com fee + slippage antes de decidir.
- **Crypto 24/7 exige conceito de sessão explícito** (UTC) para qualquer estratégia com referência diária (VWAP reset, ORB).

---

## 10. Referências internas

- Inventário de estratégias/indicadores: `backend/app/application/services/technical_analysis.py`
- Registro: `backend/app/domain/services/strategy_registry.py`
- Risco/sizing: `backend/app/infrastructure/services/risk_manager.py`
- Simulador: `backend/app/infrastructure/services/backtest_simulation_impl.py`
- Harnesses: `backend/scripts/{benchmark_all,analyze_strategies_30d,deep_backtest,optimizer,fitness_backtest,run_weekly_backtest}.py`
- Resultados atuais: `backend/strategy_ranking_30d.json`, `backend/scripts/weekly_backtest_result_*.json`
- Baseline metodológico (projeto de opções): `docs/MANUAL_DE_ESTUDO_SISTEMA_QUANTITATIVO.md`, `docs/estrategias/novas-estrategias-*.md`
