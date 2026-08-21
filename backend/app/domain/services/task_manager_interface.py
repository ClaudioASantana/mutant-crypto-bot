from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class AbstractTaskManager(ABC):
    """
    Interface para enfileirar tarefas assíncronas (como análise da IA)
    e checar os resultados.
    """
    
    @abstractmethod
    def enqueue_ia_evaluation(self, df_records: list, strategy_name: str) -> str:
        """Enfileira a avaliação da IA e retorna um task_id."""
        pass
        
    @abstractmethod
    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """
        Retorna o status da task.
        Exemplo de retorno:
        {"status": "PENDING" | "PROCESSING" | "SUCCESS" | "FAILED", "result": None | dict}
        """
        pass
