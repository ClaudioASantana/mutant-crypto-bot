import logging
import json
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone

# Variável de contexto para armazenar o ID de correlação da requisição/trade atual
correlation_id: ContextVar[str] = ContextVar("correlation_id", default="")

def generate_correlation_id() -> str:
    """Gera um novo UUID para servir como Correlation ID e o define no contexto atual."""
    new_id = str(uuid.uuid4())
    correlation_id.set(new_id)
    return new_id

class JSONFormatter(logging.Formatter):
    """
    Formatador de Log estruturado em JSON.
    Injeta automaticamente o correlation_id atual em todas as mensagens de log.
    """
    def format(self, record: logging.LogRecord) -> str:
        log_record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": correlation_id.get(),
            "module": record.module,
            "funcName": record.funcName,
            "line": record.lineno,
        }
        
        # Adiciona exc_info caso haja uma exceção sendo logada
        if record.exc_info:
            log_record["exc_info"] = self.formatException(record.exc_info)
            
        return json.dumps(log_record)

def setup_logger(name: str = "mutant_crypto_bot", level: int = logging.INFO) -> logging.Logger:
    """
    Configura e retorna um logger raiz que cospe JSON para stdout.
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Previne adicionar múltiplos handlers se for chamado mais de uma vez
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = JSONFormatter()
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
    return logger

# Instância padrão que pode ser importada
app_logger = setup_logger()
