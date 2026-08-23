# Q17 — taker flow imbalance — design pré-registrado — 2026-08-22

> Status: **documento de design**. Nada implementado como estratégia, nada em
> paper/live.

---

## 1. Por que esta rodada existe

A Q16 (incluindo o rerun longo com ~6 anos de Binance Vision) reprovou a
hipótese de **OI crowded continuation**. Isso encerra, com amostra suficiente,
a leitura de que preço + OI + funding + premium seriam suficientes para gerar
um edge líquido robusto nesse formato.

Mas o mesmo dataset longo (`BTCUSDT_metrics_long.csv`) já contém outra classe de
informação que **ainda não foi usada como driver de evento** em nenhum dos
experimentos anteriores: `sum_taker_long_short_vol_ratio` — o desequilíbrio de
fluxo agressivo comprador/vendedor.

Esta rodada existe para testar uma hipótese nova e limpa:

> extremos de taker flow, sozinhos, já carregam informação suficiente para
> continuação curta do preço acima do controle?

A vantagem metodológica desta frente é clara: ao contrário da leitura de
"squeeze do lado crowded" que nasceu *depois* de olhar a Q16, aqui estamos
usando uma variável do dataset que permaneceu ociosa até agora. Isso é um teste
novo de verdade, não uma releitura pós-hoc da mesma hipótese.

## 2. Hipótese desta rodada

### E1 — taker buy imbalance extremo

> Quando o desequilíbrio de fluxo agressivo comprador (`taker_ls`) está em
> percentil extremo alto, o retorno forward tende a ser **mais positivo** que o
> controle incondicional (continuação de alta).

### E2 — taker sell imbalance extremo

> Quando o desequilíbrio de fluxo agressivo vendedor (`taker_ls`) está em
> percentil extremo baixo, o retorno forward tende a ser **mais negativo** que o
> controle incondicional (continuação de baixa).

## 3. Definição do evento

Timeframe e causalidade seguem o padrão da trilha:

- BTCUSDT M15
- `taker_ls` = `sum_taker_long_short_vol_ratio` alinhado causalmente ao grid M15
- `taker_pct` = percentil causal de `taker_ls` na janela rolante de
  `PCT_WINDOW = 384` velas (4 dias)

### E1 — fluxo comprador extremo
- `taker_pct >= 0.90`

### E2 — fluxo vendedor extremo
- `taker_pct <= 0.10`

### O que esta rodada deliberadamente NÃO exige
- não exige `ret_lb > 0` nem `< 0`
- não exige confirmação de OI
- não exige funding positivo/negativo
- não exige premium rich/cheap

Isso é intencional: o objetivo é isolar a informação do fluxo agressivo em vez
 de reembalar o mesmo evento já reprovado pela Q16.

## 4. Custos

- `10bp round-trip` — mesma régua direcional de BTC usada em Q13/Q14/Q15/Q16.

## 5. Horizontes e primário

- **4h**
- **8h** (primário)
- **24h**

## 6. Regras causais

- `taker_pct` usa apenas a janela rolante até o candle fechado em `t`
- o alinhamento `taker_ls -> M15` é por `merge_asof(direction="backward")`
- retornos forward (4h/8h/24h) só medem o desfecho
- nenhum threshold será re-tunado depois do resultado

## 7. Guardrails

Mesma disciplina da Q16 rerun longa:

1. **Coerência cross-horizonte obrigatória:** o `marginal_net` precisa ter o
   mesmo sinal da hipótese em **4h E 8h E 24h**.
2. **Amostra independente:** `n_indep >= 20` no primário 8h.
3. **Magnitude:** `|marginal_net| > 10bp` no primário.
4. **Episódios:** concentração do maior episódio `< 50%` dos eventos brutos.
5. **Fatias:** `>= 2/3` das 6 fatias temporais com `marginal_net` no sentido da
   hipótese.
6. **Dominância de episódio:** reportar retorno médio por episódio no primário.
7. **Se `n_indep < 20`: o veredito é INCONCLUSO**, não aprovado.

## 8. Fonte de dados

- `BTCUSDT_metrics_long.csv` (~6 anos, Binance Vision `daily/metrics`) para
  `taker_ls`
- Binance Vision `monthly` + API do mês corrente para klines/premium/funding
  (mesma engenharia de ingestão já validada na Q16 rerun longa)

## 9. Veredito pré-registrado

### E1 — taker buy imbalance extremo
- **Falha** se qualquer guardrail não passar.
- **INCONCLUSO** se `n_indep < 20`.
- **Sobrevive (candidato Camada A)** somente com TODOS os guardrails passando
  e coerência em 4h/8h/24h.

### E2 — taker sell imbalance extremo
- Mesma lógica, espelhada.

## 10. O que NÃO significa sobreviver

Mesmo sobrevivendo na Camada A:
- é só um **candidato**, não um edge;
- exige revalidação na série própria (Camada B) antes de qualquer promoção;
- nada vai para paper/live nesta rodada.

## 11. Consequências possíveis

Se Q17 falhar:
- reforça a leitura de que preço/funding/basis/OI público **e também taker flow
  público** não bastam, nesse setup, para gerar edge líquido robusto;
- aumenta o peso de hipóteses com **Camada B independente** ou outro
  venue/universo.

Se Q17 sobreviver:
- vira o primeiro candidato real dessa família;
- mas segue bloqueado para paper/live até repetir na Camada B.
