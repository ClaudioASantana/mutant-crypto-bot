# Próximos Passos e Pendências do Mutant Crypto Bot

Este documento resume o estado atual do desenvolvimento e as próximas ações recomendadas para a retomada, agora com foco em **hardening operacional** e **honestidade de runtime**, usando o `mutante-opcoes-acoes` como baseline.

## 1. Mudança de prioridade

Até aqui, a maior parte das pendências estava concentrada em estratégia, backtest e filtros de entrada.

Depois da comparação arquitetural com o projeto de opções, a prioridade muda:

**antes de expandir autonomia, estratégias ou IA, o projeto precisa consolidar o contrato operacional do runtime.**

Em outras palavras:

- primeiro garantir que o sistema é honesto e seguro sobre como opera;
- depois expandir estratégias, filtros e automação.

A referência detalhada está em:

- `docs/architecture/gap_analysis_mutante_crypto_vs_opcoes_2026-08.md`

---

## 2. Prioridades imediatas (P0)

### 2.1. Status atual da rodada P0

Itens já aplicados nesta rodada:

- auth por `X-API-Key` em `POST /api/cqrs/execute_trade`;
- auth por `X-API-Key` em `POST /api/risk_settings`;
- gate de token no websocket `/ws` via query param `?token=...` quando `api_auth_token` estiver configurado;
- `OperationalConfig` central para `execution_mode`, `live_trading_enabled`, token de auth, limites globais e flags de mutação;
- bloqueio fail-closed dos executores LIVE (Binance/Deriv) quando o modo operacional não autoriza;
- `RiskManager` lendo o limite global de perda da config central, em vez de env espalhada;
- UI ajustada para enviar `X-API-Key`, autenticar o WebSocket, parar de enviar `atr: 50.0` mockado e rotular o feed de IA como telemetria ilustrativa.

Validação executada nesta rodada:

- novos testes unitários para `OperationalConfig`, security dependency e gates de LIVE;
- suíte relevante em `backend/tests/` passando com sucesso (`50 passed`), excluindo apenas coletores legados quebrados fora da suíte principal.

Pendências restantes dentro do espírito P0/P1:

- decidir se ausência de `API_AUTH_TOKEN` deve falhar já no startup ou continuar como `503` apenas nas superfícies protegidas;
- revisar se há outras mutações/controles WebSocket que também merecem auth granular;
- materializar `backend/config/operational_config.json` exemplar ou documentar oficialmente a estratégia só-via-env.

### 2.2. Proteger superfícies sensíveis com autenticação

As superfícies principais de execução/config já receberam proteção explícita nesta rodada:

- `POST /api/cqrs/execute_trade`
- `POST /api/risk_settings`
- websocket `/ws` com comandos operacionais

**Próximo objetivo:** revisar cobertura residual e fechar a política final para token ausente no servidor.

---

### 2.3. Criar um modo operacional único e fail-closed

O projeto hoje possui:

- runtime principal em `PaperTrader` via `services.json`;
- código LIVE separado para Binance em `application/services/executor.py`;
- CQRS persistido em SQLite;
- swarm autônomo operando com feed real da Binance.

O que falta é uma fonte única de verdade que diga claramente:

- se o sistema está em PAPER;
- se pode usar Binance Testnet;
- se LIVE real está bloqueado ou permitido;
- como UI, CQRS e swarm obedecem o mesmo modo.

**Objetivo:** impedir ambiguidade operacional e adotar bloqueio por padrão quando a config estiver inválida.

---

### 2.4. Parar de usar valores mockados em caminhos operacionais

A UI deixou de enviar trade manual com:

- `atr: 50.0 // mock ATR`

Agora, o frontend bloqueia a ação quando não houver ATR real disponível para o ativo atual.

A telemetria de IA também passou a ser rotulada explicitamente como ilustrativa, em vez de aparentar estado operacional real.

**Próximo objetivo:** continuar separando demo/simulação de operação real e impedir que qualquer dado artificial atravesse a trilha operacional sem rótulo.

---

## 3. Prioridades seguintes (P1)

### 3.1. Unificar persistência e journal

Hoje coexistiam:

- JSON por arquivo para PaperTrader;
- SQLite/SQLAlchemy no CQRS;
- `journal.db` separado para entradas/saídas.

Estado após a rodada atual:

- storage canônico unificado em SQLite/SQLAlchemy implementado;
- `paper_trader_states` como snapshot operacional;
- `trades` como lifecycle + journal canônico;
- runtime principal já apontando para `SqlAlchemyPaperTraderRepository` por default;
- script de import legada idempotente implementado e testado.

Documentação operacional do cutover:

- `docs/guides/cutover_persistencia_canonica_sqlite.md`

**Estado atual:** cutover concluído no banco local — `alembic upgrade head`, import legado idempotente, smoke check de schema e saneamento do `app.db` (6 states, 40 trades, head `514a3e6ef167`).

#### 3.1.1. Bootstrap oficial de banco novo documentado

O procedimento oficial para ambientes limpos agora é:

1. `cd backend && venv/bin/alembic upgrade head`
2. validar a presença física de `alembic_version`, `paper_trader_states` e `trades`
3. rodar `venv/bin/python scripts/migrate_legacy_paper_trader_data.py` **somente** se houver legado para importar

Princípios fixados:

- Alembic é a única via de criação do schema canônico;
- o runtime principal não faz bootstrap implícito de tabelas;
- o import legado falha explicitamente se o schema não existir.

Os pendentes desta trilha já foram todos fechados:

- ~~smoke check automatizado para detectar “alembic head sem tabelas canônicas”~~ — feito em `tests/integration/test_canonical_schema_smoke.py`;
- ~~decidir se `backend/data/app.db` local deve ser recriado/limpo~~ — resolvido: o `app.db` local já foi recriado e revalidado durante o cutover (6 states, 40 trades, head `514a3e6ef167`); o estado inconsistente original está preservado em backup em `backend/backups/`.

Observação operacional: `backend/data/app.db` e `backend/backups/` são artefatos locais de ambiente e agora também ficaram explicitamente ignorados no `.gitignore`, para evitar versionamento acidental do banco canônico e de backups do cutover.

#### 3.1.2. Trilha legada de scripts/research oficialmente aposentada

Após o cutover, a limpeza pós-cutover aposentou oficialmente os scripts
legados que ainda dependiam de namespaces removidos (`app.engines.*`,
`app.models.*`, `app.services.*`) ou de contratos antigos do simulador.

Trilha legada aposentada (avisos explícitos de descontinuação):

- `scripts/test_paper_trader_persistence.py`
- `scripts/test_24h.py`
- `scripts/grid_search_st.py`
- `scripts/backtester.py`
- `scripts/backtest_ai.py`
- `scripts/sweep_tp_sl.py`
- `scripts/research_backtest.py`
- `scripts/backtest_3velas.py`
- `test_cataloger.py`
- `test_cataloger2.py`

Trilha suportada a partir de agora:

- runtime principal: `app/` com repositórios SQLAlchemy canônicos;
- suite oficial de testes: `backend/tests/`;
- harnesses modernos de pesquisa/backtest:
  - `scripts/benchmark_all.py`
  - `scripts/deep_backtest.py`
  - `scripts/analyze_strategies_30d.py`
  - `scripts/optimizer.py`
- procedimento de cutover: `docs/guides/cutover_persistencia_canonica_sqlite.md`

Regra daqui em diante: qualquer novo harness de research deve ser construído
sobre `app/domain`, `app/application/services` e `app/infrastructure`
(módulos vigentes), nunca sobre namespaces antigos.

---

### 3.2. Criar `/health` honesto por dependência

O projeto depende de:

- DB/storage
- Redis/Celery
- Chroma
- backend LLM
- feed Binance/WebSocket

**Objetivo:** expor estado real dessas dependências, distinguindo `ok`, `degraded` e `error`.

---

### 3.3. Consolidar configuração operacional e contrato de risco

O `RiskManager` já possui partes valiosas da lógica, mas ainda há defaults e fallbacks espalhados no executor/simulador.

**Objetivo:** mover limites e flags críticas para uma configuração operacional tipada e compartilhada por toda a aplicação.

---

### 3.4. Formalizar proveniência do RAG operacional

É necessário separar melhor:

- memória documental (docs/wiki)
- histórico operacional real
- dados simulados/backtest

**Objetivo:** impedir contaminação de contexto entre operação real e memória sintética.

---

## 4. Melhorias estruturais posteriores (P2)

### 4.1. Alinhar UI com estado real do backend

- remover/mockar explicitamente o AI Feed cosmético;
- refletir status reais de task/worker/LLM;
- mostrar erro/ausência de dado de forma explícita.

### 4.2. Revisar filtros simulados de notícias

O `NewsFilter` atual usa eventos simulados para demo.

**Objetivo:** rotular como dev-only ou substituir por integração real em modos operacionais mais sérios.

### 4.3. Limpar documentação legada otimista demais

Alguns documentos descrevem a arquitetura como mais madura do que o runtime realmente entrega hoje.

**Objetivo:** alinhar documentação ao comportamento operacional observável.

---

## 5. Ordem recomendada de execução

1. Auth nas superfícies sensíveis.
2. Config operacional única + execution mode fail-closed.
3. Remoção de inputs mockados do caminho manual/UI.
4. Unificação de persistência e journal.
5. `/health` honesto.
6. Hardening da trilha IA/RAG.
7. Telemetria/UI fiel ao backend.
8. Retomar expansão de estratégias e pesquisa quantitativa.

---

## 6. Estratégia e backtest continuam importantes — mas depois

As trilhas quantitativas continuam válidas, inclusive:

- melhorar estratégias com filtros de confluência;
- revisitar breakout/momentum;
- refinar SMC, sweep, suporte/resistência;
- seguir ajustando SL/TP e modelos de entrada.

Mas, a partir de agora, isso deve vir **depois** do hardening operacional.

Sem isso, qualquer ganho de estratégia roda sobre uma base que ainda mistura:

- simulação e operação;
- persistências paralelas;
- telemetria cosmética;
- superfícies de execução pouco protegidas.

---

## 7. Próxima retomada sugerida

Na próxima rodada prática, o melhor ponto de partida é:

### Opção recomendada
**Começar pelo P0 de backend**

Entregáveis esperados dessa rodada:

- auth em rotas e websocket;
- config operacional centralizada;
- mode fail-closed;
- limpeza da trilha manual da UI para parar de enviar dados mockados.

Depois disso, a base fica muito mais sólida para atacar P1 e só então retomar expansão quantitativa com segurança.
