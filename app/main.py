import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.utils.rate_limiter import limiter
from app.routers import auth, users, household, menu, subscription, webhook, admin
from app.routers import google_auth

logger = logging.getLogger(__name__)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    handlers=[
        logging.FileHandler("/tmp/rozkaana-api.log"),
        logging.StreamHandler(),
    ],
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.utils.minio_client import ensure_bucket_exists
    try:
        ensure_bucket_exists()
    except Exception:
        pass
    yield


app = FastAPI(
    title="Rozkaana API",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception on %s %s: %s", request.method, request.url.path, exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected error occurred. Please try again."},
    )


MAX_REQUEST_BODY = 2 * 1024 * 1024  # 2 MB


@app.middleware("http")
async def limit_request_body(request: Request, call_next):
    # Note: checks Content-Length header only — chunked-encoded requests without
    # this header bypass the check. Adequate for API clients; nginx should be
    # configured with client_max_body_size for a hard limit.
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > MAX_REQUEST_BODY:
        return JSONResponse(status_code=413, content={"detail": "Request body too large (max 2MB)"})
    return await call_next(request)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://rozkaana.in", "https://api.rozkaana.in"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
)

app.include_router(auth.router, prefix="/api/v1")
app.include_router(google_auth.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(household.router, prefix="/api/v1")
app.include_router(menu.router, prefix="/api/v1")
app.include_router(subscription.router, prefix="/api/v1")
app.include_router(webhook.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "rozkaana-api"}


@app.get("/files/{file_path:path}")
async def serve_file(file_path: str):
    """Serve PDFs from MinIO via API proxy (MinIO is internal-only)."""
    from fastapi.responses import StreamingResponse
    from app.utils.minio_client import _client
    from app.config import settings
    import io
    try:
        resp = _client.get_object(settings.MINIO_BUCKET_NAME, file_path)
        data = resp.read()
        return StreamingResponse(
            io.BytesIO(data),
            media_type="application/pdf",
            headers={"Content-Disposition": f'inline; filename="{file_path.split("/")[-1]}"'},
        )
    except Exception:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="File not found")
