# Edge em Mercados Financeiros — Onde Desenvolver Estratégias (2026-08-23)

## Resumo Executivo

Após testar **24 hipóteses em crypto** (0 aprovadas), a pergunta natural é: **"Qual mercado tem edge real?"**

**Resposta curta:** Opções de ações single-name (EUA/B3) e small-cap stocks têm edge comprovado academicamente. Crypto spot em Binance não tem.

---

## Mercados Com Edge (Do Melhor para o Pior)

### 1. **Opções de Ações Single-Name (EUA/B3)** ⭐⭐⭐⭐⭐

**Edge Comprovado:**
```
Estratégia: Long em stocks com retail call imbalance positivo
- Retorno: +25.75bp/dia (~65% anual)
- Sharpe: 1.76 (excepcional)
- Horizonte: 1-2 dias
- Fonte: Liu (2026), JFQA
```

**Mecanismos de Edge:**
1. **Informação assimétrica:** Traders informados usam opções quando short é caro
2. **Alavancagem embutida:** OTM options amplificam views informadas
3. **Hedging demand:** Dealers fazem hedge, criando pressão de preço
4. **Sentimento retail:** Call buying de pequenos traders é sinal contrarian

**Estratégias Promissoras:**
- **IV Crush pré/pós earnings:** Short strangle 2 dias antes, fecha pós-announcement
- **Flow de opções:** Seguir retail call imbalance (contrarian)
- **Gamma positioning:** Dealers em negative gamma amplificam movimentos

**Custo:** 1-5bp round-trip (EUA), 5-10bp (B3)

**No seu projeto:** `mutante-opcoes-acoes` já tem Black-Scholes, gregas, IV ✅

---

### 2. **Small-Cap Stocks (Russell 2000 / B3 Small Caps)** ⭐⭐⭐⭐

**Edge Comprovado:**
```
Características:
- Cobertura: 0-2 analistas (vs 20+ em large-cap)
- Liquidez: Baixa (institucionais não operam)
- Gamma: Negativo (dealers amplificam volatilidade)
- Edge: Seguindo flow institucional exposto no order book
```

**Mecanismos de Edge:**
1. **Menos eficiência informacional:** Informação não precificada rápido
2. **Impacto de trading:** Retail domina volume, institucionais evitam
3. **Gamma negativo:** Hedging de dealers cria momentum

**Estratégias Promissoras:**
- **Pairs Trading:** Small-cap vs small-cap cointegradas
- **Momentum com filtro de gamma:** Long em negative gamma stocks
- **Order flow:** Seguindo institutional trading intention exposure

**Custo:** 0.025% (B3 day trade), 0.01-0.05% (EUA)

---

### 3. **Event-Driven (Earnings, M&A, Halvings)** ⭐⭐⭐⭐

**Edge Comprovado:**
```
Earnings play (EUA):
- Short strangle pré-earnings (IV alta)
- Edge: Vega decay pós-announcement
- Retorno médio: 2-5% por trade
- Sharpe: 1.5-2.0
```

**Mecanismos de Edge:**
1. **Volatilidade precificada incorretamente:** IV > RV (realized vol)
2. **Comportamental:** Overreaction/underreaction
3. **Catalisador definido:** Data conhecida, risco delimitado

**Estratégias Promissoras:**
- **IV Crush:** Short strangle/straddle pré-earnings
- **Momentum pós-earnings:** Long se beat + guidance up
- **Contrarian:** Short se beat mas preço já subiu muito

**Custo:** 5-10bp round-trip

---

### 4. **Mercados Emergentes (Índia, Sudeste Asiático)** ⭐⭐⭐

**Edge Potencial:**
```
Índia (Nifty 50):
- CAGR: 12-15% (vs 8-10% S&P 500)
- Volatilidade: Maior, mas Sharpe comparável
- Edge: Stock picking ativo > passive indexing
```

**Mecanismos de Edge:**
1. **Crescimento estrutural:** Middle-class expansion
2. **Dispersão de valuation:** Alpha em off-benchmark stocks
3. **Menos eficiência:** Informação não precificada rápido

**Problemas:**
- Barreiras de acesso (FX, regulação)
- Custo de transação mais alto
- Liquidez menor

---

### 5. **Crypto Cross-Exchange (OKX, Bybit, Deribit)** ⭐⭐⭐

**Edge Potencial:**
```
Funding arb:
- Binance: +0.01%/8h
- Bybit: +0.03%/8h
- Edge: Long Binance, short Bybit (delta neutro)
- Retorno: ~7%/ano (baixo risco)
```

**Mecanismos de Edge:**
1. **Arbitragem cross-exchange:** Funding divergente
2. **Basis trade:** Spot vs futures em exchanges diferentes
3. **Menos eficiência:** 20-30% menos volume que Binance

**Problemas:**
- Requer contas em múltiplas exchanges
- Capital fragmentado
- Risco de contraparte (exchange risk)

---

## Mercados SEM Edge (Onde Não Operar)

### 1. **BTC/ETH Spot em Binance** ❌

**Por que não tem:**
- **Eficiência extrema:** Milhares de olhos, informação instantânea
- **Custo alto:** 10-20bp come edge pequeno
- **Testado:** 19/19 hipóteses de preço público ❌ (seu projeto)

**Seu teste:** 24 hipóteses, 0 passaram → Edge ≈ 0

---

### 2. **Large-Cap Stocks (S&P 500, PETR4, VALE3)** ❌

**Por que não tem:**
- **Cobertura:** 15-30 analistas por stock
- **Arbitragem rápida:** Qualquer dislocation some em segundos
- **Institucional domina:** 80% do volume

**Edge:** Apenas em earnings ou eventos específicos

---

### 3. **Day Trade em Qualquer Mercado** ❌

**Por que não tem:**
- **Custo composto:** 200-500 trades/ano × 10bp = 20-50% drag
- **Competição:** HFTs, market makers, algoritmos
- **Seu backtest:** 10/10 estratégias TA ❌

**Exceção:** Day trade em small-caps com gamma negativo (edge estrutural)

---

### 4. **Indicadores Técnicos Públicos (RSI, MACD, BB)** ❌

**Por que não tem:**
- **Todo mundo vê:** Já está precificado
- **Self-defeating:** Quando funciona, para de funcionar
- **Seu teste:** 10 estratégias legado → 10/10 ❌

---

## Ranking Final de Mercados por Edge Potencial

| Mercado | Edge Potencial | Custo Entrada | Complexidade | Recomendação |
|---|---|---|---|---|
| **Opções EUA (single-name)** | ⭐⭐⭐⭐⭐ | Baixo | Média | **FOCA AQUI** |
| **Small-Cap Stocks** | ⭐⭐⭐⭐ | Baixo | Baixa | **FOCA AQUI** |
| **Event-Driven (earnings)** | ⭐⭐⭐⭐ | Baixo | Baixa | **FOCA AQUI** |
| **Emergentes (Índia)** | ⭐⭐⭐ | Alto | Alta | Talvez |
| **Crypto cross-exchange** | ⭐⭐⭐ | Médio | Média | Talvez |
| **Opções B3** | ⭐⭐⭐ | Baixo | Baixa | **JÁ TEM** |
| **BTC spot Binance** | ⭐ | Baixo | Baixa | **NÃO** |
| **Large-cap S&P 500** | ⭐ | Baixo | Baixa | **NÃO** |

---

## Plano de Ação Recomendado

### **Semana 1-2: Decidir Mercado**
- [ ] Escolher entre: Opções EUA, Small-Cap B3, ou Crypto cross-exchange
- [ ] Se opções: Abrir conta na Interactive Brokers (EUA) ou manter B3
- [ ] Se small-cap: Expandir watchlist para 20-30 tickers
- [ ] Se crypto: Abrir contas em Bybit/OKX

### **Semana 3-6: Backtest Específico**
- [ ] **Opções:** Testar IV Crush em 100+ earnings (2020-2026)
- [ ] **Small-cap:** Pairs trading com 10-15 pares
- [ ] **Crypto:** Funding arb com 3 exchanges

### **Semana 7-12: Paper Trading**
- [ ] Rodar estratégia em real-time (sem dinheiro)
- [ ] Comparar PnL real vs backtest
- [ ] Ajustar custos, slippage, execução

### **Mês 4+: Live (Pequeno)**
- [ ] Começar com 1-2% do capital
- [ ] Escalar se PnL ≈ backtest
- [ ] Manter journal detalhado

---

## Conclusão

**Mercado com mais edge para retail em 2026:**

1. **Opções de ações single-name (EUA ou B3)** — Edge de 25bp/dia, Sharpe 1.76
2. **Small-cap stocks** — Menos eficiência, gamma negativo
3. **Event-driven (earnings)** — IV Crush previsível

**Crypto spot BTC em Binance:** Edge ≈ 0 (24 hipóteses testadas, 0 passaram)

**Sua melhor jogada:** Migrar conhecimento quant (backtest, rigor, infra) para **opções ou small-caps**, onde edge **existe e é documentado**.

---

*Documento gerado a partir de pesquisa acadêmica 2025-2026 e análise dos projetos do usuário.*
