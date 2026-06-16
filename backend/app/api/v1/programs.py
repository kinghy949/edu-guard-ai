from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.api.deps import DbSession, require_admin, require_staff
from app.api.v1._helpers import apply_updates, get_or_404
from app.models.program import CreditBucket, Program, ProgramCourse
from app.schemas.program import (
    CreditBucketCreate,
    CreditBucketRead,
    ProgramCourseCreate,
    ProgramCourseRead,
    ProgramCreate,
    ProgramRead,
    ProgramUpdate,
)

router = APIRouter()


# ----- Program 主表 -----

@router.get("", response_model=list[ProgramRead])
def list_programs(db: DbSession, skip: int = 0, limit: int = 100):
    return db.scalars(select(Program).offset(skip).limit(limit)).all()


@router.get("/{program_id}", response_model=ProgramRead)
def get_program(program_id: int, db: DbSession):
    return get_or_404(db, Program, program_id, "培养方案")


@router.post("", response_model=ProgramRead, dependencies=[Depends(require_admin)])
def create_program(payload: ProgramCreate, db: DbSession):
    if db.scalar(select(Program).where(Program.code == payload.code)):
        raise HTTPException(status.HTTP_409_CONFLICT, "方案编码已存在")
    program = Program(**payload.model_dump())
    db.add(program)
    db.commit()
    db.refresh(program)
    return program


@router.patch("/{program_id}", response_model=ProgramRead, dependencies=[Depends(require_admin)])
def update_program(program_id: int, payload: ProgramUpdate, db: DbSession):
    program = get_or_404(db, Program, program_id, "培养方案")
    apply_updates(program, payload.model_dump(exclude_unset=True))
    db.commit()
    db.refresh(program)
    return program


@router.delete("/{program_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_admin)])
def delete_program(program_id: int, db: DbSession):
    program = get_or_404(db, Program, program_id, "培养方案")
    db.delete(program)
    db.commit()


# ----- 学分桶 -----

@router.get("/{program_id}/buckets", response_model=list[CreditBucketRead])
def list_buckets(program_id: int, db: DbSession):
    get_or_404(db, Program, program_id, "培养方案")
    return db.scalars(select(CreditBucket).where(CreditBucket.program_id == program_id)).all()


@router.post("/{program_id}/buckets", response_model=CreditBucketRead, dependencies=[Depends(require_admin)])
def create_bucket(program_id: int, payload: CreditBucketCreate, db: DbSession):
    get_or_404(db, Program, program_id, "培养方案")
    if payload.program_id != program_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "program_id 与 URL 不一致")
    bucket = CreditBucket(**payload.model_dump())
    db.add(bucket)
    db.commit()
    db.refresh(bucket)
    return bucket


@router.delete("/buckets/{bucket_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_admin)])
def delete_bucket(bucket_id: int, db: DbSession):
    bucket = get_or_404(db, CreditBucket, bucket_id, "学分桶")
    db.delete(bucket)
    db.commit()


# ----- 培养方案 × 课程 -----

@router.get("/{program_id}/courses", response_model=list[ProgramCourseRead])
def list_program_courses(program_id: int, db: DbSession):
    get_or_404(db, Program, program_id, "培养方案")
    return db.scalars(select(ProgramCourse).where(ProgramCourse.program_id == program_id)).all()


@router.post("/{program_id}/courses", response_model=ProgramCourseRead, dependencies=[Depends(require_staff)])
def link_course(program_id: int, payload: ProgramCourseCreate, db: DbSession):
    get_or_404(db, Program, program_id, "培养方案")
    if payload.program_id != program_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "program_id 与 URL 不一致")
    pc = ProgramCourse(**payload.model_dump())
    db.add(pc)
    db.commit()
    db.refresh(pc)
    return pc


@router.delete("/courses/{pc_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_staff)])
def unlink_course(pc_id: int, db: DbSession):
    pc = get_or_404(db, ProgramCourse, pc_id, "方案-课程映射")
    db.delete(pc)
    db.commit()
