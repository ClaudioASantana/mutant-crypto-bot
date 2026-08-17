# Log de Evolução da Wiki

Este é um arquivo de registro cronológico (append-only) das atividades de manutenção, ingestão de dados e auditoria da wiki.

## [2026-08-17] Inicialização da Infraestrutura de Wiki
- Criação do `schema.md` (regras de manutenção para a IA).
- Estruturação dos diretórios `crypto-wiki/raw`, `crypto-wiki/sources` e `crypto-wiki/wiki`.
- Registro das convenções para versionamento, lint e ingestão.
- Estabelecimento do padrão de links `[[nome-da-pagina]]` e frontmatter YAML para metadados.

## [2026-08-17] ingest | Análise Quantitativa: AIFilter (Prompt EMA200)
- **Fonte:** `backend/scripts/backtest_ai.py` — backtest de 300 velas BTC/USDT M15.
- **Resultado de destaque:** WR 36.11%, PnL -$73.24 (SL 1.5 / TP 3.0, taxa 0.1%/lado).
- **Página criada:** `wiki/analises/backtest-aifilter-2026-08-17.md`
- **Ação tomada:** `index.md` atualizado com link + resumo. Identificado o problema de trades com ATR pequeno (taxas > alvo).

## [2026-08-17] ingest | Backtest AIFilter com EMA200 Rígido
- **Fonte:** `backend/scripts/backtest_ai.py` — backtest limpo (sem cache) de 300 velas BTC/USDT M15.
- **Resultado:** WR 25%, PnL -$10.61, apenas 8 sinais (filtro rígido de tendência).
- **Página criada:** `wiki/analises/backtest-aifilter-ema200-rigido.md`
- **Ação tomada:** `index.md` atualizado. Diagnóstico registrado: a IA é seletiva mas imprecisa; precisa de filtros de confluência técnicos.

## [2026-08-17] ingest | Backtest AIFilter + Filtro Positivo (Padrão 3 Velas)
- **Fonte:** `backend/scripts/backtest_ai.py` — 1000 velas BTC/USDT M15, 4+1 variações de filtros.
- **Resultados:**
  - IA Pura: 165 sinais, WR 29.09%, PnL -$196.82.
  - IA + Padrão 3 Velas (SL 1.5/TP 3): 13 sinais, WR 38.46%, PnL -$11.60.
  - IA + Padrão 3 Velas (SL 1.5/TP 8): 13 sinais, WR 38.46%, **PnL +$3.58**.
- **Página criada:** `wiki/analises/backtest-aifilter-3velas-2026-08-17.md`
- **Ação tomada:** `index.md` atualizado. Conclusão: confluência positiva viável; TP agressivo (8x ATR) necessário para superar taxas. Filtro de localização S/R (BB/Donchian) foi removido do `_check_confluence_filters` (era supressão de sinais).
