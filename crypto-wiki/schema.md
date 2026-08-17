# Schema da Crypto Wiki — Mutant Crypto Bot

Este arquivo define **como** as ferramentas de IA (Claude Code) devem manter e consultar o conhecimento sobre o `mutant-crypto-bot`. Ele é o "manual de instruções" — siga estas regras em todas as sessões.

## Propósito

A wiki é o **conhecimento compilado** do projeto: estratégias, resultados de backtest, regras de gestão de risco e decisões de arquitetura. Ela não é um backup de código — é o *porquê* por trás de cada trade e cada linha.

## Estrutura

```
crypto-wiki/
├── index.md           # Catálogo central (atualizado a cada ingest)
├── log.md             # Histórico cronológico (append-only)
├── schema.md          # ESTE arquivo — as regras para a IA
├── raw/               # Fontes brutas imutáveis (PDFs, imagens, clips)
└── wiki/              # O conhecimento "compilado" (escrito pela IA)
    ├── estrategias/   # Ex: padroes-de-3-velas.md
    ├── conceitos/     # Conceitos fundamentais (RR, volatility, etc.)
    ├── indicadores/   # RSI, ATR, EMA, Heikin Ashi
    ├── analises/      # Backtests e análises de mercado
    └── fontes/        # Referências e proveniência de cada fonte
```

## Regras de Manutenção (para a IA)

1. **SEMPRE consulte a wiki antes de analisar estratégias ou tomar decisões de trade.** Se houver um arquivo em `wiki/estrategias/` relevante, leia-o primeiro e cite-o.
2. **Nunca edite `raw/`** — é a fonte de verdade imutável. Leia de lá, escreva em `wiki/`.
3. **Toda ingestão de nova fonte** (artigo, resultado de backtest, descoberta) segue este fluxo:
   a. Leia a fonte por completo.
   b. Escreva/atualize a página correspondente em `wiki/` (com metadados em frontmatter YAML: `title`, `source`, `created`, `tags`).
   c. Atualize `index.md` (link + resumo de uma linha).
   d. Adicione uma entrada em `log.md` no formato `## [AAAA-MM-DD] ingest | Título`.
4. **Contradições importam.** Se um novo dado contradiz uma página existente (ex: um backtest novo derruba um WR que estava documentado), NÃO apague o dado antigo — registre a contradição na página e adicione a nova evidência lado a lado.
5. **Orfãos e links:** Toda página deve ter pelo menos um link de entrada. Use `[[nome-da-pagina]]` para referências cruzadas.

## Fluxos de Trabalho

| Situação | Ação da IA |
|---|---|
| Novo backtest rodado | Resumo do resultado → atualizar página da estratégia + `log.md` + `index.md` |
| Pergunta sobre trade | Buscar justificativa em `wiki/`, citar a regra técnica encontrada |
| Dúvida sobre arquitetura | Buscar em `wiki/conceitos/` e `wiki/engine/` |
| Contradição detectada | Registrar a contradição na página afetada, preservando ambos os lados |
| Lint periódico | Verificar páginas órfãs, claims desatualizados, links quebrados |

## Convenções

- Todas as páginas da wiki em **português**.
- Frontmatter YAML em todas as páginas: `title`, `source` (se houver), `created` (YYYY-MM-DD), `tags`.
- Números e estatísticas SEMPRE com a unidade e o contexto (ativo, timeframe, período, modelo de taxas).
- Cite a proveniência: `source: "URL ou caminho do arquivo em raw/"`.

---

*Este schema evolui junto com o projeto. Quando descobrir algo que melhora a manutenção, atualize este arquivo e registre a mudança em `log.md`.*