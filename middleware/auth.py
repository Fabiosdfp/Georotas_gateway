import os

import httpx
from jose import jwt, JWTError
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

_jwks_cache: dict | None = None


async def _get_jwks() -> dict:
    global _jwks_cache
    if _jwks_cache is not None:
        return _jwks_cache

    jwks_url = os.environ["CLERK_JWKS_URL"]
    async with httpx.AsyncClient() as client:
        response = await client.get(jwks_url)
        response.raise_for_status()
        _jwks_cache = response.json()
        return _jwks_cache


def _find_rsa_key(jwks: dict, token: str) -> dict | None:
    unverified_header = jwt.get_unverified_header(token)
    kid = unverified_header.get("kid")
    for key in jwks.get("keys", []):
        if key["kid"] == kid:
            return key
    return None


class AuthMiddleware(BaseHTTPMiddleware):

    _PUBLIC_PATHS = {"/docs", "/openapi.json", "/redoc", "/token"}

    async def dispatch(self, request: Request, call_next):
        if request.url.path in self._PUBLIC_PATHS:
            return await call_next(request)

        auth_header = request.headers.get("authorization", "")
        if not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"detail": "Token ausente"},
            )

        token = auth_header.removeprefix("Bearer ").strip()

        try:
            jwks = await _get_jwks()
            rsa_key = _find_rsa_key(jwks, token)
            if rsa_key is None:
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Chave de assinatura não encontrada"},
                )

            payload = jwt.decode(
                token,
                rsa_key,
                algorithms=["RS256"],
                options={"verify_aud": False},
            )
        except JWTError:
            return JSONResponse(
                status_code=401,
                content={"detail": "Token inválido ou expirado"},
            )

        user_id = payload.get("sub")
        if not user_id:
            return JSONResponse(
                status_code=401,
                content={"detail": "Token não contém identificação do usuário"},
            )

        request.state.user_id = user_id
        return await call_next(request)
