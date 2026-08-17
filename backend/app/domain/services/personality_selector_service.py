"""
Serviço de Domínio para Seleção de Personalidade

Clean Architecture: esta classe contém regras de negócio puras relacionadas
à seleção da melhor personalidade para operar, baseada em métricas de
performance e lógica de histerese. Não depende de nenhuma camada externa
(como infraestrutura ou API).
"""
import time
import logging
from typing import Dict, List, Tuple

from app.domain.entities.performance import PersonalityPerformance

logger = logging.getLogger(__name__)

class PersonalitySelectorService:
    def __init__(self,
                 reset_after_seconds: int,
                 min_trades_for_fitness: int,
                 max_consecutive_losses: int,
                 hysteresis_margin: float):
        self.reset_after_seconds = reset_after_seconds
        self.min_trades_for_fitness = min_trades_for_fitness
        self.max_consecutive_losses = max_consecutive_losses
        self.hysteresis_margin = hysteresis_margin

    def select_best(self,
                    performance_trackers: Dict[str, PersonalityPerformance],
                    current_active_name: str | None) -> str | None:
        """
        Seleciona a personalidade com melhor aptidão (fitness) para operar.
        Retorna o nome da personalidade escolhida ou None se nenhuma for elegível.
        """
        if not performance_trackers:
            logger.warning("Nenhum tracker de performance para selecionar personalidade.")
            return current_active_name

        # 1. Reset de janela de performance se for muito antiga
        now = time.time()
        for perf in performance_trackers.values():
            if perf.last_update and (now - perf.last_update) > self.reset_after_seconds:
                logger.info(f"[{perf.symbol}] Reiniciando janela de performance para {perf.personality_name} (inatividade).")
                perf.reset_performance() # Método a ser criado no modelo
                perf.last_update = now

        # 2. Coletar fitness das personalidades elegíveis
        eligible: List[Tuple[str, float]] = []
        for name, perf in performance_trackers.items():
            if perf.consecutive_losses >= self.max_consecutive_losses:
                logger.warning(f"[{perf.symbol}] Personalidade '{name}' desativada por {perf.consecutive_losses} perdas seguidas.")
                continue
            if perf.trades_count < self.min_trades_for_fitness:
                eligible.append((name, 0.1))  # Bônus de exploração para novas personalidades
            else:
                eligible.append((name, perf.fitness))

        if not eligible:
            logger.warning("Nenhuma personalidade elegível encontrada.")
            return current_active_name # Mantém a atual se nenhuma outra é elegível

        # 3. Selecionar a de maior fitness
        best_name, best_fitness = max(eligible, key=lambda x: x[1])

        # 4. Aplicar Histerese para evitar trocas constantes
        if current_active_name and current_active_name in performance_trackers:
            current_active_fitness = performance_trackers[current_active_name].fitness
            # Manter a atual se a melhor não for suficientemente superior
            if (best_fitness - current_active_fitness) < self.hysteresis_margin:
                logger.debug(f"Histerese ativa: mantendo '{current_active_name}' (diferença de fitness < {self.hysteresis_margin})")
                return current_active_name

        if best_name != current_active_name:
            logger.info(f"Seleção de personalidade: trocando de '{current_active_name}' para '{best_name}' (Fitness: {best_fitness:.2f})")

        return best_name
