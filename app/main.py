from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .ai import ai_analysis
from .amazon import parse_csv
from .analytics import analyze_regions, analyze_series, opportunity_rows
from .models import COUNTRIES, ExploreRequest, Mode, OpportunityRequest, ScheduleRequest
from .providers import ProviderError, TrendsService
from .scheduler import LocalScheduler
from .scheduler import enabled as scheduler_enabled
from .storage import Storage

STATIC = Path(__file__).parent / "static"
app = FastAPI(
    title="Google Trends 工作台", version="0.1.0", docs_url=None, redoc_url=None
)
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["127.0.0.1", "localhost", "[::1]", "testserver"],
)
service = TrendsService()
storage = Storage()
scheduler = LocalScheduler(storage, service)
if scheduler_enabled():
    scheduler.start()


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
    result = service.explore(body)
    if body.mode == "live":
        storage.save_snapshot(body.model_dump(), result)
    return result


@app.post("/api/analyze")
def analyze(body: OpportunityRequest):
    return {
        "trends": [
            analyze_series(body.series, keyword) for keyword in body.request.keywords
        ],
        "regions": [
            analyze_regions(body.regions, keyword) for keyword in body.request.keywords
        ],
    }


@app.post("/api/amazon/import")
async def import_amazon(request: Request):
    content = await request.body()
    if len(content) > 5 * 1024 * 1024:
        raise ProviderError("payload_too_large", "CSV 文件不能超过 5 MB。", 413)
    try:
        rows, warnings = parse_csv(content)
    except ValueError as exc:
        raise ProviderError("csv_invalid", str(exc), 422) from exc
    count = storage.replace_amazon(rows)
    return {
        "imported": count,
        "warnings": warnings,
        "columns": ["keyword", "search_volume", "rank", "competition", "asin"],
    }


@app.get("/api/amazon")
def amazon_rows():
    return {"rows": storage.amazon(), "count": len(storage.amazon())}


@app.post("/api/amazon/opportunities")
def amazon_opportunities(body: OpportunityRequest):
    result = {
        "request": body.request.model_dump(),
        "series": body.series,
        "regions": body.regions,
    }
    rows = opportunity_rows(result, storage.amazon())
    return {"rows": rows, "count": len(rows), "imported_count": len(storage.amazon())}


@app.get("/api/history")
def history():
    return {"items": storage.history()}


@app.post("/api/schedules")
def create_schedule(body: ScheduleRequest):
    return storage.add_schedule(
        body.model_dump(exclude={"interval_days"}), body.interval_days
    )


@app.get("/api/schedules")
def list_schedules():
    return {"items": storage.schedules()}


@app.post("/api/schedules/run-due")
def run_due_schedules():
    return {"items": scheduler.run_due()}


@app.delete("/api/schedules/{schedule_id}")
def delete_schedule(schedule_id: int):
    if not storage.delete_schedule(schedule_id):
        raise ProviderError("not_found", "更新计划不存在。", 404)
    return {"deleted": True}


@app.post("/api/analyze-ai")
def analyze_with_ai(body: OpportunityRequest):
    result = {
        "request": body.request.model_dump(),
        "series": body.series,
        "regions": body.regions,
    }
    return ai_analysis(result, opportunity_rows(result, storage.amazon()))


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
