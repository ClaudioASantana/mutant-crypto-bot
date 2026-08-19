"""
Testes unitários para o filtro de notícias (NewsFilter).

Garante que o NewsFilter bloqueia operações corretamente
com base em eventos de notícias simulados.
"""

import pytest
import time

from app.infrastructure.services.news_filter import NewsFilter


@pytest.fixture
def news_filter_instance():
    """Fixture que retorna uma instância de NewsFilter com eventos simulados."""
    nf = NewsFilter(block_minutes_before=5, block_minutes_after=5)
    nf.simulated_events = [
        {"name": "Noticia_A", "epoch": int(time.time()) + 300, "impact": "Alto"},  # 5 min no futuro
        {"name": "Noticia_B", "epoch": int(time.time()) + 3600, "impact": "Medio"}  # 60 min no futuro
    ]
    return nf


def test_news_filter_safe_outside_window(news_filter_instance):
    """Deve estar seguro fora da janela de bloqueio."""
    # current_epoch bem antes da Noticia_A
    current_epoch = news_filter_instance.simulated_events[0]["epoch"] - 600
    result = news_filter_instance.check_safety(current_epoch)
    assert result["safe"] is True
    assert "Mercado livre de choques" in result["reason"]


def test_news_filter_unsafe_before_event(news_filter_instance):
    """Deve estar inseguro antes de um evento de notícia."""
    # current_epoch 2 minutos antes da Noticia_A (dentro da janela de 5 min antes)
    current_epoch = news_filter_instance.simulated_events[0]["epoch"] - 120
    result = news_filter_instance.check_safety(current_epoch)
    assert result["safe"] is False
    assert "Pré-Notícia" in result["reason"]
    assert "Noticia_A" in result["next_event"]["name"]


def test_news_filter_unsafe_after_event(news_filter_instance):
    """Deve estar inseguro depois de um evento de notícia."""
    # current_epoch 2 minutos depois da Noticia_A (dentro da janela de 5 min depois)
    current_epoch = news_filter_instance.simulated_events[0]["epoch"] + 120
    result = news_filter_instance.check_safety(current_epoch)
    assert result["safe"] is False
    assert "Pós-Notícia" in result["reason"]
    assert "Noticia_A" in result["next_event"]["name"]


def test_news_filter_no_future_events():
    """Deve estar seguro se não houver eventos futuros relevantes."""
    nf = NewsFilter(block_minutes_before=5, block_minutes_after=5)
    nf.simulated_events = [
        {"name": "Passado", "epoch": int(time.time()) - 3600, "impact": "Baixo"}
    ]
    current_epoch = int(time.time())
    result = nf.check_safety(current_epoch)
    assert result["safe"] is True
    assert "Livre de notícias" in result["reason"]
    assert result["next_event"] is None