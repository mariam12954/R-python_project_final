from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional

from app.schemas.student import StudentCreate, StudentUpdate, StudentOut
from app.services.student_service import (
    create_student, get_all_students, get_student_by_id,
    get_student_by_user_id, update_student, delete_student,
)
from app.models.user import User
from app.dependencies import get_db, get_current_user, require_admin

router = APIRouter(prefix="/students", tags=["Students"])


# POST — Admin only
@router.post("/", response_model=StudentOut, status_code=201)
def create(
    data: StudentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    return create_student(db, data)


# GET all — Admin only, with filter + pagination
@router.get("/", response_model=List[StudentOut])
def list_students(
    department: Optional[str] = Query(None),
    min_gpa: Optional[float] = Query(None, ge=0.0, le=4.0),
    max_gpa: Optional[float] = Query(None, ge=0.0, le=4.0),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    return get_all_students(db, department, min_gpa, max_gpa, skip, limit)


# GET my profile — Student sees own data only
@router.get("/me", response_model=StudentOut)
def my_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_student_by_user_id(db, current_user.id)


# GET by ID — Admin gets any, Student gets own only
@router.get("/{student_id}", response_model=StudentOut)
def get_one(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    student = get_student_by_id(db, student_id)
    if current_user.role != "admin" and student.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    return student


# PUT — Admin edits any, Student edits own only
@router.put("/{student_id}", response_model=StudentOut)
def update(
    student_id: int,
    data: StudentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    student = get_student_by_id(db, student_id)
    if current_user.role != "admin" and student.user_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="Access denied — you can only edit your own profile",
        )
    return update_student(db, student_id, data, current_user.id)


# DELETE — Admin only
@router.delete("/{student_id}", status_code=200)
def delete(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    return delete_student(db, student_id)
