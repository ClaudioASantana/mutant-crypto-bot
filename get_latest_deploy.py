import urllib.request, json

token = "8|tuVeWsRn1lD7sUNdNqrfBYmRLfwgd2XImqQVTZOvad91b313"
req = urllib.request.Request(
    'http://46.202.146.149:8000/api/v1/deployments',
    headers={'Authorization': f'Bearer {token}', 'Accept': 'application/json'}
)
try:
    with urllib.request.urlopen(req) as response:
        data = json.loads(response.read().decode())
        if not isinstance(data, list):
            data = data.get("data", [])
        data.sort(key=lambda x: x["created_at"], reverse=True)
        for d in data[:5]:
            print(f"{d['uuid']} | {d.get('application_name')} | {d['status']} | {d['created_at']}")
except Exception as e:
    print(e)
