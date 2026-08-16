# Diretrizes do Projeto: [mutante-crypto-bot]

## 🛠️ Stack Tecnológica & Versões
* **Linguagem Principal:** TypeScript (v5.x).
* **Framework Backend:** Node.js (v22.x) com Fastify.
* **Banco de Dados:** PostgreSQL via Prisma ORM.
* **Gerenciador de Pacotes:** pnpm (nunca use npm ou yarn).

## 🔏 Padrões de Código & Arquitetura
* **Arquitetura:** Clean Architecture adaptada (Camadas: Domain, UseCases, Repositories, Controllers).
* **Tratamento de Erros:** Nunca lance exceções genéricas (`throw Error`). Use a classe customizada `AppError`.
* **Tipagem:** Evite o uso de `any` ou `unknown` a menos que seja estritamente necessário. Escreva tipos explícitos para retornos de funções.
* **Componentes:** Crie funções puras e isoladas. Siga os princípios do SOLID.

## 🚀 Fluxo de Trabalho & Git
* **Mensagens de Commit:** Siga estritamente o padrão Conventional Commits (ex: `feat(auth): add login validation`).
* **Testes:** Todo novo UseCase deve vir acompanhado de testes unitários usando Vitest. Cobertura mínima de 80%.
* **Branches:** Novas features devem sair de `develop` com o prefixo `feature/`.

## ⚠️ Restrições Críticas (O que NÃO fazer)
* **Segurança:** Nunca armazene chaves de API, senhas ou tokens diretamente no código. Use variáveis de ambiente (`process.env`).
* **Dependências:** Não adicione novas bibliotecas sem antes me consultar ou verificar se já existe uma solução nativa implementada.
* **Estilização (Se aplicável):** Nunca use CSS puro ou styled-components. Utilize apenas classes utilitárias do Tailwind CSS.

## 🧠 Instruções de Resposta para o Claude
* **Formato:** Seja direto e conciso. Mostre apenas o código modificado em vez de reimprimir o arquivo inteiro.
* **Explicações:** Explique o "porquê" de uma mudança complexa, não o "o quê".
* **Língua:** Responda sempre em português do Brasil.