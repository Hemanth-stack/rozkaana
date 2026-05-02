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
    # SMTP Email (Zoho Mail)
    SMTP_HOST: str = "smtp.zoho.in"
    SMTP_PORT: int = 587
    # noreply@rozkaana.in — used for OTP, trial, and system emails
    SMTP_USER: str = "noreply@rozkaana.in"
    SMTP_PASSWORD: str = "your-zoho-password"
    SMTP_FROM_NAME: str = "Rozkaana"
    SMTP_FROM_EMAIL: str = "noreply@rozkaana.in"
    # menu@rozkaana.in — used for daily meal plan delivery
    SMTP_MENU_USER: str = "menu@rozkaana.in"
    SMTP_MENU_PASSWORD: str = "your-zoho-menu-password"

    # Razorpay (payments)
    RAZORPAY_KEY_ID: str = "rzp_test_xxxx"
    RAZORPAY_KEY_SECRET: str = "secret"
    RAZORPAY_WEBHOOK_SECRET: str = "rzp-webhook-secret"

    # WATI (kept for future WhatsApp re-integration)
    WATI_API_BASE_URL: str = "https://live-mt-server.wati.io/000000"
    WATI_ACCESS_TOKEN: str = "Bearer placeholder"
    WATI_WEBHOOK_SECRET: str = "webhook-secret"

    # Google OAuth
    GOOGLE_CLIENT_ID: str = "your-google-client-id"
    GOOGLE_CLIENT_SECRET: str = "your-google-client-secret"
    GOOGLE_REDIRECT_URI: str = "https://api.rozkaana.in/api/v1/auth/google/callback"
    FRONTEND_URL: str = "https://rozkaana.in"

    CLAUDE_API_KEY: str = "sk-ant-placeholder"
    APP_BASE_URL: str = "https://api.rozkaana.in"
    PDF_PRESIGNED_URL_EXPIRE_HOURS: int = 12
    MENU_GEN_HOUR_UTC: int = 18
    PDF_BUILD_HOUR_UTC: int = 22
    EMAIL_SEND_HOUR_UTC: int = 0

    # Security
    ADMIN_PASSWORD_HASH: str = ""   # bcrypt hash; empty = fall back to JWT[:8] (legacy)
    APP_ENV: str = "production"     # "development" enables dev-login endpoint

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
