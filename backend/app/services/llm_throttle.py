"""
Serviço global de throttling para chamadas à API de IA (LLM).

Centraliza o rate limiting e o retry com backoff exponencial para todas as
chamadas de IA do bot (AI Filter e Agente RAG), evitando erros 429
(RATE_LIMIT_EXCEEDED / RESOURCE_EXHAUSTED) do provedor (ex: Google Gemini
via cloudcode-pa.googleapis.com, conforme o erro visto no Manifest).

Configuração via variáveis de ambiente:
  LLM_MAX_REQUESTS_PER_MINUTE  (default: 10)  - teto de chamadas por minuto
  LLM_MIN_INTERVAL_SECONDS     (default: 5)   - espaçamento mínimo entre chamadas
  LLM_MAX_RETRIES              (default: 4)   - tentativas com backoff exponencial
"""

import asyncio
import logging
import os
import time

from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)

# Import defensivo para RateLimitError, lidando com múltiplas versões
# da biblioteca `openai`.
try:
    # OpenAI v1.x
    from openai import RateLimitError as OpenAIRateLimitError
except ImportError:
    try:
        # OpenAI v0.x
        from openai.error import RateLimitError as OpenAIRateLimitError
    except ImportError:
        # Se falhar, define uma classe dummy para não quebrar o `isinstance`
        class OpenAIRateLimitError(Exception):
            pass


def is_rate_limit_error(exc: BaseException) -> bool:
    """Detecta erros de rate limit (HTTP 429 / RESOURCE_EXHAUSTED) de forma genérica."""
    if isinstance(exc, OpenAIRateLimitError):
        return True
    text = str(exc).lower()
    markers = (
        "429",
        "rate_limit",
        "rate limit",
        "resource_exhausted",
        "exhausted your capacity",
        "quota",
        "too many requests",
    )
    return any(m in text for m in markers)


class LLMRateLimiter:
    """Rate limiter assíncrono global para chamadas de IA.

    Usa uma janela deslizante de 60s + um espaçamento mínimo entre chamadas
    consecutivas, serializando as requisições quando necessário para não
    estourar a cota do provedor.
    """

    def __init__(
        self,
        max_requests_per_minute: int = 10,
        min_interval_seconds: float = 5.0,
    ):
        self.max_requests_per_minute = max(1, max_requests_per_minute)
        self.min_interval_seconds = max(0.0, min_interval_seconds)
        self._timestamps: list[float] = []
        self._last_call: float = 0.0
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Aguarda até que a chamada de IA possa ser feita sem estourar o limite."""
        async with self._lock:
            now = time.monotonic()

            # Espaçamento mínimo entre chamadas consecutivas
            if self._last_call and (now - self._last_call) < self.min_interval_seconds:
                await asyncio.sleep(self.min_interval_seconds - (now - self._last_call))
                now = time.monotonic()

            # Janela deslizante de 60s
            self._timestamps = [t for t in self._timestamps if now - t < 60.0]
            if len(self._timestamps) >= self.max_requests_per_minute:
                wait_time = 60.0 - (now - self._timestamps[0])
                logger.warning(
                    f"⏳ Rate limit local atingido ({self.max_requests_per_minute}/min). "
                    f"Aguardando {wait_time:.1f}s antes da próxima chamada de IA..."
                )
                await asyncio.sleep(wait_time)
                now = time.monotonic()
                self._timestamps = [t for t in self._timestamps if now - t < 60.0]

            self._timestamps.append(now)
            self._last_call = time.monotonic()


# Instância global compartilhada por todos os bots e módulos de IA.
llm_rate_limiter = LLMRateLimiter(
    max_requests_per_minute=int(os.getenv("LLM_MAX_REQUESTS_PER_MINUTE", "10")),
    min_interval_seconds=float(os.getenv("LLM_MIN_INTERVAL_SECONDS", "5")),
)

# Decorator padrão de retry para chamadas de IA (backoff exponencial).
llm_retry = retry(
    retry=retry_if_exception(is_rate_limit_error),
    wait=wait_exponential(multiplier=2, min=4, max=60),
    stop=stop_after_attempt(int(os.getenv("LLM_MAX_RETRIES", "4"))),
    before_sleep=before_sleep_log(logger, logging.WARNING),
)
