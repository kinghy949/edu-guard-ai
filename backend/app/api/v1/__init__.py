from fastapi import APIRouter

from app.api.v1 import auth, courses, grades, programs, students, users

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

# TODO(M2/M3/M4): warnings / notifications / chat
