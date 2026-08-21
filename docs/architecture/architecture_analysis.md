# 5. Evoluções na Arquitetura: Aplicação de Clean Code e SOLID

## Princípios Aplicados

### SRP (Single Responsibility Principle)
- As responsabilidades foram claramente separadas em camadas e classes menores.
- Rotas (`api/v1/routers`) apenas recebem requisições e delegam.
- Serviços de aplicação (`application/services`) orquestram a lógica de negócio.
- Entidades de domínio (`domain/entities`) representam o estado e regras centrais.
- Adaptadores de infraestrutura (`infrastructure/*`) lidam com detalhes técnicos (I/O, APIs externas).

### OCP (Open/Closed Principle)
- O `StrategyRegistry` permite adicionar novas estratégias sem modificar o core.
- O `ConfigurationLoader` agora permite trocar implementações de repositórios, filtros e provedores sem tocar no `main.py`.
- Novas personalidades são adicionadas apenas editando `config/portfolios.json`.

### LSP (Liskov Substitution Principle)
- As interfaces abstratas (`AbstractAIFilter`, `AbstractNewsFilter`, `AbstractTradeExecutor`) definem contratos claros.
- Qualquer implementação concreta pode ser injetada sem quebrar o comportamento esperado dos clientes.

### DIP (Dependency Inversion Principle)
- O núcleo da aplicação (`TradingDecisionService`, `TradingOrchestrator`) depende de abstrações, não de implementações concretas.
- As implementações concretas são injetadas no `main.py` (Composition Root).
- A fábrica de `TradeExecutor` é injetada como uma função, permitindo total flexibilidade na criação de instâncias.

## Componentes Novos e Refatorados

### `StrategyRegistry`
- Centraliza o registro e resolução de estratégias de análise técnica.
- Permite que novas estratégias sejam adicionadas com um simples decorator `@register_strategy`.

### Interfaces de Domínio
- `AbstractAIFilter`, `AbstractNewsFilter`, `AbstractTradeExecutor`: definem contratos claros para filtros e execução.
- `AbstractPaperTraderRepository`: abstrai a persistência de estado do simulador.

### `ConfigurationLoader` Estendido
- Agora carrega não apenas portfólios, mas também a configuração de todos os serviços de infraestrutura.
- Um novo `ServiceResolver` mapeia nomes amigáveis para classes concretas.
- O `main.py` usa `services.json` para instanciar todos os componentes de infraestrutura.
- Trocar um repositório ou filtro agora é uma mudança de configuração, não de código.

### `Personality` e `portfolios.json`
- Cada ativo pode ter múltiplas "personalidades" (sub-bots), cada uma com sua própria estratégia, timeframe e configuração de risco.
- Toda a configuração de personalidades é externalizada em `config/portfolios.json`.

## Benefícios

- **Flexibilidade**: Trocar um componente (filtro, repositório, executor) é uma mudança de configuração.
- **Testabilidade**: Componentes podem ser facilmente mockados ou substituídos em testes.
- **Manutenibilidade**: O núcleo da lógica de negócio está isolado e protegido de mudanças em detalhes de infraestrutura.
- **Extensibilidade**: Novas estratégias, filtros ou personalidades podem ser adicionadas sem modificar o código existente.