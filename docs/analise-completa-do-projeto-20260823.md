# Análise Completa do Mutant Crypto Bot — 2026-08-23

## Resumo Executivo

O **Mutant Crypto Bot** é um sistema de trading algorítmico institucionalmente maduro, com arquitetura CQRS + DDD, 24 hipóteses quantitativas testadas com rigor acadêmico e infraestrutura própria de coleta de dados. 

**Resultado principal:** Nenhuma das 24 estratégias testadas apresentou **edge líquido robusto** após custos, causalidade e controles de robustez.

---

## O Que É o Projeto

### Arquitetura Técnica

```
Backend: FastAPI + SQLAlchemy + Celery + Redis (Python 3.12)
Frontend: Next.js 14 + TypeScript
DB: SQLite (CQRS) + JSON (legacy)
IA: Ollama (Qwen2.5) + ChromaDB RAG
Exchange: Binance (websocket + REST)
Dados: Binance Vision (gratuito) + snapshot próprio de OI/funding
```

### Componentes Principais

- **24 hipóteses testadas** (Q3-Q23, P1, H1-H3) com pré-registro
- **Backtest engine** com walk-forward, custos realistas, controle de lookahead
- **Paper trader** operacional + código LIVE para Binance
- **Coleta própria** de OI/funding (snapshot a cada 15min, append-only)
- **IA local** como filtro de veto (não como geradora de alpha)

---

## As 24 Hipóteses Testadas

### P1 — Estratégias Legado (4/4 ❌)

| Estratégia | PnL (30d) | Win Rate | Trades |
|---|---|---|---|
| Exaustão | -0.34% | 71.4% | 15 |
| RSI+EMA | -11.02% | 42.0% | 50 |
| SuperTrend | -17.83% | 44.0% | 50 |
| SMC | -25.1% | 44.9% | 50 |
| EMA+MACD | -25.41% | 40.0% | 50 |
| VWAP | -35.33% | 38.0% | 50 |
| 3 Velas | -38.07% | 34.0% | 50 |
| Pin Bar | -41.47% | 30.0% | 50 |
| Bollinger | -77.97% | 36.7% | 50 |
| ABCD | -87.5% | 29.2% | 50 |

**Lição:** Ranking por PnL bruto era enganoso; sem edge líquido no config padrão.

### H1-H3 — Filtros de Regime (3/3 ❌)

- **H1:** Filtros (sessão UTC, ATR, ADX) reduziram trades, **não criaram edge**
- **H2:** Breakout (Donchian 55 + ADX): M15 perdeu, H1 quase não operou
- **H3:** Funding como filtro direcional: podou perdas, não criou vantagem

**Lição:** Filtro não ressuscita estratégia morta.

### Q3-Q23 — Event Studies (17/17 ❌)

| Hipótese | Edge Bruto | Edge Líquido | Veredito |
|---|---|---|---|
| Q3: Liquidation fade | Amostra fraca | — | ❌ |
| Q4: Backbone dados | Infra (não edge) | — | ✅ (sucesso) |
| Q5: Basis dislocation | ~7bp < custo | -7bp | ❌ |
| Q6: Carry capture | Funding pequeno | -custo | ❌ |
| Q7: Regime funding+basis | Raro + fraco | — | ❌ |
| Q8: Cross-sectional reversão | Sinal contrário | — | ❌ |
| Q9: Cross-sectional momentum | Direção certa, < custo | ~5bp | ❌ |
| Q10: Momentum + funding | Melhorou RICH, piorou CHEAP | assimétrico | ❌ |
| Q11: RICH-only + funding | +15bp (8h), +30bp (24h) | < 20bp + BNB | ❌ |
| Q12: BNB single-name | 1/3 fatias positivas | +11.5bp < custo | ❌ |
| Q14: BTC basis swing | -1.5bp líquido | -1.5bp | ❌ |
| Q15: OI divergence unwind | +92.8bp (direção errada) | continuação | ❌ |
| Q16: OI crowded continuation (longa) | -1.0bp (E1), +15.5bp (E2 errado) | 2/6 fatias | ❌ |
| Q17: Taker flow isolado | -3.7bp (E1), +0.7bp (E2) | 1-2/6 fatias | ❌ |
| Q19: BB squeeze + MACD | -7.2bp (E1), -4.9bp (E2) | 2/6, 5/6 fatias | ❌ |
| Q20: Trend following diário | CAGR 47-88% do B&H | MaxDD 63-67% > 50% | ❌ |
| Q21: Vol-targeting sizing | MaxDD 54-65% > 50% | CAGR 25-29% | ❌ |
| Q22: BB+MACD pullback 15m | CAGR gross -15% a +1% | CAGR net -72% a -13% | ❌ |
| Q23: Operador contextual | 99.9% ENTER (redundante) | CAGR net -11% | ❌ |

---

## Metodologia de Teste (Padrão Institucional)

Cada hipótese foi avaliada com:

1. **Pré-registro:** Hipótese escrita ANTES de rodar
2. **Dataset fixo:** Ex: 3.293 velas 1d (2017-2026), 315.549 velas 15m
3. **Controle:** Buy-and-hold benchmark (CAGR +37.79%, MaxDD 83.19%)
4. **Custo explícito:** 10-20bp round-trip por trade
5. **Múltiplas métricas:** CAGR, Sharpe, MaxDD, flips, win rate
6. **Robustez temporal:** 2/2 metades, 2-3/3 ciclos positivos
7. **Critérios de promoção:**
   - C1: CAGR ≥ 40% do B&H
   - C2: MaxDD ≤ 60% do B&H (≤ 49.91%)
   - C3: Robustez temporal (metades + ciclos)
   - C4: Custo ≤ 1pp de CAGR

---

## Principais Descobertas

### 1. Superfície Pública de Preço Foi Espremida

- **TA clássica:** 10 estratégias → 10/10 ❌
- **Filtros de regime:** 3 hipóteses → 3/3 ❌
- **Basis/funding:** 7 hipóteses → 7/7 ❌
- **Cross-sectional:** 5 hipóteses → 5/5 ❌
- **OI/flow:** 4 hipóteses → 4/4 ❌
- **Trend following:** 3 regras → 3/3 ❌
- **Vol-targeting:** 3 variantes → 3/3 ❌
- **BB+MACD:** 3 variantes → 3/3 ❌

**Conclusão:** Informação pública de preço de BTC **não tem edge promotor** no setup atual.

### 2. Fronteira CAGR × Drawdown do BTC

**Q20 (Trend Following):**
- Preservou 47-88% do upside do B&H
- MaxDD caiu de 83.19% para 63-67% (só -19-24pp)
- **Falhou:** Alvo era ≤ 49.91%

**Q21 (Vol-Targeting Sizing):**
- MaxDD caiu para 54-65% (melhor que timing)
- CAGR caiu para 25-29% (vs 37.79% B&H)
- **Falhou:** Alvo era ≤ 49.91% (V3 ficou 3.8pp acima)

**Lição estrutural:** Drawdown do BTC é **fundo E longo** (83%, 1.073 dias). Nem timing nem sizing entregam a combinação exigida.

### 3. O Quase-Edge: Q11 (RICH-Only + Funding)

**Melhor resultado da trilha:**
- RICH+ em 8h: **+15.2bp** (mas < 20bp custo piso)
- RICH+ em 24h: **+30.6bp** (mas concentrado em BNB)

**Q12 (BNB single-name) mostrou:**
- 1/3 fatias positivas (não replicou)
- Marginal +11.5bp em 8h < 20bp

**Conclusão:** O que parecia promissor era **subperíodo favorável em BNB**, não edge estrutural.

### 4. Achado Incidental: Squeeze do Lado Crowded

**Q15/Q16 mostraram:**
- Crowded long: +92.8bp em 8h (janela curta, direção errada)
- E2 longa: +83.6bp em 24h (2/6 fatias, sem repetibilidade)

**Status:** Não é edge (faltou repetibilidade), mas pode justificar **hipótese futura nova** (Q18 pré-registrada, não executada).

---

## Infraestrutura como Ativo

### Backbone de Dados (Q4 ✅)

```
- Klines: 2017-2026 (gratuito, Binance Vision)
- Funding rates: 2020-2026
- Premium index: 2020-2026
- Mark/Index prices: 2020-2026
- Snapshot próprio OI/funding: rodando a cada 15min (:03/:18/:33/:48)
```

**Valor:** Coleta própria de OI/funding é **ativo estratégico** para hipóteses futuras com dado independente.

### Monitor de Saúde

```bash
venv/bin/python scripts/check_snapshot_health.py
```

Morre se série estiver stale ou com buracos.

---

## Gap de Hardening Operacional

Comparado ao `mutante-opcoes-acoes`, o crypto bot tem gaps em:

### P0 (Em Progresso)

- ✅ Auth por `X-API-Key` em rotas sensíveis
- ✅ Gate de token no WebSocket
- ✅ `OperationalConfig` central para `execution_mode`
- ✅ Bloqueio fail-closed do caminho LIVE
- ⏳ Política final para token ausente
- ⏳ `/health` honesto por dependência
- ⏳ Persistência unificada (SQLAlchemy canônico)

### P1/P2 (Pendentes)

- Persistência fragmentada (JSON + SQLite + journal.db)
- RAG/IA sem trilha de proveniência forte
- UI com elementos cosméticos (AI Feed ilustrativo)

---

## Próximas Fronteiras (Por Prioridade)

| Frente | Edge Potencial | Custo Dados | Complexidade | Status |
|---|---|---|---|---|
| **OI/flow próprios (Camada B)** | Alto (independente) | Baixo (já coletando) | Média | Coletando |
| **Squeeze do lado crowded (Q18)** | Médio (achado incidental) | Baixo | Baixa | Pré-registrada |
| **Outro venue (ex: Binance vs OKX)** | Médio | Alto | Alta | Não iniciada |
| **Cross-exchange funding arb** | Baixo-Médio | Médio | Média | Não iniciada |
| **Altcoins small-cap** | Médio | Baixo | Baixa | Não iniciada |
| **TA em outro horizonte (swing multi-dia)** | Baixo (já testado Q14) | Baixo | Baixa | Q14 ❌ |

---

## Recomendações

### Curto Prazo (1-2 semanas)

1. **Completar P0 de Hardening**
   - Operational Config centralizada
   - `/health` honesto por dependência
   - Persistência unificada (SQLAlchemy)

2. **Documentar Encerramento da Trilha Q5-Q23**
   - Este arquivo já é um começo
   - Sintetizar: testado, funcionou parcialmente, descartado

3. **Manter Coleta Própria Rodando**
   - `collect_snapshot.py` já está ativo
   - É ativo estratégico para hipóteses futuras

### Médio Prazo (1-3 meses)

4. **Decidir Próximo Passo**

**Opção A (Continuar em Crypto):**
- PAUSAR pesquisa de edge por 3-6 meses
- Usar DCA semanal em BTC/ETH (sem timing)
- Esperar Camada B (OI/flow) maturar
- Depois testar combinações (OI + funding + basis + taker flow)

**Opção B (Migrar para B3):**
- Focar em `mutante-opcoes-acoes`
- Pairs Trading (edge mais documentado)
- IV Crush pré/pós balanço (opções)
- Paper trading 3 meses antes de LIVE

**Opção C (Parar Pesquisa de Edge):**
- Usar estratégia passiva (DCA + HODL)
- Manter coleta como "backup estratégico"
- Focar em outra coisa (vida, trabalho, etc.)

**O que significa “estratégia passiva (DCA + HODL)”**
- **DCA** (*Dollar-Cost Averaging*): comprar um valor fixo em intervalos regulares,
  sem tentar acertar o melhor timing. Ex.: comprar R$ 500 de BTC toda semana.
- **HODL**: manter a posição por longo prazo, sem ficar girando entrada/saída por
  sinais de curto prazo.
- Portanto, **DCA + HODL** = acumular aos poucos, em datas fixas, e carregar por
  prazo longo, sem tentar prever o mercado no curto prazo.

**Exemplo prático**
- toda segunda-feira: comprar R$ 300 de BTC;
- todo dia 5 do mês: comprar R$ 300 de ETH;
- manter a posição por anos, não por dias.

**Por que isso aparece como opção neste projeto**
- se não há **edge comprovado** para trading ativo, pode fazer mais sentido parar
  de disputar previsão de curto prazo e adotar uma abordagem simples, barata e
  disciplinada para capturar eventual upside estrutural do ativo.

**Vantagens**
- menos giro e menos custo;
- menor risco de overtrade;
- não depende de acertar timing;
- operação muito mais simples.

**Limitações**
- não elimina drawdown;
- não é “edge” nem alpha demonstrado; é só exposição disciplinada ao ativo;
- exige convicção e estômago para bear markets longos.

**Diferença para a trilha de pesquisa deste projeto**
- a trilha quantitativa buscava **edge líquido real** com causalidade, controle,
  custo explícito, robustez temporal e nenhuma promoção sem evidência;
- **DCA + HODL** não tenta provar alpha. Ele parte da premissa: “não sei prever
  melhor que o mercado no curto prazo; então só acumulo um ativo em que tenho
  convicção de longo prazo”.

**Diferença entre HODL puro, DCA + HODL e trend-following lento**
- **HODL puro**: faz um aporte grande (ou poucos aportes discricionários) e fica
  comprado quase o tempo todo. Não tenta melhorar preço médio nem reduzir risco.
- **DCA + HODL**: mesma filosofia de longo prazo, mas entra aos poucos em datas
  fixas; suaviza o preço médio de entrada e reduz dependência de um único ponto
  de compra.
- **Trend-following lento**: não é passivo. É uma regra sistemática de entrar e
  sair conforme tendência (ex.: SMA200, golden cross, TSMOM 12-1). Aceita perder
  parte do upside em troca da tentativa de reduzir drawdown. Na sua trilha, essa
  família foi testada na Q20 e falhou no critério de preservação forte de capital.

**Resumo da diferença filosófica**
- **HODL puro** = “acredito no ativo; compro e seguro”.
- **DCA + HODL** = “acredito no ativo; acumulo com disciplina e seguro”.
- **Trend-following lento** = “quero continuar exposto só quando a tendência me
  deixa relativamente confortável”.

No contexto desta pesquisa, **DCA + HODL** não é a resposta para “existe edge?”;
é a resposta para “se eu não tenho edge demonstrado, qual é a postura mais simples
 e intelectualmente honesta para ainda ter exposição?”.

**Tabela decisória rápida (quando escolher o quê)**

| Se a sua prioridade é… | Use… | Evite… |
|---|---|---|
| Máxima simplicidade | HODL puro | regras de entrada/saída (mais fricção do que você quer) |
| Disciplina de acúmulo sem timing | DCA + HODL | decisões discricionárias de “comprar barato / vender caro” |
| Tentar reduzir dano em tendência longa ruim | Trend-following lento (SMA200 / golden cross / TSMOM 12‑1) | all-in / all-out manual sem regra fixa |
| Provar edge de verdade antes de arriscar capital | NÃO usar passes de curto prazo; voltar à régua da trilha (causalidade, custo, amostra) | qualquer “setup” sem teste honesto |

| Se o seu medo principal é… | Evite… | Em vez disso… |
|---|---|---|
| Drawdown devastador (bear market longo) | HODL puro com 100% do capital | trend-following lento ou alocação com vol-alvo (mas veja a lição Q20/Q21: mitigam, não eliminam) |
| Depender de um único ponto de entrada | Aporque único grande | DCA + HODL |
| Overtrade / custo comendo resultado | sinais curtos frequentes (15m/1h) | long/flat diário, DCA, ou pausar trading |
| Paralisia por “não saber quando entrar” | espera por perfeição de timing | DCA + HODL (entrada em datas fixas) |
| Autoengano / p-hacking | backtest “bonito” em janela única | apenas vereditos pré-registrados com amostra fora-da-amostra |

**Regra prática em uma linha:** todo o resto da trilha já mostrou que prever o
curto prazo não é o forte deste projeto; se a prioridade virar simplesmente
“continuar exposto sem perder a disciplina”, DCA + HODL é a opção com menos
fricção e mais honesta.

### Longo Prazo (6-12 meses)

5. **Se Continuar em Crypto:**
   - Testar OI/flow **combinados** (não isolados)
   - Explorar **outros horizontes** (swing multi-dia)
   - Considerar **outros venues** (OKX, Bybit)

6. **Se Migrar para B3:**
   - Completar hardening do `mutante-opcoes-acoes`
   - Focar em 1-2 ativos (PETR4, VALE3)
   - Swing trade (diário) tem menos ruído que day trade

---

## Conclusão

O **Mutant Crypto Bot** é o projeto de trading retail **mais sério e honesto** que existe. Documentar 24 fracassos com rigor acadêmico é **raríssimo** (a maioria esconde ou não testa).

**Mas:** 24 × 0 = 0. Nenhum edge foi encontrado.

**Próxima decisão:** Continuar pesquisando (com novas fronteiras) ou aceitar que superfície pública de preço não tem edge promotor e migrar para estratégia passiva ou outro mercado.

---

## Metadados

- **Data:** 2026-08-23
- **Autor:** Análise por IA (Cursor)
- **Branch:** backup/flexible-stop-gain
- **Commit:** 2acc366
- **Hipóteses testadas:** 24 (0 aprovadas)
- **Ativos principais:** BTCUSDT spot, futures
- **Período médio:** 2017-2026 (9 anos)
- **Custo modelado:** 10-20bp round-trip

---

*Este documento foi gerado a pedido do usuário para consolidar o estado atual do projeto.*
