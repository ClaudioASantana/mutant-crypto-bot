import asyncio
import logging
import pandas as pd
from typing import Dict, Any
from celery import shared_task
from app.infrastructure.ai_filter_openai import OpenAIFilter

logger = logging.getLogger(__name__)

# Reutilizar a instancia para aproveitar pool HTTP/conexões
_ai_filter_instance = None

def get_ai_filter():
    global _ai_filter_instance
    if _ai_filter_instance is None:
        _ai_filter_instance = OpenAIFilter()
    return _ai_filter_instance

@shared_task(name="evaluate_trade_async", bind=True, max_retries=3)
def evaluate_trade_async(self, df_records: list, strategy_name: str) -> Dict[str, Any]:
    """
    Tarefa assíncrona do Celery para avaliar um trade pela IA.
    Recebe os registros em formato de lista (dicionários) porque DataFrames
    não são serializáveis nativamente em JSON para a fila do Celery.
    """
    try:
        # Reconstrói o DataFrame a partir da lista
        df = pd.DataFrame.from_records(df_records)
        
        ai_filter = get_ai_filter()
        
        # Como o make_decision é async e Celery é sync, precisamos de um event loop
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
        result = loop.run_until_complete(ai_filter.make_decision(df, strategy_name))
        return result
        
    except Exception as exc:
        logger.error(f"Erro ao processar a avaliação da IA (tentativa {self.request.retries}): {exc}")
        # Tenta novamente em caso de falha de timeout/rede
        raise self.retry(exc=exc, countdown=5 * (self.request.retries + 1))
