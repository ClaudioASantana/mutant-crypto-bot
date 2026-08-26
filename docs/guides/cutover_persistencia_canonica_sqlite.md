# Cutover para Persistência Canônica SQLite/SQLAlchemy

Este guia documenta a virada do runtime principal do `mutant-crypto-bot` para o storage canônico unificado em SQLite/SQLAlchemy, absorvendo o journal legado na tabela `trades` e preservando snapshots operacionais em `paper_trader_states`.

O objetivo do cutover é substituir o runtime padrão baseado em JSON por:

- `paper_trader_states` como snapshot operacional por `identity`;
- `trades` como trilha canônica de lifecycle + proveniência;
- Alembic como etapa explícita de schema management;
- script de import legada como etapa one-shot, idempotente e separada das migrations estruturais.

---

## 1. Estado esperado após esta rodada

O backend agora está preparado para operar com persistência canônica:

- o runtime principal usa `SqlAlchemyPaperTraderRepository` como default;
- `PaperTrader` persiste abertura/fechamento na tabela `trades`;
- o CQRS manual grava trades canônicos com `source=MANUAL_CQRS`;
- o script `backend/scripts/migrate_legacy_paper_trader_data.py` importa:
  - `backend/data/journal.db`
  - `backend/app/data/journal.db` (se existir)
  - `backend/data/simulator_state_*.json`
- a migração legada é idempotente;
- JSON/InMemory ficam restritos a compatibilidade, backtest e testes.

Validação executada nesta rodada:

- testes da migração legada: passando;
- suíte backend relevante: `78 passed, 1 warning`;
- `app.main` sobe com `paper_trader_repository = SqlAlchemyPaperTraderRepository`.

---

## 2. Onde fica o banco canônico

A fonte de verdade é `OperationalConfig.sqlite_db_path` em:

- [backend/app/core/operational_config.py](../../backend/app/core/operational_config.py)

Default atual:

- `backend/data/app.db`

DSN derivado:

- `sqlite:///<sqlite_db_path>`

Importante:

- o path é resolvido de forma absoluta, ancorado em `BACKEND_DIR`;
- isso evita repetir o bug antigo de depender do CWD do processo;
- não use caminhos relativos arbitrários para o banco canônico no cutover.

---

## 3. Pré-condições antes do cutover

Antes de virar ou validar o runtime principal, garanta:

1. backup dos JSONs e DBs legados;
2. backend parado, ou pelo menos sem swarm escrevendo simultaneamente;
3. ambiente Python correto (`backend/venv`);
4. volume/diretório `backend/data/` preservado;
5. confirmação de que o banco de destino é o mesmo path configurado em `OperationalConfig`.

---

## 4. Backup recomendado

No diretório `backend/`:

```bash
mkdir -p backups
cp -a data "backups/data-before-canonical-cutover-$(date +%Y%m%d-%H%M%S)"
[ -f app/data/journal.db ] && cp app/data/journal.db "backups/journal-app-$(date +%Y%m%d-%H%M%S).db"
```

Se houver outro `SQLITE_DB_PATH` configurado via env/config, faça backup dele também.

Nunca rode import/migration destrutiva sem backup dos artefatos abaixo:

- `data/simulator_state_*.json`
- `data/journal.db`
- `app/data/journal.db` (se existir)
- banco canônico de destino (`app.db` ou equivalente)

---

## 5. Migration estrutural do schema

No diretório `backend/`:

```bash
venv/bin/alembic upgrade head
```

A migration estrutural esperada cria:

- `paper_trader_states`
- `trades`
- `alembic_version`

### Atenção: "stamped" não é igual a schema válido

Durante esta rodada foi encontrado um estado local inconsistente: um `app.db` que tinha apenas a tabela `alembic_version`, marcada em `head`, mas **sem** `paper_trader_states` e **sem** `trades`.

Isso significa:

- `venv/bin/alembic current` pode parecer saudável;
- mas o runtime ainda quebrará ao acessar os repositórios canônicos.

Por isso, após `upgrade head`, valide **também** a existência física das tabelas.

### Validação mínima após o Alembic

```bash
venv/bin/python - <<'PY'
import sqlite3
from app.core.operational_config import load_operational_config

path = load_operational_config().sqlite_db_path
conn = sqlite3.connect(path)
tables = [r[0] for r in conn.execute(
    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
)]
print({"sqlite_db_path": path, "tables": tables})
PY
```

Resultado esperado: presença explícita de:

- `alembic_version`
- `paper_trader_states`
- `trades`

Se `alembic_version` existir sozinho, **pare o cutover** e corrija o banco antes de seguir.

### 5.1. Bootstrap oficial de banco novo (ambiente limpo)

Para ambientes novos ou sem dados legados (novo deploy, CI, clone fresco em
dev), o procedimento é determinístico e exige dois passos:

**1. Criar o schema (única via de schema management)**

```bash
cd backend
venv/bin/alembic upgrade head
```

Nunca chame `Base.metadata.create_all(...)` manualmente e nunca dependa do
runtime para criar o schema: o runtime falha de forma explícita se as tabelas
canônicas não existirem, e o import legado também falha fail-fast nesse caso.

**2. Validar a presença física das tabelas**

Mesma checagem da seção 5:

```bash
venv/bin/python - <<'PY'
import sqlite3
from app.core.operational_config import load_operational_config

path = load_operational_config().sqlite_db_path
conn = sqlite3.connect(path)
tables = [r[0] for r in conn.execute(
    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
)]
print({"sqlite_db_path": path, "tables": tables})
PY
```

Esperado: `alembic_version`, `paper_trader_states`, `trades`.

**3. Popular dados legados, somente se existirem**

Se o ambiente já tiver `simulator_state_*.json` ou `journal.db` reaproveitáveis,
rode o import idempotente para popular o banco:

```bash
venv/bin/python scripts/migrate_legacy_paper_trader_data.py
```

Se não houver dados legados, pule o import: o backend sobe vazio e o swarm
passa a persistir trades a partir do próximo ciclo.

Regras do bootstrap:

- `alembic upgrade head` é a única via de criação de schema em produção/dev;
- o import legado exige o schema já existente e recusa-se a criar tabelas;
- ambiente sem legado não precisa de backup; com legado, siga a seção 4.

---

## 6. Importação dos dados legados

Com o schema estrutural válido, rode o import legado:

```bash
venv/bin/python scripts/migrate_legacy_paper_trader_data.py
```

O script:

- lê snapshots `simulator_state_*.json`;
- upserta `paper_trader_states`;
- importa trades no storage canônico;
- enriquece trades com dados do `journal.db` quando houver correspondência por `id`;
- preserva `id` legado;
- é idempotente em reexecuções.

### Regras de merge relevantes

- prioridade principal de deduplicação: `trade.id`;
- fallback estrutural existe apenas para cenários sem id estável;
- no dataset legado real, existem trades distintos com mesma entrada estrutural;
- por isso, **não** se deve colapsar trades só porque compartilham `(identity, symbol, side, entry_epoch, entry_price)`.

### Proveniência esperada

- `MIGRATED_JOURNAL` quando há enriquecimento pelo journal;
- `MIGRATED_JSON` quando o trade veio apenas do snapshot.

### Status/fechamento

- JSON vence quando já traz fechamento real;
- journal enriquece proveniência (`strategy`, `ai_*`, `rsi`, `leverage`);
- journal órfão com `OPEN` deve permanecer `OPEN`, sem inventar fechamento.

---

## 7. Validação pós-import

Depois do import, valide contagens e presença de dados.

### 7.1. Contagens básicas

```bash
venv/bin/python - <<'PY'
import sqlite3
from app.core.operational_config import load_operational_config

path = load_operational_config().sqlite_db_path
conn = sqlite3.connect(path)
for table in ("paper_trader_states", "trades"):
    total = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    print(table, total)
PY
```

### 7.2. Distribuição por source/status

```bash
venv/bin/python - <<'PY'
import sqlite3
from app.core.operational_config import load_operational_config

path = load_operational_config().sqlite_db_path
conn = sqlite3.connect(path)
print("sources")
for row in conn.execute("SELECT source, COUNT(*) FROM trades GROUP BY source ORDER BY source"):
    print(row)
print("statuses")
for row in conn.execute("SELECT status, outcome, COUNT(*) FROM trades GROUP BY status, outcome ORDER BY status, outcome"):
    print(row)
PY
```

### 7.3. Smoke check de exemplos esperados

Verificar um trade enriquecido:

```bash
venv/bin/python - <<'PY'
import sqlite3
from app.core.operational_config import load_operational_config

path = load_operational_config().sqlite_db_path
conn = sqlite3.connect(path)
row = conn.execute(
    "SELECT id, symbol, status, outcome, source, strategy, ai_reason, rsi FROM trades WHERE id = ?",
    ("5109a8f5",),
).fetchone()
print(row)
PY
```

Verificar um `OPEN` preservado:

```bash
venv/bin/python - <<'PY'
import sqlite3
from app.core.operational_config import load_operational_config

path = load_operational_config().sqlite_db_path
conn = sqlite3.connect(path)
row = conn.execute(
    "SELECT id, symbol, status, outcome, source FROM trades WHERE id = ?",
    ("34c4ce65",),
).fetchone()
print(row)
PY
```

---

## 8. Flip do runtime principal

Nesta rodada, o default já foi alterado em:

- [backend/config/services.json](../../backend/config/services.json)
- [backend/app/main.py](../../backend/app/main.py)

Estado atual:

- `paper_trader_repository` default = `SqlAlchemyPaperTraderRepository`
- `PaperTrader` continua com assinatura única `repository=...`
- o composto SQL delega internamente para:
  - `SqlAlchemyPaperTraderStateRepository`
  - `SqlAlchemyTradeRepository`

Isso permite o cutover sem reescrever o wiring do swarm nem quebrar os scripts de backtest que usam compostos alternativos.

---

## 9. Restart e smoke checks operacionais

Depois de `upgrade + import + validação`, reinicie o backend e valide:

1. startup sem erro de repositório/tabela ausente;
2. `PaperTrader.load_state()` reconstruindo runtime a partir de:
   - `paper_trader_states`
   - `trades`
3. WebSocket/UI ainda recebendo o mesmo shape derivado de runtime;
4. CQRS manual conseguindo abrir trade em `trades`;
5. swarm conseguindo:
   - abrir trade canônico;
   - fechar trade canônico;
   - persistir snapshot operacional.

### Sinais de problema no restart

- erro `no such table: trades`
- erro `no such table: paper_trader_states`
- backend subindo “zerado” apesar de existir legado para importar
- `alembic current` em head, mas schema ausente fisicamente
- runtime ainda escrevendo JSON por engano no caminho principal

---

## 10. Rollback operacional

Se a validação falhar:

1. pare o backend;
2. restaure o backup de `data/`;
3. restaure o banco canônico anterior, se aplicável;
4. volte temporariamente o wiring para JSON apenas se for estritamente necessário para continuidade operacional;
5. só repita o cutover depois de corrigir a causa raiz e revalidar em sandbox.

Evite rollback parcial misturando:

- schema novo;
- import incompleto;
- runtime já apontando para SQL;
- JSON legado ainda sendo tratado como fonte principal.

---

## 11. Comandos de referência

### Testes da migração

```bash
venv/bin/python -m pytest tests/integration/scripts/test_migrate_legacy_paper_trader_data.py -q
```

### Suíte backend principal

```bash
venv/bin/python -m pytest tests/ --ignore=tests/unit/test_market_structure.py -q
```

### Smoke check automatizado do schema canônico

```bash
venv/bin/python -m pytest tests/integration/test_canonical_schema_smoke.py -q
```

### Alembic

```bash
venv/bin/alembic upgrade head
venv/bin/alembic current
venv/bin/alembic heads
```

### Import legado

```bash
venv/bin/python scripts/migrate_legacy_paper_trader_data.py
```

---

## 12. Próximo passo recomendado após o cutover

Depois que o cutover estiver validado em ambiente real/sandbox operacional, os próximos passos naturais são:

1. ~~aposentar o `journal.py` legado do caminho principal~~ — feito: `backend/app/application/services/journal.py` virou shim fail-fast;
2. aposentar a trilha legada de scripts/research que ainda dependia de `app.engines.*`, `app.models.*` e `app.services.*` — feito; ver `docs/research/proximos_passos_e_pendencias.md` §3.1.2;
3. ~~documentar um procedimento oficial de bootstrap de banco novo~~ — feito: seção 5.1 deste guia;
4. ~~adicionar smoke check automatizado para detectar o caso “alembic head sem tabelas canônicas”~~ — feito: `tests/integration/test_canonical_schema_smoke.py`;
5. ~~revisar se o banco local atual (`backend/data/app.db`) precisa ser recriado/limpo~~ — resolvido: o `app.db` local foi recriado e revalidado durante o cutover; o estado inconsistente original (stamped head sem tabelas) está preservado em `backups/app.db.prestamped-20260821-233413`.
