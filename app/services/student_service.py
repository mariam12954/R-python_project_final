"""
student_service.py
==================
Business logic لعمليات الطلاب (CRUD + caching + audit logging).

لا يحتوي على FastAPI dependencies — اللي محتاج get_db فقط.
get_current_user / require_admin موجودان في app/dependencies.py

ملاحظة حول الـ metrics:
الـ MetricsHandler في logging_config.py يلتقط تلقائياً:
  "CREATE student SUCCESS"  → crud.creates++
  "GET all students — returned ... records"  → crud.reads++
  "UPDATE student id=N SUCCESS"  → crud.updates++
  "DELETE student id=N SUCCESS"  → crud.deletes++
لا داعي لاستدعاء record_crud() يدوياً.
"""

import json
from datetime import datetime
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models.student import Student
from app.models.audit_log import AuditLog
from app.schemas.student import StudentCreate, StudentUpdate
from app.core.logging_config import logger
from app.core import cache


# ── Helpers ──────────────────────────────────────────────────────

def _student_to_dict(student: Student) -> dict:
    """تحويل ORM object لـ dict قابل للـ JSON (للـ cache)."""
    return {
        "id": student.id,
        "full_name": student.full_name,
        "department": student.department,
        "gpa": student.gpa,
        "year": student.year,
        "user_id": student.user_id,
        "created_at": str(student.created_at),
        "updated_at": str(student.updated_at),
    }


# ── CRUD ─────────────────────────────────────────────────────────

def create_student(db: Session, data: StudentCreate) -> Student:
    logger.info("CREATE student attempt — user_id=%d", data.user_id)
    existing = db.query(Student).filter(Student.user_id == data.user_id).first()
    if existing:
        logger.warning(
            "CREATE student FAILED — profile already exists for user_id=%d", data.user_id
        )
        raise HTTPException(status_code=400, detail="Student profile already exists for this user")

    student = Student(**data.model_dump())
    db.add(student)
    db.commit()
    db.refresh(student)

    cache.cache_invalidate_student(student.id)
    # MetricsHandler يلتقط هذا السطر → crud.creates++
    logger.info(
        "CREATE student SUCCESS — student_id=%d user_id=%d", student.id, student.user_id
    )
    return student


def get_all_students(
    db: Session,
    department=None,
    min_gpa=None,
    max_gpa=None,
    skip: int = 0,
    limit: int = 10,
):
    cache_key = cache.key_all_students(department, min_gpa, max_gpa, skip, limit)
    cached = cache.cache_get(cache_key)
    if cached is not None:
        logger.debug("GET all students — served from cache (key=%s)", cache_key)
        return cached

    logger.debug(
        "GET all students — querying DB (dept=%s min_gpa=%s max_gpa=%s skip=%d limit=%d)",
        department, min_gpa, max_gpa, skip, limit,
    )
    query = db.query(Student)
    if department:
        query = query.filter(Student.department.ilike(f"%{department}%"))
    if min_gpa is not None:
        query = query.filter(Student.gpa >= min_gpa)
    if max_gpa is not None:
        query = query.filter(Student.gpa <= max_gpa)
    students = query.offset(skip).limit(limit).all()

    cache.cache_set(
        cache_key,
        [_student_to_dict(s) for s in students],
        ttl=cache.CACHE_TTL_ALL_STUDENTS,
    )
    # MetricsHandler يلتقط "GET all students — returned" → crud.reads++
    logger.info("GET all students — returned %d records", len(students))
    return students


def get_student_by_id(db: Session, student_id: int) -> Student:
    cache_key = cache.key_student(student_id)
    cached = cache.cache_get(cache_key)
    if cached is not None:
        logger.debug("GET student id=%d — served from cache", student_id)
        student = db.query(Student).filter(Student.id == student_id).first()
        if student:
            return student

    logger.debug("GET student id=%d — querying DB", student_id)
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        logger.warning("GET student id=%d — NOT FOUND", student_id)
        raise HTTPException(status_code=404, detail="Student not found")

    cache.cache_set(cache_key, _student_to_dict(student), ttl=cache.CACHE_TTL_STUDENT_BY_ID)
    return student


def get_student_by_user_id(db: Session, user_id: int) -> Student:
    student = db.query(Student).filter(Student.user_id == user_id).first()
    if not student:
        logger.warning("GET student by user_id=%d — NOT FOUND", user_id)
        raise HTTPException(status_code=404, detail="Student profile not found")
    return student


def update_student(
    db: Session, student_id: int, data: StudentUpdate, updated_by_user_id: int
) -> Student:
    logger.info("UPDATE student id=%d by user_id=%d", student_id, updated_by_user_id)
    student = get_student_by_id(db, student_id)
    update_data = data.model_dump(exclude_unset=True)
    if not update_data:
        logger.warning("UPDATE student id=%d — no fields provided", student_id)
        raise HTTPException(status_code=400, detail="No fields to update")

    for field, value in update_data.items():
        setattr(student, field, value)
    student.updated_at = datetime.utcnow()

    log = AuditLog(
        user_id=updated_by_user_id,
        action="UPDATE",
        target_student_id=student_id,
        updated_fields=json.dumps(update_data),
    )
    db.add(log)
    db.commit()
    db.refresh(student)

    cache.cache_invalidate_student(student_id)
    # MetricsHandler يلتقط "UPDATE student id=N SUCCESS" → crud.updates++
    logger.info(
        "UPDATE student id=%d SUCCESS — fields=%s", student_id, list(update_data.keys())
    )
    return student


def delete_student(db: Session, student_id: int) -> dict:
    logger.info("DELETE student id=%d", student_id)
    student = get_student_by_id(db, student_id)
    db.delete(student)
    db.commit()

    cache.cache_invalidate_student(student_id)
    # MetricsHandler يلتقط "DELETE student id=N SUCCESS" → crud.deletes++
    logger.info("DELETE student id=%d SUCCESS", student_id)
    return {"message": f"Student {student_id} deleted successfully"}
