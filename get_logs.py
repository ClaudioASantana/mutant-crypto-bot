import urllib.request, json
req = urllib.request.Request(
    'http://localhost:8000/api/v1/deployments/q5eodct54o7u9er3wi0rpijx',
    headers={'Authorization': f'Bearer {open("/home/mcmoriam/.gemini/antigravity-ide/mcp/coolify/.env").read().split("=")[1].strip()}', 'Accept': 'application/json'}
)
try:
    with urllib.request.urlopen(req) as response:
        data = json.loads(response.read().decode())
        print(data['logs'][-2000:])
except Exception as e:
    print(e)
