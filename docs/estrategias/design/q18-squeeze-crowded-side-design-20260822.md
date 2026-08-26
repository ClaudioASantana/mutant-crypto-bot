# Q18 — squeeze do lado crowded — design pré-registrado — 2026-08-22

> Status: **documento de design apenas**. Esta hipótese **não será executada
> hoje**.
>
> ⚠️ **Aviso metodológico central:** a hipótese desta rodada nasceu de um achado
> incidental do rerun longo da Q16. Portanto, a amostra 2020-09-01 → 2026-08-21
> da Camada A histórica está **contaminada para validação**: ela pode sugerir a
> hipótese, mas não pode confirmá-la honestamente.

---

## 1. Por que esta rodada existe

O rerun longo da Q16 mostrou um comportamento sugestivo no braço E2:

- crowded short continuation (hipótese pedida) **falhou**;
- mas o retorno forward veio fortemente **positivo** em 24h (`+83,6bp`,
  `t=2,96`), sugerindo que o lado crowded pode estar sendo **espremido**
  (squeeze) em vez de simplesmente continuar.

Isso é interessante o suficiente para ser preservado como hipótese formal.

## 2. Hipótese desta rodada

### E1 — crowded long squeeze

> Quando o BTC entra em estado de **crowded long buildup**
> (preço subindo + OI crescendo forte + funding positivo + premium rich), o
> retorno forward tende a ser **mais negativo** que o controle — não por unwind
> lento, mas por squeeze contra o lado crowded.

### E2 — crowded short squeeze

> Quando o BTC entra em estado de **crowded short buildup**
> (preço caindo + OI crescendo forte + funding negativo + premium cheap), o
> retorno forward tende a ser **mais positivo** que o controle — squeeze de alta
> contra o lado crowded.

## 3. Definição do evento

**Idêntica à Q16**. Nada muda no evento; muda apenas o sinal pedido.

- BTCUSDT M15
- `ret_lb` = retorno trailing de `LOOKBACK_BARS = 16` velas (4h)
- `oi_pct` = percentil causal do `oi_chg` na janela de `PCT_WINDOW = 384`
- `prem_pct` = percentil causal do `premium_rel` na mesma janela

### E1 — crowded long
- `ret_lb > 0`
- `oi_pct >= 0.90`
- funding último conhecido `> 0`
- `prem_pct >= 0.75`

### E2 — crowded short
- `ret_lb < 0`
- `oi_pct >= 0.90`
- funding último conhecido `< 0`
- `prem_pct <= 0.25`

## 4. Sinal pedido desta hipótese

- `SIGN_REQUESTED["E1"] = -1`
- `SIGN_REQUESTED["E2"] = +1`

Ou seja: exatamente o espelho da Q16.

## 5. Custos, horizontes e guardrails

Mantidos **sem alteração** da Q16 rerun longa:
- custo `10bp round-trip`
- horizontes `4h / 8h (primário) / 24h`
- `n_indep >= 20`
- concentração do maior episódio `< 50%`
- `>= 2/3` das 6 fatias confirmando
- coerência cross-horizonte obrigatória

## 6. Amostra contaminada — não pode validar a própria hipótese

Este é o ponto principal do documento.

A hipótese Q18 nasce de uma observação feita **dentro** da mesma janela de
Camada A histórica que seria usada para avaliá-la (`BTCUSDT_metrics_long.csv`,
2020-09-01 → 2026-08-21). Portanto:

- essa janela pode servir para **gerar** a hipótese;
- mas **não** pode servir para **confirmá-la**.

Se rodássemos hoje a Q18 na mesma amostra, estaríamos apenas flipando o sinal
pós-hoc em um resultado já visto — um caso clássico de p-hacking. Mesmo que os
guardrails passassem, isso **não contaria como evidência**.

## 7. Gatilho objetivo de execução futura

Q18 só pode ser executada honestamente quando houver **dado genuinamente novo**.
Qualquer um dos gatilhos abaixo é suficiente:

1. **Camada B madura**
   - a série própria (`oi_funding_ratios.csv`) acumula profundidade suficiente
     para entregar `n_indep >= 20` no primário 8h;
   - previsão operacional atual: ~2026-10-21, conforme
     `scripts/check_snapshot_health.py`.

2. **Camada A realmente nova**
   - meses futuros passam a existir no Binance Vision monthly **além** de
     2026-08;
   - a amostra nova é testada separadamente, sem reusar a janela que gerou a
     hipótese.

## 8. Veredito pré-registrado (para quando houver dado novo)

### E1 — crowded long squeeze
- Falha / Inconcluso / Sobrevive com a mesma lógica da Q16, mas com sinal
  pedido negativo.

### E2 — crowded short squeeze
- Falha / Inconcluso / Sobrevive com a mesma lógica da Q16, mas com sinal
  pedido positivo.

## 9. O que este documento faz hoje

- **preserva** a hipótese para não ser esquecida;
- **impede** que ela seja testada de forma desonesta na mesma amostra;
- mantém a disciplina da trilha: hipótese nova só pode ser promovida por dado
  novo.

Nada vai para paper/live a partir desta rodada.

## 10. Atualização 2026-08-23 — refinamento Q24

A **Q24** refinou esta hipótese adicionando **confluência total**
(preço + OI + funding em sinal e magnitude + premium + taker flow extremos no
mesmo lado) e mediu a **viabilidade de frequência** na Camada A histórica (sem
retorno forward):

- E1 (crowded long confluente): **~8,1 meses** de amostra nova para `n_indep>=20`;
- E2 (crowded short confluente): **~16,7 meses**;

Ver `q24-confluencia-crowded-squeeze-design-20260823.md` e
`../../backend/scripts/check_q24_fresh_sample_ready.py`.

A régua de execução futura aqui continua valendo: só dado **novo** decide o
veredito; a janela `<= 2026-08-21` nunca conta como evidência.
