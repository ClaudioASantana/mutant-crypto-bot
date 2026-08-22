import pytest
from fastapi import HTTPException

from app.core.security import _make_api_key_dependency


@pytest.mark.asyncio
async def test_api_key_dependency_rejects_missing_header():
    dependency = _make_api_key_dependency(lambda: "secret-token", "X-API-Key")

    with pytest.raises(HTTPException) as exc_info:
        await dependency(None)

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_api_key_dependency_rejects_invalid_header():
    dependency = _make_api_key_dependency(lambda: "secret-token", "X-API-Key")

    with pytest.raises(HTTPException) as exc_info:
        await dependency("wrong-token")

    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_api_key_dependency_accepts_valid_header():
    dependency = _make_api_key_dependency(lambda: "secret-token", "X-API-Key")

    await dependency("secret-token")


@pytest.mark.asyncio
async def test_api_key_dependency_rejects_missing_server_token():
    dependency = _make_api_key_dependency(lambda: "", "X-API-Key")

    with pytest.raises(HTTPException) as exc_info:
        await dependency("secret-token")

    assert exc_info.value.status_code == 503
