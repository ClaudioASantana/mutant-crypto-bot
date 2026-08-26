# Q13 — Swing horizon study (48h / 72h / 7d) — veredito — 2026-08-22

> Design pré-registrado: `q13-swing-horizon-design-20260822.md`.
> Script: `backend/scripts/experiment_q13_swing_horizon.py`.
> Hipótese: alguns sinais reais que morreram em horizontes curtos poderiam
> sobreviver quando o custo fosse diluído em 48h/72h/7d.

## 1. S1 — BTC basis extremo positivo (Q5 lado P+)

### 48h (primário)
- `n_raw = 483`
- `n_indep = 38`
- `gross = +0,00022`
- `net = -0,00078`
- `ctrl_net = -0,00056`
- `marginal_net = -0,00021`

Veredito primário S1:
- `n_ok = True`
- `sign_ok = True` (continuou mais negativo que o controle)
- `mag_ok = False`

**❌ S1 FALHA em 48h.**

Leitura:
- o sinal direcional do Q5 ainda existe em swing;
- mas em 48h ele continua pequeno demais para superar a régua econômica de 10bp.

### 72h
- `n_indep = 27`
- `marginal_net = -0,00289` (**-28,9bp**)

### 7d
- `n_indep = 12`
- `marginal_net = -0,00755` (**-75,5bp**)

Leitura importante:
- em 72h e 7d o efeito parece crescer bastante;
- mas o par primário pré-registrado de 48h falhou;
- 7d já sofre de amostra independente pequena (`n=12`).

Conclusão honesta para S1:
> a ideia de **basis extremo positivo como sinal swing** não está morta, mas o
> setup desta rodada **não a validou** no primário. O que apareceu aqui é um
> indício de que, se algum fio ainda vale perseguir, ele está mais para 72h/7d
> do que para 48h.

## 2. S2 — RICH+ cross-sectional com funding positivo (Q11/Q12)

### 72h (primário)
- `n_raw = 113`
- `n_indep = 11`
- `gross = +0,00873`
- `net = +0,00673`
- `ctrl_net = -0,00200`
- `marginal_net = +0,00873` (**+87,3bp**)
- concentração por símbolo = **100%**

Veredito primário S2:
- `n_ok = False`
- `sign_ok = True`
- `mag_ok = True`
- `conc_ok = False`

**❌ S2 FALHA em 72h.**

Leitura:
- o efeito em 72h ficou economicamente forte;
- mas a amostra independente é muito pequena (`n=11`);
- e a concentração em um único símbolo permanece total.

### 7d
- `n_indep = 7`
- `marginal_net = +0,01594` (**+159,4bp**)
- concentração por símbolo = **100%**

Isso reforça a mesma leitura:
- parece haver um caso local muito forte;
- mas não há generalidade, nem robustez multiativo;
- portanto isso ainda não é edge cross-sectional validado.

## 3. Veredito geral da Q13

**❌ Reprovada.**

Mas a rodada foi extremamente informativa.

### O que a Q13 matou
- a ideia de que "basta esticar um pouco o horizonte" para qualquer coisa virar edge;
- isso não aconteceu de forma limpa e robusta.

### O que a Q13 salvou parcialmente
Ela mostrou que **o problema de custo curto era real** em pelo menos duas frentes:

1. **S1 (BTC basis extremo positivo)**
   - o efeito cresce claramente em 72h/7d;
   - mas o primário 48h não validou a hipótese.

2. **S2 (RICH+ com funding)**
   - o efeito cresce muito em 72h/7d;
   - mas continua concentrado em um único símbolo e com `n_indep` insuficiente.

## 4. Interpretação estratégica

Q13 não encontrou uma estratégia pronta, mas refinou o mapa de forma importante:

### A. BTC basis extremo positivo agora é a trilha mais limpa
Entre tudo que testamos, S1 ficou com a leitura mais promissora porque:
- o sinal direcional já existia desde a Q5;
- o efeito em 72h/7d ficou materialmente maior;
- não dependeu de um único ativo fora de BTC;
- o problema é mais de **escolha de horizonte / amostra** do que de sinal errado.

### B. Cross-sectional RICH+ continua sendo um caso local, não um edge geral
O efeito ficou grande em swing, mas:
- `n_indep` despencou;
- a concentração por símbolo ficou em **100%**;
- portanto continua parecendo um caso especial, não uma família escalável.

## 5. Encerramento

Q13 está encerrada como **reprovada**.
Nada vai para paper/live.
Nenhuma estratégia é promovida.

## 6. Consequência prática para a pesquisa

Se a pesquisa continuar **agora**, o fio mais honesto a perseguir não é mais a
família cross-sectional. O melhor candidato passou a ser:

### Próximo melhor fio: BTC basis extremo positivo em horizonte swing
Mas com um desenho novo e explícito, por exemplo:
- horizonte primário 72h ou 7d;
- independência temporal forte;
- talvez walk-forward por fatias temporais;
- mantendo o mesmo custo e a mesma honestidade.

Se não quisermos continuar refinando o que ainda é só um indício, o próximo salto
mais estrutural continua sendo:
- **OI divergence / crowding unwind**, quando a série própria amadurecer.