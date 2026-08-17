# CLAUDE.md — Crypto Wiki do Mutant Crypto Bot

Esta pasta é uma **wiki de conhecimento** mantida por assistentes de IA (Claude Code). É um "artefato composto": o conhecimento é compilado uma vez e mantido atualizado, nunca re-derivado do zero.

## Instruções rápidas

1. **Antes de analisar estratégias, backtests ou decisões de trade deste bot, CONSULTE esta wiki.** Procure a página relevante em `wiki/` e cite-a.
2. **Leia e siga o esquema:** todas as regras detalhadas de manutenção estão em **[`schema.md`](schema.md)** — índice, log, frontmatter, tratamento de contradições, fluxos de ingest/lint/query.
3. **Nunca edite `raw/`** (fonte de verdade imutável). Escreva apenas em `wiki/`.
4. Ao ingerir uma nova fonte ou rodar um backtest, **atualize `index.md` e `log.md`** conforme o fluxo do schema.

## Estrutura

```
crypto-wiki/
├── CLAUDE.md    # Este arquivo (instruções rápidas)
├── schema.md    # Regras de manutenção COMPLETAS
├── index.md     # Catálogo de páginas
├── log.md       # Histórico cronológico append-only
├── raw/         # Fontes brutas imutáveis
├── sources/     # Fontes adicionais em processamento
└── wiki/        # Conhecimento compilado (escrito pela IA)
    ├── estrategias/
    ├── conceitos/
    ├── indicadores/
    ├── analises/
    └── fontes/
```

Todas as páginas devem estar em **português**, com frontmatter YAML e links `[[wiki-link]]`.