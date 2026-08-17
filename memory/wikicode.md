---
name: 3-candle-pattern-wiki
description: Filosofia operacional dos padrões de 3 candles documentada na wiki do projeto.
metadata:
  type: project
---
A wiki do projeto ([`crypto-wiki/wiki/estrategias/padroes-de-3-velas.md`](../crypto-wiki/wiki/estrategias/padroes-de-3-velas.md)) documenta a filosofia operacional dos padrões de 3 candles.

**Fundamentos:**
- A Regra do Ponto Médio valida reversões: a terceira vela deve fechar além de 50% do corpo da primeira.
- Os padrões de 3 velas são raros e de alta confirmação (ex: Three White Soldiers ~82%, Morning Star ~78%).
- O **3 Bar Play** (continuação) tem 3 fases: Ignição (volume alto), Descanso (volume baixo), Expansão (rompimento).
- **Heikin Ashi vs Tradicional:** para stop curto na vela 2 → Heikin Ashi (filtra ruído); para stop estrutural na vela 1 → velas tradicionais (zero-lag, alvos longos 1:3).
- A wiki insiste que os padrões **nunca devem ser operados isoladamente** — exigem confluência de volume, localização e timeframe.

Vincular com [[strategy-philosophy]] para as regras de confluência implementadas no código do bot.
