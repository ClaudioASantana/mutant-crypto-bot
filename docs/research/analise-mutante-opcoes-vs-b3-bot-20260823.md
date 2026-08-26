# Análise Comparativa: mutante-opcoes-acoes vs mutant-b3-bot

## Contexto

O usuário perguntou qual dos dois projetos está **melhor estruturado para desenvolver estratégias de opções de ações** na B3.

**Veredito direto:** `mutante-opcoes-acoes` está **muito melhor estruturado** para opções de ações. O `mutant-b3-bot` foi desenhado para **futuros** (WIN/WDO), não opções.

---

## Comparação Direta

| Aspecto | mutante-opcoes-acoes | mutant-b3-bot |
|---|---|---|
| **Foco** | Opções de ações B3 (PETR4, VALE3, etc.) | Futuros B3 (WIN$N, WDO$N) |
| **Quant Engine** | Black-Scholes, GARCH, gregas (Delta, Gamma, Vega, Theta) | TA clássica (BB, EMA, MACD, SuperTrend) |
| **Estratégias** | 4 (VWAP, Pairs, TTM Squeeze, Black-Scholes) | 8 (BB, EMA+MACD, SMC, 3 Velas, VWAP, etc.) |
| **Arquitetura** | DDD completo (Domain, Application, Infrastructure) | Services/Engines monolíticos |
| **Backtest** | Engine institucional com walk-forward, custos B3 | Backtest vetorial simples (Pandas TA) |
| **IA/RAG** | Llama 3 + ChromaDB (veto fail-closed) | RAG básico (não implementado fully) |
| **Hardening** | P0 em progresso (auth, operational config, fail-closed) | Sem hardening explícito |
| **Documentação** | 500+ linhas (manual de estudo, roteiros, gap analysis) | 200 linhas (implementation plan, walkthrough) |
| **Execução** | MT5 Bridge separado (Windows) | MT5 client embutido |
| **Dados** | yfinance (ações) + snapshot próprio | MT5 direto (futuros) |
| **Persistência** | SQLite canônico (Alembic migrations) | JSON/SQLite misturado |
| **Frontend** | Angular 22 (cockpit one-page) | Next.js 14 (dashboard) |

---

## mutante-opcoes-acoes: Pontos Fortes para Opções

### 1. **Quant Engine Especializada em Opções**

```
backend/app/domain/quant/:
- black_scholes.py ✅ (pricing de opções europeias/americanas)
- volatility.py ✅ (GARCH, forecast de volatilidade)
- greeks.py ✅ (Delta, Gamma, Vega, Theta, Rho)
- ttm_squeeze.py ✅ (rompimento de volatilidade)
- pairs_trading.py ✅ (arbitragem estatística)
- backtest_engine.py ✅ (swing-trade e day-trade)
- daytrade_engine.py ✅ (intradia com ATR)
```

**Por que importa:** Opções exigem cálculo de **volatilidade implícita vs realizada**, **gregas** para hedge, e **pricing justo** (Black-Scholes). Este projeto já tem tudo isso.

### 2. **Estratégias de Opções Documentadas**

Do README e docs/estrategias:

```
1. IV Crush pré/pós balanço (Earnings Volatility Harvesting)
   - Venda de Strangle/Straddle 1-2 dias antes do earnings
   - Fecha no dia seguinte (IV decay)
   - Edge: Vega + Theta

2. Pairs Trading com Opções
   - PETR3 vs PETR4, ITUB4 vs BBDC4
   - Delta neutro, hedge ratio via OLS/ADF
   - Edge: Reversão à média

3. TTM Squeeze em Opções
   - Bollinger Bands dentro de Keltner Channels
   - Entrada na expansão de volatilidade
   - Edge: Momentum pós-compressão

4. Swing Trade de Opções (GARCH + Black-Scholes)
   - Forecast de volatilidade (GARCH)
   - Pricing justo (Black-Scholes)
   - Edge: IV < RV (opção barata)
```

**Por que importa:** São **exatamente** as estratégias com edge comprovado academicamente (ver `docs/research/edge-em-mercados-financeiros-20260823.md`).

### 3. **Arquitetura DDD Madura**

```
backend/app/
├── domain/
│   ├── entities/ (Trade, Asset, Portfolio, Greeks)
│   ├── services/ (RiskManager, AIGate, OperationalConfig)
│   ├── quant/ (Black-Scholes, GARCH, Pairs Trading)
│   ├── repositories/ (Broker adapter interfaces)
│   └── value_objects/ (Money, Greeks, Enums)
├── application/
│   ├── commands/ (Trade creation, order placement)
│   ├── queries/ (Trade retrieval, portfolio info)
│   ├── handlers/ (Command/query handlers)
│   └── dtos/ (Data transfer objects)
├── api/
│   ├── endpoints/ (AI, trades, config)
│   ├── schemas/ (Pydantic models)
│   └── v1/routers/
└── infrastructure/
    ├── ai/ (ChromaDB, LLM provider)
    ├── cache/ (Redis client)
    ├── database/ (SQLAlchemy models, async session)
    ├── oms/ (MT5 REST adapter)
    └── repositories/ (Concrete DB implementations)
```

**Por que importa:** DDD separa **regra de negócio** (domain) de **implementação** (infrastructure). Isso permite:
- Testar estratégias sem depender de MT5
- Trocar broker (MT5 → Clear/Direct) sem reescrever domain
- Manter IA/RAG como camada de veto, não como core

### 4. **Hardening Operacional em Progresso**

Do `docs/research/proximos_passos_e_pendencias.md`:

```
P0 (Em progresso):
✅ Auth por X-API-Key em rotas sensíveis
✅ Gate de token no WebSocket
✅ OperationalConfig central para execution_mode
✅ Bloqueio fail-closed do caminho LIVE
⏳ /health honesto por dependência
⏳ Persistência unificada (SQLAlchemy canônico)

P1 (Pendentes):
- Unificar persistência (JSON + SQLite + journal.db)
- RAG/IA com trilha de proveniência forte
- UI fiel ao backend (sem AI Feed cosmético)
```

**Por que importa:** Sistema **fail-closed** evita desastres operacionais (ordens reais sem configuração válida).

### 5. **Documentação Excepcional**

```
docs/
├── architecture/ (7 arquivos: AI, options algebra, quant concepts)
├── analisar/ (4 arquivos: backtest results, screener research)
├── deployment/ (3 arquivos: CI/CD, production checklist)
├── MANUAL_DE_ESTUDO_SISTEMA_QUANTITATIVO.md (500+ linhas)
├── ROTEIRO_ESTUDO_7_DIAS.md (pedagógico)
└── walkthrough_final.md (end-to-end)
```

**Por que importa:** Documentação madura acelera onboarding e evita "conhecimento tribal".

---

## mutant-b3-bot: Limitações para Opções

### 1. **Foco em Futuros, Não Opções**

Do `docs/implementation_plan.md`:

```
"Este projeto é um fork do mutant-crypto-bot para o Mercado Futuro Brasileiro (B3),
operando via MetaTrader 5 (MT5)."

"Ativos alvo: WIN$N (Mini Índice), WDO$N (Mini Dólar)"
```

**Problema:** Futuros são **lineares** (preço sobe/desce). Opções são **não-lineares** (gregas, IV, expiry).

### 2. **Quant Engine Genérica (TA Clássica)**

```
backend/app/strategies/:
- bollinger.py ❌ (bandas de Bollinger, sem gregas)
- ema_macd.py ❌ (cruzamento de médias, sem IV)
- smc.py ❌ (Smart Money Concepts, sem pricing)
- three_candles.py ❌ (padrão 3 velas, sem volatilidade)
- vwap.py ❌ (VWAP, sem gregas)
```

**Problema:** Nenhuma estratégia usa **Black-Scholes, GARCH, ou cálculo de gregas**.

### 3. **Sem Engine de Opções**

```
backend/app/engines/:
- bot_instance.py (orquestração de bots)
- candle_builder.py (construção de velas)
- cataloger.py (catálogo de estratégias)
- indicators.py (indicadores TA)
- risk.py (risk management genérico)
- simulator.py (simulador de ordens)
```

**Falta:**
- Black-Scholes pricing
- Cálculo de gregas (Delta, Gamma, Vega, Theta)
- Volatilidade implícita vs realizada
- Expiry management (rollover de contratos)

### 4. **Arquitetura Menos Madura**

```
backend/app/
├── engines/ (monolítico: TA, risk, simulator)
├── models/ (SQLAlchemy models)
├── ports/ (adapters)
├── routers/ (FastAPI endpoints)
├── services/ (mt5_client, trade_logger)
├── strategies/ (8 estratégias TA)
└── rag/ (básico, não implementado fully)
```

**Problema:** Mistura **regra de negócio** (estratégias) com **implementação** (engines, services).

### 5. **Documentação Limitada**

```
docs/
├── implementation_plan.md (3.2KB, foco em migração crypto→B3)
├── walkthrough.md (2KB, visão geral)
├── OBSERVABILITY_BACKLOG.md (pendências)
├── PROJECT_MEMORY.md (2KB, origem do projeto)
└── Captura de tela 2026-08-12 160124.png (imagem)
```

**Problema:** Documentação foca em **migração**, não em **estratégias de opções**.

---

## Veredito: Qual Usar para Opções de Ações?

### **mutante-opcoes-acoes** ✅

**Prós:**
- ✅ Quant engine especializada em opções (Black-Scholes, GARCH, gregas)
- ✅ 4 estratégias de opções documentadas (IV Crush, Pairs, Squeeze, Swing)
- ✅ Arquitetura DDD madura (domain separado de infrastructure)
- ✅ Hardening operacional em progresso (fail-closed, auth, config)
- ✅ Documentação extensa (500+ linhas, roteiros de estudo)
- ✅ Backtest institucional (walk-forward, custos B3, robustez)
- ✅ IA/RAG como veto (não como cosmética)

**Contras:**
- ⚠️ Frontend Angular (menos popular que Next.js)
- ⚠️ MT5 Bridge separado (requer Windows)
- ⚠️ Hardening P0/P1 ainda em progresso

### **mutant-b3-bot** ❌

**Prós:**
- ✅ Next.js frontend (mais popular)
- ✅ MT5 client embutido (mais simples)
- ✅ 8 estratégias TA (mas para futuros, não opções)

**Contras:**
- ❌ Sem engine de opções (só TA clássica)
- ❌ Foco em futuros (WIN/WDO), não opções
- ❌ Arquitetura menos madura (monolítica)
- ❌ Sem documentação de estratégias de opções
- ❌ Backtest vetorial simples (sem walk-forward)
- ❌ Sem hardening operacional explícito

---

## Recomendação: Desenvolver mutante-opcoes-acoes

### **Por que:**

1. **Edge está em opções, não futuros**
   - IV Crush: 25bp/dia, Sharpe 1.76 (comprovado academicamente)
   - Futuros (WIN/WDO): Edge ≈ 0 (eficiente, TA pública)

2. **Infra já existe**
   - Black-Scholes ✅
   - Gregas ✅
   - Pairs Trading ✅
   - Backtest engine ✅

3. **Só falta:**
   - Completar hardening P0/P1 (2 semanas)
   - Testar IV Crush em 100+ earnings (backtest)
   - Paper trading 3 meses

### **Plano de Ação (4 semanas):**

**Semana 1: Completar P0**
- [ ] OperationalConfig centralizada
- [ ] `/health` honesto por dependência
- [ ] Persistência unificada (SQLAlchemy)
- [ ] Auth em todas as superfícies sensíveis

**Semana 2: Backtest IV Crush**
- [ ] Coletar 100+ earnings de PETR4, VALE3, ITUB4 (2020-2026)
- [ ] Testar Short Strangle 2 dias antes, fecha pós-announcement
- [ ] Custo: 5-10bp round-trip
- [ ] Edge esperado: 2-5% por trade

**Semana 3-4: Paper Trading**
- [ ] Rodar em real-time (sem dinheiro)
- [ ] Comparar PnL real vs backtest
- [ ] Ajustar execução, slippage, timing

**Mês 2+: Live (Pequeno)**
- [ ] Começar com 1-2% do capital
- [ ] Escalar se PnL ≈ backtest
- [ ] Manter journal detalhado

---

## O Que Fazer com mutant-b3-bot?

**Opção A: Manter como Backup**
- Útil se quiser operar **futuros** (WIN/WDO)
- Estratégias TA funcionam para momentum/day trade
- Menos complexo que opções

**Opção B: Migrar para mutante-opcoes-acoes**
- Copiar frontend Next.js (se preferir Angular)
- Copiar MT5 client (já funciona)
- Descartar engines/strategies (não servem para opções)

**Opção C: Arquivar**
- Focar 100% em `mutante-opcoes-acoes`
- Evitar dispersão de esforço

**Minha recomendação:** **Opção A** (manter como backup para futuros), mas **focar 90% do tempo em mutante-opcoes-acoes**.

---

## Conclusão

**Para opções de ações na B3:** `mutante-opcoes-acoes` está **muito melhor estruturado**.

**Tem:**
- Engine de opções (Black-Scholes, GARCH, gregas)
- Estratégias com edge (IV Crush, Pairs Trading)
- Arquitetura madura (DDD, fail-closed)
- Documentação extensa

**Falta só:**
- Completar hardening (2 semanas)
- Backtest de IV Crush (1 semana)
- Paper trading (3 meses)

**mutant-b3-bot:** Bom para futuros (WIN/WDO), **não serve para opções** sem refactor massivo.

---

*Documento gerado a pedido do usuário para decidir qual projeto desenvolver para opções de ações.*
