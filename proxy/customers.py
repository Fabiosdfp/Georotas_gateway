import os
from typing import Optional

import httpx
from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, Field

router = APIRouter(prefix="/customers", tags=["Customers"])

CUSTOMERS_API_URL = os.environ.get("CUSTOMERS_API_URL", "http://localhost:8080")

FORWARDED_EXCLUDE_HEADERS = {"host", "authorization", "content-length", "transfer-encoding"}


# ---------- Modelos para documentação Swagger ----------

class CustomerBody(BaseModel):
    name: str = Field(..., example="João Silva", description="Nome do cliente")
    address: str = Field(..., example="Rua Marquês de São Vicente 225, Rio de Janeiro", description="Endereço do cliente (será geocodificado automaticamente)")


class CustomerResponseModel(BaseModel):
    id: str = Field(..., description="UUID do cliente")
    userId: str = Field(..., description="ID do usuário autenticado (extraído do JWT)")
    name: str = Field(..., description="Nome do cliente")
    address: str = Field(..., description="Endereço do cliente")
    lat: Optional[float] = Field(None, description="Latitude (geocodificada)")
    lng: Optional[float] = Field(None, description="Longitude (geocodificada)")
    createdAt: Optional[str] = Field(None, description="Data de criação")
    updatedAt: Optional[str] = Field(None, description="Data de última atualização")


# ---------- Helpers ----------

def _forward_headers(request: Request) -> dict[str, str]:
    headers = {
        k: v
        for k, v in request.headers.items()
        if k.lower() not in FORWARDED_EXCLUDE_HEADERS
    }
    headers["X-User-Id"] = request.state.user_id
    return headers


async def _proxy(method: str, path: str, request: Request, body_override: bytes | None = None) -> Response:
    url = f"{CUSTOMERS_API_URL}{path}"
    headers = _forward_headers(request)
    body = body_override if body_override is not None else await request.body()

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


# ---------- Endpoints ----------

@router.post(
    "",
    summary="Cadastrar novo cliente",
    description="Cria um novo cliente. O endereço é geocodificado automaticamente via Nominatim.",
    response_model=CustomerResponseModel,
    status_code=201,
)
async def create_customer(body: CustomerBody, request: Request):
    return await _proxy("POST", "/customers", request, body_override=body.model_dump_json().encode())


@router.get("", summary="Listar clientes", description="Retorna todos os clientes do usuário autenticado.")
async def list_customers(request: Request):
    return await _proxy("GET", "/customers", request)


@router.get("/{customer_id}", summary="Buscar cliente por ID", description="Retorna um cliente pelo seu UUID.")
async def get_customer(customer_id: str, request: Request):
    return await _proxy("GET", f"/customers/{customer_id}", request)


@router.put(
    "/{customer_id}",
    summary="Atualizar cliente",
    description="Atualiza os dados de um cliente existente.",
    response_model=CustomerResponseModel,
)
async def update_customer(customer_id: str, body: CustomerBody, request: Request):
    return await _proxy("PUT", f"/customers/{customer_id}", request, body_override=body.model_dump_json().encode())


@router.delete("/{customer_id}", summary="Remover cliente", description="Remove um cliente pelo seu UUID.", status_code=204)
async def delete_customer(customer_id: str, request: Request):
    return await _proxy("DELETE", f"/customers/{customer_id}", request)
