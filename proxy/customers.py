import os

import httpx
from fastapi import APIRouter, Request, Response

router = APIRouter(prefix="/customers", tags=["Customers"])

CUSTOMERS_API_URL = os.environ.get("CUSTOMERS_API_URL", "http://localhost:8080")

FORWARDED_EXCLUDE_HEADERS = {"host", "authorization", "content-length", "transfer-encoding"}


def _forward_headers(request: Request) -> dict[str, str]:
    headers = {
        k: v
        for k, v in request.headers.items()
        if k.lower() not in FORWARDED_EXCLUDE_HEADERS
    }
    headers["X-User-Id"] = request.state.user_id
    return headers


async def _proxy(method: str, path: str, request: Request) -> Response:
    url = f"{CUSTOMERS_API_URL}{path}"
    headers = _forward_headers(request)
    body = await request.body()

    async with httpx.AsyncClient() as client:
        response = await client.request(
            method=method,
            url=url,
            headers=headers,
            content=body if body else None,
            timeout=30.0,
        )

    return Response(
        content=response.content,
        status_code=response.status_code,
        headers=dict(response.headers),
    )


@router.post("", summary="Cadastrar novo cliente", description="Proxy para POST /customers na Customers API")
async def create_customer(request: Request):
    return await _proxy("POST", "/customers", request)


@router.get("", summary="Listar clientes", description="Proxy para GET /customers na Customers API")
async def list_customers(request: Request):
    return await _proxy("GET", "/customers", request)


@router.get("/{customer_id}", summary="Buscar cliente por ID", description="Proxy para GET /customers/{id} na Customers API")
async def get_customer(customer_id: str, request: Request):
    return await _proxy("GET", f"/customers/{customer_id}", request)


@router.put("/{customer_id}", summary="Atualizar cliente", description="Proxy para PUT /customers/{id} na Customers API")
async def update_customer(customer_id: str, request: Request):
    return await _proxy("PUT", f"/customers/{customer_id}", request)


@router.delete("/{customer_id}", summary="Remover cliente", description="Proxy para DELETE /customers/{id} na Customers API")
async def delete_customer(customer_id: str, request: Request):
    return await _proxy("DELETE", f"/customers/{customer_id}", request)
