from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://rozkaana:password@localhost:5432/rozkaana"
    DATABASE_URL_SYNC: str = "postgresql+psycopg2://rozkaana:password@localhost:5432/rozkaana"
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"
    JWT_SECRET_KEY: str = "changeme-256-bit-secret"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin123"
    MINIO_BUCKET_NAME: str = "rozkaana-pdfs"
    MINIO_SECURE: bool = False
    WATI_API_BASE_URL: str = "https://live-mt-server.wati.io/000000"
    WATI_ACCESS_TOKEN: str = "Bearer token"
    WATI_WEBHOOK_SECRET: str = "webhook-secret"
    RAZORPAY_KEY_ID: str = "rzp_test_xxxx"
    RAZORPAY_KEY_SECRET: str = "secret"
    RAZORPAY_WEBHOOK_SECRET: str = "rzp-webhook-secret"
    MSG91_AUTH_KEY: str = "msg91-auth-key"
    MSG91_TEMPLATE_ID: str = "template-id"
    MSG91_SENDER_ID: str = "NUTRSV"
    OPENAI_API_KEY: str = "sk-placeholder"
    APP_BASE_URL: str = "http://localhost:8000"
    PDF_PRESIGNED_URL_EXPIRE_HOURS: int = 12
    MENU_GEN_HOUR_UTC: int = 18
    PDF_BUILD_HOUR_UTC: int = 22
    WA_SEND_HOUR_UTC: int = 0

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
