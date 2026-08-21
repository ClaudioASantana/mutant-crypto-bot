import os
import asyncio
from celery import Celery
import logging

logger = logging.getLogger(__name__)

# Initialize Celery app
celery_broker = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
celery_backend = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")

celery_app = Celery(
    "mutant_crypto_bot",
    broker=celery_broker,
    backend=celery_backend,
    include=["app.infrastructure.queue.tasks"]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=120, # Limite de tempo em segundos para nao travar o worker
)
