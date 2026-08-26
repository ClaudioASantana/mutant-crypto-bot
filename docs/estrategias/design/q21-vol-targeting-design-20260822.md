# Q21 — exposição calibrada à volatilidade (vol-targeting) — design pré-registrado — 2026-08-22

> Status: **documento de design**. Nada implementado como estratégia, nada em
> paper/live.

---

## 1. De onde esta rodada nasce

A **Q20** fez a correção metodológica da trilha (sair de média por evento, entrar em
curva de equity) e entregou um resultado limpo e específico:

- SMA200, Golden Cross e TSMOM 12-1 **preservaram participação** no upside do BTC
  (47%–88% do CAGR) com robustez temporal e custo irrelevante;
- porém **nenhuma** cortou drawdown o suficiente: MaxDD ficou em 63–67% (vs 83% do
  buy-and-hold), bem acima do teto exigido de 49,91% (60% do B&H).

A leitura estrutural: **o gargalo não é previsão direcional, é tamanho de exposição.**
Regras de timing clássicas mudam de lado tarde demais; o que mata a curva é continuar
exposto com notional cheio durante as fases de volatilidade extrema (2018, 2022).

Esta rodada testa um mecanismo **ortogonal** ao timing: **dimensionar a exposição para
uma volatilidade-alvo fixa**, sem tentar prever direção nenhuma.

## 2. Hipótese

> Dimensionar a posição de acordo com a volatilidade realizada recente — cortando
> exposição automaticamente quando a vol explode e subindo quando ela acalma —
> consegue **cortar materialmente o max drawdown** do BTC enquanto **preserva uma
> fração relevante do CAGR**?

Note o que esta hipótese **não** é:

- não prevê direção;
- não escolhe "long" vs "flat" por tendência;
- é uma política de **sizing**, não de timing.

Se passar, o que encontramos é uma **política robusta de preservação de capital** sobre
BTC — não alpha, e não uma forma de "bater" o mercado. Isso é declarado desde já.

## 3. O que esta rodada NÃO é

- não é re-tune da Q20 (mesmos critérios, mecanismo diferente);
- não é pullback em tendência (essa formulação está **bloqueada**: mesma família, mesma
  amostra, e nasceu pós-falha);
- não é grid-search de parâmetros: as especificações são fixas, padrão e pré-registradas;
- não usa stop-loss otimizado, nem short, nem alavancagem.

## 4. Fonte de dados

Igual à Q20:

- **spot BTCUSDT 1d** via Binance Vision monthly klines;
- mês corrente completado por API spot;
- faixa alvo: **2017-08-17 → execução atual** (~9 anos, 3 ciclos completos);
- mesmo parse de timestamps com detecção de unidade (ms ≤ 2024-12, us ≥ 2025-01).

## 5. Mecanismo (sem lookahead)

- retorno diário simples: `r_t = close_t / close_{t-1} − 1`
- volatilidade realizada na janela de `W` dias, no fechamento de `t`:
  `σ_t = std({r_{t-W+1}, …, r_t}, ddof=0) × √365`
- exposição para o dia seguinte (decidida no fechamento de `t`):
  `e_{t+1} = min(σ_target / σ_t, 1.0)`  →  `e ∈ [0, 1]`, sem alavancagem
- retorno bruto da estratégia em `t+1`: `gross_{t+1} = e_{t+1} × r_{t+1}`
- **custo** por troca de exposição, proporcional ao notional negociado:
  `c_t = |e_t − e_{t-1}| × 0,0005`  (5bp por unidade de notional trocada)
- retorno líquido: `net_t = gross_t − c_t`
- `e` inicial = 0 (começa flat); a exposição do primeiro dia paga custo de entrada.

Não há lookahead: `e_t` usa apenas retornos até o fechamento de `t-1`, aplicado ao
retorno de `t` (mesma disciplina `shift(1)` da Q20).

## 6. Especificações fixas pré-registradas (não são grid)

Três especificações padrão da família "volatility-managed portfolios", com janela e
alvo fixos de antemão — nenhuma escolhida após ver o resultado:

| Variante | Janela de vol (W) | Vol-alvo (aa) |
|---|---|---|
| **V1** | 30 barra (~1 mês) | 40% |
| **V2** | 60 barras (~3 meses) | 40% |
| **V3** | 30 barras (~1 mês) | 30% |

A ideia da concordância de classe (≥2/3) é exatamente evitar que **um único conjunto de
parâmetros** sobreviva por sorte.

## 7. Métricas a reportar (por variante + benchmark)

- curva de equity diária;
- CAGR líquido e bruto;
- vol anualizada;
- Sharpe, Sortino;
- max drawdown e duração do drawdown;
- % média de tempo/menos exposição (mean exposure);
- notional total negociado (turnover real em múltiplos do capital);
- gross vs net (impacto de custo);
- retorno por ano-calendário;
- robustez temporal (primeira vs segunda metade, ciclos 2017-19 / 2020-22 / 2023+).

## 8. Benchmark

- **buy-and-hold spot BTCUSDT** no mesmo período;
- referência adicional: as três regras da Q20 (na mesma régua), para mostrar onde
  o mecanismo se distingue.

## 9. Veredito pré-registrado

Uma variante só **SOBREVIVE como candidata** se, na janela cheia:

1. **Participação:** CAGR líquido ≥ 40% do CAGR do buy-and-hold.
2. **Preservação:** max drawdown ≤ 60% do maxDD do buy-and-hold.
3. **Robustez temporal:**
   - nenhum ano responde por ≥ 50% do retorno total;
   - ≥ 1/2 metades positiva e ≥ 2/3 ciclos positivos.
4. **Custo não explica tudo:** diferença CAGR gross − net ≤ 1,0 ponto percentual.
5. **Concordância de classe:** ≥ 2/3 das variantes (isto é, 2 das 3: V1, V2, V3)
   passam os critérios 1–4.

### Sub-janelas pré-registradas (idênticas à Q20)

- primeira metade vs segunda metade;
- regimes por ciclo: 2017-08→2019-12, 2020-01→2022-12, 2023-01→execução atual.

## 10. O que NÃO significa sobreviver

Mesmo sobrevivendo:

- não é promoção para paper/live;
- vira apenas **candidato** a validação posterior;
- e fica registrado com o rótulo honesto: é **gestão de risco sobre BTC**, não alpha
  direcional. Sua utilidade é descer o drawdown de uma posição long/flat, não prever.

## 11. Consequências possíveis

- Se **passar** (≥2/3): primeiro mecanismo da trilha que ataca o drawdown na origem da
  dor; candidato a virar camada de risk-management no bot (sozinho ou sobre regras), mas
  sempre após validação em amostra nova.
- Se **falhar** (participação e/ou preservação abaixo do teto): saberemos o ponto exato
  da fronteira "CAGR × drawdown" para BTC long/flat — e a trilha aponta com ainda mais
  força para a única frente com informação verdadeiramente nova (Camada B madura).