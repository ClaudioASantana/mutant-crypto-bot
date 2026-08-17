from app.domain.entities.market import Signal, AccountState, RiskEvaluation, RiskDecision, SignalType

def evaluate_risk(signal: Signal, account: AccountState) -> RiskEvaluation:
    if signal.type == SignalType.NONE:
        return RiskEvaluation(
            decision=RiskDecision.BLOCKED,
            reason="No signal to execute",
            stake=0.0
        )

    dynamic_stop = -account.daily_stop_loss
    if account.highest_daily_pnl >= account.daily_stop_gain:
        dynamic_stop = account.highest_daily_pnl - account.daily_stop_gain

    if account.daily_pnl <= dynamic_stop:
        return RiskEvaluation(
            decision=RiskDecision.BLOCKED,
            reason=f"Daily dynamic stop reached: {account.daily_pnl} <= {dynamic_stop}",
            stake=0.0
        )

    # Stake fixo: Martingale/Gale removido. Cada operação usa o mesmo risco base.
    calculated_stake = account.stake_initial

    return RiskEvaluation(
        decision=RiskDecision.APPROVED,
        reason="Risk constraints passed",
        stake=calculated_stake
    )
