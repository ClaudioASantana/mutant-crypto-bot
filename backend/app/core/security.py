import secrets
from typing import Callable

from fastapi import Header, HTTPException, status

from app.core.operational_config import load_operational_config, OperationalConfigError


API_KEY_HEADER = "X-API-Key"


def _validate_header_token(provided_token: str | None, expected_token: str, header_name: str) -> None:
    if not provided_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Header obrigatório ausente: {header_name}",
        )

    if not secrets.compare_digest(provided_token.strip(), expected_token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Credencial inválida.",
        )


def _make_api_key_dependency(secret_loader: Callable[[], str], header_name: str):
    async def dependency(x_api_key: str | None = Header(default=None, alias=header_name)):
        try:
            expected_token = secret_loader().strip()
        except OperationalConfigError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Configuração operacional inválida: {exc}",
            ) from exc

        if not expected_token:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"{header_name} não configurado no servidor.",
            )

        _validate_header_token(x_api_key, expected_token, header_name)

    return dependency


require_api_key = _make_api_key_dependency(lambda: load_operational_config().api_auth_token, API_KEY_HEADER)
