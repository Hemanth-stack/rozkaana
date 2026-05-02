import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.utils.rate_limiter import limiter
from app.routers import auth, users, household, menu, subscription, webhook, admin
from app.routers import google_auth

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
    """Serve files from MinIO — used by WATI for PDF delivery."""
    from fastapi.responses import StreamingResponse
    from app.utils.minio_client import _client, settings as _s
    import io
    try:
        resp = _client.get_object(_s.MINIO_BUCKET_NAME, file_path)
        data = resp.read()
        return StreamingResponse(
            io.BytesIO(data),
            media_type="application/pdf",
            headers={"Content-Disposition": f'inline; filename="{file_path.split("/")[-1]}"'},
        )
    except Exception:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="File not found")
