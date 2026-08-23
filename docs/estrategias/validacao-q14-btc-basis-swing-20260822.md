# Q14 — BTC basis swing study — veredito — 2026-08-22

> Design pré-registrado: `q14-btc-basis-swing-design-20260822.md`.
> Script: `backend/scripts/experiment_q14_btc_basis_swing.py`.
> Hipótese: o sinal direcional da Q5 (basis extremo positivo → retorno futuro
> mais negativo) talvez só aparecesse de forma economicamente válida quando o
> hold fosse mais longo (72h/7d), desde que sobrevivesse a guardrails de
> concentração temporal.

## 1. Resultado principal (par primário = 72h)

- `n_raw = 982`
- `n_indep = 58`
- `gross = +0,00177`
- `net = +0,00077`
- `ctrl_net = +0,00091`
- `marginal_net = -0,00015` (**-1,5bp**)

Veredito primário:
- `n_ok = True`
- `sign_ok = True`
- `mag_ok = False`

**❌ Q14 FALHA no primário 72h.**

Leitura:
- o sinal ainda ficou levemente mais negativo que o controle;
- porém a diferença líquida foi de apenas **-1,5bp**;
- isso fica muito abaixo da régua econômica de `10bp` round-trip.

Ou seja: existe, no máximo, um conteúdo informacional muito pequeno — pequeno
demais para promover como edge líquido.

## 2. Resultados auxiliares

### 48h
- `n_raw = 1013`
- `n_indep = 81`
- `marginal_net = +0,00088` (**+8,8bp**)

Leitura:
- além de não superar custo, **o sinal virou para o lado errado** vs controle.
- Isso é importante porque a regra de sobrevivência pedia coerência direcional
  também em 48h.

### 7d
- `n_raw = 958`
- `n_indep = 25`
- `marginal_net = -0,00412` (**-41,2bp**)

Leitura:
- em 7d o efeito volta a ficar material;
- mas isso não salva a hipótese, porque:
  1. o par primário 72h falhou economicamente;
  2. 48h não confirmou a direção;
  3. 7d já trabalha com amostra independente bem menor (`n=25`).

## 3. Guardrails temporais

### A. Concentração por episódio
- episódios (`gap < 24h`): `26`
- maior episódio: `143` eventos
- concentração do maior episódio: **13,5%** dos eventos brutos

Veredito:
- **✅ passou** no guardrail de concentração.
- O resultado não dependia de um único burst extremo de mercado.

### B. Fatias temporais (3 fatias de ~63 dias) no primário 72h

#### Fatia 1/3
- `n_indep = 20`
- `marginal_net = +0,00443` (**+44,3bp**)
- **falhou a direção da hipótese**

#### Fatia 2/3
- `n_indep = 20`
- `marginal_net = -0,00111` (**-11,1bp**)
- confirmou a direção

#### Fatia 3/3
- `n_indep = 18`
- `marginal_net = -0,00329` (**-32,9bp**)
- confirmou a direção

Veredito:
- `2/3` fatias confirmaram a direção.
- **✅ passou** no guardrail de repetibilidade temporal mínima.

Isso é útil porque elimina uma interpretação simplista do tipo:
> "falhou porque tudo veio de um único episódio ou de um único pedaço da janela."

Não foi isso.

## 4. O que a Q14 realmente provou

Q14 fez algo importante: ela separou duas narrativas que a Q13 deixava misturadas.

### Narrativa A — "o efeito da Q13 era só um artefato temporal"
Q14 **enfraquece** essa narrativa, porque:
- a concentração por episódio foi baixa (`13,5%`);
- e `2/3` fatias temporais confirmaram a direção.

### Narrativa B — "mesmo sendo um efeito real, ele não paga a conta"
Q14 **fortalece** esta narrativa de forma decisiva, porque:
- no par primário 72h, o `marginal_net` foi só **-1,5bp**;
- 48h ficou na direção errada;
- a única leitura realmente forte ficou em 7d, com amostra menor e fora do
  par primário.

Portanto, a interpretação correta é:
> **há no máximo um traço informacional pequeno e irregular; não há edge líquido
> robusto e promovível nesta família.**

## 5. Veredito final da família "basis extremo direcional"

Combinando:
- Q5 (intraday / 4h) → sinal real, mas abaixo do custo;
- Q13 (swing inicial) → indício promissor, porém sem guardrails suficientes;
- Q14 (swing com guardrails) → primário 72h falha economicamente;

A decisão honesta passa a ser:

**❌ Encerrar a família `basis extremo direcional` como candidata de edge para o setup atual.**

Não vai para paper/live.
Não merece novo refinamento incremental em cima da mesma informação pública.

## 6. Consequência prática para a pesquisa

Com a Q14, o melhor próximo passo deixa de ser refinar basis/funding/preço no
mesmo eixo e passa a ser buscar **outra classe de informação**.

Prioridade natural agora:

### Próxima fronteira: OI divergence / crowding unwind
Motivo:
- é exatamente a classe de dado novo que ainda não foi testada com profundidade;
- pode capturar crowding de forma mais estrutural do que premium isolado;
- a coleta própria já foi iniciada em `collect_snapshot.py`.

Leitura prática:
- manter o coletor rodando;
- esperar a série própria amadurecer por ~4–6 semanas;
- então abrir a próxima hipótese formal nessa frente.

## 7. Encerramento

Q14 está **reprovada**.

Mas foi uma reprovação útil e limpa:
- ela não matou um bom sinal por bug,
- não foi uma armadilha de episódio único,
- e não foi uma leitura concentrada num único subperíodo.

Ela matou a hipótese pelo motivo mais importante de todos:

> **o efeito não supera custo de forma robusta no par primário que tentava
> transformá-lo em edge swing.**
