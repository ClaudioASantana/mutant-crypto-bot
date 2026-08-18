"""
Gerenciador de Conexões WebSocket.

Infraestrutura: lida com detalhes de transporte (WebSocket),
permitindo broadcast de mensagens para clientes conectados
com filtro por símbolo.
"""
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Gerencia conexões WebSocket ativas e broadcast de mensagens."""

    def __init__(self):
        self.active_connections: dict[Any, str] = {}

    async def connect(self, websocket, default_symbol: str) -> None:
        """Aceita uma nova conexão WebSocket e a associa ao símbolo padrão."""
        await websocket.accept()
        self.active_connections[websocket] = default_symbol

    def set_watched_symbol(self, websocket, symbol: str) -> None:
        """Atualiza o símbolo que uma conexão está assistindo."""
        if websocket in self.active_connections:
            self.active_connections[websocket] = symbol

    def disconnect(self, websocket) -> None:
        """Remove uma conexão do gerenciador."""
        if websocket in self.active_connections:
            del self.active_connections[websocket]

    async def broadcast(self, message: dict) -> None:
        """Envia uma mensagem para todas as conexões que estão assistindo o símbolo da mensagem."""
        try:
            msg_str = json.dumps(message)
        except Exception as e:
            logger.error(f"Falha ao serializar mensagem para broadcast: {e}")
            return

        msg_symbol = message.get("symbol")
        # Itera sobre uma cópia para evitar problemas de concorrência
        for connection, watched_symbol_conn in list(self.active_connections.items()):
            if msg_symbol and msg_symbol != watched_symbol_conn:
                continue
            try:
                await connection.send_text(msg_str)
            except Exception:
                # A conexão pode ter caído, a desconexão será tratada no endpoint
                pass
