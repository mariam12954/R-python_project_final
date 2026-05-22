"""
main.py
=======
نقطة دخول التطبيق.

الـ middleware يسجّل كل request/response — والـ MetricsHandler
في logging_config يلتقطهم تلقائياً ويحدّث الـ counters.
"""

import time
import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.database import engine, Base
from app.core.logging_config import logger
from app.routes import auth, students, audit_logs
from app.routes.monitoring import router as monitoring_router
import app.models

# ── إنشاء الجداول ────────────────────────────────────────────────
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Student Management System", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Middleware: تسجيل كل request/response ────────────────────────
# الـ MetricsHandler يلتقط هذه الرسائل تلقائياً من خلال الـ logger
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    # MetricsHandler يلتقط "REQUEST METHOD /path" → total_requests++
    logger.info("REQUEST  %s %s", request.method, request.url.path)
    try:
        response = await call_next(request)
        elapsed = round((time.time() - start) * 1000, 2)
        level = logging.WARNING if response.status_code >= 400 else logging.INFO
        # MetricsHandler يلتقط "RESPONSE METHOD /path -> CODE (N ms)" → errors + times
        logger.log(
            level,
            "RESPONSE %s %s -> %d  (%.2f ms)",
            request.method,
            request.url.path,
            response.status_code,
            elapsed,
        )
        return response
    except Exception as exc:
        elapsed = round((time.time() - start) * 1000, 2)
        logger.error(
            "UNHANDLED EXCEPTION %s %s (%.2f ms): %s",
            request.method, request.url.path, elapsed, exc,
            exc_info=True,
        )
        raise


# ── Routers ──────────────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(students.router)
app.include_router(audit_logs.router)
app.include_router(monitoring_router)   # /metrics  /logs  /dashboard

# ── Health ───────────────────────────────────────────────────────
@app.get("/health")
def health():
    logger.debug("Health check called")
    return {"status": "ok"}

# ── Frontend (آخر حاجة — تمسك كل الـ routes الباقية) ─────────────
app.mount("/", StaticFiles(directory="frontendd", html=True), name="frontend")

logger.info("Student Management System started.")
