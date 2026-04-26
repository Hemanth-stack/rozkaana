from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str
    redis_url: str
    minio_endpoint: str
    minio_access_key: str
    minio_secret_key: str
    minio_bucket: str
    jwt_secret: str
    jwt_expire_minutes: int
    wati_api_url: str
    wati_access_token: str
    wati_webhook_secret: str
    razorpay_key_id: str
    razorpay_key_secret: str
    openai_api_key: str
    msg91_auth_key: str
    celery_broker_url: str
    celery_result_backend: str
    menu_generation_hour: int
    pdf_build_hour: int
    wa_send_hour: int

    class Config:
        env_file = ".env"

settings = Settings()