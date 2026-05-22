"""
auth_service.py
===============
Business logic للمصادقة — تسجيل وتسجيل دخول فقط.

get_current_user / require_admin انتقلوا لـ app/dependencies.py
لأنهم FastAPI dependencies وليسوا business logic.
"""

from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models.user import User
from app.schemas.user import UserCreate
from app.core.security import hash_password, verify_password, create_access_token
from app.core.logging_config import logger


def register_user(db: Session, user_data: UserCreate) -> User:
    """يسجّل مستخدم جديد — يرفض لو الاسم أو الإيميل مكرر."""
    logger.info("Registration attempt for username='%s'", user_data.username)

    if db.query(User).filter(User.username == user_data.username).first():
        logger.warning("Registration failed — username already exists: '%s'", user_data.username)
        raise HTTPException(status_code=400, detail="Username already exists")

    if db.query(User).filter(User.email == user_data.email).first():
        logger.warning("Registration failed — email already registered: '%s'", user_data.email)
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=hash_password(user_data.password),
        role=user_data.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # MetricsHandler يلتقط "User registered successfully" تلقائياً → crud.creates++
    logger.info(
        "User registered successfully: id=%d username='%s' role='%s'",
        user.id, user.username, user.role,
    )
    return user


def login_user(db: Session, username: str, password: str) -> dict:
    """يتحقق من credentials ويرجع JWT token."""
    # MetricsHandler يلتقط "Login attempt" → auth.login_attempts++
    logger.info("Login attempt for username='%s'", username)

    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.hashed_password):
        # MetricsHandler يلتقط "Login FAILED" → auth.login_failures++
        logger.warning("Login FAILED for username='%s' — invalid credentials", username)
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not user.is_active:
        logger.warning("Login FAILED for username='%s' — account inactive", username)
        raise HTTPException(status_code=403, detail="Account is inactive")

    token = create_access_token({"sub": user.username, "role": user.role})
    logger.info("Login SUCCESS for username='%s' role='%s'", user.username, user.role)
    return {"access_token": token, "token_type": "bearer"}
