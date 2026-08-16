# 🧠 Crypto Wiki — Schema do Mantenedor

Este diretório é uma **wiki de conhecimento persistente** sobre **Estratégias de Operações em Criptomoedas**, mantida inteiramente pelo LLM (Claude). O humano curadoria fontes, faz perguntas e direciona a análise; o LLM faz toda a escrita, manutenção e cross-referência.

## 🗂️ Arquitetura (3 camadas)

```
crypto-wiki/
├── CLAUDE.md          ← este arquivo (schema/convenções)
├── index.md           ← catálogo de todas as páginas (orientado a conteúdo)
├── log.md             ← registro cronológico append-only (ingests, queries, lints)
├── raw/               ← fontes brutas IMUTÁVEIS (artigos, papers, docs) — nunca editar
│   └── assets/        ← imagens baixadas localmente
└── wiki/              ← páginas geradas pelo LLM
    ├── estrategias/   ← páginas de estratégias de trading (uma por estratégia)
    ├── conceitos/     ← conceitos de mercado (liquidez, funding, on-chain, gestão de risco...)
    ├── indicadores/   ← indicadores técnicos (RSI, MACD, Bollinger, funding rate...)
    ├── fontes/        ← página-resumo de cada fonte ingerida de raw/
    └── analises/      ← sínteses e análises geradas em queries e arquivadas
```

## 📏 Convenções

* **Língua:** tudo em **português do Brasil** (nomes de indicadores/estratégias podem manter o termo original em inglês quando for o uso comum, ex: *funding rate*, *long/short*).
* **Links internos:** use sempre o formato Obsidian `[[Nome da Página]]` — sem caminho, sem extensão. O título H1 da página deve bater com o nome usado nos links.
* **Frontmatter YAML** em toda página de `wiki/`:

```yaml
---
tags: [estrategia]        # ou: conceito, indicador, fonte, analise
atualizado: 2026-08-16
fontes: 2                 # nº de fontes que embasam a página
status: ativo             # ativo | desatualizado | em-revisao
---
```

* **Citações:** ao afirmar algo que veio de uma fonte, referencie `[[Nome da Fonte]]` (página em `wiki/fontes/`).
* **Contradições:** quando uma nova fonte contradiz uma página existente, **não apague** a afirmação antiga silenciosamente — registre a divergência em uma seção `## ⚠️ Divergências` na página afetada.
* **Contexto do projeto:** esta wiki vive dentro do repositório `mutant-crypto-bot`. Sempre que relevante, conecte o conhecimento teórico à implementação real do bot (ex: `backend/app/engines/strategy.py`, resultados de backtest em `docs/`). Páginas de estratégia devem ter uma seção `## 🤖 No mutant-crypto-bot` quando houver relação com o código.

## 📄 Formatos de página

### Estratégia (`wiki/estrategias/`)
`# Nome` → visão geral → **Tese** (por que funciona) → **Setup** (condições de entrada) → **Gestão de risco** (stop, alvo, position sizing) → **Timeframes & ativos** → **Vantagens/Armadilhas** → `## 🤖 No mutant-crypto-bot` → `## 🔗 Ver também` (links `[[...]]`) → `## 📚 Fontes`

### Conceito / Indicador
`# Nome` → definição → como se calcula/interpreta → uso prático em estratégias (com links) → limitações → `## 🔗 Ver também` → `## 📚 Fontes`

### Fonte (`wiki/fontes/`)
`# Título da Fonte` → metadados (origem, data, arquivo em `raw/`) → resumo executivo → pontos-chave (bullets) → páginas da wiki que esta fonte embasa → trechos/dados notáveis

### Análise (`wiki/analises/`)
`# Pergunta ou Tema` → data → síntese com citações `[[...]]` → conclusão → perguntas abertas que surgiram

## ⚙️ Workflows

### 1. Ingest (nova fonte)
1. Ler a fonte em `raw/` (se for PDF/imagem, ler texto primeiro e imagens depois).
2. Discutir os principais takeaways com o usuário.
3. Criar página em `wiki/fontes/` com o resumo.
4. Criar/atualizar páginas de estratégias, conceitos e indicadores citados — incluindo cross-links nos dois sentidos.
5. Sinalizar contradições com afirmações já existentes (seção `## ⚠️ Divergências`).
6. Atualizar `index.md` (novas páginas + contagens).
7. Adicionar entrada em `log.md`.

### 2. Query (pergunta do usuário)
1. Ler `index.md` primeiro para localizar páginas relevantes; então ler as páginas.
2. Responder com síntese citando `[[páginas]]`.
3. **Perguntar ao usuário se deseja arquivar a resposta** em `wiki/analises/` — boas respostas viram páginas e entram no `index.md` e no `log.md`.

### 3. Lint (health-check periódico — rodar quando pedido)
Verificar: contradições entre páginas; afirmações obsoletas superadas por fontes novas; páginas órfãs (sem links de entrada); conceitos mencionados sem página própria; cross-referências faltando; lacunas que uma busca web poderia preencher. Sugerir novas fontes e perguntas de investigação. Registrar em `log.md`.

## 🗒️ log.md
Append-only, um bloco por evento, prefixo consistente e parseável:

```markdown
## [2026-08-16] ingest | Título da Fonte
- Páginas criadas: [[X]], [[Y]] | atualizadas: [[Z]]
- Notas: divergência registrada em [[W]]
```

Checar últimos eventos: `grep "^## \[" log.md | tail -10`

## 🚫 Restrições
* **Nunca editar nada em `raw/`** — fontes são imutáveis.
* **Nunca armazenar chaves de API, senhas ou tokens** em nenhum arquivo (herdado do projeto pai).
* Não inventar dados de mercado ou resultados de backtest — se não há fonte, marcar como *hipótese* ou *a verificar*.
* Não apagar páginas sem confirmação do usuário; marcar `status: em-revisao` quando o conteúdo for questionável.
