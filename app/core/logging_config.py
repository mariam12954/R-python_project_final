"""
logging_config.py
=================
مصدر واحد للـ logger في كل التطبيق.

الفكرة:
- كل logger.info / logger.warning / logger.error ... يمر على MetricsHandler
- MetricsHandler يحلّل نص الرسالة ويحدّث counters الـ metrics تلقائياً
- بالتالي logging_config و metrics مربوطان: الـ logger هو المصدر الوحيد
  والـ metrics تستمع منه، مش بنكتب record_xxx() يدوياً في كل مكان

Levels written to each destination:
  console (stdout)  →  INFO and above
  file (logs/app.log) →  DEBUG and above (everything)
  MetricsHandler    →  DEBUG and above (parses for counters)
"""

import logging
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional

# ── Log file path ────────────────────────────────────────────────
LOGS_DIR = Path("logs")
LOGS_DIR.mkdir(exist_ok=True)
LOG_FILE = LOGS_DIR / "app.log"


# ═══════════════════════════════════════════════════════════════════
# MetricsHandler — يحدّث الـ counters من خلال الـ log records
# ═══════════════════════════════════════════════════════════════════

class MetricsHandler(logging.Handler):
    """
    Custom logging.Handler يستمع لكل رسالة تمر على الـ logger
    ويحدّث counters الـ metrics منها — بدون أي استدعاء يدوي.

    الـ patterns المعترف بها من نص الرسالة:
      REQUEST  METHOD /path           → total_requests + endpoint
      RESPONSE METHOD /path -> CODE  → response_times + errors
      Login attempt                  → auth.login_attempts
      Login FAILED                   → auth.login_failures
      Login SUCCESS                  → (لا شيء إضافي)
      Token validated                → auth.token_validations
      CREATE student SUCCESS         → crud.creates
      GET all students — returned    → crud.reads
      UPDATE student ... SUCCESS     → crud.updates
      DELETE student ... SUCCESS     → crud.deletes
      User registered successfully   → crud.creates  (user)
    """

    # Regexes
    _RE_REQUEST  = re.compile(r"REQUEST\s+(\w+)\s+(\S+)")
    _RE_RESPONSE = re.compile(r"RESPONSE\s+(\w+)\s+(\S+)\s*->\s*(\d+)\s+\(([0-9.]+)\s*ms\)")
    _RE_LOGIN_AT  = re.compile(r"Login attempt", re.IGNORECASE)
    _RE_LOGIN_FAIL= re.compile(r"Login FAILED",  re.IGNORECASE)
    _RE_TOKEN_VAL = re.compile(r"Token validated", re.IGNORECASE)
    _RE_CRUD_C    = re.compile(r"(CREATE student SUCCESS|User registered successfully)")
    _RE_CRUD_R    = re.compile(r"GET (all students|student id=).*(returned|served)")
    _RE_CRUD_U    = re.compile(r"UPDATE student id=\d+ SUCCESS")
    _RE_CRUD_D    = re.compile(r"DELETE student id=\d+ SUCCESS")

    def __init__(self):
        super().__init__(level=logging.DEBUG)
        self._lock = Lock()
        self._data: Dict[str, Any] = {
            "app_start_time": datetime.utcnow().isoformat(),
            "total_requests": 0,
            "total_errors_4xx": 0,
            "total_errors_5xx": 0,
            "requests_per_endpoint": defaultdict(int),
            "response_times_ms": [],          # keep last 1 000
            "auth_login_attempts": 0,
            "auth_login_failures": 0,
            "auth_token_validations": 0,
            "crud_creates": 0,
            "crud_reads": 0,
            "crud_updates": 0,
            "crud_deletes": 0,
        }

    # ── logging.Handler interface ────────────────────────────────
    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = record.getMessage()
            self._parse(msg, record.levelno)
        except Exception:
            self.handleError(record)

    # ── Internal parser ──────────────────────────────────────────
    def _parse(self, msg: str, level: int) -> None:
        with self._lock:
            d = self._data

            # REQUEST  GET /students
            m = self._RE_REQUEST.search(msg)
            if m:
                method, path = m.group(1), m.group(2)
                d["total_requests"] += 1
                d["requests_per_endpoint"][f"{method} {path}"] += 1
                return

            # RESPONSE GET /students -> 200  (12.34 ms)
            m = self._RE_RESPONSE.search(msg)
            if m:
                status = int(m.group(3))
                elapsed = float(m.group(4))
                times = d["response_times_ms"]
                times.append(elapsed)
                if len(times) > 1000:
                    d["response_times_ms"] = times[-1000:]
                if 400 <= status < 500:
                    d["total_errors_4xx"] += 1
                elif status >= 500:
                    d["total_errors_5xx"] += 1
                return

            # Auth events
            if self._RE_LOGIN_AT.search(msg):
                d["auth_login_attempts"] += 1
                return
            if self._RE_LOGIN_FAIL.search(msg):
                d["auth_login_failures"] += 1
                return
            if self._RE_TOKEN_VAL.search(msg):
                d["auth_token_validations"] += 1
                return

            # CRUD
            if self._RE_CRUD_C.search(msg):
                d["crud_creates"] += 1
                return
            if self._RE_CRUD_R.search(msg):
                d["crud_reads"] += 1
                return
            if self._RE_CRUD_U.search(msg):
                d["crud_updates"] += 1
                return
            if self._RE_CRUD_D.search(msg):
                d["crud_deletes"] += 1
                return

    # ── Public API ───────────────────────────────────────────────
    def snapshot(self) -> Dict[str, Any]:
        """Return a copy of current metrics."""
        with self._lock:
            d = self._data
            times = d["response_times_ms"]
            avg = round(sum(times) / len(times), 2) if times else 0.0
            total = d["total_requests"]
            err = d["total_errors_4xx"] + d["total_errors_5xx"]
            return {
                "app_start_time":        d["app_start_time"],
                "total_requests":        total,
                "total_errors_4xx":      d["total_errors_4xx"],
                "total_errors_5xx":      d["total_errors_5xx"],
                "error_rate_pct":        round(err / max(total, 1) * 100, 2),
                "avg_response_ms":       avg,
                "requests_per_endpoint": dict(d["requests_per_endpoint"]),
                "auth": {
                    "login_attempts":    d["auth_login_attempts"],
                    "login_failures":    d["auth_login_failures"],
                    "token_validations": d["auth_token_validations"],
                },
                "crud": {
                    "creates": d["crud_creates"],
                    "reads":   d["crud_reads"],
                    "updates": d["crud_updates"],
                    "deletes": d["crud_deletes"],
                },
            }

    def read_logs(
        self,
        min_level: str = "DEBUG",
        last_n: int = 200,
        search: Optional[str] = None,
    ) -> List[Dict[str, str]]:
        """
        يقرأ من app.log ويرجع entries مفلترة.
        الربط هنا واضح: نفس الـ LOG_FILE اللي بيكتب فيه الـ file_handler.
        """
        _LEVEL_ORDER = {"DEBUG": 10, "INFO": 20, "WARNING": 30,
                        "ERROR": 40, "CRITICAL": 50}
        _LINE_RE = re.compile(
            r"^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})"
            r" \| (?P<level>\w+)\s*"
            r" \| (?P<name>[\w.]+)"
            r" \| (?P<message>.+)$"
        )
        min_ord = _LEVEL_ORDER.get(min_level.upper(), 10)
        results: List[Dict[str, str]] = []

        if not LOG_FILE.exists():
            return results

        try:
            with LOG_FILE.open(encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    line = line.rstrip()
                    m = _LINE_RE.match(line)
                    if not m:
                        continue
                    lvl = m.group("level").upper()
                    if _LEVEL_ORDER.get(lvl, 0) < min_ord:
                        continue
                    if search and search.lower() not in line.lower():
                        continue
                    results.append({
                        "timestamp": m.group("ts"),
                        "level":     lvl,
                        "logger":    m.group("name"),
                        "message":   m.group("message"),
                    })
        except Exception as exc:
            # لا نقدر نستخدم logger هنا (circular) — نكتب على stderr
            print(f"[MetricsHandler] Failed to read log file: {exc}", file=sys.stderr)

        return results[-last_n:]


# ═══════════════════════════════════════════════════════════════════
# Setup — runs once at import time
# ═══════════════════════════════════════════════════════════════════

def _setup() -> tuple:
    """Build and return (logger, metrics_handler)."""
    _logger = logging.getLogger("student_mgmt")
    _logger.setLevel(logging.DEBUG)

    if _logger.handlers:
        # Already configured — find the existing MetricsHandler
        for h in _logger.handlers:
            if isinstance(h, MetricsHandler):
                return _logger, h
        # Shouldn't happen, but create a new one just in case
        _mh = MetricsHandler()
        _logger.addHandler(_mh)
        return _logger, _mh

    fmt = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console — INFO+
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)

    # File — DEBUG+ (everything goes here, MetricsHandler reads it too)
    fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)

    # MetricsHandler — parses every record automatically
    _mh = MetricsHandler()

    _logger.addHandler(ch)
    _logger.addHandler(fh)
    _logger.addHandler(_mh)
    _logger.propagate = False

    return _logger, _mh


# ── Public singletons ────────────────────────────────────────────
logger, metrics_handler = _setup()
