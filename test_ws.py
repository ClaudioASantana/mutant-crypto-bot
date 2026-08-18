import asyncio
import websockets
import json

async def test_websocket():
    uri = "ws://localhost:8000/ws"
    try:
        async with websockets.connect(uri) as websocket:
            print("Conectado ao WebSocket")

            # 1. Receber mensagens iniciais (de BTC/USDT)
            print("\n--- Recebendo mensagens iniciais (BTC/USDT) ---")
            initial_messages = []
            for _ in range(5):
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                    data = json.loads(response)
                    initial_messages.append(data)
                    print(f"Recebido: {data.get('event')} para {data.get('symbol', 'N/A')}")
                    if data.get("event") == "active_symbol" and data.get("data") == "BTC/USDT":
                        break
                except asyncio.TimeoutError:
                    print("Timeout ao aguardar mensagem inicial (BTC/USDT)")
                    break

            assert any(m.get("event") == "active_symbol" and m.get("data") == "BTC/USDT" for m in initial_messages), "Não recebeu active_symbol para BTC/USDT"
            print("Mensagens iniciais (BTC/USDT) recebidas com sucesso.")

            # 2. Enviar comando para mudar de símbolo para ETH/USDT
            watch_msg = {
                "command": "WATCH_SYMBOL",
                "symbol": "ETH/USDT"
            }
            await websocket.send(json.dumps(watch_msg))
            print("\n--- Enviado comando WATCH_SYMBOL para ETH/USDT ---")

            # 3. Receber respostas para ETH/USDT e verificar
            print("\n--- Recebendo mensagens após WATCH_SYMBOL (ETH/USDT) ---")
            received_eth_simulator = False
            received_eth_chart_history = False
            received_eth_catalog = False

            # Ajustei o timeout para dar tempo de receber todos os eventos
            for _ in range(15): # Aumentei o número de mensagens esperadas
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=3.0)
                    data = json.loads(response)
                    print(f"Recebido: {data.get('event')} para {data.get('symbol', 'N/A')}")

                    if data.get("event") == "active_symbol" and data.get("data") == "ETH/USDT":
                        print("Confirmado: Símbolo ativo atualizado para ETH/USDT.")
                    elif data.get("event") == "simulator" and data.get("symbol") == "ETH/USDT":
                        received_eth_simulator = True
                        print(f"Confirmado: Estado do simulador para ETH/USDT (personalidade: {data.get('data', {}).get('personality_name', 'N/A')}).")
                    elif data.get("event") == "chart_history" and data.get("symbol") == "ETH/USDT":
                        received_eth_chart_history = True
                        print(f"Confirmado: Histórico do gráfico para ETH/USDT ({len(data.get('data', []))} velas).")
                    elif data.get("event") == "catalog" and data.get("symbol") == "ETH/USDT":
                        received_eth_catalog = True
                        print(f"Confirmado: Catálogo para ETH/USDT.")

                    if received_eth_simulator and received_eth_chart_history and received_eth_catalog:
                        print("\nTodos os eventos esperados para ETH/USDT foram recebidos.")
                        break

                except asyncio.TimeoutError:
                    print("Timeout ao aguardar mais mensagens após WATCH_SYMBOL.")
                    break

            assert received_eth_simulator, "Não recebeu evento 'simulator' para ETH/USDT."
            assert received_eth_chart_history, "Não recebeu evento 'chart_history' para ETH/USDT."
            assert received_eth_catalog, "Não recebeu evento 'catalog' para ETH/USDT."
            print("\nTeste de troca de símbolo via WebSocket CONCLUÍDO COM SUCESSO!")

    except websockets.exceptions.ConnectionClosedOK:
        print("Conexão WebSocket fechada normalmente.")
    except Exception as e:
        print(f"Erro inesperado no teste WebSocket: {e}")

if __name__ == "__main__":
    asyncio.run(test_websocket())
