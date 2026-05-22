"""
dependencies.py
===============
فايل مركزي يجمع كل FastAPI dependencies المستخدمة في التطبيق.

بدلاً من import get_db / get_current_user / require_admin
من أماكن مختلفة في كل route، كل route تعمل:

    from app.dependencies import get_db, get_current_user, require_admin

وده يوفر:
  - مكان واحد للتعديل لو تغير منطق أي dependency
  - تجنب الـ circular imports
  - وضوح: أي شخص يفتح الملف يشوف كل dependencies التطبيق دفعة واحدة
"""

from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.core.database import get_db          # noqa: F401  — re-exported
from app.core.security import decode_token
from app.core.logging_config import logger
from app.models.user import User

# ── HTTP Bearer scheme ───────────────────────────────────────────
_http_bearer = HTTPBearer()


async def get_token(
    credentials: HTTPAuthorizationCredentials = Depends(_http_bearer),
) -> str:
    """يسحب الـ JWT token من الـ Authorization header."""
    return credentials.credentials


# ── Auth dependencies ────────────────────────────────────────────

def get_current_user(
    token: str = Depends(get_token),
    db: Session = Depends(get_db),
) -> User:
    """
    يتحقق من الـ JWT ويرجع المستخدم الحالي.
    يرفع 401 لو التوكن غلط أو منتهي.
    """
    payload = decode_token(token)
    if not payload:
        logger.warning("Token validation FAILED — invalid or expired token")
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user = db.query(User).filter(User.username == payload.get("sub")).first()
    if not user:
        logger.warning(
            "Token validation FAILED — user not found for sub='%s'",
            payload.get("sub"),
        )
        raise HTTPException(status_code=401, detail="User not found")

    logger.debug("Token validated for username='%s'", user.username)
    return user


def require_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    مثل get_current_user لكن يشترط role == 'admin'.
    يرفع 403 لو المستخدم مش admin.
    """
    if current_user.role != "admin":
        logger.warning(
            "Authorization FAILED — user='%s' tried admin-only endpoint",
            current_user.username,
        )
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


def require_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """يتحقق إن الحساب مفعّل (is_active=True)."""
    if not current_user.is_active:
        logger.warning(
            "Access DENIED — user='%s' account is inactive",
            current_user.username,
        )
        raise HTTPException(status_code=403, detail="Account is inactive")
    return current_user
