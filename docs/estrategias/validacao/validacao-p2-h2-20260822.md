# Validação P2 — H2 (breakout de regime) — 2026-08-22

> Status: **H2 reprovada**. O novo sinal de continuação (Donchian 55 + ADX +
> banda de ATR) não passou no walk-forward de 90 dias em M15 nem H1.

## 1. Hipótese testada

> "Breakout de regime em M15/H1 com filtro de volatilidade sobrevive melhor que
> o zoo de reversão refutado em P1/H1."

Estratégia implementada como sinal novo, não wrapper:

- canal Donchian de 55 velas;
- regime de tendência `ADX_14 >= 25`;
- ATR no percentil `[0.40, 0.90]` da janela (nem morto, nem extremo);
- gatilho só em **breakout fresco**, comparando o fechamento atual com o canal
  calculado até a vela anterior (anti-lookahead);
- saída no harness por `TP = 3x ATR`, `SL = 1.5x ATR`, `time stop = 24h`.

Fonte: `backend/scripts/experiment_h2_breakout.py`.

## 2. Protocolo

Mesmo protocolo usado para refutar P1:

- BTCUSDT;
- timeframes: M15 e H1;
- 90 dias de histórico;
- 8 janelas OOS de 7 dias, passo 7 dias, warmup 30 dias;
- custos: `fee_rate=0.0004`, `slippage_bps=1.0`;
- critério de admissão: **≥5/8 janelas positivas + PnL agregado > 0 + PF > 1,3**.

## 3. Resultado

| TF | folds+ | PnL OOS | PF OOS | trades | média/fold | Veredito |
|---|---:|---:|---:|---:|---:|---|
| M15 | 3/8 | −77,21 | 0,12 | 48 | 6,0 | ❌ reprovada |
| H1 | 2/8 | +1,31 | 1,13 | 4 | 0,5 | ❌ reprovada |

## 4. Leitura

1. **M15 continua caro demais para um breakout mediano.** A estratégia até opera
   com frequência razoável (48 trades em 8 folds), mas o payoff líquido não
   cobre custos e stops: PF 0,12 e PnL agregado fortemente negativo.
2. **H1 melhora a direção do PnL, mas some com a amostra.** O agregado ficou
   levemente positivo (+1,31), porém em apenas 4 trades no período inteiro
   (0,5/fold) e PF 1,13 — abaixo do mínimo de 1,3 e muito longe da exigência de
   5/8 janelas positivas.
3. **O desenho do sinal novo foi mais honesto que o zoo anterior**, porque já
   nasceu com anti-lookahead no canal e filtro de regime/ATR embutidos. Ainda
   assim, não há evidência de edge robusto.
4. O padrão se repete: quando sobe o timeframe e a seletividade, a estratégia
   deixa de perder muito, mas também quase deixa de operar. Quando ganha
   frequência (M15), perde qualidade líquida.

## 5. Veredito

**H2 está reprovada.** O breakout de regime não atende o critério mínimo de
admissão em nenhum timeframe:

- M15 falha em PnL, PF e janelas positivas;
- H1 falha em PF e janelas positivas, além de ter amostra insuficiente.

Portanto, **nenhuma hipótese P2 validou edge até aqui**:

- H1: filtros não salvam um sinal sem edge;
- H2: sinal novo de continuação também não sobrevive ao walk-forward.

## 6. Próximo passo

**Nada vai para paper/live.**

H3 (funding rate como filtro direcional) só faz sentido como pesquisa adicional
se quisermos testar uma hipótese de microestrutura externa. Mas, dado que H2
não sobreviveu nem como base, H3 não deve ser interpretada como "última milha"
para promoção operacional — seria uma nova frente de research, ainda sem direito
a paper/live até repetir toda a régua de validação.
