# Q15 — OI divergence / crowding unwind — veredito — 2026-08-22

> Design pré-registrado: `q15-oi-divergence-design-20260822.md`.
> Script: `backend/scripts/experiment_q15_oi_divergence.py`.
> Escopo desta rodada: **Camada A**, usando apenas o histórico público recente
> da Binance (~30 dias paginados por `endTime`).

## 1. O que a Q15 testou

Hipótese formal desta rodada:

- **E1 — crowded long buildup**
  - preço vinha subindo;
  - OI crescia forte;
  - funding positivo;
  - premium relativamente rich.

  Leitura testada:
  > após esse buildup crowded, o retorno forward deveria ficar **mais negativo**
  > que o controle (crowding unwind / reversão).

- **E2 — crowded short buildup**
  - versão espelhada para o lado short.

Cada lado foi julgado separadamente, sem forçar simetria.

## 2. Cobertura real da camada A

- dataset final: `2879` velas M15
- range: `2026-07-23 19:00 UTC` → `2026-08-22 18:30 UTC`
- custo assumido: `10bp` round-trip
- horizonte primário: **8h**

Observação importante:
- a paginação dos endpoints públicos de OI/ratios funcionou e deu cerca de 30 dias;
- portanto esta rodada foi válida como leitura recente;
- mas ainda **não** é validação longa o bastante para promover edge.

## 3. Resultado do E1 — crowded long buildup

### Contagem
- `n_raw = 85`
- `n_indep = 11` no primário 8h

### Guardrail de episódios
- episódios (`gap < 24h`): `6`
- maior episódio: `28` eventos
- concentração do maior episódio: **32,9%**

Leitura:
- **passou** no guardrail de concentração de episódio;
- não dependia de um único burst extremo.

### 4h
- `n_indep = 14`
- `gross = +0,01017`
- `net = +0,00917`
- `ctrl_net = -0,00001`
- `marginal_net = +0,00919` (**+91,9bp**)

### 8h (primário)
- `n_indep = 11`
- `gross = +0,01127`
- `net = +0,01027`
- `ctrl_net = +0,00099`
- `marginal_net = +0,00928` (**+92,8bp**)

### 24h
- `n_indep = 8`
- `gross = +0,01230`
- `net = +0,01130`
- `ctrl_net = +0,00546`
- `marginal_net = +0,00584` (**+58,4bp**)

## 4. Leitura correta do E1

Este foi o ponto central da rodada:

> o E1 **não** gerou unwind / reversão.

Ele gerou o oposto:
- após preço subir com OI crescendo, funding positivo e premium rich,
- o retorno forward ficou **mais positivo** que o controle, não mais negativo.

Portanto, na camada A, o que apareceu foi:
- **continuação de crowded long**, não unwind de crowded long.

Só que mesmo essa leitura alternativa **não sobrevive** como candidata séria,
porque:
- `n_indep` no primário ficou muito baixo (`11`);
- a hipótese formal testada era reversão, não continuação;
- e a repetibilidade temporal falhou.

## 5. Fatias temporais do E1 no primário 8h

### Fatia 1/3
- `n_indep = 3`
- `marginal_net = +0,00343`

### Fatia 2/3
- `n_indep = 4`
- `marginal_net = -0,00464`

### Fatia 3/3
- `n_indep = 4`
- `marginal_net = +0,02672`

Leitura:
- apenas **1/3 fatias** confirmou a direção da hipótese original de unwind;
- as outras fatias ficaram na direção contrária ou misturadas;
- logo, a repetibilidade temporal **falhou**.

## 6. Resultado do E2 — crowded short buildup

- `n_raw = 0`
- `n_indep = 0`

Leitura:
- nesta janela recente, o filtro do E2 simplesmente não gerou eventos;
- portanto o lado short ficou **sem veredito**, não aprovado e não reprovado por magnitude.

## 7. Veredito formal

### E1 — crowded long buildup
Critérios do primário 8h:
- `n_ok = False`
- `sign_ok = False`
- `mag_ok = True`
- `conc_ok = True`
- `slice_ok = False`

**❌ E1 FALHA.**

Motivos reais:
1. `n_indep` insuficiente;
2. sinal na direção oposta à hipótese de unwind;
3. repetibilidade temporal insuficiente (`1/3` fatias).

### E2 — crowded short buildup
**❌ Sem veredito**, por ausência de eventos na camada A observada.

## 8. O que a Q15 realmente ensinou

A rodada foi útil porque separou duas coisas:

### A. OI realmente adiciona informação
Sim — o filtro não produziu puro ruído. O E1 mostrou deslocamento relevante vs controle.

### B. Mas a leitura de crowding unwind não foi a que apareceu
O padrão observado foi mais compatível com:
- **continuação de crowded long** por algumas horas,
- e não reversão/descompressão imediata.

Isso é importante porque evita insistir numa narrativa errada só porque “OI parece promissor”.

## 9. Consequência prática para a pesquisa

Q15 camada A **não validou** a hipótese de OI divergence como unwind/reversão.

Mas ela abriu uma possibilidade melhor definida para a próxima rodada:

> talvez a informação de OI recente esteja capturando **continuação curta de crowding**, não unwind.

Só que essa leitura alternativa ainda **não merece promoção**, porque:
- veio de janela curta (~30 dias);
- `n_indep` foi baixo;
- a estabilidade por fatias falhou.

## 10. Decisão honesta agora

- **Não promover** nada para paper/live.
- **Não concluir** que OI divergence falhou como classe inteira.
- Concluir apenas que:
  - a formulação **unwind/reversão** falhou nesta camada A;
  - o que apareceu foi um indício de **continuação curta**, ainda insuficiente.

## 11. Próximo passo mais honesto

A continuação natural não é refinamento livre ad hoc. O próximo passo correto é
abrir uma hipótese nova e separada, por exemplo:

### Q16 — OI crowded continuation
Testando explicitamente se:
- preço sobe + OI sobe + funding positivo + premium rich
- implica continuação forward de 4h/8h acima do controle

com:
- novo pré-registro;
- mesmos guardrails de episódios/fatias;
- e, idealmente, revalidação futura na série própria acumulada.

## 12. Encerramento

Q15 camada A está **reprovada** para a hipótese originalmente proposta.

Mas foi uma reprovação informativa:
- não mostrou ausência total de informação;
- mostrou que a **direção da informação** talvez seja outra;
- e impediu que a pesquisa confundisse “crowding existe” com “crowding unwind está validado”.
