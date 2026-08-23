# Q6 — Carry / funding capture — veredito do event study — 2026-08-22

> Design pré-registrado: `q6-carry-capture-design-20260822.md`.
> Script: `backend/scripts/experiment_q6_carry_capture.py`.
> Hipótese testada: em confluência de premium extremo + funding do mesmo sinal,
> capturar **apenas o próximo funding** numa estrutura delta-neutral idealizada
> já bastaria para gerar valor líquido positivo após custo mínimo.

## 1. Resultado do par primário (C+ e C− em M15)

Controle incondicional da janela:
- `carry_gross` médio: **+0,00005**
- `carry_net` médio: **-0,00095**

### C+ — premium extremo positivo + funding positivo
Estrutura conceitual: `short perp / long spot`
- `n = 142`
- `carry_gross = +0,00006`
- `carry_net = -0,00094`
- `control_net = -0,00095`
- `marginal = +0,00001`
- tempo médio até próximo funding: `4,20h`

### C− — premium extremo negativo + funding negativo
Estrutura conceitual: `long perp / short spot`
- `n = 18`
- `carry_gross = +0,00002`
- `carry_net = -0,00098`
- `control_net = -0,00095`
- `marginal = -0,00003`
- tempo médio até próximo funding: `5,21h`

## 2. Veredito pré-registrado

**❌ FALHA.**

A hipótese simples foi falsificada por três caminhos ao mesmo tempo:

1. **Amostra insuficiente no lado C−**
   - regra exigia `n >= 30` por lado;
   - obtivemos `n = 18`.

2. **Carry líquido negativo em ambos os lados**
   - C+: `-0,00094`
   - C−: `-0,00098`

3. **Sem superação material do controle**
   - C+ bate o controle só em **1 bp**, economicamente irrelevante;
   - C− fica pior que o controle.

Ou seja: o funding médio histórico de BTCUSDT nessa janela é da ordem de
**0,5 bp por funding capture**, enquanto o custo round-trip mínimo que estamos
cobrando é **10 bp**. A aritmética destrói a hipótese antes mesmo de modelar
borrow, slippage multi-venue, spread spot/perp, ou mark-to-market da basis.

## 3. Conclusão correta

Isso **não** significa que toda pesquisa de carry morreu.
Significa algo mais específico e útil:

> **Capturar só o próximo funding, de forma oportunística e reativa a um evento,
> não paga a conta.**

Essa versão era a mais simples e causal do carry. Se ela já falha num upper
bound idealizado, então não faz sentido promovê-la nem refiná-la localmente.

## 4. O que continua vivo conceitualmente

Se ainda houver algo a perseguir nessa família, terá de ser diferente em
estrutura, por exemplo:
- manter a posição por **múltiplos funding intervals**, não só o próximo;
- exigir regimes de funding persistentemente altos, não apenas sinal atual;
- modelar basis/funding como **estado de regime** e não como gatilho de evento;
- ou migrar para hipótese de arbitragem/carry mais longa, com outra régua.

Mas isso já é **outra hipótese**, não continuação desta.

## 5. Encerramento desta rodada

Q6 está encerrada como **reprovada**.
Nada vai para paper/live.
Nenhuma estratégia é promovida.

### Placar consolidado da trilha quantitativa até agora
- P1: 4/4 candidatas reprovadas.
- H1: filtros reprovados.
- H2: breakout de regime reprovado.
- H3: funding como filtro direcional reprovado.
- Q3: liquidation fade reprovada.
- Q5: basis/premium dislocation direcional reprovada.
- Q6: carry capture simples (próximo funding) reprovada.

A boa notícia metodológica é que o funil está funcionando:
- encontramos hipóteses com algum racional estrutural,
- medimos de forma causal,
- cobramos custo,
- e matamos cedo o que não paga a conta.

Isso evita exatamente o erro clássico de confundir sinal estatístico pequeno com
edge líquido real.