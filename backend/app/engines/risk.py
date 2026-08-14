from app.models.market import Signal, AccountState, RiskEvaluation, RiskDecision, SignalType

def evaluate_risk(signal: Signal, account: AccountState) -> RiskEvaluation:
    if signal.type == SignalType.NONE:
        return RiskEvaluation(
            decision=RiskDecision.BLOCKED,
            reason="No signal to execute",
            stake=0.0,
            gale_level=0
        )
        
    dynamic_stop = -account.daily_stop_loss
    if account.highest_daily_pnl >= account.daily_stop_gain:
        dynamic_stop = account.highest_daily_pnl - account.daily_stop_gain
        
    if account.daily_pnl <= dynamic_stop:
        return RiskEvaluation(
            decision=RiskDecision.BLOCKED,
            reason=f"Daily dynamic stop reached: {account.daily_pnl} <= {dynamic_stop}",
            stake=0.0,
            gale_level=0
        )
        
    if account.current_gale_level > account.max_gale:
        return RiskEvaluation(
            decision=RiskDecision.BLOCKED,
            reason=f"Max gale level exceeded: {account.current_gale_level} > {account.max_gale}",
            stake=0.0,
            gale_level=0
        )
        
    calculated_stake = account.stake_initial * (2 ** account.current_gale_level)
    
    return RiskEvaluation(
        decision=RiskDecision.APPROVED,
        reason="Risk constraints passed",
        stake=calculated_stake,
        gale_level=account.current_gale_level
    )
