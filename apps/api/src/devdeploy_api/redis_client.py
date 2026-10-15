"""Redis connection helpers."""

from redis import Redis
from redis.exceptions import RedisError

from devdeploy_api.config import get_settings

settings = get_settings()


def get_redis() -> Redis:
    return Redis.from_url(settings.redis_url, socket_connect_timeout=1.5)


def ping_redis() -> bool:
    client = get_redis()
    try:
        return bool(client.ping())
    except RedisError:
        return False
    finally:
        client.close()
