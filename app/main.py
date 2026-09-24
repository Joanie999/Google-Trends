from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .models import COUNTRIES, ExploreRequest, Mode
from .providers import ProviderError, TrendsService

STATIC = Path(__file__).parent / "static"
app = FastAPI(
    title="Google Trends 工作台", version="0.1.0", docs_url=None, redoc_url=None
)
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["127.0.0.1", "localhost", "[::1]", "testserver"],
)
service = TrendsService()


@app.middleware("http")
async def local_only(request: Request, call_next):
    origin = request.headers.get("origin")
    if request.url.path.startswith("/api/") and (
        request.headers.get("sec-fetch-site") == "cross-site"
        or (origin and urlsplit(origin).netloc != request.headers.get("host"))
    ):
        return JSONResponse(
            {"error": {"code": "origin", "message": "请从本机工作台页面发起查询。"}},
            status_code=403,
        )
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    )
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.exception_handler(ProviderError)
async def provider_error(request, exc):
    return JSONResponse(
        {"error": {"code": exc.code, "message": exc.message}}, status_code=exc.status
    )


@app.exception_handler(RequestValidationError)
async def invalid_request(request, exc):
    return JSONResponse(
        {
            "error": {
                "code": "validation",
                "message": "请检查输入：1–5 个关键词，每个不超过 100 个字符，并选择有效的地区、时间和类型。",
            }
        },
        status_code=422,
    )


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "version": "0.1.0",
        "provider": "trendspyg",
        "countries": COUNTRIES,
    }


@app.post("/api/explore")
def explore(body: ExploreRequest):
    return service.explore(body)


@app.get("/api/trending")
def trending(geo: str = Query(default="US"), mode: Mode = "live"):
    if not geo or geo not in COUNTRIES:
        raise ProviderError("validation", "实时热搜需要选择具体国家或地区。", 422)
    return service.trending(geo, mode)


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/docs", include_in_schema=False)
def api_docs():
    return FileResponse(STATIC / "api-docs.html")


app.mount("/static", StaticFiles(directory=STATIC), name="static")
