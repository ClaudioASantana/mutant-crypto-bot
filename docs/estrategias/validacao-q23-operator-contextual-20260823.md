# Validação Q23 — operador contextual (pullback em tendência + checklist) — 2026-08-23

> Pré-registro: [q23-operator-contextual-pullback-design-20260823.md](q23-operator-contextual-pullback-design-20260823.md) (seção 13 congela os números)
> Script: `backend/scripts/experiment_q23_operator_contextual.py`
> Task de execução: `bi5wkhdln` (exit code 0, output completo lido)

## Veredito final

**❌ REPROVADA — nem CHECKLIST nem VETO superaram a BASE**

E há um achado mais importante do que o "não passou": **o checklist quase não
filtrou nada**. 99,9% dos candidatos do setup-base já nasceram com score ≥ 6
(ENTER). O teste da hipótese central — "o checklist separa entradas boas de
ruins" — ficou **comprometido pelo desenho**, não decidido pelo mercado.

---

## Dataset

- `315.557` velas 15m spot BTCUSDT, `2017-08-17 04:00 → 2026-08-23 01:30`.

## Benchmark — buy & hold (mesmo período)

| Métrica | Valor |
|---|---|
| CAGR | **+37,91%** |
| Vol anualizada | +73,99% |
| Sharpe | +2,41 |
| Sortino | +2,93 |
| Total | +1.711,84% |
| Max drawdown | **83,97%** |
| Duração do drawdown | 1.079 dias |

## Processo (distribuição do checklist sobre os candidatos do setup-base)

| Métrica | Valor |
|---|---|
| Candidatos do setup-base | 1.665 |
| Score médio dos candidatos | **8,20** (faixa possível: −2 a +10) |
| ENTER (score ≥ 6) | **99,9%** |
| WAIT (3 a 5) | 0,1% |
| VETO (≤ 2) | 0,0% |

## Modos testados

| Métrica | BASE | CHECKLIST (score≥6) | VETO (score≥3) |
|---|---|---|---|
| CAGR líquido | -11,29% | -11,39% | -11,29% |
| CAGR bruto | +6,71% | +6,58% | +6,71% |
| Max drawdown | 66,94% | 67,28% | 66,94% |
| Duração do drawdown | 3.097 dias | 3.097 dias | 3.097 dias |
| Tempo em mercado | 4,2% | 4,2% | 4,2% |
| Flips | 3.330 | 3.328 | 3.330 |
| gross − net (pp) | 18,00 | 17,97 | 18,00 |
| Trades | 1.665 | 1.664 | 1.665 |
| avg_trade_gross | +0,0413% | +0,0407% | +0,0413% |
| avg_trade_net | -0,0587% | -0,0593% | -0,0587% |
| win_rate_gross | 27,0% | 27,0% | 27,0% |
| payoff_gross | 3,14 | 3,14 | 3,14 |
| Metades positivas | 0/2 | 0/2 | 0/2 |
| Ciclos positivos | 0/3 | 0/3 | 0/3 |

**CHECKLIST removeu apenas 1 trade de 1.665. VETO removeu 0.** Os três modos
são, na prática, a mesma curva.

## Veredito codificado (pré-registrado, seção 13.9)

| Variante | processo | custo_não_piora | pelo_menos_um | Resultado |
|---|---|---|---|---|
| CHECKLIST | ❌ False | ✅ True | ❌ False | ❌ NÃO SUPERA |
| VETO | ❌ False | ✅ True | ✅ True (empate técnico) | ❌ NÃO SUPERA |

`>>> Q23 classe operador-contextual: ❌ FALHA`

---

## Leitura honesta do resultado

### 1. O achado mais importante: o checklist não teve o que discriminar

A hipótese da Q23 era: *"um score de contexto separa entradas boas de
ruins melhor que o setup-base sozinho."* Para isso valer a pena testar, o
score precisa **variar** entre os candidatos. Aqui não variou: 99,9% deles
já nasceram em ENTER.

**Causa raiz, não coincidência:** o próprio setup-base já exige, por
definição, boa parte do que o checklist pontua:

| Exigência do setup-base (seção 13.3) | Item do checklist que ela garante |
|---|---|
| `ema20 > ema50` e `close > ema20` | A1 (+1) e A2 (+1) |
| pullback recente até `bb_mid` | B2 (+1) |
| retomada de `bb_mid` | B1 (+1) |
| `macd_hist > 0` | C1 (+1) |

Isso já soma **5 pontos garantidos** em todo candidato, a **1 ponto** do
limiar de ENTER (6). Bastava mais um item qualquer bater — e quase sempre
batia (A3 tendência de regime, C2 momentum subindo, C3 RSI em faixa
"normal" de retomada são todos prováveis justamente no momento em que o
setup dispara) — para o score estourar o teto.

**Lição de desenho:** um checklist que reusa, com pesos positivos, os
mesmos ingredientes que já definem o gatilho de entrada não está testando
"contexto adicional" — está testando **redundância**. Para o checklist ter
poder de discriminação de verdade, ele precisa carregar informação
**ortogonal** ao que o setup-base já exige, não uma paráfrase pontuada dele.

### 2. Mesmo sem o problema do checklist, o setup-base sozinho já falha duro

Isso não é só um problema metodológico do score — o **BASE** (setup-base
puro, sem gate nenhum) já reprova com folga:

- **Bruto mal supera zero relativo ao B&H**: `CAGR_gross = +6,71%` contra
  `+37,91%` do buy-and-hold — antes de qualquer custo, o setup já entrega
  uma fração pequena do que o mercado deu de graça.
- **Depois do custo, fica negativo**: `CAGR_net = -11,29%`, apesar de o
  custo por trade ser moderado (`gross-net = 18,00pp` sobre 1.665 trades,
  bem menos hiper-rotativo que a Q22).
- **Não preserva nada**: `MaxDD 66,94%` continua próximo do `83,97%` do
  B&H — não há preservação de capital, e por sinal o tempo em mercado é
  só `4,2%`, então o drawdown vem majoritariamente do próprio B&H "vazando"
  pelas poucas vezes em que a estratégia fica exposta em queda.
- **Nenhuma robustez temporal**: `0/2` metades e `0/3` ciclos positivos —
  o resultado é negativo em praticamente todo período, não é dominado por
  um trecho ruim isolado.
- **Win rate baixo com payoff alto**: `27,0%` de acerto e `payoff 3,14`
  parecem "estilo trend-following" (poucos vencedores grandes cobrindo
  muitos perdedores pequenos), mas na prática **não cobre nem o custo**.

Ou seja: mesmo que o checklist tivesse discriminado de verdade, não havia
"entradas boas" suficientes para separar — o próprio pool de candidatos do
setup-base já não tem qualidade média que sustente uma estratégia.

### 3. Comparação com a Q22

A Q23 usa essencialmente a mesma família de sinal da variante P2 da Q22
(pullback em tendência + reclaim de `bb_mid` + MACD), mas com saída um
pouco menos "gatilho-feliz" (removeu a saída por exaustão isolada e o
requisito de subida por 2 barras na entrada). O resultado é consistente
com a Q22: bruto fraco, e aqui o número de flips caiu bastante (`3.330` vs
`15.794`/`20.040` da Q22), mas ainda assim não sobrou edge líquido depois
do custo.

**Conclusão cruzada:** já são duas formulações de pullback em BB+MACD em
15m (Q22-P2 e Q23-BASE) que reprovam — uma por hiper-rotação destrutiva,
outra por bruto fraco demais mesmo com rotação moderada.

---

## O que isso NÃO significa

- Não significa que "checklist contextual" como ideia geral está morta —
  significa que **esta implementação específica** teve um problema de
  desenho (redundância score×setup) que não deu ao checklist chance real
  de mostrar o que poderia fazer.
- Não autoriza reabrir esta mesma amostra para re-tunar os pesos do
  checklist ou os limiares ENTER/WAIT/VETO — isso seria p-hacking.
- Não muda o fato de que nada vai para paper/live.

## Lição para uma eventual Q24 (se a trilha decidir seguir a família)

Se a ideia de "operador contextual" for retomada, o desenho seguinte
precisaria, no mínimo:
1. **separar setup-base e checklist de fato** — o score deveria carregar
   variáveis que o setup-base **não** exige (ex.: volume relativo, book
   imbalance, contexto de OI/funding da Camada B, distância a suporte/
   resistência de prazo mais longo), não reafirmar tendência/momentum que
   o gatilho já garante;
2. **verificar a distribuição do score nos candidatos antes de gastar a
   rodada de veredito** — se > 95% cai num único bucket, o desenho está
   quebrado e precisa ser corrigido **antes** de rodar contra a amostra
   decisiva (isso teria evitado gastar esta rodada em um teste sem poder
   discriminativo);
3. considerar que o próprio setup-base de pullback BB+MACD em 15m já
   está duplamente reprovado (Q22-P2, Q23-BASE) — talvez o próximo
   setup-base não devesse vir da mesma família.

## Próximo passo honesto

Registrar ❌ no mapa e no resumo, junto com a lição de desenho (item 1
acima), que é o achado mais valioso desta rodada. A trilha volta ao ponto
em que estava: sem edge líquido robusto encontrado na superfície pública
de preço do BTC, agora com mais uma confirmação de que pullback BB+MACD em
15m — em qualquer formulação testada até aqui (Q19, Q22, Q23) — não
sustenta uma estratégia.
