# Resumo da trilha quantitativa — 2026-08-22

Estamos numa trilha de **pesquisa quantitativa honesta** para descobrir se existe alguma estratégia de crypto com **edge líquido real**, sem cair em autoengano de:
- PnL bruto,
- amostra pequena,
- indicador bonito,
- ou hipótese que “parece fazer sentido” mas morre quando cobramos custo.

## O objetivo
Encontrar uma estratégia que sobreviva a esta régua:
- causal / sem lookahead
- custo explícito
- comparação contra controle
- amostra suficiente
- nada vai para paper/live sem passar de verdade

---

# Onde começamos
Primeiro atacamos o que já existia no projeto.

## P1 — zoo de estratégias legado
Testamos e reavaliamos estratégias clássicas já presentes no bot.

Resultado:
- **4/4 reprovadas**

Lição:
- o ranking antigo por PnL bruto não era confiável;
- quase tudo parecia melhor do que realmente era.

---

# Depois fomos para hipóteses mais estruturadas

## H1 — filtros de regime
Tentativa:
- pegar estratégias ruins e aplicar filtros “inteligentes”:
  - sessão UTC
  - ATR percentile
  - ADX

Ideia:
- talvez o problema não fosse a estratégia, mas operar fora do regime certo.

Resultado:
- **reprovada**
- os filtros reduziram trades, mas **não criaram edge**
- em vários casos só ficaram “menos ruins” porque operaram menos

Resumo:
- filtro não ressuscita estratégia morta.

---

## H2 — regime breakout
Tentativa:
- breakout com Donchian 55
- ADX
- ATR band
- TP/SL/time stop
- com anti-lookahead correto

Resultado:
- **reprovada**
- M15 perdeu dinheiro
- H1 quase não operou

Resumo:
- breakout “bonito” na teoria, sem edge líquido na prática.

---

## H3 — funding como filtro direcional
Tentativa:
- usar funding para filtrar os sinais da H2
- ex.: short só quando funding positivo e crescendo

Resultado:
- **reprovada**
- cortou perdas em alguns casos
- mas não virou edge

Resumo:
- funding ajudou a podar lixo, mas não criou vantagem econômica real.

---

# Depois mudamos de família: event studies

## Q3 — liquidation fade
Tentativa:
- estudar flush / wick reclaim
- ideia: movimentos de exaustão poderiam gerar reversão após liquidação

Resultado:
- **reprovada**
- amostra muito fraca
- principal evento não teve base robusta

Resumo:
- narrativa boa, evidência ruim.

---

## Q4 — backbone de dados
Aqui **não era hipótese de edge**.
Era infraestrutura.

O que fizemos:
- montamos um backbone gratuito com:
  - klines
  - premium index
  - funding
  - mark/index
  - ratios
  - snapshot próprio de OI/flow

Resultado:
- **sucesso**
- backbone operacional
- esse foi o grande destravamento da pesquisa

Resumo:
- sem isso, as hipóteses seguintes nem seriam testáveis direito.

---

# A fase atual: Q5 em diante
Depois do backbone, passamos a testar hipóteses mais “crypto-native”.

---

## Q5 — basis / premium dislocation direcional
Pergunta:
- quando o basis/premium fica extremo, o preço reverte?

Resultado:
- **reprovada**
- houve algum sinal real
- mas **pequeno demais para sobreviver ao custo**

Resumo:
- primeiro caso em que vimos:
  - “tem algo aqui”
  - mas **não é grande o bastante para virar edge líquido**

---

## Q6 — carry / capture do próximo funding
Pergunta:
- se o funding estiver favorável, capturar só o próximo funding já paga a conta?

Resultado:
- **reprovada**
- o funding médio era pequeno demais
- o custo come tudo

Resumo:
- carry curto oportunístico não paga.

---

## Q7 — regime persistente de funding + basis
Pergunta:
- talvez não seja evento único, mas um regime persistente de crowding

Resultado:
- **reprovada**
- regimes existiam
- mas eram raros e economicamente fracos

Resumo:
- melhor conceito que Q6, mesma conclusão econômica.

---

## Q8 — cross-sectional relative value
Pergunta:
- talvez o problema seja operar direção absoluta de BTC
- e o edge esteja em comparação entre ativos

Hipótese:
- ativos “rich” vs “cheap” deveriam reverter relativamente ao basket

Resultado:
- **reprovada**
- grande amostra
- mas o sinal veio **contra a hipótese**

Resumo:
- a reversão cross-sectional simples não apareceu.

---

## Q9 — cross-sectional momentum
Como a Q8 sugeriu continuação em vez de reversão, viramos a hipótese:

Pergunta:
- e se rich continuar rich e cheap continuar cheap?

Resultado:
- **reprovada**
- mas foi uma das mais interessantes
- o sinal ficou **na direção certa**
- porém **fraco demais para vencer custo**

Resumo:
- primeira hipótese cross-sectional “quase boa”
- estruturalmente melhor, economicamente insuficiente

---

## Q10 — momentum cross-sectional com confirmação de funding
Pergunta:
- se o funding confirmar o deslocamento, a magnitude melhora?

Resultado:
- **reprovada**
- melhorou bastante o lado **RICH**
- piorou o lado **CHEAP**
- ainda muito abaixo do custo

Resumo:
- apareceu um indício importante:
  - o lado **RICH + funding positivo** parece mais promissor do que o resto
- mas ainda não é edge líquido

---

## Q11 — RICH-only cross-sectional continuation
Pergunta:
- isolando só o lado rich com funding positivo, a magnitude finalmente cresce?

Resultado:
- **reprovada**
- foi o melhor resultado da família:
  - RICH+ em 8h: **+15,2bp**
  - RICH+ em 24h: **+30,6bp**
- mas o horizonte primário (8h) ficou abaixo do custo piso de `20bp`
- e os eventos vieram **concentrados em BNBUSDT**

Resumo:
- primeiro caso que chegou perto da barreira econômica;
- mas dependia de um único ativo — pista para o teste decisivo.

---

## Q12 — BNBUSDT single-name rich+ (anti-snooping)
Pergunta:
- o caso BNB rich+ é real e repetível, ou é artefato de janela?

Resultado:
- **reprovada**
- guardrails aplicados:
  - episódios (gap < 24h): maior episódio = **16,4%** → não era um pump único
  - fatias de 30 dias: **só 1 de 3 fatias** foi positiva → não replicou
  - custo piso: marginal `+11,5bp` em 8h < `20bp`
- morreu por **não-repetibilidade temporal** + **custo no primário**

Resumo:
- o que parecia promissor virou um **subperíodo favorável que não se repetiu**;
- com isso, a família cross-sectional premium/funding está honestamente
  **esgotada**.

---

# Em que ponto estamos agora
Estamos neste ponto:

## O que já sabemos
Não apareceu edge líquido robusto em:
- TA clássica
- filtros de regime
- breakout
- funding como filtro simples
- liquidation fade
- basis extremo direcional
- carry curto
- regime simples persistente
- reversão cross-sectional
- momentum cross-sectional simétrico
- momentum cross-sectional com funding nos dois lados
- rich-only cross-sectional
- BNB single-name rich+

## O que parece menos ruim
As linhas mais promissoras até aqui foram:

1. **Q5**
- basis extremo direcional tinha um efeito real
- mas pequeno demais

2. **Q9**
- momentum cross-sectional acertou o sentido
- mas pequeno demais

3. **Q10/Q11**
- o lado **RICH + funding positivo** foi o que mais se aproximou
- Q12 mostrou que parte era concentração em BNB e em uma fatia de janela
- ainda assim, é o único pedaço que merece olhar futuro com dado novo

---

# Para onde ir agora
Ver `mapa-decisoes-trilha-quant-20260822.md` (o mapa final de decisões).

Resumo executivo do mapa:
1. **Agora:** encerrar Q16 como reprovada e manter a coleta própria rodando.
2. **Próxima frente séria:** só abrir hipótese nova se ela trouxer **informação nova** — OI/flow próprios combinados, squeeze do lado crowded pré-registrado em amostra nova, ou outro venue/universo.
3. **Contínuo:** manter o coletor de snapshot rodando periodicamente — é o único caminho para testar OI/fluxo real de forma independente.

Ver também: `validacao-q11-rich-only-20260822.md`,
`validacao-q12-bnb-single-name-20260822.md`,
`validacao-q16-rerun-serie-longa-20260822.md`,
`validacao-q17-taker-flow-imbalance-20260822.md` e
`validacao-q19-volatility-compression-breakout-20260822.md`.

# Atualização final da frente OI/flow/TA (2026-08-22)

## Q14 — BTC basis swing study
Resultado:
- **reprovada**
- 72h primário: `n_indep = 58`, `marginal_net = -1,5bp`
- guardrails temporais passaram, mas o efeito não superou custo

Conclusão:
- a família **basis extremo direcional** foi encerrada para o setup atual.

## Q15 — OI divergence / crowding unwind
Pergunta:
- usar OI real recente da Binance para testar se episódios de crowding geram
  **unwind / reversão**.

Resultado:
- **reprovada** para a hipótese original de unwind
- E1 (crowded long) apareceu com força, mas na **direção oposta**:
  - 8h primário: `n_indep = 11`
  - `marginal_net = +92,8bp`
- E2 (crowded short) não gerou eventos na janela observada

Conclusão:
- OI parece carregar informação;
- mas, nesta camada A, o padrão observado foi **continuação de crowded long**,
  não unwind.

## Q16 — OI crowded continuation (rerun série longa)
Pergunta:
- formalizar a leitura pós-hoc da Q15 como um **flip test pré-registrado**;
- depois rerodar com ~6 anos de Binance Vision para decidir se o aparente
  `+92,8bp` da janela curta era real ou falso positivo de amostra.

Resultado:
- **reprovada** na Camada A histórica
- dataset final: `208.601` velas M15 (`2020-09-01 → 2026-08-21 23:45`)
- E1 (crowded long continuation):
  - `n_indep = 860` no primário 8h
  - `marginal_net = -1,0bp`
  - sinal falhou, magnitude falhou, coerência cross-horizonte falhou
- E2 (crowded short continuation):
  - `n_indep = 124` no primário 8h
  - `marginal_net = +15,5bp`
  - efeito ficou forte **na direção errada** e só `2/6` fatias confirmaram

Conclusão:
- a hipótese de **OI crowded continuation** não sobreviveu ao aumento de amostra;
- a Q16 original estava certa em não promover nada com `n_indep=11`;
- não é mais caso de esperar a Camada B para "destravar" essa hipótese — ela já foi decidida.

## Q17 — taker flow imbalance isolado (série longa)
Pergunta:
- extremos de `sum_taker_long_short_vol_ratio`, sozinhos, carregam continuação curta acima do controle?

Resultado:
- **reprovada**
- dataset final igual ao da Q16 longa: `208.601` velas M15 (`2020-09-01 → 2026-08-21 23:45`)
- E1 (taker buy imbalance extremo):
  - `n_indep = 4.979` no primário 8h
  - `marginal_net = -3,7bp`
  - falhou em sinal, magnitude, fatias (`1/6`) e coerência cross-horizonte
- E2 (taker sell imbalance extremo):
  - `n_indep = 4.573` no primário 8h
  - `marginal_net = +0,7bp`
  - falhou em sinal, magnitude, fatias (`2/6`) e coerência cross-horizonte

Conclusão:
- **taker flow público isolado** não bastou para gerar edge líquido robusto;
- a reprovação é estrutural, não por falta de amostra;
- isso fecha a leitura de que preço, funding, basis, OI público **e também taker flow público**, cada um isoladamente neste setup, não entregaram edge promotável.

## Q18 — squeeze do lado crowded
Status:
- **pré-registrada, não executada**
- hipótese preservada em `q18-squeeze-crowded-side-design-20260822.md`

Conclusão:
- continua bloqueada até haver **amostra genuinamente nova** (Camada B madura ou meses novos de Camada A);
- rodar agora seria flip pós-hoc na mesma amostra da Q16 e configuraria p-hacking.

## Q19 — volatility compression breakout (BB squeeze + MACD)
Pergunta:
- compressão extrema de volatilidade + confirmação direcional do MACD carregam expansão curta acima do controle?

Resultado:
- **reprovada**
- dataset final: `58.223` velas H1 (`2020-01-01 → 2026-08-22 22:00`)
- E1 (compressão + MACD positivo):
  - `n_indep = 733` no primário 8h
  - `marginal_net = -7,2bp`
  - falhou em sinal, magnitude, fatias (`2/6`) e coerência cross-horizonte
- E2 (compressão + MACD negativo):
  - `n_indep = 775` no primário 8h
  - `marginal_net = -4,9bp`
  - acertou a direção e `5/6` fatias, mas ficou **abaixo do custo** e quebrou no 24h (`+6,4bp`)

Conclusão:
- a formulação mais limpa de **BB squeeze + MACD** não sobreviveu aos guardrails;
- o braço short sugere **algum** conteúdo informacional, mas pequeno demais para virar edge líquido;
- isso estende a conclusão da trilha também para a família clássica de TA pública sobre preço.

## Q20 — trend participation lenta em BTC (spot 1d, long/flat, curva de equity)
Pergunta:
- talvez estivéssemos cobrando a coisa errada da forma errada:
  em vez de prever direção em 4h/8h, regras lentas e públicas de tendência
  conseguiriam **preservar uma fração relevante do upside de BTC** enquanto
  **cortam drawdown de forma material**?

Mudança metodológica:
- sair de **event study por média de retorno forward**;
- entrar em **curva de equity** de estratégia;
- usar **spot BTCUSDT 1d** desde `2017-08-17`;
- testar três regras clássicas, sem re-tune:
  - `close > SMA200`
  - `SMA50 > SMA200`
  - momentum `12-1` (12 meses excluindo o último mês)

Resultado:
- **reprovada**
- dataset final: `3.293` velas 1d spot (`2017-08-17 → 2026-08-22`)
- benchmark buy-and-hold:
  - CAGR `+37,79%`
  - maxDD `83,19%`
  - total `+1697,82%`
- R1 SMA200:
  - CAGR `+24,92%`
  - maxDD `63,69%`
  - robustez temporal ok (`2/2` metades, `3/3` ciclos)
- R2 Golden Cross:
  - CAGR `+17,82%`
  - maxDD `66,75%`
  - robustez temporal ok (`2/2` metades, `3/3` ciclos)
- R3 TSMOM 12-1:
  - CAGR `+33,27%`
  - maxDD `63,34%`
  - robustez temporal ok (`2/2` metades, `2/3` ciclos)
- custo foi pequeno nas três (`gross-net` de `0,12pp` a `0,45pp`)
- **0/3 regras passaram**

Conclusão:
- a intuição de que tendência longa em crypto existe **não era totalmente falsa**:
  as três regras preservaram participação relevante no upside, tiveram Sharpe bom,
  robustez temporal e custo irrelevante;
- mas a promessa central da família — **evitar o grande drawdown** — **não se cumpriu**;
- o max drawdown caiu de `83,19%` para algo entre `63%` e `67%`, o que ainda é
  um drawdown catastrófico e ficou **muito acima** do limite exigido (`<= 49,91%`);
- portanto, a versão clássica de **trend-following diário long/flat em BTC** não entrega
  a preservação de capital que justificaria abrir mão de CAGR.

## Q21 — exposição calibrada à volatilidade (vol-targeting)
Pergunta:
- se o problema não é direção, mas **tamanho de exposição**, então reduzir o notional
  automaticamente quando a vol explode consegue cortar o drawdown do BTC de forma
  material sem destruir demais o CAGR?

Mudança conceitual:
- Q20 atacava o problema por **timing** (entrar/sair);
- Q21 atacou o mesmo problema por **sizing** (quanto ficar exposto), sem tentar prever
  direção nenhuma.

Resultado:
- **reprovada**
- dataset final igual ao da Q20: `3.293` velas 1d spot (`2017-08-17 → 2026-08-22`)
- benchmark buy-and-hold:
  - CAGR `+37,79%`
  - maxDD `83,19%`
- variantes pré-registradas:
  - V1 (30d, alvo 40%): maxDD `64,97%`, CAGR `+29,42%`
  - V2 (60d, alvo 40%): maxDD `61,07%`, CAGR `+26,92%`
  - V3 (30d, alvo 30%): maxDD `53,75%`, CAGR `+25,10%`
- todas as três variantes:
  - passaram em participação
  - passaram em robustez temporal (`2/2` metades, `3/3` ciclos)
  - passaram em custo (`gross-net` ~`0,18pp` a `0,34pp`)
  - **falharam apenas no critério de preservação**
- **0/3 variantes passaram**

Conclusão:
- a Q21 confirmou a leitura da Q20: o problema central não é custo nem falta de
  robustez temporal;
- o problema é a **fronteira CAGR × drawdown do BTC**;
- mesmo uma política de sizing claramente melhor que o timing para cortar risco não
  conseguiu baixar o maxDD para o teto exigido (`<= 49,91%`);
- isso praticamente fecha a superfície pública de preço em BTC spot 1d:
  - **timing clássico** não basta;
  - **sizing por vol** também não basta.

## Q22 — pullback em tendência com BB + MACD (15m)
Pergunta:
- a leitura visual do usuário com Bollinger + MACD não parecia squeeze puro;
  parecia **retomada após pullback curto**. Se isso fosse traduzido de forma objetiva,
  haveria edge líquido em BTC spot 15m?

Mudança conceitual:
- a Q19 testou **compressão extrema + expansão**;
- a Q22 testou a leitura alternativa mais generosa da imagem:
  **pullback + recuperação da banda média + reaceleração do MACD**.

Resultado:
- **reprovada**
- dataset final: `315.549` velas 15m spot (`2017-08-17 04:00 → 2026-08-22 23:30`)
- benchmark buy-and-hold:
  - CAGR `+37,87%`
  - maxDD `83,97%`
- variantes:
  - P1 Midline Reclaim:
    - CAGR bruto `-14,81%`
    - CAGR líquido `-71,98%`
    - `20.040` flips
  - P2 Trend Pullback:
    - CAGR bruto `-1,28%`
    - CAGR líquido `-58,91%`
    - `15.794` flips
  - P3 Exhaustion Exit:
    - CAGR bruto `+1,41%`
    - CAGR líquido `-12,63%`
    - `2.686` flips
- **0/3 variantes passaram**

Conclusão:
- esta foi uma resposta importante para a intuição visual: ela merecia ser testada
  separadamente, e foi;
- o resultado mostrou que a tradução objetiva da leitura visual **não isolou um regime
  limpo**;
- o setup ficou hiper-rotativo em 15m, e o custo destruiu completamente qualquer
  resíduo de alpha;
- isso fecha mais uma porta da superfície pública de preço do BTC:
  não só squeeze/expansão falha, como também **pullback/retomada com BB + MACD** falha.

## Q23 — operador contextual (setup-base + checklist)
Pergunta:
- um **checklist contextual determinístico** (tendência, localização,
  momentum e regime), aplicado sobre um setup-base de pullback em tendência,
  consegue separar entradas boas de ruins melhor do que operar o setup-base
  sozinho?

Resultado:
- **reprovada**
- dataset final: `315.557` velas 15m spot (`2017-08-17 04:00 → 2026-08-23 01:30`)
- candidatos do setup-base: `1.665`
- distribuição do checklist sobre os candidatos:
  - `ENTER (score>=6)`: **99,9%**
  - `WAIT (3..5)`: `0,1%`
  - `VETO (<=2)`: `0,0%`
- efeito prático:
  - `CHECKLIST` removeu **1 trade de 1.665**
  - `VETO` removeu **0 trades**
  - os três modos (`BASE`, `CHECKLIST`, `VETO`) viraram, na prática, a mesma curva
- `BASE` (setup-base sozinho) já falhava por si só:
  - `CAGR_gross = +6,71%`
  - `CAGR_net = -11,29%`
  - `MaxDD = 66,94%`
  - `0/2` metades positivas
  - `0/3` ciclos positivos

Conclusão:
- esta rodada trouxe uma lição mais valiosa de **desenho** do que de mercado:
  o checklist quase não teve o que discriminar;
- a razão é estrutural: ele reusava com pesos positivos vários itens que o
  próprio setup-base já exigia (`ema20>ema50`, `close>ema20`, retomada de
  `bb_mid`, `macd_hist>0`), então os candidatos já nasciam quase aprovados;
- portanto, a Q23 **não mostrou que "contexto" ajuda** — mostrou que esta
  implementação específica do contexto era **redundante com o gatilho**;
- ao mesmo tempo, o setup-base puro também não entregou edge líquido,
  reforçando a conclusão da Q22: a família **pullback BB+MACD em 15m** segue
  sem hipótese promotável.

## Q24 — confluência total de crowded squeeze (hipótese viva, aguardando amostra nova)
Pergunta:
- a Q18 preservou a hipótese de que o lado **crowded** é **espremido** (E1 long
  squeeze sinal −1, E2 short squeeze sinal +1), mas bloqueada por contaminação
  de amostra;
- a Q24 pergunta se a confluência **total** — preço + OI + funding (sinal **e**
  magnitude) + premium + taker flow tudo em extremo no mesmo lado — é uma
  assinatura mais forte desse squeeze (e não apenas uma reafirmação da Q18).

O que foi feito (2026-08-23):
- **pré-registro** congelado em `q24-confluencia-crowded-squeeze-design-20260823.md`;
- **viabilidade de frequência** (sem retorno forward, sem t-stat, sem veredito
  econômico) sobre a Camada A histórica:
  - E1 (crowded long confluente): `216` raw, `131` indep, maior episódio `6,0%`,
    média `2,47` indep/mês → **~8,1 meses** de amostra nova para `n_indep >= 20`;
  - E2 (crowded short confluente): `8` raw, `6` indep, maior episódio `37,5%`,
    média `1,20` indep/mês → **~16,7 meses**;
- decisão: **E1 mantida como frente séria viável**; **E2 em observação** (rara);
- monitor: `backend/scripts/check_q24_fresh_sample_ready.py` (diz quando a
  amostra pós-`2026-08-21 23:45` estiver pronta).

Análise:
- a confluência **E1 é viável em frequência**, o que justifica esperar amostra
  nova para validar de verdade;
- ainda **não existe nenhuma evidência econômica** para a Q24 — só o achado
  incidental da Q18, que não pode validar a própria hipótese;
- a Q24 **não é** um backtest novo do que já falhou; é o mesmo evento da Q16
  com **sinal espelhado** (Q18) e **confluência adicional** (taker + magnitude
  de funding), decidido apenas por dado genuinamente novo.

- **cron ativo:** `collect_snapshot.py` a cada 15 min (`:03/:18/:33/:48`), append-only em `backend/data/derivatives/live_snapshot/oi_funding_ratios.csv`
- **monitor:** `venv/bin/python scripts/check_snapshot_health.py` — morre se a série estiver stale ou com buracos
- **papel atual da Camada B:** servir de canal independente/out-of-sample para hipóteses novas de OI/flow, não mais como desbloqueio de amostra da Q16
- **consequência importante:** o dump gratuito da Binance Vision já resolveu a necessidade de profundidade histórica; provedor pago não é necessário para decidir esta frente

## Achado incidental a guardar, não promover

- tanto na Q15 quanto no braço E2 da Q16 longa apareceu material sugerindo
  **squeeze do lado crowded** (e não unwind/continuação na narrativa original);
- isso **não** é edge agora porque faltou repetibilidade temporal;
- mas pode justificar uma hipótese futura, nova e pré-registrada do zero, em vez de reabrir Q15/Q16.

## Próximo passo honesto

- manter a coleta própria rodando;
- encerrar Q16, Q17 e Q19 como reprovadas;
- manter Q18 apenas como pré-registro aguardando amostra nova;
- se a família de TA for retomada, partir para uma formulação **diferente** (ex.: pullback em tendência), não para retunar o mesmo squeeze na mesma amostra;
- só abrir uma nova frente se ela trouxer **informação nova** (OI/flow próprios combinados, squeeze em amostra nova, outro venue/universo), em vez de reinterpretar de novo a mesma hipótese.

---

# Resumo em uma frase
Estamos fazendo uma **varredura séria de hipóteses de edge em crypto**, matando tudo que não sobrevive a custo, causalidade e repetibilidade; após as Q20 e Q21, a trilha já havia mostrado que **nem timing clássico nem sizing por vol** resolvem a fronteira `CAGR × drawdown` do BTC, e as Q22 e Q23 reforçaram que **nem a leitura visual objetivada de BB + MACD nem um checklist contextual redundante com o próprio gatilho** produzem edge líquido robusto em 15m — então ainda não existe hipótese promotável para paper/live.
