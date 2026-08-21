import logging
from typing import Dict, Any
from app.domain.services.task_manager_interface import AbstractTaskManager
from app.infrastructure.queue.tasks import evaluate_trade_async
from celery.result import AsyncResult

logger = logging.getLogger(__name__)

class CeleryTaskManager(AbstractTaskManager):
    """
    Implementação concreta do Task Manager usando Celery.
    Isola o domínio de saber sobre a infraestrutura específica da fila.
    """
    
    def enqueue_ia_evaluation(self, df_records: list, strategy_name: str) -> str:
        """Envia a avaliação para o Celery."""
        try:
            task = evaluate_trade_async.delay(df_records, strategy_name)
            logger.info(f"Tarefa de avaliação da IA enfileirada: {task.id}")
            return task.id
        except Exception as e:
            logger.error(f"Falha ao enfileirar tarefa no Celery: {e}")
            return ""

    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """Consulta o status da task no backend do Celery (Redis)."""
        if not task_id:
            return {"status": "FAILED", "result": None}
            
        try:
            res = AsyncResult(task_id)
            state = res.state
            
            # Mapeamento do status Celery para nosso domínio
            if state == "SUCCESS":
                return {"status": "SUCCESS", "result": res.result}
            elif state == "FAILURE" or state == "REVOKED":
                return {"status": "FAILED", "result": None}
            else:
                return {"status": "PROCESSING", "result": None}
                
        except Exception as e:
            logger.error(f"Erro ao consultar status da tarefa {task_id}: {e}")
            return {"status": "FAILED", "result": None}
