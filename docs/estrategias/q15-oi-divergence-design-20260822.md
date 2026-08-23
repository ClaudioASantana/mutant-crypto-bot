# Q15 — OI divergence / crowding unwind — design pré-registrado — 2026-08-22

> Status: **documento de design**. Nada implementado como estratégia, nada em
> paper/live. Esta rodada abre a próxima fronteira estrutural da trilha:
> **open interest real** como proxy de crowding, em vez de depender apenas de
> price/premium/funding público.

---

## 1. Por que esta rodada existe

Após a Q14, a família de `basis extremo direcional` ficou honestamente
encerrada para o setup atual:
- Q5 mostrou um traço informacional real, mas abaixo do custo;
- Q13 sugeriu possível força em swing, mas sem guardrails suficientes;
- Q14 mostrou que, mesmo com guardrails temporais e mais amostra, o primário
  72h não pagou a conta.

Logo, insistir em mais refinamentos de premium/funding/preço com a mesma classe
informacional tem baixo valor esperado.

A próxima hipótese séria precisa usar **outra fonte de informação**. A mais
natural é:

> **open interest divergence / crowding unwind**

Isto é, momentos em que o preço anda numa direção enquanto o OI cresce de forma
coerente com crowding, e depois esse crowding desmonta com reversão/descompressão.

## 2. Fonte de dados e limitação explícita

Q15 terá duas camadas de evidência, deliberadamente separadas:

### Camada A — estudo público imediato
Usar endpoints públicos da Binance Futures que já entregam histórico recente:
- `futures/data/openInterestHist`
- `futures/data/globalLongShortAccountRatio`
- `futures/data/topLongShortAccountRatio`
- `futures/data/takerlongshortRatio`
- `fapi/v1/klines`
- `fapi/v1/premiumIndexKlines`
- `fapi/v1/fundingRate`

**Limitação explícita:** esses endpoints públicos de histórico recente não dão
backfill arbitrário profundo via `startTime` antigo. Portanto, a camada A será
interpretada como:
- **estudo recente exploratório-controlado**, não validação histórica longa.

### Camada B — revalidação com série própria
Usar nossa série append-only em:
- `backend/data/derivatives/live_snapshot/oi_funding_ratios.csv`

Essa camada serve para:
- ampliar a janela ao longo do tempo;
- revalidar se o que aparecer na camada A se repete na série própria;
- evitar depender para sempre da cobertura curta do endpoint público.

## 3. Hipótese central

> Quando o BTC entra em episódio de crowding mensurável por **alta conjunta de
> preço e open interest**, especialmente sob funding/premium positivos, há dois
> desfechos possíveis:
>
> 1. **continuação curta** do movimento crowded; ou
> 2. **unwind / reversão** quando o fluxo enfraquece.
>
> O objetivo da Q15 não é assumir qual das duas vale. É medir qual leitura, se
> alguma, produz marginal líquido robusto contra um controle apropriado.

## 4. Primeira versão da hipótese (pré-registrada)

A primeira formulação será de **unwind/reversão**, porque é a leitura mais
alinhada ao objetivo de crowding unwind:

### Evento E1 — crowded long buildup
No BTCUSDT em M15/H1, marcar evento quando TODOS os critérios forem verdadeiros:
- retorno trailing do preço nas últimas `N` barras > 0;
- variação percentual do OI nas mesmas `N` barras >= percentil alto causal;
- funding atual > 0;
- premium relativo atual >= mediana causal (ou threshold positivo simples);

Leitura da hipótese:
- se o mercado está subindo **com OI crescendo**, o movimento pode estar sendo
  alimentado por crowding de longs tardios;
- após o evento, o retorno forward tende a ser **mais negativo** que o controle.

### Evento E2 — crowded short buildup
Versão espelhada:
- retorno trailing do preço < 0;
- variação percentual do OI <= percentil baixo causal (ou OI crescendo junto de
  queda de preço, a depender da implementação final do evento espelhado);
- funding atual < 0;
- premium relativo <= mediana causal negativa / cheap.

Leitura da hipótese:
- se o mercado cai com crowding de shorts, o retorno forward tende a ser **mais
  positivo** que o controle.

## 5. Importante: Q15 não assume simetria verdadeira

Assim como a trilha já mostrou assimetrias em outros casos, Q15 não vai forçar a
conclusão de que long crowding e short crowding têm o mesmo comportamento.

Por isso, E1 e E2 serão reportados separadamente. Um pode falhar e o outro não.

## 6. Horizonte e estrutura de teste

### Camada A (endpoint público recente)
- timeframes-base candidatos: `15m` e `1h`
- horizontes forward:
  - `4h`
  - `8h`
  - `24h`
  - opcionalmente `48h` se a cobertura recente permitir

### Camada B (série própria)
- inicialmente só snapshots de `15m`
- horizonte depende da profundidade acumulada
- primeira leitura honesta só depois de janela suficiente para independência
  mínima e pelo menos 2–3 subperíodos

## 7. Custos

Como primeira formulação, Q15 será tratada como sinal **direcional BTC**, não
como trade relativo multi-perna.

Portanto:
- custo base: **10bp round-trip**

Se mais tarde surgir uma estrutura relativa/hedge, isso será outra hipótese,
não esta.

## 8. Regras causais

- OI, funding, premium e ratios usam apenas o último valor conhecido até `t`;
- percentis/ranks são calculados causalmente;
- retornos futuros só medem o resultado do evento;
- nenhuma escolha de horizonte será promovida depois do fato sem novo
  pré-registro.

## 9. Guardrails metodológicos

### A. Controle obrigatório
Para cada evento, comparar contra:
- retorno incondicional equivalente da janela; e, se viável,
- controle condicional por regime simples de volatilidade.

### B. Independência
Reportar:
- `n_raw`
- `n_indep` com cooldown igual ao horizonte

O veredito se apoia em `n_indep`.

### C. Não confundir endpoint recente com prova longa
Se a camada A mostrar efeito bom, isso **não** promove edge ainda. Ela apenas
vira candidata a:
- revalidação na série própria acumulada; e/ou
- estudo walk-forward quando houver mais profundidade.

### D. Não forçar E1 e E2 no mesmo pacote
Cada lado será julgado separadamente.

## 10. Critério de sobrevivência (camada A)

Para qualquer evento/lado/horizonte sobreviver como **candidato**:
- `n_indep >= 20`
- sinal coerente com a hipótese
- `|marginal_net| > 10bp`
- não estar concentrado num único episódio extremo
- não depender visivelmente de um único micro-subperíodo recente

Mesmo sobrevivendo, o máximo que isso significa é:
- **merece revalidação com a série própria**

Não significa promoção para paper/live.

## 11. Entregáveis da Q15

1. `backend/scripts/experiment_q15_oi_divergence.py`
2. `docs/estrategias/validacao-q15-oi-divergence-20260822.md`
3. eventual atualização do `mapa-decisoes-trilha-quant-20260822.md`

## 12. Consequência prática da coleta já configurada

A coleta periódica local foi configurada para rodar a cada 15 minutos e gravar
em:
- `backend/data/derivatives/live_snapshot/oi_funding_ratios.csv`

Isso transforma a série própria em ativo cumulativo do projeto:
- ela não depende mais de execução manual;
- e passa a servir como trilha de validação longitudinal das próximas hipóteses
  de OI/fluxo.

## 13. Interpretação correta dos futuros resultados

### Se a camada A falhar agora
- isso enfraquece a hipótese de que OI público recente já basta para extrair o
  edge;
- mas não mata totalmente a frente, porque a série própria longa ainda pode
  capturar estrutura melhor.

### Se a camada A sobreviver agora
- isso não é edge pronto;
- é apenas o primeiro indício de que a frente de OI merece revalidação mais
  longa.

**Nada vai para paper/live nesta rodada.**
