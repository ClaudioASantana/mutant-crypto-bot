import yaml
with open('docker-compose.yaml', 'r') as f:
    data = yaml.safe_load(f)
data['services']['backend']['labels'] = [
    'traefik.enable=true',
    'traefik.http.routers.mutant-backend.rule=Host(`dev-api.mutante.grupocin.com.br`)',
    'traefik.http.services.mutant-backend.loadbalancer.server.port=8000'
]
data['services']['frontend']['labels'] = [
    'traefik.enable=true',
    'traefik.http.routers.mutant-frontend.rule=Host(`dev-mutante.grupocin.com.br`)',
    'traefik.http.services.mutant-frontend.loadbalancer.server.port=3000'
]
with open('docker-compose.yaml', 'w') as f:
    yaml.dump(data, f, default_flow_style=False)
