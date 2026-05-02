from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import auth, users, household, menu, subscription, webhook, admin
from app.routers import google_auth


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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
    """Serve files from MinIO publicly — used by WATI to download PDFs."""
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
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="File not found")
