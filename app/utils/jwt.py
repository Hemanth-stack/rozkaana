from app.utils.security import create_access_token, create_refresh_token, decode_token


def verify_token(token: str) -> dict | None:
    try:
        return decode_token(token)
    except Exception:
        return None


__all__ = ["create_access_token", "create_refresh_token", "decode_token", "verify_token"]
