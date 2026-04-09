import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from auth.token import router as token_router
from middleware.auth import AuthMiddleware
from proxy.customers import router as customers_router

load_dotenv()

app = FastAPI(
    title="GeoGateway",
    version="1.0.0",
    description="API Gateway do MVP de geração de rotas para entregas — PUC-Rio",
)

app.add_middleware(AuthMiddleware)

app.include_router(token_router)
app.include_router(customers_router, prefix="/api")


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )

    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
        }
    }

    for path_key, path_value in openapi_schema.get("paths", {}).items():
        for operation in path_value.values():
            if path_key == "/token":
                operation["security"] = []
            else:
                operation["security"] = [{"BearerAuth": []}]

    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi
