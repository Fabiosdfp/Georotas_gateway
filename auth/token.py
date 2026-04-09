import os

import httpx
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

router = APIRouter(tags=["Auth — Testes"])

BACKEND_API = "https://api.clerk.com/v1"


class TokenRequest(BaseModel):
    email: str


class TokenResponse(BaseModel):
    token: str


def _fapi_base_url() -> str:
    jwks_url = os.environ["CLERK_JWKS_URL"]
    return jwks_url.split("/.well-known/")[0]


def _clerk_secret() -> str:
    return os.environ["CLERK_SECRET_KEY"]


@router.post(
    "/token",
    response_model=TokenResponse,
    summary="Gerar JWT para testes",
    description=(
        "Apenas para testes — gera um JWT válido a partir do email de um "
        "usuário cadastrado no Clerk (não requer senha)."
    ),
)
async def generate_token(body: TokenRequest):
    fapi_url = _fapi_base_url()
    secret = _clerk_secret()
    backend_headers = {
        "Authorization": f"Bearer {secret}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        # 1) Buscar user_id pelo email via Backend API
        try:
            r = await client.get(
                f"{BACKEND_API}/users",
                params={"email_address[]": body.email},
                headers=backend_headers,
            )
        except httpx.RequestError:
            return _error(502, "Não foi possível conectar ao Clerk Backend API")

        if r.status_code != 200:
            return _error(502, f"Clerk Backend API retornou status {r.status_code}")

        users = r.json()
        if not users:
            return _error(404, "Usuário não encontrado no Clerk")

        user_id = users[0]["id"]

        # 2) Criar sign_in_token via Backend API
        try:
            r = await client.post(
                f"{BACKEND_API}/sign_in_tokens",
                json={"user_id": user_id},
                headers=backend_headers,
            )
        except httpx.RequestError:
            return _error(502, "Falha ao criar sign_in_token")

        if r.status_code not in (200, 201):
            return _error(502, f"Clerk sign_in_tokens retornou status {r.status_code}")

        ticket = r.json().get("token")
        if not ticket:
            return _error(502, "Clerk não retornou o ticket")

        # 3) Inicializar dev browser na FAPI
        try:
            r = await client.post(f"{fapi_url}/v1/dev_browser", content="")
        except httpx.RequestError:
            return _error(502, "Falha ao inicializar dev browser")

        dev_token = r.json().get("token")
        if not dev_token:
            return _error(502, "Clerk não retornou dev browser token")

        # 4) Sign-in via FAPI com ticket
        try:
            r = await client.post(
                f"{fapi_url}/v1/client/sign_ins",
                params={"__clerk_db_jwt": dev_token},
                data={"strategy": "ticket", "ticket": ticket},
            )
        except httpx.RequestError:
            return _error(502, "Falha ao realizar sign-in via FAPI")

        if r.status_code != 200:
            return _error(502, f"FAPI sign_in retornou status {r.status_code}")

        data = r.json()

        sign_in_status = data.get("response", {}).get("status")
        if sign_in_status != "complete":
            return _error(502, f"Sign-in não concluído: status={sign_in_status}")

        try:
            sessions = data["client"]["sessions"]
            created_session_id = data["response"]["created_session_id"]
            session = next(s for s in sessions if s["id"] == created_session_id)
            jwt = session["last_active_token"]["jwt"]
        except (KeyError, StopIteration, TypeError):
            return _error(502, "Resposta do Clerk não contém o token esperado")

    return TokenResponse(token=jwt)


def _error(status_code: int, detail: str):
    return JSONResponse(status_code=status_code, content={"detail": detail})
