# Gap Analysis — Mutant Crypto Bot vs Mutante Opções Ações (2026-08)

## Objetivo

Este documento compara o estado atual do `mutant-crypto-bot` com os padrões operacionais e de hardening já consolidados no `mutante-opcoes-acoes`.

A meta não é "copiar" o robô de opções, e sim portar os princípios que continuam válidos no domínio cripto:

- modo operacional explícito e fail-closed;
- healthchecks honestos por dependência;
- persistência/journal canônicos;
- auth em superfícies de execução;
- IA/RAG tratadas como camada de veto auditável, não como cosmética;
- UI honesta sobre o que é real, mockado, persistido ou apenas simulado.

---

## Resumo executivo

### Status da rodada P0 (2026-08-21)

A rodada P0 de hardening já teve progresso material no repositório crypto:

- `backend/app/core/operational_config.py` criado para centralizar `execution_mode`, flags críticas, token de auth e defaults operacionais;
- `backend/app/core/security.py` criado para validar `X-API-Key` com `compare_digest` e responder `401/403/503` de forma explícita;
- `backend/app/main.py` atualizado para carregar a configuração operacional no startup, logar o modo efetivo e exigir token no WebSocket `/ws` quando configurado;
- `backend/app/api/v1/routers/cqrs_router.py` e `backend/app/api/v1/routers/trading.py` endurecidos com auth nas mutações e gates de `allow_manual_trade` / `allow_runtime_risk_update`;
- `backend/app/application/services/executor.py` e `backend/app/application/services/deriv_executor.py` endurecidos com bloqueio fail-closed do caminho LIVE por default;
- `backend/app/infrastructure/services/risk_manager.py` ajustado para ler o limite global da configuração operacional central;
- `frontend/src/app/page.tsx` ajustado para enviar `X-API-Key`, autenticar o WebSocket com `?token=...`, bloquear trade manual sem ATR real e rotular explicitamente a telemetria ilustrativa da IA.

Ao mesmo tempo, continuam abertos itens importantes de P1/P2:

- persistência ainda fragmentada entre JSON, SQLAlchemy/SQLite e `journal.db` manual;
- ausência de `/health` honesto por dependência;
- RAG/IA ainda sem trilha de proveniência forte entre real, simulado e documental;
- política de startup quando `API_AUTH_TOKEN` está ausente ainda merece decisão final de produto/operação.

O `mutant-crypto-bot` tem uma arquitetura promissora em camadas, com sinais de Clean Architecture, CQRS, Composition Root por configuração e separação entre domínio/aplicação/infraestrutura. Porém, no estado atual, ele mistura **simulação operacional**, **CQRS persistido em SQLite**, **RAG/IA local/remota**, **fila Celery**, **swarm autônomo via Binance** e **UI com elementos cosméticos** sem uma governança única de runtime.

Com a rodada P0 aplicada, essa lacuna caiu bastante no eixo de auth/execução/UI, mas ainda não foi eliminada nas trilhas de persistência, health e RAG.

No `mutante-opcoes-acoes`, a rodada recente de hardening caminhou justamente na direção oposta:

- `execution_mode` efetivo e tipado;
- `/health` honesto para dependências reais;
- auth por token em superfícies sensíveis;
- redução de "200 com erro" e contratos mentirosos;
- AI Gate fail-closed;
- persistência e topologia operacional mais explícitas.

A lacuna principal do projeto crypto hoje não é "falta de features"; é **falta de contrato operacional único**.

---

## 1. Execução operacional e modo de runtime

### Estado atual no crypto

O runtime principal sobe um swarm de bots e injeta o executor configurado via `services.json`, hoje apontando para `PaperTrader`:

- `backend/app/main.py`
- `backend/config/services.json`

Evidência:

- `backend/config/services.json`
  - `"trade_executor": { "implementation": "PaperTrader" }`
- `backend/app/main.py`
  - carrega `service_configs = config_loader.load_service_configs_from_json("config/services.json")`
  - resolve `TradeExecutorImpl = ServiceResolver.get(service_configs["trade_executor"]["implementation"])`
  - cria `trade_executor_factory(...)` e injeta no `TradingOrchestrator`

Ao mesmo tempo, existe código de execução LIVE separado para Binance em:

- `backend/app/application/services/executor.py`

Evidência:

- `BinanceExecutor.execute_entry(...)` chama `self.exchange.create_market_order(...)`
- `BinanceExecutor.execute_exit(...)` chama `self.exchange.create_market_order(..., params={'reduceOnly': True})`

Ou seja: **há uma trilha PAPER efetivamente ativa e uma trilha LIVE disponível em código, mas sem um `execution_mode` tipado, centralizado e fail-closed**.

### Baseline no projeto de opções

No `mutante-opcoes-acoes`, o padrão mais maduro é centralizar a decisão operacional em uma config tipada:

- `backend/app/domain/services/operational_config.py`

O objeto `OperationalConfig` torna explícitos:

- `execution_mode`
- `ignore_market_hours`
- limites de capital/exposição/drawdown

E carrega defaults + persistência em um único lugar.

### Gap

**P0** — o projeto crypto ainda não tem uma fonte única de verdade para dizer:

- se está em PAPER, TESTNET, LIVE real ou modo híbrido proibido;
- quais superfícies podem operar em cada modo;
- se o caminho LIVE está bloqueado por padrão;
- como a UI e a API refletem esse modo.

### Recomendação

Criar um equivalente de `operational_config.py` no crypto com, no mínimo:

- `execution_mode` tipado (`PAPER`, `BINANCE_TESTNET`, `BINANCE_LIVE`, etc.);
- flags críticas de automação/autorização;
- limites globais de risco;
- governança central para o swarm, CQRS e UI.

**Princípio:** se a configuração não estiver válida, o sistema deve **bloquear execução real**, não escolher um default permissivo.

---

## 2. Persistência e journal operacional

### Estado atual no crypto

Hoje há **três** trilhas de persistência convivendo:

1. **JSON por arquivo**
   - `backend/app/infrastructure/repositories/json_paper_trader_repository.py`
2. **SQLite/SQLAlchemy para CQRS**
   - `backend/app/infrastructure/database/database.py`
   - `backend/app/infrastructure/database/models.py`
   - `backend/app/infrastructure/repositories/sqlalchemy_paper_trader_repository.py`
3. **SQLite manual separado para journal**
   - `backend/app/application/services/journal.py`

#### 2.1 JSON

O runtime principal usa `JsonPaperTraderRepository` por configuração:

- `backend/config/services.json`
  - `"paper_trader_repository": { "implementation": "JsonPaperTraderRepository", "params": { "base_path": "data" } }`

Esse repositório faz save atômico, o que é positivo:

- grava `.tmp`
- `os.replace(tmp_file_path, file_path)`

Mas continua sendo um journal de estado por arquivo, fora de um modelo relacional consultável.

#### 2.2 SQLAlchemy/SQLite

No CQRS, `SqlAlchemyPaperTraderRepository` persiste `account_state`, `personality` e `active_trades` em JSON dentro da tabela `paper_trader_states`.

Evidência:

- `backend/app/infrastructure/database/models.py`
  - tabela `paper_trader_states`
  - colunas JSON `account_state`, `personality`, `active_trades`

- `backend/app/infrastructure/repositories/sqlalchemy_paper_trader_repository.py`
  - `Base.metadata.create_all(bind=engine)`
  - `save(...)` faz `db_state.account_state = ...`, `db_state.personality = ...`, `db_state.active_trades = ...`

#### 2.3 Trade journal separado

O `TradeJournal` cria um banco `journal.db` à parte e registra entradas/saídas de trade fora da trilha SQLAlchemy.

Evidência:

- `backend/app/application/services/journal.py`
  - cria tabela `trades` via `sqlite3.connect(...)`
  - `log_entry(...)` faz `INSERT INTO trades`
  - `log_exit(...)` faz `UPDATE trades`

### Problemas observados

- não existe um **journal canônico único**;
- o swarm autônomo grava numa trilha diferente da CQRS;
- a consulta de `active_trades` no CQRS não é a mesma representação usada pelo `TradeJournal`;
- o projeto usa `Base.metadata.create_all(...)` no repositório, em vez de migrations formais;
- não há lifecycle unificado de trade (`PENDING`, `FILLED`, `REJECTED`, `CLOSED`) no mesmo storage.

### Baseline no projeto de opções

O projeto de opções já evoluiu na direção certa:

- repositório explícito de trades (`trade_repository.py`);
- modelos dedicados (`trade_model.py`);
- sessão de banco separada (`session.py`);
- migrations em `backend/migrations/`.

### Gap

**P1** — o crypto tem persistência funcional, mas ainda **fragmentada** e sem um modelo operacional canônico.

### Recomendação

Unificar em duas peças claras:

1. **estado operacional** do executor/swarm;
2. **journal de trades** consultável e versionado por migrations.

Idealmente:

- SQLAlchemy como storage canônico;
- JSON/in-memory apenas para backtest/testes;
- `journal.db` absorvido pela mesma infraestrutura oficial.

---

## 3. Risco e circuit breakers

### Estado atual no crypto

O `RiskManager` atual concentra parte importante da lógica:

- `backend/app/infrastructure/services/risk_manager.py`

Ele já faz:

- bloqueio quando `signal.type == NONE`;
- circuit breaker global por env `GLOBAL_MAX_DAILY_LOSS`;
- stop dinâmico com `daily_stop_loss`, `daily_stop_gain`, `highest_daily_pnl`;
- cálculo de sizing;
- cálculo de SL/TP;
- trailing stop;
- time stop.

Isso é bom.

Mas ainda há fragilidades:

1. dependência direta de env dentro da regra (`os.getenv("GLOBAL_MAX_DAILY_LOSS", "-100.0")`), sem config operacional central;
2. coexistência de lógica legada no `PaperTrader`;
3. shapes diferentes entre CQRS e simulador principal;
4. UI podendo alterar risco sem auth.

### Exemplo de inconsistência já visível

No `PaperTrader`, ainda existem fallbacks locais:

- `daily_stop_loss = 50.0`
- `daily_stop_gain = 50.0`
- `stake_initial = 10.0`
- `risk_percent = 2.0`
- comentários `TODO` para receber personalidade correta e refatorar sizing

Esse desenho sinaliza que o contrato entre `RiskManager`, personalidade, executor e persistência ainda não foi totalmente consolidado.

### Baseline no projeto de opções

No projeto de opções, a remediação mirou exatamente o problema de config e governança:

- `backend/app/domain/services/risk_manager.py`
- `backend/app/domain/services/operational_config.py`

Mesmo com itens ainda abertos, o padrão perseguido é: **ler config válida de uma única fonte e falhar de forma explícita quando ela estiver inválida**.

### Gap

**P1** — o crypto já tem lógica de risco relevante, mas ainda não está plenamente acoplada a uma configuração operacional única e a uma trilha única de execução.

### Recomendação

- mover limites globais para config operacional tipada;
- remover defaults cosméticos do caminho live/swarm;
- garantir que manual trade, swarm e qualquer execução futura passem pelo mesmo contrato de risco;
- explicitar o lifecycle de conta/PnL diário entre restarts.

---

## 4. Auth e superfície de ataque

### Estado atual no crypto

As rotas principais observadas não mostram auth:

- `backend/app/api/v1/routers/cqrs_router.py`
- `backend/app/api/v1/routers/trading.py`
- `backend/app/main.py` (websocket `/ws`)

O endpoint manual de execução:

- `POST /api/cqrs/execute_trade`

recebe `ExecuteTradeCommand`, injeta DB e chama handler, sem dependência de API key.

A UI também faz chamadas diretas sem auth:

- `frontend/src/app/page.tsx`
  - `fetch(.../api/cqrs/execute_trade?identity=default, { method: "POST", ... })`
  - `fetch(.../api/risk_settings, { method: "POST", ... })`

### Baseline no projeto de opções

O baseline já tem dependências explícitas de auth por header:

- `backend/app/core/security.py`
  - `require_api_key`
  - `require_bridge_key`

Esse padrão protege superfícies de execução e bridge com:

- header obrigatório;
- 401 se ausente;
- 403 se inválido;
- 503 se segredo não configurado.

### Gap

**P0** — hoje, o crypto expõe superfícies de execução/config sem auth explícita no caminho principal.

### Recomendação

Aplicar o mesmo padrão do baseline nas rotas sensíveis do crypto:

- `execute_trade`
- mutações de risco/config
- websocket de comando
- qualquer rota futura de troca de modo operacional

E separar:

- endpoints públicos de leitura segura;
- endpoints administrativos/operacionais autenticados.

---

## 5. Healthcheck e observabilidade honesta

### Estado atual no crypto

A exploração inicial não encontrou um `/health` equivalente ao do projeto de opções.

Hoje o sistema depende de vários componentes reais:

- SQLite / storage local
- Redis/Celery
- WebSocket/Binance feed
- Chroma local persistido em diretório
- backend LLM remoto/local via `MANIFEST_BASE_URL`

Também há sinais de UI e docs que podem dar percepção otimista demais:

- `docs/architecture/architecture_analysis.md` descreve entregas já “concluídas” em termos fortes;
- `frontend/src/app/page.tsx` usa mocks de telemetria de IA;
- vários fetches silenciam erro com `catch (e) {}`.

### Baseline no projeto de opções

O `/health` do projeto de opções faz o que o crypto ainda precisa passar a fazer:

- `backend/app/api/endpoints/health.py`
- `backend/app/domain/services/health_service.py`

Ele reporta dependência por dependência e distingue:

- `ok`
- `degraded`
- `error`

com honestidade operacional.

Exemplo útil do baseline:

- Chroma em fallback local não é tratado como "ok" pleno;
- MT5 bridge só fica ok se realmente conectado, não apenas respondendo HTTP.

### Gap

**P1** — falta um healthcheck central e honesto no crypto.

### Recomendação

Criar `/health` no crypto reportando pelo menos:

- storage relacional / DB;
- Redis / Celery backend;
- Chroma (persist-local vs indisponível);
- LLM backend;
- feed Binance (último tick / conexão ativa / stale);
- modo operacional corrente.

---

## 6. IA / RAG e proveniência dos dados

### Estado atual no crypto

A trilha de IA está em:

- `backend/app/infrastructure/ai_filter_openai.py`
- `backend/app/rag/chroma_trade_history.py`
- `backend/app/rag/vector.py`
- `backend/app/rag/agent.py`
- `backend/app/infrastructure/queue/tasks.py`

#### 6.1 AI filter

O `OpenAIFilter`:

- usa `MANIFEST_API_KEY` ou `OPENAI_API_KEY`;
- usa `MANIFEST_BASE_URL` default `http://192.168.1.10:8080/v1`;
- instancia `ChromaTradeHistory()`;
- chama LLM com prompt + few-shot;
- em erro ou indisponibilidade retorna `WAIT`.

Isso já é melhor do que fail-open.

#### 6.2 RAG de histórico de trade

`ChromaTradeHistory`:

- persiste em `CHROMA_DB_DIR` local;
- indexa documentos do tipo `"Contexto de mercado: ... Resultado: ..."`;
- metadata inclui `symbol`, `side`, `outcome`, `pnl`.

Porém não há, no estado atual observado, um esquema forte de proveniência como no baseline do projeto de opções, que diferencia explicitamente:

- `LIVE`
- `BACKTEST`
- `SEED`
- `UNKNOWN`

No crypto, isso abre espaço para confusão futura entre:

- trades reais do swarm/CQRS;
- resultados simulados/backtest;
- documentação vetorial em `docs/`.

#### 6.3 RAG documental

`backend/app/rag/vector.py` reconstrói o vector store a partir de markdowns em `docs/` quando o diretório vetorial não existe ou está vazio.

Isso é útil para um agente explicativo/documental, mas é uma trilha diferente da memória de trades e precisa ficar claramente separada.

### Baseline no projeto de opções

No projeto de opções, o hardening caminhou para:

- fail-closed explícito quando LLM está offline;
- rotulagem de proveniência do RAG;
- rejeição por segurança quando não há base confiável.

### Gap

**P1** — o crypto não está claramente fail-open, mas ainda precisa **formalizar proveniência e segregação de memórias** antes de qualquer autonomia mais agressiva.

### Recomendação

Separar explicitamente:

1. RAG documental/explicativo;
2. memória de trades operacionais;
3. dados simulados/backtest.

E adicionar campos explícitos de proveniência no histórico vetorial operacional.

---

## 7. UI e honestidade do operador

### Estado atual no crypto

A UI atual em `frontend/src/app/page.tsx` mistura dados reais com estados cosméticos/mockados.

Exemplos:

1. **Mock AI Neural Feed polling**
   - altera `aiTaskState` com `Math.random()` a cada 3 segundos;
   - exibe “Calculando RAG”, “Analisando Price Action”, etc., sem vínculo real com Celery/LLM.

2. **Trade manual com ATR mockado**
   - `handleManualTrade(...)` envia `atr: 50.0 // mock ATR`

3. **Silêncio em falhas**
   - vários `catch (e) {}` em fetches de portfolio/risk/CQRS.

### Gap

**P0/P2 misto** — parte é problema de honestidade operacional e parte é UX técnica.

- é aceitável ter UI de demo se ela estiver claramente rotulada como demo;
- não é aceitável deixar o operador acreditar que um estado é real quando é mock/cosmético.

### Recomendação

- remover ou rotular fortemente o AI Feed mockado;
- impedir trade manual com inputs artificiais no caminho operacional;
- distinguir visualmente:
  - dado real persistido;
  - dado ausente;
  - simulação;
  - fallback/local cache.

---

## 8. Celery, Redis e autonomia assíncrona

### Estado atual no crypto

O projeto já tem fila assíncrona:

- `backend/app/infrastructure/queue/task_manager.py`
- `backend/app/infrastructure/queue/tasks.py`
- `docker-compose.yaml`

Isso é um bom sinal arquitetural.

Mas hoje ainda existe uma assimetria:

- a task async avalia IA em background;
- o swarm principal também faz loop de decisão em tempo real;
- a UI tem telemetria mockada em vez de ler o status real dessas tasks.

### Gap

**P2** — a infraestrutura assíncrona existe, mas ainda não está refletida de forma honesta e unificada no operador/health/fluxo principal.

### Recomendação

Depois do hardening de execução/auth/persistência:

- conectar AI task state real à UI;
- expor health/status do worker e Redis;
- definir com clareza quais decisões são síncronas e quais dependem de fila.

---

## 9. Notícias / filtros externos simulados

### Estado atual no crypto

`backend/app/infrastructure/services/news_filter.py` gera eventos simulados:

- `NFP (Payroll) [Simulado]`
- `Discurso do FED [Simulado]`

para demonstrar bloqueio de notícias.

Isso pode ser aceitável em ambiente de desenvolvimento, mas não pode ser tratado como se fosse um calendário macro real.

### Gap

**P2**, com risco de honestidade operacional.

### Recomendação

- rotular explicitamente como simulador/dev-only;
- desligar em modo operacional real;
- ou substituir por um provider real de calendário macro.

---

## 10. Matriz de prioridade

## P0 — corrigir antes de qualquer aumento de autonomia

1. **Auth nas superfícies sensíveis**
   - `execute_trade`
   - mutações de risco/config
   - websocket de comando

2. **Modo operacional único e fail-closed**
   - impedir ambiguidade entre PAPER, testnet e live;
   - bloquear execução real se config estiver inválida.

3. **Honestidade da UI em execução manual**
   - remover ATR mockado do caminho operacional;
   - parar de misturar telemetria falsa com operação real.

## P1 — confiabilidade operacional

4. **Unificar persistência e journal**
5. **Adicionar `/health` honesto**
6. **Formalizar proveniência do RAG operacional**
7. **Consolidar contrato de risco/config**

## P2 — qualidade e clareza arquitetural

8. alinhar Celery/UI/telemetria
9. rotular/remover filtros e estados simulados
10. limpar docs antigas que descrevem o sistema em termos mais maduros do que o runtime real entrega hoje

---

## Plano recomendado de remediação

### Fase 1 — Honestidade operacional

- criar config operacional única;
- proteger rotas e websocket com auth;
- remover inputs mockados do caminho manual;
- documentar claramente o que é PAPER, o que é CQRS, o que é swarm.

### Fase 2 — Persistência e observabilidade

- unificar storage/journal;
- introduzir migrations formais;
- adicionar `/health` por dependência;
- tornar status de worker/LLM/feed visível.

### Fase 3 — IA/RAG segura

- separar memória documental vs histórico operacional;
- adicionar proveniência explícita;
- endurecer fallbacks e auditoria.

### Fase 4 — UX operacional honesta

- eliminar mock visual não rotulado;
- refletir estados reais do backend;
- distinguir erro, ausência de dado, simulação e dado persistido.

---

## Conclusão

O `mutant-crypto-bot` já tem componentes interessantes e várias decisões arquiteturais corretas. O problema principal não é incapacidade técnica do projeto, e sim **sobreposição de trilhas operacionais sem contrato único**.

O `mutante-opcoes-acoes` mostra um caminho mais seguro: centralizar governança operacional, tornar o sistema honesto sobre suas dependências e bloquear comportamentos inseguros por padrão.

O próximo passo recomendado é usar este documento como baseline para abrir uma rodada objetiva de remediação no crypto começando por:

1. auth;
2. execution mode fail-closed;
3. persistência/journal unificados;
4. healthcheck honesto;
5. limpeza de mocks operacionais na UI.
