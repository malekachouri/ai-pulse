from fastapi import APIRouter, Request, Response, status
from sqlalchemy import text

router = APIRouter(tags=["health"])


@router.get("/health/live", summary="Liveness probe")
async def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready", summary="Readiness probe (checks database and pgvector)")
async def ready(request: Request, response: Response) -> dict[str, object]:
    checks: dict[str, str] = {}
    try:
        async with request.app.state.session_factory() as s:
            await s.execute(text("SELECT 1"))
            ext = await s.scalar(text("SELECT extversion FROM pg_extension WHERE extname = 'vector'"))
            checks["database"] = "ok"
            checks["pgvector"] = "ok" if ext else "missing"
    except Exception as exc:  # noqa: BLE001 - report any failure as not ready
        checks["database"] = f"error: {type(exc).__name__}"
    ok = all(v == "ok" for v in checks.values())
    if not ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"status": "ok" if ok else "unavailable", "checks": checks}
