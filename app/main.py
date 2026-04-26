from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import auth, users, household, menu, subscription, webhook, admin


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.utils.minio_client import ensure_bucket_exists
    try:
        ensure_bucket_exists()
    except Exception:
        pass
    yield


app = FastAPI(
    title="NutriSeva API",
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
app.include_router(users.router, prefix="/api/v1")
app.include_router(household.router, prefix="/api/v1")
app.include_router(menu.router, prefix="/api/v1")
app.include_router(subscription.router, prefix="/api/v1")
app.include_router(webhook.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "nutriseva-api"}
