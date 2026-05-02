import io
from datetime import timedelta

from minio import Minio
from minio.error import S3Error

from app.config import settings

_client = Minio(
    settings.MINIO_ENDPOINT,
    access_key=settings.MINIO_ACCESS_KEY,
    secret_key=settings.MINIO_SECRET_KEY,
    secure=settings.MINIO_SECURE,
)


def ensure_bucket_exists() -> None:
    try:
        if not _client.bucket_exists(settings.MINIO_BUCKET_NAME):
            _client.make_bucket(settings.MINIO_BUCKET_NAME)
    except S3Error:
        pass


def upload_pdf(object_key: str, pdf_bytes: bytes) -> str:
    ensure_bucket_exists()
    _client.put_object(
        settings.MINIO_BUCKET_NAME,
        object_key,
        io.BytesIO(pdf_bytes),
        length=len(pdf_bytes),
        content_type="application/pdf",
    )
    return object_key


def get_presigned_url(object_key: str) -> str:
    # If MinIO is on localhost it's not reachable by browsers — use the API proxy instead.
    # The /files/{path} endpoint on the API server fetches from MinIO internally.
    if "localhost" in settings.MINIO_ENDPOINT or "127.0.0.1" in settings.MINIO_ENDPOINT:
        return f"{settings.APP_BASE_URL}/files/{object_key}"
    return _client.presigned_get_object(
        settings.MINIO_BUCKET_NAME,
        object_key,
        expires=timedelta(hours=settings.PDF_PRESIGNED_URL_EXPIRE_HOURS),
    )


def delete_object(object_key: str) -> None:
    try:
        _client.remove_object(settings.MINIO_BUCKET_NAME, object_key)
    except S3Error:
        pass
