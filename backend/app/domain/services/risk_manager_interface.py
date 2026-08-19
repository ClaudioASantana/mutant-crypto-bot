"""
Interface (Port) para o Gerenciador de Risco.

Define o contrato para qualquer implementação de gerenciamento de risco,
seguindo o Princípio de Inversão de Dependência (DIP).
"""
from abc import ABC, abstractmethod
from typing import Dict, Any

from app.domain.entities.market import AccountState, RiskEvaluation, Signal
from app.domain.entities.personality import Personality


class AbstractRiskManager(ABC):
    """
    Define os métodos que um gerenciador de risco deve implementar.
    """

    @abstractmethod
    def evaluate_pre_trade_risk(self, signal: Signal, account: AccountState, personality: Personality) -> RiskEvaluation:
        """
        Avalia o risco antes de abrir um trade, considerando o estado da conta
        e as configurações de risco da personalidade.

        Args:
            signal: O sinal de trade proposto.
            account: O estado atual da conta.
            personality: A personalidade que está propondo o trade.

        Returns:
            Um objeto RiskEvaluation indicando se o trade é aprovado ou bloqueado.
        """
        pass

    @abstractmethod
    def calculate_position_sizing(self, personality: Personality, current_balance: float, current_price: float, atr: float, symbol: str) -> Dict[str, Any]:
        """
        Calcula o tamanho da posição (margem, quantidade) com base na
        estratégia de dimensionamento da posição da personalidade.

        Args:
            personality: A personalidade para a qual o dimensionamento está sendo calculado.
            current_balance: Saldo atual disponível na conta.
            current_price: Preço atual do ativo.
            atr: Average True Range atual do ativo, para dimensionamento baseado em volatilidade.
            symbol: Símbolo do ativo (ex: "BTC/USDT"), necessário para algumas lógicas.

        Returns:
            Um dicionário contendo "margin_usdt" e "qty" (quantidade do ativo).
        """
        pass

    @abstractmethod
    def calculate_sl_tp(self, personality: Personality, entry_price: float, atr: float, direction: str) -> Dict[str, float]:
        """
        Calcula os preços de Stop Loss (SL) e Take Profit (TP) com base nas
        configurações de risco da personalidade e no ATR.

        Args:
            personality: A personalidade para a qual os preços SL/TP estão sendo calculados.
            entry_price: Preço de entrada do trade.
            atr: Average True Range atual do ativo.
            direction: Direção do trade ("CALL" ou "PUT").

        Returns:
            Um dicionário contendo "sl_price" e "tp_price".
        """
        pass

    @abstractmethod
    def manage_trailing_stop(self, trade: Dict[str, Any], current_price: float, personality: Personality) -> Dict[str, Any]:
        """
        Gerencia a lógica de Trailing Stop para um trade aberto.
        Atualiza o SL do trade se as condições forem atendidas.

        Args:
            trade: O dicionário que representa o trade aberto.
            current_price: O preço atual do ativo.
            personality: A personalidade associada ao trade.

        Returns:
            O dicionário do trade atualizado com o novo SL (se alterado).
        """
        pass

    @abstractmethod
    def check_time_stop(self, trade: Dict[str, Any], current_epoch: int, personality: Personality) -> bool:
        """
        Verifica se um trade deve ser fechado por limite de tempo.

        Args:
            trade: O dicionário que representa o trade aberto.
            current_epoch: O epoch atual.
            personality: A personalidade associada ao trade.

        Returns:
            True se o trade deve ser fechado por time stop, False caso contrário.
        """
        pass