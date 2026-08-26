# Q16 — OI crowded continuation — veredito — 2026-08-22

> Design pré-registrado: `q16-oi-crowded-continuation-design-20260822.md`.
> Script: `backend/scripts/experiment_q16_oi_crowded_continuation.py`.
> Escopo: **Camada A** (histórico público ~30 dias), flip test pré-registrado
> da leitura pós-hoc da Q15.

## 1. Contexto do flip test

Na Q15, a hipótese era **unwind/reversão** após crowded long. O resultado no
primário veio na direção oposta (mais positivo que o controle). Isso gerou uma
leitura pós-hoc de **continuação**.

Q16 é a formalização honesta dessa leitura alternativa, com:
- os **mesmos eventos e parâmetros da Q15** (sem re-tuning);
- e guardrails **mais rígidos**, porque flip tests têm risco real de
  data-snooping (lição da Q12).

## 2. Resultado E1 — crowded long continuation

### Dados
- `n_raw = 85`
- `n_indep = 11` no primário 8h
- episódios (`gap < 24h`): `6`
- maior episódio: `28` eventos (**32,9%** do raw)
- retorno médio do maior episódio: `+0,02539`

### 4h
- `n_indep = 14`
- `marginal_net = +0,00919` (**+91,9bp**)

### 8h (primário)
- `n_indep = 11`
- `marginal_net = +0,00928` (**+92,8bp**)

### 24h
- `n_indep = 8`
- `marginal_net = +0,00585` (**+58,5bp**)

### Fatias temporais (primário 8h)
- fatia 1/3: `n_indep = 3`, `marginal_net = +0,00343` ✅
- fatia 2/3: `n_indep = 4`, `marginal_net = -0,00464` ❌
- fatia 3/3: `n_indep = 4`, `marginal_net = +0,02672` ✅
- confirmaram: **2/3**

### Guardrails
- `n_ok = False` (`n_indep = 11 < 20`)
- `sign_ok = True`
- `mag_ok = True`
- `conc_ok = True`
- `slice_ok = True` (**2/3**)
- `cross_ok = True` (mesma direção em 4h, 8h, 24h)

## 3. Veredito E1

**🔵 INCONCLUSO** (camada A).

Motivo único: **amostra independente insuficiente** (`n_indep = 11 < 20`).

Leitura importante:
- a leitura de **continuação** ficou mais coerente que a leitura de unfold da
  Q15 (2/3 de fatias confirmando aqui, contra 1/3 lá);
- mas com `n_indep` desse tamanho, isso ainda é um **indício**, não evidência.

## 4. Resultado E2 — crowded short continuation

- `n_raw = 0`
- sem veredito (ausência de eventos na camada A observada)

## 5. O que isto significa

A Q16 foi desenhada para decidir se a leitura pós-hoc da Q15 merecia ser
tratada como coisa séria. O que ela mostrou:

1. **A leitura de continuação não morreu**: sinal, magnitude, concentração e
   fatias passaram, e a coerência cross-horizonte (4h/8h/24h) passou.
2. **Mas ela não está provada**: `n_indep = 11` é pequeno demais para a régua
   da trilha.

Ou seja: o flip test **investiu a favor** da continuação, mas a camada A
(histórico público de ~30 dias) simplesmente não tem profundidade suficiente
para decidir — nem a favor, nem contra.

## 6. Consequência prática

A decisão correta não é "continuar refinando a camada A". É:

1. **Tratar a continuação de crowded long como hipótese aberta, bloqueada por
   amostra.**
2. **Deixar a camada B resolver**: nossa série própria acumulando desde
   2026-08-22, a cada 15 min, vai gerar os `n_indep` que faltam.
3. Manter a régua: só vai a paper/live se a camada B repetir o efeito com
   `n_indep >= 20`, fatias e episódios satisfeitos.

## 7. Encerramento

Q16 encerra como **inconclusa** na camada A — não reprovada, não aprovada.

Combinando Q15 + Q16:
- a família "OI divergence como unwind" está **favorável**;
- a família "OI crowded continuation" está **aberta, mas sem evidência forte**;
- a zona de decisão ficou restrita à espera da série própria.

**Nada vai para paper/live.**