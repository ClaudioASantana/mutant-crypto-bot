import asyncio
import websockets
async def test():
    async with websockets.connect("wss://stream.binance.com:9443/ws/btcusdt@trade") as ws:
        print("Connected!")
        msg = await ws.recv()
        print("Received:", msg)

asyncio.run(test())
