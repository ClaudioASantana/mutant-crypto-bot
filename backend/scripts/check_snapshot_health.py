#!/usr/bin/env python3
"""Monitor operacional da série própria de microestrutura (OI/funding/ratios).

Lê o CSV append-only gravado pelo cron (`collect_snapshot.py`) e responde a
perguntas operacionais que decidem quando podemos reabrir hipóteses:

1. A série está viva e fresca? (última amostra dentro do esperado)
2. A série está completa? (sem buracos grandes entre snapshots)
3. Quantos dias de cobertura já temos?
4. Previsão honesta de quando a Camada B terá amostra suficiente.

Sem chamadas de rede — só lê o arquivo local.
Uso: venv/bin/python scripts/check_snapshot_health.py
"""

import os
import sys
from datetime import datetime, timezone, timedelta

import pandas as pd

DEFAULT_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "derivatives", "live_snapshot", "oi_funding_ratios.csv"
)

CRON_INTERVAL_MIN = 15
MAX_STALE_MIN = 30           # frescor máximo aceitável
MAX_GAP_MIN = 45             # buraco máximo aceitável entre amostras
TARGET_COVERAGE_DAYS = 60    # dias de série própria para n_indep>=20 esperado

SEED_UTC = "2026-08-22T15:07:16Z"


def main() -> int:
    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PATH
    if not os.path.exists(path):
        print(f"❌ Arquivo não existe: {path}")
        print("   Rode o coletor antes: venv/bin/python scripts/collect_snapshot.py")
        return 1

    df = pd.read_csv(path, parse_dates=["ts_utc"])
    df = df.sort_values("ts_utc").reset_index(drop=True)
    if len(df) < 2:
        print(f"❌ Série quase vazia ({len(df)} linha). Confira o cron.")
        return 1

    now = datetime.now(timezone.utc)
    first = df["ts_utc"].iloc[0]
    last = df["ts_utc"].iloc[-1]
    n = len(df)

    age_min = (now - last).total_seconds() / 60
    print(f"📊 Série própria de snapshots")
    print(f"   registros      : {n}")
    print(f"   primeira       : {first:%Y-%m-%d %H:%M} UTC")
    print(f"   última         : {last:%Y-%m-%d %H:%M} UTC  (idade {age_min:.0f} min)")
    print(f"   esperado total : {int((last - first).total_seconds()/60/CRON_INTERVAL_MIN) + 1} "
          f"(cron {CRON_INTERVAL_MIN}min a partir de {SEED_UTC})")

    # ---- frescor ----
    fresh = age_min <= MAX_STALE_MIN
    print(f"\n   frescor         : {'✅ ok' if fresh else '❌ STALE'} "
          f"(última amostra < {MAX_STALE_MIN} min)")

    # ---- cobertura / buracos ----
    diffs = df["ts_utc"].diff().dropna().dt.total_seconds() / 60
    big_gaps = diffs[diffs > MAX_GAP_MIN]
    coverage_days = (last - first).total_seconds() / 86400
    print(f"   cobertura       : {coverage_days:.1f} dias")
    if len(big_gaps):
        print(f"   ⚠️  buracos > {MAX_GAP_MIN}min : {len(big_gaps)} "
              f"(maior {big_gaps.max():.0f} min)")
    else:
        print(f"   buracos         : ✅ nenhum > {MAX_GAP_MIN} min")

    # ---- previsão de prontidão Camada B ----
    target_dt = first + timedelta(days=TARGET_COVERAGE_DAYS)
    remaining_days = (target_dt - now).total_seconds() / 86400
    print(f"\n   alvo Camada B   : {TARGET_COVERAGE_DAYS} dias de série própria")
    if remaining_days <= 0:
        print(f"   -> ✅ PRONTO? Cobertura (hoje) já atinge {TARGET_COVERAGE_DAYS} dias.")
        print(f"      Reabrir Q16 com merge public+own e checar n_indep>=20 de verdade.")
    else:
        print(f"   -> ⏳ faltam ~{remaining_days:.0f} dias "
              f"(previsão {target_dt:%Y-%m-%d}).")

    # ---- status agregado ----
    if fresh and not len(big_gaps):
        print("\n   ✅ Série viva e íntegra. Manter cron rodando.")
    else:
        print("\n   ⚠️  Investigue: cron parado ou buracos no agendamento.")
    return 0


if __name__ == "__main__":
    sys.exit(main())