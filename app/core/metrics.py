"""
metrics.py
==========
Thin wrapper فوق MetricsHandler الموجود في logging_config.

كل الـ counters بتتحدث تلقائياً من خلال الـ logger —
هذا الملف يوفر فقط دوال get_metrics() و read_logs()
للاستخدام من routes/monitoring.py

لا تستدع record_xxx() يدوياً — الـ MetricsHandler يعمل ذلك تلقائياً.
"""

from typing import Any, Dict, List, Optional
from app.core.logging_config import metrics_handler


def get_metrics() -> Dict[str, Any]:
    """Snapshot فوري من الـ counters المحدّثة تلقائياً بالـ logger."""
    return metrics_handler.snapshot()


def read_logs(
    min_level: str = "DEBUG",
    last_n: int = 200,
    search: Optional[str] = None,
) -> List[Dict[str, str]]:
    """يقرأ من نفس app.log اللي يكتب فيه الـ logger."""
    return metrics_handler.read_logs(min_level=min_level, last_n=last_n, search=search)
