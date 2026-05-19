from fastapi import APIRouter

from app.api.v1 import auth, courses, grades, imports, progress, programs, students, users, warnings

router = APIRouter()


@router.get("/ping")
def ping():
    return {"pong": True}


router.include_router(auth.router, prefix="/auth", tags=["auth"])
router.include_router(users.router, prefix="/users", tags=["users"])
router.include_router(students.router, prefix="/students", tags=["students"])
router.include_router(programs.router, prefix="/programs", tags=["programs"])
router.include_router(courses.router, prefix="/courses", tags=["courses"])
router.include_router(grades.router, prefix="/grades", tags=["grades"])
router.include_router(imports.router, prefix="/imports", tags=["imports"])
router.include_router(progress.router, prefix="/progress", tags=["progress"])
router.include_router(warnings.router, prefix="/warnings", tags=["warnings"])

# TODO(M3/M4): notifications / chat
