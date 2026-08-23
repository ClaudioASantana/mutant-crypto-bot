# Acompanhamento mensal da trilha — 2026-08-23

> Documento operacional, não de pesquisa. Ele existe para que, em qualquer mês,
> dê para responder em 5 minutos: **o que está morto, o que está vivo, e o que
> só está esperando maturar.**

---

## 1. Estado da trilha (resumo de uma olhada)

| Frente | Status | Próximo gatilho |
|---|---|---|
| Q3 → Q23 (famílias de preço, funding, basis, OI, taker, TA) | ❌ encerradas como reprovadas | nada |
| P1 / H1–H3 (legado + filtros de regime) | ❌ encerradas | nada |
| **Q24-E1** (crowded long squeeze, confluência total) | ⏳ **viva, aguardando amostra nova** | ~8,1 meses de dado novo (≈ **2027-04**) |
| **Q24-E2** (crowded short squeeze, confluência total) | ⏳ viva, porém lenta | ~16,7 meses de dado novo (≈ **2028-01**) |
| **Camada B** (snapshot próprio OI/funding/flow) | 🟢 coletando via cron | canal independente futuro; hoje pequena |

Status da busca: **ainda não existe edge líquido promotável para paper/live.**
Procurar estratégia "nova" além da Q24 na janela antiga = p-hacking, proibido.

---

## 2. Rotina mensal (checklist — a fazer no 1º dia útil de cada mês)

### Passo 1 — atualizar dados (Camada A)

`venv/bin/python backend/scripts/download_binance_vision_metrics.py`

- baixa os CSVs diários de métricas novos (OI, ratios, taker) e alimenta o store local;
- 1º de cada mês também pode puxar os arquivos `monthly/` do mês fechado anterior
  (klines, premiumIndexKlines, fundingRate).

Verificar que a cobertura local passou da marca anterior.

### Passo 2 — checar prontidão da Q24

`venv/bin/python backend/scripts/check_q24_fresh_sample_ready.py`

- lê a cobertura local e diz se a amostra **fora-da-amostra** (pós `2026-08-21 23:45`)
  já tem tamanho para revalidar E1 / E2;
- se disser **PRONTO** para E1 (~2027-04), parar aqui e me chamar para escrever e
  rodar o harness de validação (seção 10 do design da Q24: 4h/8h/24h, custo 10bp,
  n_indep≥20, fatias ≥2/3, coerência cross-horizonte, controle do BTC).

### Passo 3 — checar saúde da Camada B

`venv/bin/python backend/scripts/check_snapshot_health.py`

- confere se a série própria (`live_snapshot/oi_funding_ratios.csv`) está atualizada
  e sem buracos;
- conferir de passagem que o cron `:03/:18/:33/:48` segue ativo.

### Passo 4 — registrar no fim deste documento

- cobertura de dados nova (até qual data);
- saúde da Camada B;
- decisões tomadas no mês (vereditos novos, se houver).

---

## 3. Regras que não se negociam (em qualquer mês)

1. **Custo explícito, causalidade, controle e amostra suficiente** — sempre.
2. **Nunca usar a janela `<= 2026-08-21 23:45`** como evidência da Q18/Q24.
   Essa janela gerou a hipótese; não pode confirmá-la.
3. **Nada vai para paper/live** sem atravessar a régua de verdade.
4. **Zero retune pós-resultado** — limiar é fixado antes, cronometrado.
5. **Proveniência separada**: backtest, memória operacional real e docs nunca
   se misturam.

---

## 4. Decisões na mesa hoje

| Pergunta em aberto | Onde responde | Quando |
|---|---|---|
| A confluência E1 tem edge? | Q24, seção 10 | quando o checker disser PRONTO (~2027-04) |
| A confluência E2 tem edge? | Q24, seção 10 | ~2028-01 |
| A Camada B vira canal de teste independente? | quando madura | coleta contínua |

Fora disso, a superfície pública de preço do BTC já foi espremida de forma séria
e negativa em: timing, sizing, squeeze, pullback, operador contextual,
crowding, taker e carry. **Não reabrir nenhuma dessas na janela antiga.**

---

## 5. Registro mensal

| Mês | Cobertura até | Camada B ok? | Q24-E1 | Q24-E2 | Decisões / notas |
|---|---|---|---|---|---|
| 2026-08 | 2026-08-21 | — | ⏳ 8,1m restantes | ⏳ 16,7m restantes | Q24 pré-registrada; viabilidade sem retorno |
| 2026-09 | | | | | |
| … | | | | | |