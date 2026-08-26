# Q16 — OI crowded continuation — design pré-registrado — 2026-08-22

> Status: **documento de design**. Nada implementado como estratégia, nada em
> paper/live.
>
> ⚠️ **Aviso anti-snooping:** esta rodada é um **flip test**. Ela nasce de uma
> leitura **pós-hoc** da Q15: lá a hipótese era unwind/reversão, e o resultado
> no primário veio na direção oposta (continuação). O risco de "perseguir o
> último vencedor" é real e conhecido (lição da Q12). Por isso, esta rodada
> impõe condições **mais** rígidas, não mais frouxas.

---

## 1. Por que esta rodada existe

A Q15 (Camada A, ~30 dias de OI público) testou a hipótese de:

> crowded long buildup → reversão/unwind

e o resultado no primário 8h foi o **oposto**:
- `marginal_net = +0,00928` (**+92,8bp**, mais positivo que o controle, não mais negativo).

Além disso:
- a magnitude em 4h/8h/24h foi consistentemente positiva;
- mas `n_indep` ficou baixo em todos os horizontes (14/11/8);
- e a repetibilidade por fatias **falhou** (só 1/3 fatias na direção da hipótese original).

Portanto, o que a Q15 registrou foi:
- um **indício** de que OI carrega informação;
- mas com a **direção** possivelmente invertida em relação ao que prevíamos;
- e sem amostra independente suficiente para decidir.

Q16 existe para testar essa leitura alternativa de forma **pré-registrada**,
antes de qualquer promoção — com os mesmos parâmetros da Q15, sem re-tuning.

## 2. Hipótese desta rodada

> Quando o BTC entra em estado de **crowded long buildup**
> (preço subindo + OI crescendo forte + funding positivo + premium rich),
> o retorno forward tende a ser **mais positivo** que o controle incondicional
> — ou seja, continuação de crowding, e não unwind/reversão.

Lado espelhado (todas as leituras invertidas):

> Quando o BTC entra em **crowded short buildup**
> (preço caindo + OI crescendo forte + funding negativo + premium cheap),
> o retorno forward tende a ser **mais negativo** que o controle.

## 3. Definição do evento — idêntica à Q15, sem alteração

Mesmos parâmetros, mesmo timeframe, mesma causalidade:

- BTCUSDT M15
- `ret_lb` = retorno trailing de `LOOKBACK_BARS = 16` velas (4h)
- `oi_pct` = percentil causal do `oi_chg` na janela rolante de `PCT_WINDOW = 384` velas
  - onde `oi_chg = oi_t / oi_{t-16} - 1`
- `prem_pct` = percentil causal do `premium_rel` na mesma janela de 384 velas

### E1 — crowded long continuation
- `ret_lb > 0`
- `oi_pct >= 0.90`
- funding último conhecido `> 0`
- `prem_pct >= 0.75`

### E2 — crowded short continuation
- `ret_lb < 0`
- `oi_pct >= 0.90`
- funding último conhecido `< 0`
- `prem_pct <= 0.25`

## 4. Custos

- `10bp round-trip` — sinal direcional BTC, mesma régua da Q15/Q14/Q13.

## 5. Horizontes e primário

- **4h**
- **8h** (primário)
- **24h**

## 6. Regras causais

- `oi_pct` e `prem_pct` usam apenas dados até o candle fechado;
- funding usa o último valor conhecido até `t`;
- os retornos futuros (4h/8h/24h) apenas medem o resultado;
- nada é re-tunado depois de olhar o resultado desta rodada.

## 7. Guardrails (mais rígidos que Q15, devido ao flip)

1. **Coerência cross-horizonte obrigatória:** o `marginal_net` precisa ter o
   mesmo sinal da hipótese em **4h E 8h E 24h** — não basta o primário.
2. **Amostra independente:** `n_indep >= 20` no primário 8h.
3. **Magnitude:** `|marginal_net| > 10bp` no primário (custo).
4. **Episódios:** concentração do maior episódio `< 50%` dos eventos brutos.
5. **Fatias:** `>= 2/3` das 3 fatias temporais com `marginal_net` no sentido da
   hipótese.
6. **Dominância de episódio:** reportar retorno médio por episódio no primário;
   se um único episódio concentrar o efeito, isso conta contra.
7. **Se `n_indep < 20`: o veredito é INCONCLUSO**, não aprovado. A camada A é
   exploratória; a camada B (série própria acumulada) é quem decide.

## 8. Fonte de dados — mesmas limitações da Q15

- Camada A: endpoints públicos de OI/ratios paginados por `endTime`, ≈30 dias
- Camada B: nossa série própria (`oi_funding_ratios.csv`), ainda em acumulação

## 9. Veredito pré-registrado

### E1 — crowded long continuation
- **Falha** se qualquer guardrail não passar.
- **INCONCLUSO** se `n_indep < 20`.
- **Sobrevive (candidato Camada A)** somente com TODOS os guardrails passando
  E coerência em 4h/8h/24h E `>= 2/3` fatias confirmando.

### E2 — crowded short continuation
- Mesma lógica, espelhada.

## 10. O que NÃO significa sobreviver

Mesmo sobrevivendo na Camada A:
- é só um **candidato**, não um edge;
- exige revalidação completa na série própria acumulada (Camada B);
- nada vai para paper/live nesta rodada.

## 11. Consequências possíveis

Se E1/E2 falharem ou ficarem inconclusos:
- a leitura pós-hoc da Q15 está oficialmente desfavorável;
- e a família OI no formato atual pode ser encerrada para Camada A;
- o caminho restante seria Camada B com série própria, ou outra classe de
  informação.