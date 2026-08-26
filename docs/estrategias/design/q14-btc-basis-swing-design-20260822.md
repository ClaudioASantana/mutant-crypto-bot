# Q14 — BTC basis swing study — design pré-registrado — 2026-08-22

> Status: **documento de design**. Nada implementado como estratégia, nada em
> paper/live. Esta rodada dá continuidade ao único fio que a Q13 deixou
> honestamente em aberto: **BTC basis extremo positivo (S1)** parecia crescer
> de magnitude em 72h/7d, mas com `n_indep` pequeno e sem nenhuma checagem de
> repetibilidade temporal — exatamente o tipo de armadilha que a Q12 já expôs
> para o caso BNB rich+.

---

## 1. Por que esta rodada existe (e por que não é reabrir o que já falhou)

A Q13 pré-registrou **48h** como par primário de S1 e esse par **falhou**
(`marginal_net = -2,1bp`, abaixo do custo de 10bp). Isso está encerrado — não
será reaberto.

O que ficou em aberto foi uma observação **não pré-registrada como veredito**,
apenas reportada como leitura secundária: em 72h e 7d a magnitude cresceu
bastante (`-28,9bp` e `-75,5bp`). Isso não prova nada por si só — pode ser:
- um efeito real que só aparece com hold mais longo; ou
- um artefato de poucos eventos independentes concentrados num único
  subperíodo (o mesmo erro que a Q12 encontrou no BNB).

Q14 existe para testar essa segunda hipótese de forma explícita, **antes**
de tratar 72h como edge candidato.

## 2. O que muda em relação à Q13

1. **Janela maior**: para ter amostra independente suficiente em 72h *e*
   poder fatiar em subperíodos sem esvaziar cada fatia, a janela de estudo
   sobe de 90 para **190 dias** (busca com buffer de 220 dias).
2. **Novo par primário, pré-registrado agora, não escolhido depois de ver o
   resultado**: horizonte **72h**. 48h e 7d entram como contexto
   confirmatório, não como critério de aprovação.
3. **Guardrail de clustering temporal** (equivalente ao que a Q12 fez por
   símbolo, aqui aplicado ao tempo): eventos brutos são agrupados em
   episódios (gap < 24h). Se um único episódio concentrar `>= 50%` dos
   eventos brutos, o sinal é tratado como concentrado num pump/dump único, não
   como um padrão recorrente.
4. **Guardrail de fatias temporais** (mesmo espírito da Q12): a janela de 190
   dias é dividida em 3 fatias de ~63 dias. O sinal só é considerado
   repetível se pelo menos **2 de 3 fatias** confirmarem a direção da
   hipótese (retorno do evento mais negativo que o controle da própria
   fatia).

## 3. Hipótese (mantida da Q5/Q13)

> Quando o percentil causal do basis (`premium_rel` do BTCUSDT, janela
> rolante de 384 candles M15) atinge `>= 0,95` (basis extremamente positivo),
> o retorno forward do BTC tende a ser **mais negativo** que o controle
> incondicional da mesma janela — reversão após crowding de longs pagando
> funding/premium muito alto.

## 4. Definição do evento (idêntica à Q5/Q13, sem alteração)

- BTCUSDT M15.
- `premium_rel = premium_close / perp_close`.
- `premium_pct` = percentil causal numa janela rolante de 384 candles
  (`(arr <= arr[-1]).mean()`), sem lookahead.
- Evento: `premium_pct >= 0.95`.

## 5. O que Q14 mede

Para os horizontes 48h / 72h / 7d:
- retorno forward bruto do evento;
- retorno líquido (após custo de 10bp round-trip);
- controle incondicional equivalente da mesma janela;
- marginal líquido (`net_evento - net_controle`);
- `n_raw` e `n_indep` (cooldown = horizonte, igual à Q13);
- concentração do maior episódio (gap < 24h) em `% dos eventos brutos`;
- resultado por fatia temporal (3 fatias de ~63 dias) no horizonte primário.

## 6. Custos

- `10bp round-trip` — mesma régua da Q5/Q6/Q7/Q13 (S1 é uma perna direcional
  simples, sem estrutura relativa).

## 7. Regras causais (sem mudança)

- `premium_pct` usa apenas candles fechados até `t`;
- os retornos futuros (48h/72h/7d) só medem resultado, nunca definem evento;
- nenhuma escolha de parâmetro é feita depois de olhar o resultado do estudo.

## 8. Veredito pré-registrado (falsificável)

Par primário: **72h**.

### Falha se qualquer um destes for verdadeiro:
- `n_indep < 20`;
- sinal não é mais negativo que o controle (`sign_ok = False`);
- `|marginal_net| <= 10bp` (custo);
- concentração do maior episódio `>= 50%` dos eventos brutos;
- menos de `2/3` fatias temporais confirmam a direção da hipótese.

### Sobrevive somente se TODOS estes forem verdadeiros:
- `n_indep >= 20` em 72h;
- sinal negativo coerente também em 48h (mesmo sinal, não precisa passar o
  custo) e em 7d;
- `|marginal_net| > 10bp` em 72h;
- concentração do maior episódio `< 50%`;
- `>= 2/3` fatias temporais confirmam a direção.

## 9. Interpretação correta dos dois desfechos

**Se sobreviver**: ainda não é estratégia pronta para paper/live. Significa
que o efeito é candidato a um walk-forward formal com custo real de
execução (slippage de livro, não só bp fixo) antes de qualquer promoção.

**Se falhar**: encerra a família "basis extremo direcional" em todos os
horizontes testados até aqui (M15/H1 intraday na Q5, swing na Q13/Q14). A
próxima fronteira estrutural passa a ser prioritariamente **OI
divergence/crowding unwind**, quando a série própria (`collect_snapshot.py`,
seed em 2026-08-22) acumular profundidade suficiente (~4–6 semanas).

**Nada vai para paper/live nesta rodada, independentemente do resultado.**
