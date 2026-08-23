#!/usr/bin/env python3
"""Monitor de prontidão da Q24 — amostra fora-da-amostra.

Pré-registro: docs/estrategias/q24-confluencia-crowded-squeeze-design-20260823.md

Responsabilidade: informar, quando rodado, se já existe amostra genuinamente
nova suficiente para validar a Q24-E1 / Q24-E2, sem reusar a janela que gerou a
hipótese (cutoff da Q16 longa: 2026-08-21 23:45).

Sem retorno, sem veredito econômico. Apenas prontidão de amostra.
"""

import os
import sys
from datetime import datetime, timezone

import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Cutoff da janela que gerou a hipótese (Q16 longa / Q18). Nada antes disso
# conta como validação honesta.
OLD_CUTOFF = pd.Timestamp("2026-08-21 23:45", tz="UTC")

# Estimativas da viabilidade (Q24 2026-08-23): médias de eventos independentes/mês.
TARGET_MONTHS = {
    "E1": 8.1,   # média 2,47 indep/mês → n_indep>=20
    "E2": 16.7,  # média 1,20 indep/mês → n_indep>=20
}

BASE = os.path.join(os.path.dirname(__file__), "..", "data", "derivatives", "binance_vision")
METRICS_LONG = os.path.join(BASE, "metrics", "BTCUSDT_metrics_long.csv")
DAILY_DIR = os.path.join(BASE, "metrics", "BTCUSDT", "daily")


def latest_local_cutoff() -> pd.Timestamp:
    """Última data coberta pelos nossos dados locais de Camada A."""
    if os.path.isdir(DAILY_DIR):
        files = sorted(f for f in os.listdir(DAILY_DIR) if f.endswith(".csv"))
        if files:
            last_name = files[-1]  # AAA-MM-DD.csv
            try:
                return pd.Timestamp(datetime.strptime(last_name, "%Y-%m-%d.csv"), tz="UTC")
            except ValueError:
                pass
    if os.path.exists(METRICS_LONG):
        keepcols = ["create_time"]
        df = pd.read_csv(METRICS_LONG, usecols=keepcols)
        ts = pd.to_datetime(df["create_time"], utc=True).max()
        return pd.Timestamp(ts, tz="UTC")
    return pd.Timestamp.now(timezone.utc)


def main():
    print("📡 Q24 — prontidão da amostra fora-da-amostra (Sem retorno, só cobertura)")
    print(f"   Cutoff da janela geradora (Q16 longa): {OLD_CUTOFF:%Y-%m-%d %H:%M} UTC\n")

    now = pd.Timestamp.now(timezone.utc)
    last = latest_local_cutoff()
    print(f"   Cobertura local atual: {last:%Y-%m-%d} (hoje: {now:%Y-%m-%d})")

    if last <= OLD_CUTOFF:
        fresh_days = 0
        print("   ⚠️  A cobertura local ainda NÃO passou do cutoff. Rode o downloader:")
        print("       backend/scripts/download_binance_vision_metrics.py")
        print("   (e, para os meses fechados, espere os arquivos monthly futuros do Binance Vision)")
        fresh_months = 0.0
    else:
        fresh_days = (last - OLD_CUTOFF).total_seconds() / 86400.0
        fresh_months = fresh_days / 30.44
        print(f"   Amostra nova: {fresh_days:.1f} dias (~{fresh_months:.1f} meses) desde o cutoff")

    print("\n   Metas pré-registradas (viabilidade 2026-08-23):")
    for side, target_months in TARGET_MONTHS.items():
        if fresh_months >= target_months:
            print(f"   - {side}: ✅ PRONTO ({fresh_months:.1f} meses >= {target_months:.1f}) — revalidar o evento em amostra nova")
        else:
            remaining = target_months - fresh_months
            est_date = OLD_CUTOFF + pd.Timedelta(days=target_months * 30.44)
            print(f"   - {side}: ⏳ não pronto ({fresh_months:.1f} meses de {target_months:.1f}) — falta ~{remaining:.1f} meses (≈ {est_date:%Y-%m})")

    print("\n   Ao estar PRONTO, validar com a lógica da Q16/Q18:")
    print("   - horizontes 4h/8h(primário)/24h · custo 10bp · n_indep>=20 · fatias >=2/3 · coerência cross-horizonte")
    print("   - comparar contra controle do BTC no mesmo período · sinal pedido E1=-1, E2=+1")
    print("   - NUNCA usar a janela <= 2026-08-21 como evidência da hipótese")


if __name__ == "__main__":
    main()