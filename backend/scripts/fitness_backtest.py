#!/usr/bin/env python3
"""
🧬 Fitness Backtest - Mutant Crypto Bot
=========================================
Simula o seletor dinamico de personalidades comparando:
  - Portfolio ESTATICO (cada personalidade opera sozinha)
  - Portfolio DINAMICO  (seletor de fitness + histerese escolhe quem opera)

Uso: python scripts/fitness_backtest.py
"""

import sys
import os
import importlib.util
import numpy as np
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(SCRIPT_DIR, "..")))

# Carregar deep_backtest como modulo (sem executar seu main)
spec = importlib.util.spec_from_file_location("deep_backtest", os.path.join(SCRIPT_DIR, "deep_backtest.py"))
db = importlib.util.module_from_spec(spec)
spec.loader.exec_module(db)
fetch_klines   = db.fetch_klines
STRATEGIES     = db.STRATEGIES

from app.models.performance import PersonalityPerformance
from app.engines.technical_analysis import (
    apply_indicators, eval_three_candles_composite
)

# ═══════════════════════════════════════════════════════════════════════
# Configuracao
# ═══════════════════════════════════════════════════════════════════════
SYMBOL = "BTCUSDT"
DAYS   = 7

# Stake / alavancagem identicos ao deep_backtest
STAKE_USD   = 100.0
LEVERAGE    = 10

# Constantes do seletor (devem espelhar bot_instance.py)
SELECTOR_HYSTERESIS              = 2.0
SELECTOR_MIN_TRADES              = 3
SELECTOR_MAX_CONSECUTIVE_LOSSES  = 4
SELECTOR_RESET_AFTER_SECONDS     = 4 * 3600

# Personalidades simuladas (definidas a mao, para teste)
PERSONALITIES = [
    {"name": "Cirurgiao",   "strategy": "Wyckoff_SMC", "timeframe": 900,
     "risk_config": {"sl_multiplier": 1.5, "tp_multiplier": 8.0}},
    {"name": "Trabalhador", "strategy": "SMC",          "timeframe": 300,
     "risk_config": {"sl_multiplier": 1.5, "tp_multiplier": 3.0}},
]

# ═══════════════════════════════════════════════════════════════════════
# Engine de execucao (espelha o on_tick do BotInstance, offline)
# ═══════════════════════════════════════════════════════════════════════

class TradeAccount:
    """Conta de um papel (personalidade ou simulacao)."""
    def __init__(self, name: str):
        self.name = name
        self.balance = 200.0
        self.pnl = 0.0
        self.wins = 0
        self.losses = 0
        self.trades = 0
        self.signals = 0  # Contador de sinais que resultaram em trades
        self.positions = []     # trades abertos
        self.history = []       # trades fechados
        self.equity_curve = []  # (epoch, equity)

    def open_trade(self, direction: str, tf: int, epoch: int, entry: float, sl: float, tp: float, name: str):
        if len(self.positions) > 0:
            return  # apenas 1 posicao por vez (espelha active_trade_ids)
        self.positions.append({
            "id": self.trades, "direction": direction, "tf": tf, "name": name,
            "entry": entry, "sl": sl, "tp": tp
        })
        # Incrementa o contador de sinais que resultaram em trades APENAS se o trade foi aberto
        self.signals += 1

    def manage_trades(self, epoch: int, high: float, low: float) -> list:
        """Checa SL/TP usando a vela inteira. Retorna trades fechados."""
        closed = []
        for pos in list(self.positions):
            if pos["direction"] == "CALL":
                if low <= pos["sl"]:
                    closed.append(self._close(pos, epoch, pos["sl"], False))
                elif high >= pos["tp"]:
                    closed.append(self._close(pos, epoch, pos["tp"], True))
            else:
                if high >= pos["sl"]:
                    closed.append(self._close(pos, epoch, pos["sl"], False))
                elif low <= pos["tp"]:
                    closed.append(self._close(pos, epoch, pos["tp"], True))
        for c in closed:
            self.positions.remove(c["pos"])
        return closed

    def _close(self, pos, epoch, exit_price, is_win):
        entry = pos["entry"]
        if pos["direction"] == "CALL":
            pct_tp = (pos["tp"] - entry) / entry
            pct_sl = (entry - pos["sl"]) / entry
        else:
            pct_tp = (entry - pos["tp"]) / entry
            pct_sl = (pos["sl"] - entry) / entry
        pnl = (STAKE_USD * LEVERAGE * pct_tp) if is_win else -(STAKE_USD * LEVERAGE * pct_sl)
        self.pnl += pnl
        if is_win:
            self.wins += 1
        else:
            self.losses += 1
        self.trades += 1
        self.balance += pnl
        self.equity_curve.append((epoch, round(self.balance, 2)))
        self.history.append({"pnl": pnl, "is_win": is_win, "exit_price": exit_price, "exit_epoch": epoch})
        return {"pos": pos, "pnl": pnl, "is_win": is_win, "exit_price": exit_price, "exit_epoch": epoch}

# ═══════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════

def build_signal(df_sub, strategy_name, debug_enabled=False):
    """Retorna "CALL"/"PUT"/"NONE" aplicando a estrategia + confluencia de 3 velas."""
    if debug_enabled: print(f"    -> build_signal: df_sub len={len(df_sub)}, strategy={strategy_name}")
    sig = STRATEGIES[strategy_name](df_sub)
    if debug_enabled: print(f"    -> Estratégia {strategy_name} retornou: {sig}")
    if sig == "NONE":
        return "NONE"
    # Confluencia 3 velas (filtro positivo, igual ao live AI+3V)
    pattern = eval_three_candles_composite(df_sub, require_confluence=True)
    if debug_enabled: print(f"    -> Padrão 3 velas: {pattern}")
    if pattern == sig:
        return sig
    return "NONE"

def compute_sl_tp(entry, atr, direction, risk_cfg):
    sl_mult = risk_cfg.get("sl_multiplier", 1.5)
    tp_mult = risk_cfg.get("tp_multiplier", 8.0)
    if direction == "CALL":
        return entry - atr * sl_mult, entry + atr * tp_mult
    return entry + atr * sl_mult, entry - atr * tp_mult

def build_epoch_index(frame) -> np.ndarray:
    """Converte o index (datetime) em array de epoch seconds (UTC)."""
    # O index do pandas e um DatetimeIndex, que internamente armazena em milissegundos.
    # Para epoch em segundos, dividimos por 1000.
    return frame.index.astype(np.int64) // 1000

def pick_active(trackers, current_active):
    """Replica _select_best_personality + histerese do BotInstance."""
    eligible = []
    for name, perf in trackers.items():
        if perf.consecutive_losses >= SELECTOR_MAX_CONSECUTIVE_LOSSES:
            continue
        if perf.trades_count < SELECTOR_MIN_TRADES:
            # Dar um bônus maior para incentivar a exploração de novas personalidades
            eligible.append((name, 1.0))
        else:
            eligible.append((name, perf.fitness))
    if not eligible:
        return current_active or next(iter(trackers))

    best_name, best_fitness = max(eligible, key=lambda x: x[1])
    if current_active in trackers:
        cur_fitness = trackers[current_active].fitness
        if (best_fitness - cur_fitness) < SELECTOR_HYSTERESIS:
            return current_active
    return best_name

# ═══════════════════════════════════════════════════════════════════════
# Simulacoes
# ═══════════════════════════════════════════════════════════════════════

def simulate_static(personality, frames, m5_index, m5_epochs, debug=False):
    """Uma personalidade opera sozinha."""
    tf = personality["timeframe"]
    frame = frames[tf]
    frame_epochs = build_epoch_index(frame)
    acct  = TradeAccount(personality["name"])
    start_idx = 50
    signals_generated = 0

    for i in range(start_idx, len(m5_index)):
        epoch = int(m5_epochs[i])
        row = frames[300].iloc[i]

        # 1. Gerenciar trades abertos
        acct.manage_trades(epoch, row["high"], row["low"])

        # 2. Avaliar sinal no fechamento do bucket do timeframe da personalidade
        #    Estratégia: detectar mudança de bucket comparando com a próxima vela.
        #    Se a próxima vela pertencer a um bucket_id diferente, então esta vela
        #    é a última do bucket atual.
        current_bucket_id = epoch // tf

        # Obter o epoch da próxima vela M5 (se existir)
        if i + 1 < len(m5_epochs):
            next_epoch = int(m5_epochs[i + 1])
            next_bucket_id = next_epoch // tf

            is_bucket_close = (current_bucket_id != next_bucket_id)
            if debug and i % 100 == 0: # Log a cada 100 iterações para não poluir
                print(f"[{datetime.fromtimestamp(epoch, tz=None).strftime('%H:%M')}] epoch={epoch}, tf={tf}, current_bucket_id={current_bucket_id}, next_bucket_id={next_bucket_id}, is_bucket_close={is_bucket_close}")
        else:
            # Última vela, considerar como fechamento de bucket
            is_bucket_close = True
            if debug:
                print(f"[{datetime.fromtimestamp(epoch, tz=None).strftime('%H:%M')}] Última vela, considerando como fechamento de bucket.")

        if not is_bucket_close:
            continue

        # posicao do bucket atual no frame do tf (ponto de abertura do bucket em formacao)
        bucket_open = (epoch // tf) * tf
        fidx = int(np.searchsorted(frame_epochs, bucket_open, side="left"))
        if fidx == 0 or fidx >= len(frame_epochs) or frame_epochs[fidx] != bucket_open:
            # Bucket ainda nao existe no frame (ou sem dados suficientes)
            if debug:
                print(f"[{datetime.fromtimestamp(epoch, tz=None).strftime('%H:%M')}] bucket nao encontrado no frame (fidx={fidx}), skip")
            continue

        # Velas FECHADAS ate agora: indices [0, fidx)
        sub = frame.iloc[:fidx]
        # if len(sub) < start_idx:
        #     if debug: print(f"[{datetime.fromtimestamp(epoch, tz=None).strftime('%H:%M')}] len(sub) < start_idx, skip")
        #     continue

        sig_raw = STRATEGIES[personality["strategy"]](sub)
        if sig_raw == "NONE" and debug:
            print(f"[{datetime.fromtimestamp(epoch, tz=None).strftime('%H:%M')}] {personality['name']}: Sinal BRUTO = NONE")

        sig = build_signal(sub, personality["strategy"])
        if sig == "NONE":
            if debug and sig_raw != "NONE":
                print(f"[{datetime.fromtimestamp(epoch, tz=None).strftime('%H:%M')}] {personality['name']}: Sinal bloqueado pela confluencia 3V")
            continue
        signals_generated += 1
        if debug: print(f"[{datetime.fromtimestamp(epoch, tz=None).strftime('%H:%M')}] SINAL GERADO: {personality['name']} -> {sig}")

        # Entrada = close da ultima vela fechada
        last = frame.iloc[fidx - 1]
        entry = float(last["close"])
        atr = last.get("ATRr_14", entry * 0.005)
        if atr != atr or atr == 0:
            atr = entry * 0.005
        sl, tp = compute_sl_tp(entry, float(atr), sig, personality["risk_config"])
        acct.open_trade(sig, tf, epoch, entry, sl, tp, personality["name"])

    acct.signals = signals_generated
    return acct

def simulate_dynamic(personalities, frames, m5_index, m5_epochs, debug=False):
    """Seletor de fitness escolhe quem pode operar."""

    # Cada personalidade tem sua propria conta de trade
    personality_accounts = {p["name"]: TradeAccount(p["name"]) for p in personalities}

    trackers = {p["name"]: PersonalityPerformance(personality_name=p["name"], symbol=SYMBOL) for p in personalities}
    frame_epochs_map = {tf: build_epoch_index(frames[tf]) for tf in frames}
    current_active = personalities[0]["name"]
    start_idx = 50
    switches = 0
    signals_total = 0

    for i in range(start_idx, len(m5_index)):
        epoch = int(m5_epochs[i])
        row = frames[300].iloc[i]

        # 1. Gerenciar trades de TODAS as personalidades
        all_closed_trades = []
        for p_name, acct in personality_accounts.items():
            closed_for_p = acct.manage_trades(epoch, row["high"], row["low"])
            all_closed_trades.extend(closed_for_p)

        # 2. Atualizar trackers de quem teve trade fechado nesta vela
        for c in all_closed_trades:
            name = c["pos"]["name"]  # dono do trade gravado na abertura
            perf = trackers[name]
            perf.record_trade(c["is_win"], c["pnl"])
            perf.last_update = epoch

        # 3. Selecionar melhor personalidade (fitness + histerese)
        new_active = pick_active(trackers, current_active)
        if new_active != current_active:
            switches += 1
            if debug:
                print(f"  🔄 [{datetime.fromtimestamp(epoch, tz=None).strftime('%d/%m %H:%M')}] Troca: {current_active} -> {new_active}")
                # Mostrar PnL parcial de cada conta na troca
                for p_name, acct in personality_accounts.items():
                    print(f"      PnL {p_name}: ${acct.pnl:.2f} (trades: {acct.trades})")
            current_active = new_active

        # 4. Shadow Mode: avaliar sinal de TODAS as personalidades, executar APENAS a ativa
        for p_name, personality in {p["name"]: p for p in personalities}.items():
            acct = personality_accounts[p_name]
            tf = personality["timeframe"]
            frame = frames[tf] # O frame de velas do TF da personalidade
            frame_epochs = frame_epochs_map[tf] # O index de epochs do TF da personalidade

            # Checar se este epoch M5 corresponde ao fechamento de um bucket da PERSONALIDADE
            current_personality_bucket_id = epoch // tf

            if i + 1 < len(m5_epochs):
                next_m5_epoch = int(m5_epochs[i + 1])
                next_personality_bucket_id = next_m5_epoch // tf
                is_bucket_close = (current_personality_bucket_id != next_personality_bucket_id)
            else:
                # Última vela M5, considerar como fechamento do bucket da personalidade
                is_bucket_close = True

            if not is_bucket_close:
                continue

            # A lógica de `fidx` é a mesma do simulate_static, usando os dados da personalidade
            bucket_open = current_personality_bucket_id * tf
            fidx = int(np.searchsorted(frame_epochs, bucket_open, side="left"))
            if fidx == 0 or fidx >= len(frame_epochs) or frame_epochs[fidx] != bucket_open:
                # Se o bucket nao existe ou nao esta completo no frame da personalidade, pular
                continue

            sub = frame.iloc[:fidx]
            sig = build_signal(sub, personality["strategy"], debug_enabled=debug)
            if sig == "NONE":
                continue

            # Contar o sinal apenas para a personalidade ativa
            if p_name == current_active:
                acct.signals += 1

            # Executar trade APENAS se e a personalidade ativa e nao tem trade aberto
            if p_name == current_active and len(acct.positions) == 0:
                last = frame.iloc[fidx - 1]
                entry = float(last["close"])
                atr = last.get("ATRr_14", entry * 0.005)
                if atr != atr or atr == 0:
                    atr = entry * 0.005
                sl, tp = compute_sl_tp(entry, float(atr), sig, personality["risk_config"])
                # Passar o nome da personalidade para identificar o dono do trade
                acct.open_trade(sig, tf, epoch, entry, sl, tp, p_name)

    # Agregação final para relatorio
    total_dynamic_account = TradeAccount("Dynamic Aggregated")
    for acct in personality_accounts.values():
        total_dynamic_account.pnl += acct.pnl
        total_dynamic_account.wins += acct.wins
        total_dynamic_account.losses += acct.losses
        total_dynamic_account.trades += acct.trades
        total_dynamic_account.signals += acct.signals if hasattr(acct, 'signals') else 0

    total_dynamic_account.balance = total_dynamic_account.balance + total_dynamic_account.pnl
    # total_dynamic_account.signals = signals_total # Removido, será agregado por acct.signals

    return {
        "account": total_dynamic_account,
        "trackers": trackers,
        "final_active": current_active,
        "switches": switches,
    }

def report(name, acct):
    print(f"\n  📊 {name}")
    print(f"  ─────────────────────────────────────────────")
    print(f"  Sinais gerados: {getattr(acct, 'signals', 'n/a')} | Trades: {acct.trades} | Wins: {acct.wins} | Losses: {acct.losses}")
    wr = (acct.wins / acct.trades * 100) if acct.trades else 0.0
    print(f"  Win Rate: {wr:.2f}% | PnL Total: ${acct.pnl:.2f} | Saldo Final: ${acct.balance:.2f}")

def main():
    print(f"\n🧬 Mutant Crypto Bot -- Fitness Backtest Engine")
    print(f"   Simbolo: {SYMBOL} | Periodo: {DAYS} dias | Setup: {', '.join(p['name'] for p in PERSONALITIES)}\n")

    # Baixar dados M5 e M15
    frames = {}
    for tf_name, (interval, tf_sec) in [("M5", ("5m", 300)), ("M15", ("15m", 900))]:
        df = fetch_klines(SYMBOL, interval, DAYS)
        frames[tf_sec] = apply_indicators(df)
        print(f"   {tf_name}: {len(df)} velas (ATR calculado)")

    m5_index = frames[300].index
    m5_epochs = build_epoch_index(frames[300])

    print(f"\n{'='*60}")
    print("  SIMULACAO ESTATICA (cada personalidade sozinha)")
    print(f"{'='*60}")
    static_results = {}
    for p in PERSONALITIES:
        print(f"\n  Rodando {p['name']} ({p['strategy']} M{p['timeframe']//60})...")
        acct = simulate_static(p, frames, m5_index, m5_epochs, debug=True)
        static_results[p["name"]] = acct
        report(p["name"], acct)

    print(f"\n{'='*60}")
    print("  SIMULACAO DINAMICA (seletor de fitness + histerese)")
    print(f"{'='*60}")
    dyn = simulate_dynamic(PERSONALITIES, frames, m5_index, m5_epochs, debug=True)
    report(f"DINAMICO ({dyn['final_active']} ativo no final)", dyn["account"])
    print(f"\n  Trocas de personalidade: {dyn['switches']}")

    print(f"\n{'='*60}")
    print("  COMPARATIVO")
    print(f"{'='*60}")
    best_static_name = max(static_results, key=lambda k: static_results[k].pnl)
    best_static = static_results[best_static_name]
    print(f"  Melhor estatico: {best_static_name} -> ${best_static.pnl:.2f}")
    print(f"  Dinamico       : -> ${dyn['account'].pnl:.2f}")
    delta = dyn["account"].pnl - best_static.pnl
    verdict = "✅ SUPERIOR ao melhor estatico" if delta > 0 else "❌ Deixou a desejar vs melhor estatico"
    print(f"  Diferenca: ${delta:.2f} | {verdict}")

    # Persistir relatorio
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_path = os.path.join(SCRIPT_DIR, f"fitness_report_{ts}.txt")
    lines = [
        f"FITNESS BACKTEST - {SYMBOL} | {DAYS} dias | {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}",
        "=" * 60,
    ]
    for name, acct in static_results.items():
        lines.append(f"ESTATICO {name}: trades={acct.trades} pnl=${acct.pnl:.2f}")
    lines.append(f"DINAMICO: trades={dyn['account'].trades} pnl=${dyn['account'].pnl:.2f} trocas={dyn['switches']}")
    lines.append(f"VEREDITO: {verdict} (delta ${delta:.2f})")
    with open(report_path, "w") as f:
        f.write("\n".join(lines))
    print(f"\n  Relatorio salvo em: {report_path}\n")

if __name__ == "__main__":
    main()