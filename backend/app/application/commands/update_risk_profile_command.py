from pydantic import BaseModel

class UpdateRiskProfileCommand(BaseModel):
    """
    Comando para atualizar as configurações de risco da conta/personalidade.
    """
    daily_stop_loss: float
    daily_stop_gain: float
    stake_initial: float
