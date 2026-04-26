import redis.asyncio as aioredis
import redis as sync_redis
from app.config import settings

# Async pool for FastAPI routes
async_pool = aioredis.ConnectionPool.from_url(
    settings.REDIS_URL,
    max_connections=20,
    decode_responses=True,
)

# Sync client for Celery tasks
sync_redis_client = sync_redis.from_url(settings.REDIS_URL, decode_responses=True)


async def get_redis():
    client = aioredis.Redis(connection_pool=async_pool)
    try:
        yield client
    finally:
        await client.aclose()


def menu_history_key(owner_id: str, slot: str) -> str:
    return f"menu_history:{owner_id}:{slot}"


def regen_lock_key(owner_id: str) -> str:
    return f"regen_lock:{owner_id}"


def otp_rate_key(phone: str) -> str:
    return f"otp_rate:{phone}"


def wa_msg_key(message_id: str) -> str:
    return f"wa_msg:{message_id}"


def invite_token_key(token: str) -> str:
    return f"household_invite:{token}"


def cuisine_override_key(owner_id: str, date_str: str) -> str:
    return f"cuisine_override:{owner_id}:{date_str}"
