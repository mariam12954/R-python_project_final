"""
Redis caching layer — Cache-Aside pattern.
Falls back gracefully if Redis is unavailable (e.g. during tests).
"""

import json
import os
from typing import Optional, Any

import redis

from app.core.logging_config import logger

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# ── TTLs (seconds) ──────────────────────────────────────────────
CACHE_TTL_ALL_STUDENTS = 60       # list endpoint
CACHE_TTL_STUDENT_BY_ID = 120     # single-record endpoint

# ── Key helpers ─────────────────────────────────────────────────
def key_all_students(department=None, min_gpa=None, max_gpa=None, skip=0, limit=10) -> str:
    return f"students:all:{department}:{min_gpa}:{max_gpa}:{skip}:{limit}"

def key_student(student_id: int) -> str:
    return f"students:{student_id}"


def _get_redis() -> Optional[redis.Redis]:
    """Return a Redis client, or None if the server is unreachable."""
    try:
        client = redis.from_url(REDIS_URL, socket_connect_timeout=1, decode_responses=True)
        client.ping()
        return client
    except Exception:
        return None


# ── Public helpers ───────────────────────────────────────────────

def cache_get(key: str) -> Optional[Any]:
    """Return the cached value (parsed from JSON), or None on miss/error."""
    r = _get_redis()
    if r is None:
        return None
    try:
        raw = r.get(key)
        if raw is None:
            logger.debug("Cache MISS: %s", key)
            return None
        logger.debug("Cache HIT: %s", key)
        return json.loads(raw)
    except Exception as exc:
        logger.warning("Cache GET error for key=%s: %s", key, exc)
        return None


def cache_set(key: str, value: Any, ttl: int = 60) -> None:
    """Serialize *value* to JSON and store it in Redis with the given TTL."""
    r = _get_redis()
    if r is None:
        return
    try:
        r.setex(key, ttl, json.dumps(value))
        logger.debug("Cache SET: %s (ttl=%ds)", key, ttl)
    except Exception as exc:
        logger.warning("Cache SET error for key=%s: %s", key, exc)


def cache_delete(key: str) -> None:
    """Remove a single key from the cache."""
    r = _get_redis()
    if r is None:
        return
    try:
        r.delete(key)
        logger.debug("Cache DELETE: %s", key)
    except Exception as exc:
        logger.warning("Cache DELETE error for key=%s: %s", key, exc)


def cache_invalidate_student(student_id: int) -> None:
    """Invalidate a student record AND all list caches (pattern delete)."""
    r = _get_redis()
    if r is None:
        return
    try:
        # Remove the specific record
        r.delete(key_student(student_id))
        # Remove all list variants
        for k in r.scan_iter("students:all:*"):
            r.delete(k)
        logger.debug("Cache invalidated for student_id=%d + all list keys", student_id)
    except Exception as exc:
        logger.warning("Cache invalidation error (student_id=%d): %s", student_id, exc)
