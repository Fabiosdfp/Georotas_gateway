import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from starlette.responses import HTMLResponse

from auth.token import router as token_router
from middleware.auth import AuthMiddleware
from proxy.customers import router as customers_router

load_dotenv()

app = FastAPI(
    title="GeoGateway",
    version="1.0.0",
    description="API Gateway do MVP de geração de rotas para entregas — PUC-Rio",
    docs_url=None,   # desabilita o /docs padrão
    redoc_url=None,   # desabilita o /redoc padrão
)

app.add_middleware(AuthMiddleware)

app.include_router(token_router)
app.include_router(customers_router, prefix="/api")


# ---------- Swagger UI customizado com auto-auth ----------

_SWAGGER_HTML = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <title>GeoGateway — Swagger UI</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css">
    <style>
        html { box-sizing: border-box; }
        *, *::before, *::after { box-sizing: inherit; }
        body { margin: 0; background: #fafafa; }

        /* Esconde o botão Authorize e os cadeados */
        .auth-wrapper,
        .authorization__btn,
        .authorize { display: none !important; }

        /* Badge de status de autenticação */
        #auth-badge {
            position: fixed; top: 12px; right: 20px; z-index: 9999;
            padding: 8px 18px; border-radius: 20px;
            font-family: system-ui, sans-serif; font-size: 13px; font-weight: 600;
            box-shadow: 0 2px 8px rgba(0,0,0,.15);
            transition: all .3s ease;
        }
        #auth-badge.off  { background: #f93e3e; color: #fff; }
        #auth-badge.on   { background: #49cc90; color: #fff; }
        #auth-badge.warn { background: #f0ad4e; color: #fff; }
    </style>
</head>
<body>
    <div id="auth-badge" class="off">🔒 Não autenticado — execute POST /token</div>
    <div id="swagger-ui"></div>

    <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
    <script>
        let _token = null;
        let _tokenTimer = null;
        const badge = document.getElementById('auth-badge');

        function setBadge(state, text) {
            badge.className = state;
            badge.textContent = text;
        }

        SwaggerUIBundle({
            url: "/openapi.json",
            dom_id: '#swagger-ui',
            presets: [
                SwaggerUIBundle.presets.apis,
                SwaggerUIBundle.SwaggerUIStandalonePreset
            ],
            layout: "BaseLayout",
            deepLinking: true,
            defaultModelsExpandDepth: -1,

            /* Injeta Authorization automaticamente em todas as requisições */
            requestInterceptor: function (req) {
                if (_token && !req.url.endsWith('/token')) {
                    req.headers['Authorization'] = 'Bearer ' + _token;
                }
                return req;
            },

            /* Captura o token da resposta de POST /token */
            responseInterceptor: function (res) {
                try {
                    if (res.url && res.url.endsWith('/token') && res.status === 200) {
                        var body = res.body;
                        if (typeof body === 'string') body = JSON.parse(body);
                        if (body && body.token) {
                            _token = body.token;
                            setBadge('on', '🔓 Autenticado — token válido por 60 s');

                            /* Aviso nos últimos 10 s */
                            if (_tokenTimer) clearTimeout(_tokenTimer);
                            _tokenTimer = setTimeout(function () {
                                setBadge('warn', '⏳ Token expirando em 10 s…');
                            }, 50000);

                            /* Limpa quando expirar */
                            setTimeout(function () {
                                _token = null;
                                if (_tokenTimer) clearTimeout(_tokenTimer);
                                setBadge('off', '🔒 Token expirado — execute POST /token novamente');
                            }, 60000);
                        }
                    }
                } catch (e) { /* silencia */ }
                return res;
            }
        });
    </script>
</body>
</html>"""


@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui() -> HTMLResponse:
    return HTMLResponse(content=_SWAGGER_HTML)


# ---------- OpenAPI schema ----------

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )

    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi
