# Validação Q3 — post-liquidation fade (event study) — 2026-08-22

> Status: **hipótese primária não sobreviveu à fase de event study**.
> Nenhuma estratégia foi criada. Nada vai para paper/live.

## 1. O que foi testado

Conforme o design pré-registrado em
[ q3-liquidation-fade-design-20260822.md](q3-liquidation-fade-design-20260822.md),
rodamos um **event study** antes de transformar qualquer ideia em regra de
trading.

Evento primário (pré-registrado):
- **Evento B — `wick_reclaim`**: pavio inferior ≥ 2×ATR(14) e fechamento bullish,
  medido em **BTCUSDT M15**, com retorno forward de **4h** a partir do close do
  candle do evento.

Eventos auxiliares:
- **Evento A — `climatic_drop`**: vela bearish com corpo ≥ 2,5×ATR(14) e volume
  ≥ 2×média(50).
- H1 como TF secundário.

Custos: 10bp round-trip (`fee 4bp + slippage 1bp` por ponta).
Controle: retorno forward incondicional de todas as velas na mesma janela.

## 2. Dados e limitação material

Fontes públicas Binance Futures usadas:
- `fapi/v1/klines` — OHLCV M15/H1;
- `fapi/v1/fundingRate` — funding histórico.

**Não** havia disponível anonimamente nesta rodada:
- histórico de **open interest** (endpoint exige API key);
- dados oficiais de **liquidação**.

Logo, o estudo mediu **proxies de flush por price action + volume**, não
"liquidação forçada" observada diretamente. Isso limita a atribuição causal,
mas ainda permite responder se existe um efeito estatístico útil pós-dislocação.

## 3. Resultado

### M15

| Evento | 1h net | 4h net | 8h net | 24h net | n |
|---|---:|---:|---:|---:|---:|
| Controle incondicional | ~−0,0010 | ~−0,0009 | ~−0,0009 | ~−0,0007 | 8,6k+ |
| A — climatic_drop | −0,0038 | **−0,0047** | −0,0035 | −0,0030 | 17 |
| B — wick_reclaim | −0,0028 | **−0,0026** | −0,0041 | +0,0087 | 1 |

Leitura:
- **Evento A foi ativamente ruim** em M15 — comprar o fechamento de uma queda
  climática perde para o controle em todos os horizontes.
- **Evento B falhou por amostra insuficiente**: apareceu só **1** vez em 90 dias
  com a definição pré-registrada (2×ATR). Não dá para validar nem refutar com
  robustez estatística, mas pela régua pré-definida a hipótese **falha**.

### H1

| Evento | 1h net | 4h net | 8h net | 24h net | n |
|---|---:|---:|---:|---:|---:|
| A — climatic_drop | +0,0044 | −0,0029 | +0,0081 | −0,0019 | 4 |
| B — wick_reclaim | — | — | — | — | 0 |

Leitura:
- amostra pequena demais para concluir qualquer coisa;
- H1 não resgata a hipótese nesta rodada.

## 4. Sensibilidade exploratória (não pré-registrada)

Para entender se o Evento B morreu por "definição apertada demais" ou por
inexistência de efeito, medimos **exploratoriamente** M15/4h com thresholds
mais soltos de pavio:

| Definição exploratória de wick | n | retorno net médio 4h |
|---|---:|---:|
| `wick >= 1.0 × ATR` | 49 | **+0,0007** |
| `wick >= 1.5 × ATR` | 11 | −0,0021 |
| `wick >= 2.0 × ATR` | 1 | −0,0026 |

Leitura:
- existe um **sinal fraco exploratório** quando o pavio é definido de forma bem
  mais frouxa (`1.0×ATR`), mas o efeito é pequeno (~7bp líquidos em 4h) e não
  foi pré-registrado;
- como o custo round-trip já é 10bp, isso é um efeito muito marginal para virar
  regra operacional sem confirmação mais forte.

## 5. Veredito

A regra pré-registrada era explícita:
> Evento B × 4h em M15 falha se `n < 20`, ou net ≤ 0, ou net ≤ controle net.

Resultado observado:
- `n = 1` → **falha por amostra insuficiente**.

Portanto, **a hipótese primária Q3 não sobreviveu ao event study**.

Além disso:
- o proxy alternativo A (`climatic_drop`) parece ruim em M15;
- a sensibilidade exploratória sugere um possível efeito pequeno em wick mais
  frouxo, mas insuficiente para promover qualquer estratégia.

## 6. Conclusão operacional

**Nada vai para paper/live.**

A frente Q3 entregou um aprendizado útil:
- não encontramos evidência robusta de um "flush and fade" simples e utilizável
  com proxies públicos de OHLCV + funding;
- se essa hipótese for reaberta no futuro, o próximo passo correto não é mudar
  mais parâmetros, e sim **melhorar os dados** (open interest/liquidações reais)
  antes de tentar outra iteração.
