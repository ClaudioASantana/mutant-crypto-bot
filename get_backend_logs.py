import urllib.request, json

token = "8|tuVeWsRn1lD7sUNdNqrfBYmRLfwgd2XImqQVTZOvad91b313"
req = urllib.request.Request(
    'http://46.202.146.149:8000/api/v1/applications/z24yoi2jdvk7dpys2xr5pio1/envs/dev/services/backend/logs',
    headers={'Authorization': f'Bearer {token}', 'Accept': 'application/json'}
)
try:
    with urllib.request.urlopen(req) as response:
        print(response.read().decode())
except urllib.error.HTTPError as e:
    print(f"HTTP Error {e.code}: {e.read().decode()}")
except Exception as e:
    print(e)
