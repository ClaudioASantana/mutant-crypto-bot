Viewed prompt_para_outra_ide.md:1-164

O arquivo existe. Deve ter sido problema do link. Aqui vai o conteúdo completo para você copiar direto daqui:

---

Preciso que você aplique as seguintes configurações e melhorias no projeto. O projeto é um monorepo com **Frontend (Next.js + Turbopack)** e **Backend (FastAPI + Asyncio + SQLAlchemy Async)**.

---

## PROBLEMA IDENTIFICADO

Temos um bug de **contenção de stdin** entre os dois dev servers. Quando o Next.js (Turbopack) e o Uvicorn (FastAPI) rodam simultaneamente, eles competem pelo stdin do terminal. Isso causa **paradas silenciosas sem mensagem de erro** — um processo congela e só retoma quando o outro perde o foco. A causa raiz é que ambos monitoram o stdin.

## CORREÇÃO OBRIGATÓRIA

### 1. Isolar o stdin de cada processo

Em **todos** os scripts de dev, redirecionar stdin para vazio:

- **Windows PowerShell**: `echo '' | <comando>`
- **WSL/Linux**: `<comando> < /dev/null`

### 2. Configurar `next.config.ts` com proxy reverso para o backend

```typescript
import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  experimental: {
    turbo: {
      resolveAlias: {
        // aliases se necessário
      },
    },
  },
  webpack: (config, { isServer }) => {
    if (!isServer) {
      config.watchOptions = {
        ...config.watchOptions,
        poll: false,
        aggregateTimeout: 300,
      };
    }
    return config;
  },
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://localhost:8000/api/:path*',
      },
    ];
  },
  output: 'standalone',
};

export default nextConfig;
```

### 3. Criar scripts de orquestração no `package.json` da raiz

```json
{
  "scripts": {
    "dev": "concurrently --kill-others-on-fail --names FRONT,BACK --prefix-colors cyan,yellow \"npm run dev:frontend\" \"npm run dev:backend\"",
    "dev:frontend": "cd frontend && next dev --turbopack --port 3000 < /dev/null",
    "dev:backend": "cd backend && uvicorn app.main:app --reload --port 8000 < /dev/null"
  }
}
```

Se não tiver `concurrently`, instale: `npm install -g concurrently`

### 4. Se usar Docker, garantir `stdin_open: false` e `tty: false` em cada service do `docker-compose.yml`

---

## REESTRUTURAÇÃO DO BACKEND PYTHON — Clean Architecture + DDD + CQRS

Reestruture (ou crie) o backend FastAPI seguindo esta arquitetura de camadas. Adapte os nomes de entidades ao domínio real do projeto.

### Estrutura de Pastas

```
backend/
├── app/
│   ├── main.py                          # FastAPI app factory
│   │
│   ├── core/                            # Configuração global
│   │   ├── config.py                    # Pydantic BaseSettings
│   │   ├── security.py                  # JWT, hashing
│   │   ├── dependencies.py              # Dependency Injection central
│   │   ├── exceptions.py                # Exceções de domínio customizadas
│   │   └── events.py                    # Event bus interno (pub/sub)
│   │
│   ├── domain/                          # CAMADA DE DOMÍNIO (DDD) — sem dependência externa
│   │   ├── entities/                    # Entidades ricas com regras de negócio
│   │   ├── value_objects/               # Objetos imutáveis (Email, CPF, Money)
│   │   ├── events/                      # Domain Events (UserCreated, etc.)
│   │   ├── repositories/               # INTERFACES (ABCs) — apenas contratos/ports
│   │   └── services/                    # Domain Services (lógica cross-entity)
│   │
│   ├── application/                     # CAMADA DE APLICAÇÃO (Use Cases)
│   │   ├── commands/                    # CQRS — Comandos de escrita (dataclass frozen)
│   │   ├── queries/                     # CQRS — Queries de leitura (dataclass frozen)
│   │   ├── handlers/                    # Command Handlers e Query Handlers
│   │   └── dtos/                        # Data Transfer Objects
│   │
│   ├── infrastructure/                  # CAMADA DE INFRAESTRUTURA
│   │   ├── database/
│   │   │   ├── connection.py            # AsyncEngine, session factory
│   │   │   ├── models/                  # SQLAlchemy ORM models
│   │   │   └── migrations/              # Alembic
│   │   ├── repositories/               # Implementações concretas dos ports do domain
│   │   ├── external/                    # Integrações externas (email, pagamento)
│   │   └── cache/                       # Redis, etc.
│   │
│   └── api/                             # CAMADA DE APRESENTAÇÃO
│       ├── v1/routers/                  # FastAPI routers (controllers)
│       ├── v1/schemas/                  # Pydantic schemas (request/response)
│       └── middlewares/                 # Auth, CORS, logging
│
└── tests/
    ├── unit/domain/
    ├── unit/application/
    └── integration/infrastructure/
```

### Padrões a seguir

**CQRS**: Toda operação de escrita deve ser um `Command` (dataclass frozen) processado por um `CommandHandler`. Toda leitura deve ser uma `Query` processada por um `QueryHandler`. Nunca misture leitura e escrita no mesmo handler.

**Repository Pattern**: A camada `domain/repositories/` contém **apenas interfaces** (classes abstratas ABC). A implementação concreta (SQLAlchemy, etc.) fica em `infrastructure/repositories/`. O domínio NUNCA importa infraestrutura.

**Dependency Injection**: Use `fastapi.Depends()` para injetar repositórios e handlers nos routers. Exemplo:

```python
# core/dependencies.py
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise

def get_user_repository(session: AsyncSession = Depends(get_db_session)) -> UserRepository:
    return SQLAlchemyUserRepository(session)

def get_create_user_handler(
    repo: UserRepository = Depends(get_user_repository),
    event_bus: EventBus = Depends(get_event_bus),
) -> CreateUserHandler:
    return CreateUserHandler(repo=repo, event_bus=event_bus)
```

**Domain Events**: Após operações de escrita, o handler publica domain events via EventBus. Side effects (email, cache, logs) reagem a esses eventos — nunca ficam dentro do handler principal.

**Regra de ouro da dependência**: API → Application → Domain ← Infrastructure. O domínio é o centro e não depende de nada externo. A infraestrutura implementa os contratos definidos pelo domínio.

---

Analise o estado atual do projeto, identifique o que já existe, e crie um plano de implementação para aplicar essas mudanças. Priorize: (1) correção do stdin, (2) next.config.ts, (3) scripts de orquestração, (4) reestruturação do backend.

---

☝️ Tudo acima — é só selecionar, copiar e colar na outra IDE.