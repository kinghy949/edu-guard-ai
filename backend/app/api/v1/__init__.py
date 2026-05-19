from fastapi import APIRouter

router = APIRouter()


@router.get("/ping")
def ping():
    return {"pong": True}


# TODO: include sub-routers in M1
# from app.api.v1 import auth, students, programs, grades, warnings, chat
# router.include_router(auth.router, prefix="/auth", tags=["auth"])
# router.include_router(students.router, prefix="/students", tags=["students"])
# router.include_router(programs.router, prefix="/programs", tags=["programs"])
# router.include_router(grades.router, prefix="/grades", tags=["grades"])
# router.include_router(warnings.router, prefix="/warnings", tags=["warnings"])
# router.include_router(chat.router, prefix="/chat", tags=["chat"])
