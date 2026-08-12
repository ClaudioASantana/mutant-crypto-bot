import urllib.request, json, os

token = open("/home/mcmoriam/.gemini/antigravity-ide/mcp/coolify/.env").read().split("=")[1].strip()

req = urllib.request.Request(
    'http://localhost:8000/api/v1/applications/z24yoi2jdvk7dpys2xr5pio1',
    data=json.dumps({"build_timeout": 1200}).encode(),
    headers={'Authorization': f'Bearer {token}', 'Accept': 'application/json', 'Content-Type': 'application/json'},
    method='PATCH'
)
try:
    with urllib.request.urlopen(req) as response:
        print(response.read().decode())
except Exception as e:
    print(e)
