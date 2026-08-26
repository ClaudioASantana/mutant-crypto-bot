# Mapa final de decisões — trilha quantitativa — 2026-08-22

> Referência consolidada da trilha de pesquisa de edge em crypto.
> Objetivo único: **não confundir PnL bruto com edge líquido real**.
> Toda a trilha foi conduzida com: hipótese pré-registrada, dados causais
> (sem lookahead), controle de mercado, custo explícito e amostra suficiente.

---

## 1. Resumo em uma frase

Nenhuma das hipóteses testadas passou a régua de edge líquido robusto.
Algumas mostraram sinal estatístico real, mas todas morreram na barreira
econômica (custo), na não-repetibilidade temporal, ou (Q16, Q17, Q19) não
sobreviveram ao aumento de amostra / ao teste isolado da variável / ao teste
limpo de TA clássica. A Q20 — a primeira com lente de **curva de equity** em
vez de média por evento — confirmou que a família clássica de trend-following
preserva participação, mas **não corta drawdown o suficiente** para justificar a
troca de CAGR por segurança. A Q21 testou o mecanismo ortogonal (**sizing** por
vol-alvo, sem timing) e confirmou o mesmo gargalo: reduz drawdown melhor que
timing (mínimo de 53,75% vs 83% do B&H), mas ainda acima da barra de preservação.
A Q22 fez a tradução mais generosa da leitura visual de BB + MACD (pullback +
retomada em 15m) e mostrou que ela não se sustenta objetivamente: o alpha bruto
é inexistente/fraco e a rotação torna o custo devastador. A Q23 tentou modelar
um **operador contextual** (setup-base + checklist de score) sobre a mesma
família de pullback e trouxe uma lição de desenho, não só de mercado: o
checklist quase não discriminou nada (99,9% dos candidatos já nasciam
aprovados, por redundância com o próprio gatilho), e o setup-base isolado já
falhava (bruto muito abaixo do B&H, líquido negativo, sem robustez temporal).

---

## 2. O que foi definitivamente descartado (fechar portas)

| Frente | Hipótese | Veredito | Razão principal |
|---|---|---|---|
| P1 | Zoo de estratégias legado (TA clássica) | ❌ | Ranking por PnL bruto era enganoso; sem edge líquido no config padrão |
| H1 | Filtros de regime (sessão/ATR/ADX) | ❌ | Reduzem trades, não criam edge |
| H2 | Regime breakout (Donchian 55 + ADX) | ❌ | M15 perde; H1 quase não opera |
| H3 | Funding como filtro direcional | ❌ | Poda perdas, não cria vantagem |
| Q3 | Liquidation fade (flush e wick reclaim) | ❌ | Amostra fraca; principal evento sem base |
| Q5 | Basis/premium dislocation direcional | ❌ | Sinal real, porém < custo |
| Q6 | Carry: capturar o próximo funding | ❌ | Funding médio pequeno demais |
| Q7 | Regime persistente de funding+basis | ❌ | Regimes raros e economicamente fracos |
| Q8 | Reversão cross-sectional (rich reverter, cheap reverter) | ❌ | Sinal veio contrário à hipótese |
| Q9 | Momentum cross-sectional simétrico | ❌ | Direção certa, magnitude < custo |
| Q10 | Momentum cross-sectional + funding nos dois lados | ❌ | Melhorou só o rich; cheio e assimétrico |
| Q11 | RICH-only + funding pos (focus 8h/24h) | ❌ | Aproximou (+15bp/8h, +30bp/24h), mas não passou 20bp no primário e dominou com BNB |
| Q12 | BNBUSDT single-name rich+ (anti-snooping) | ❌ | Não replicou em 2/3 fatias; perdeu custo |
| Q14 | BTC basis swing study (72h primário, com guardrails temporais) | ❌ | Passou guardrails, mas o primário entregou só -1,5bp líquido vs controle |
| Q15 | OI divergence / crowding unwind (camada A pública) | ❌ | OI carregou informação, mas na direção oposta: continuação de crowded long, não unwind |
| Q16 | OI crowded continuation (flip test, série longa Camada A histórica) | ❌ | Com ~6 anos de amostra, E1 perdeu o efeito e E2 ficou forte na direção errada e sem repetibilidade temporal |
| Q17 | Taker flow imbalance isolado (percentil extremo, sem confirmação de OI/funding/premium) | ❌ | `n_indep` fartos (4979/4573 no 8h), mas sinal, magnitude, fatias e coerência cross-horizonte falharam nos dois braços |
| Q19 | Volatility compression breakout (BB squeeze + MACD, H1, 2020-01→2026-08) | ❌ | E1 efeito na direção errada; E2 efeito fraco (~5bp) e sem coerência no 24h |
| Q20 | Trend participation lenta em BTC (spot 1d, long/flat: SMA200 / Golden Cross / TSMOM 12-1, curva de equity) | ❌ | Participação, robustez e custo passam; preservação falha: MaxDD cai só para 63–67% (vs 83% B&H), longe dos 60% exigidos |
| Q21 | Exposição calibrada à volatilidade (vol-targeting, spot 1d: W30/T40, W60/T40, W30/T30, curva de equity) | ❌ | Reduz MaxDD melhor que timing (53,75% melhor caso), mas ainda acima do teto de 49,91%; participação, robustez e custo passam — só preservação falha |
| Q22 | Pullback em tendência com BB + MACD (spot 15m: midline reclaim / trend pullback / exhaustion exit) | ❌ | Leitura visual objetivada não gerou alpha bruto relevante e virou hiper-rotativa; custo destruiu tudo (2.686–20.040 flips, até 57pp de erosão de CAGR) |
| Q23 | Operador contextual: setup-base pullback BB+MACD + checklist determinístico (BASE vs CHECKLIST vs VETO, spot 15m) | ❌ | Checklist mal discriminou (99,9% dos candidatos já nasciam ENTER — redundância com o próprio setup-base); e o setup-base sozinho já falhava (CAGR_gross +6,71% vs +37,91% B&H, CAGR_net -11,29%, 0/2 metades, 0/3 ciclos) |

**Decisão:** nenhuma dessas deve ir para paper/live, nem ser repromovida sem uma
mudança estrutural de informação ou de estrutura de custo.

---

## 3. O que quase funcionou (guardar como aprendizado)

Estes são os dois resultados mais informativos da trilha — não promovidos, mas
úteis como pista para o futuro:

1. **Q5/Q13/Q14 — basis extremo tem conteúdo informacional, mas não edge líquido**
   - Q5: P+ (basis muito positivo) → retorno forward negativo em M15, porém ~7bp < custo
   - Q13: 72h/7d pareceram promissores, mas ainda sem guardrails suficientes
   - Q14: com 190 dias e guardrails temporais, o primário 72h entregou só **-1,5bp** vs controle
   - ✅ há traço informacional; ❌ não há margem econômica robusta
   - **Lição:** premium/basis público até carrega informação, mas ela é pequena e irregular demais para o custo do setup atual.

2. **Q10/Q11/Q16/Q19 — alguns subcasos parecem bons em janelas curtas, mas quebram quando cobramos robustez**
   - Q11: o subcaso rich confirmado por funding superou o baseline sem funding
   - Q12 mostrou que parte disso era concentração em BNB e em uma fatia
   - Q16 original parecia o melhor candidato aberto (`+92,8bp` em 8h), mas o
     rerun com ~6 anos mostrou que era falso positivo de amostra curta:
     E1 zerou/negativou; E2 ficou forte só na direção errada e em poucas fatias
   - Q19 (BB squeeze + MACD) parecia a formulação mais limpa da TA clássica; o
     braço short (E2) até acertou a direção em 4h/8h e em 5/6 fatias, mas só
     entregou **-4,9bp** no primário e virou **+6,4bp** no 24h
   - **Lição:** um resultado bonito em janela curta, ou uma leitura visual boa,
     ainda não vale nada sem profundidade temporal, margem econômica e estabilidade por regime.

3. **Q20 — trend-following clássico preserva upside, mas não corta drawdown**
   - a primeira rodada com lente de **curva de equity** (não média por evento) deu
     um veredito limpo: SMA200, Golden Cross e TSMOM 12-1 preservaram entre 47% e
     88% do CAGR do buy-and-hold, com vol menor, Sharpe comparável, robustez temporal
     (2/2 metades e 2–3/3 ciclos) e custo desprezível;
   - porém **todas** falharam no critério de preservação: max drawdown caiu só para
     **63–67%** (vs 83% do B&H), ~19–24% de corte, longe dos 40% exigidos — e a
     duração do drawdown seguiu em ~1.050 dias, praticamente igual ao B&H;
   - **Lição:** a promessa-assinatura do trend-following ("evitar o crash") não se
     cumpre em BTC na granularidade diária long/flat clássica; o que ele entrega é
     suavização parcial de vol, não preservação real de capital no pior cenário.

4. **Q21 — sizing por volatilidade reduz drawdown melhor que timing, mas ainda não passa**
   - testou o mecanismo ortogonal ao timing (dimensionar `e ∈ [0,1]` para uma vol-alvo
     fixa, sem prever direção). Reduziu o MaxDD de 83,19% para **61–65%** (alvo 40%) e
     **53,75%** (alvo 30%), com Sharpe ≥ B&H e vol muito menor (34–43% vs 67%);
   - ainda assim, **0/3** variantes passaram: todas falharam **só** no critério de
     preservação (MaxDD ≤ 49,91%). A V3 ficou 3,8pp acima do teto;
   - **Lição estrutural (fecha o ciclo com a Q20):** para BTC long/flat, *timing* (Q20)
     preserva upside mas sai tarde demais, e *sizing* (Q21) corta exposição mas continua
     metade-investido num ativo que cai 73%/64% — resultado: MaxDD ~54% mesmo no alvo
     mais conservador. A fronteira `CAGR × drawdown` do BTC é funda e longa demais para
     regras públicas simples de preço entregarem a combinação exigida.

5. **Q22 — a leitura visual de BB + MACD não sobrevive quando objetivada**
   - a hipótese era generosa com a intuição visual do usuário: não testou squeeze puro,
     e sim **pullback em tendência + recuperação da banda média + MACD reacelerando**;
   - o resultado foi pior do que “quase passa”: **P1/P2** já não têm alpha bruto útil
     (`CAGR_gross -14,81% / -1,28%`) e **P3** mal fica positivo (`+1,41%`), antes de custo;
   - além disso, a família ficou **hiper-rotativa** em 15m (`2.686` a `20.040` flips), e o
     custo destruiu completamente a curva (`gross-net` até **57pp**);
   - **Lição:** uma leitura visual boa em alguns trechos pode existir, mas a sua tradução
     objetiva e replicável sobre amostra longa não isolou um regime “limpo”; virou chop,
     micro-retomadas fracas e reentradas demais. A superfície pública de preço do BTC em
     15m também foi espremida de forma séria e negativa.

6. **Q23 — o checklist contextual não teve o que discriminar, e o setup-base já falhava**
   - a ideia era testar se um score de contexto (tendência, localização, momentum, regime)
     separa entradas boas de ruins melhor que um gatilho isolado de pullback BB+MACD;
   - **achado principal, mais valioso que o número final:** 99,9% dos 1.665 candidatos do
     setup-base já nasciam com score ≥ 6 (ENTER). O checklist removeu 1 trade de 1.665
     (CHECKLIST) e 0 (VETO) — os três modos (BASE/CHECKLIST/VETO) são, na prática, a mesma
     curva;
   - **causa raiz identificada:** o checklist reusa, com pesos positivos, os mesmos
     ingredientes que já definem o gatilho de entrada (tendência de EMA, retomada de
     `bb_mid`, `macd_hist > 0`) — isso já garante 5 dos 6 pontos necessários para ENTER
     em todo candidato. Um checklist redundante com o próprio setup não testa “contexto
     adicional”, testa paráfrase;
   - **mesmo sem esse problema, o setup-base sozinho já reprovava**: `CAGR_gross +6,71%`
     (vs `+37,91%` do B&H), `CAGR_net -11,29%`, `MaxDD 66,94%` (quase igual ao B&H),
     `0/2` metades e `0/3` ciclos positivos;
   - **Lição de desenho, reaproveitável em qualquer Q futura:** (a) verificar a
     distribuição do score/filtro sobre os candidatos **antes** de gastar a rodada de
     veredito — se >95% cai num único bucket, o desenho está quebrado; (b) um filtro
     contextual só tem chance de agregar valor se carregar informação **ortogonal** ao
     que o gatilho de entrada já exige, não uma reafirmação pontuada dele.

---

## 4. O que ainda vale perseguir (próximas fronteiras sérias)

Com as famílias de preço/funding/basis/OI público já bastante espremidas para
esta régua, o edge — se existir neste mercado — precisa vir de uma fonte de
informação mais independente, ou de uma hipótese estruturalmente nova:

### {++1. OI/flow próprios (Camada B) como canal independente, não como muleta de amostra++}
- manter o cron `collect_snapshot.py` rodando (`:03/:18/:33/:48`) e o monitor de saúde ativo;
- usar essa série para validar **hipóteses novas** com dado independente da Binance Vision/API, não para "salvar" Q16 (que já foi decidida);
- combinação prioritária: OI + funding + basis + taker flow + price response.

### {++2. Squeeze do lado crowded (hipótese nova, se pré-registrada do zero)++}
- achado incidental pós-Q15/Q16: tanto crowded long quanto crowded short mostraram episódios em que o lado apinhado foi "espremido" em vez de simplesmente reverter/continuar como na narrativa inicial;
- a leitura mais chamativa ficou em E2 da Q16 longa (`+83,6bp` em 24h), mas **sem repetibilidade temporal** (`2/6` fatias) e na direção oposta à hipótese pedida;
- consequência: isso **não é edge** e não reabre a Q16;
- **Q18** preservou a hipótese sem executá-la (`q18-squeeze-crowded-side-design-20260822.md`): o evento é idêntico à Q16, o sinal pedido é o espelho (E1 = −1, E2 = +1), e a amostra que a gerou está contaminada para validação;
- **Q24** refinou a hipótese com **confluência total** (adiciona funding em magnitude extrema e taker flow extremo no mesmo lado) e mediu apenas **viabilidade de frequência** sobre a janela histórica (`q24-confluencia-crowded-squeeze-design-20260823.md`, `experiment_q24_confluence_viability.py`) — eliminando qualquer cálculo de retorno forward hoje:
  - **E1** (crowded long confluente): 216 raw, 131 indep, maior episódio 6,0%, média **2,47 indep/mês** → ~**8,1 meses** de amostra nova para `n_indep >= 20` → **viável em frequência, mantida viva**;
  - **E2** (crowded short confluente): 8 raw, 6 indep, maior episódio 37,5%, média **1,20 indep/mês** → ~**16,7 meses** → **viável porém muito lenta, em observação**;
- monitor de prontidão: `backend/scripts/check_q24_fresh_sample_ready.py` — reporta quando a amostra fora-da-amostra (pós-`2026-08-21 23:45`) atingir o tamanho para revalidar.
- regra inegociável: **nunca usar `<= 2026-08-21` como evidência da Q24**. Veredito só com dado novo.

### {++3. Order flow / taker flow real++}
- taker buy/sell ratio, taker volumes (snapshot próprio ou Binance Vision);
- **Q17 já testou a versão isolada** (percentil extremo de `sum_taker_long_short_vol_ratio`,
  sem confirmação de OI/funding/premium) na Camada A histórica: **❌ reprovada** —
  `n_indep` fartos (4979/4573 no primário 8h), mas sinal, magnitude, fatias e coerência
  cross-horizonte falharam nos dois braços. Ver
  [validacao-q17-taker-flow-imbalance-20260822.md](validacao-q17-taker-flow-imbalance-20260822.md).
- status: taker flow **isolado** está encerrado. O que resta nesta fronteira é taker flow
  **combinado** com outras variáveis (ex.: só como confirmação dentro de um evento de
  OI/funding, ou via snapshot próprio/Camada B como canal independente) — não uma
  variável nova sozinha repetindo o mesmo formato de evento já esgotado.

### {++4. Outro mercado/venue/universo++}
- mercados menos eficientes, outros exchanges, spot vs perp arb, cross-margin;
- status: caro em dados/integração, mas pode ser mais promissor do que continuar extraindo sinal da mesma superfície pública já testada até a exaustão.

### {++5. Horizonte mais longo / swing (multi-dia)++}
- continua conceitualmente válido por diluir custo por trade;
- porém, dentro da informação pública atual, já foi testado no BTC basis swing (Q14) e reprovado no primário;
- e a **Q20** testou a forma mais robusta dessa família (trend-following diário clássico,
  long/flat, curva de equity): preservou upside mas **não cortou drawdown** — maxDD ficou em
  63–67% vs 83% do B&H. Com isso, a família "participar de tendência longa" em BTC spot
  **não entregou a preservação de capital** que a justificava;
- portanto cai para prioridade menor, atrás de frentes com nova informação observável.

**Monitor operacional que permanece valendo:**
- `venv/bin/python scripts/check_snapshot_health.py`
- a série própria continua sendo um ativo do projeto, mesmo sem papel de desbloquear a Q16.

**Decisão explícita:** não precisamos de provedor pago para resolver a Q16.
O dump gratuito da Binance Vision já entregou profundidade suficiente para
encerrar essa hipótese.
---

## 5. Programa de pesquisa recomendado (prioridade honesta)

1. **Agora:** registrar o encerramento da Q16 e manter a coleta própria rodando.
2. **Próxima frente séria:** desenhar, só se fizer sentido, uma hipótese nova com
   OI/flow próprios (Camada B) ou uma formulação explícita de **squeeze do lado crowded**,
   em vez de reabrir unwind/continuation já reprovados.
3. **Contínuo:** manter o coletor de snapshot rodando de forma periódica —
   é o único caminho para testar OI/fluxo real de forma independente.
4. **Opcional depois:** explorar outro mercado/venue/universo se a frente de OI/flow também falhar.

---

## 6. Regras que este mapa aponta como não-negociáveis

1. **Não promover** nada que não passe: causalidade + controle + custo + amostra.
2. **Não confundir** "sinal estatístico" com "edge líquido".
3. **Não seguir** o último vencedor sem validação temporal (lição da Q12).
4. **Não aumentar** custos implícitos ou viés de sobrevivência na narrativa.
5. **Sempre** voltar a este mapa antes de abrir uma nova hipótese.

---

## 7. Conclusão

A trilha até aqui **não encontrou a estratégia** — e isso é um resultado
legítimo e valioso: fechar portas com rigor é exatamente o que separa um
projeto sério de um que coleciona backtests bonitos.

O capital de pesquisa foi usado para aprender o que **não** funciona e quais
dados fazem falta. Depois da Q20 e da Q21, o quadro ficou ainda mais claro:
**nem o timing clássico (trend-following) nem o sizing por volatilidade** — os
dois mecanismos ortogonais possíveis sobre a mesma superfície de preço — entregam
a combinação de participação + preservação de capital que justificaria promoção.
O gargalo é estrutural: o drawdown do BTC é fundo **e** longo demais. Esse é o
alicerce para que as próximas hipóteses (OI, fluxo, outro universo) sejam
testadas no mesmo padrão de honestidade.