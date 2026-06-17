from fastapi import APIRouter

from app.api.v1 import (
    admin_settings,
    audit,
    auth,
    chat,
    courses,
    grades,
    imports,
    llm_config,
    notifications,
    programs,
    progress,
    students,
    users,
    warning_rules,
    warnings,
)

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
router.include_router(notifications.router, prefix="/notifications", tags=["notifications"])
router.include_router(chat.router, prefix="/chat", tags=["chat"])
router.include_router(llm_config.router, prefix="/admin/llm-config", tags=["llm-config"])
router.include_router(audit.router, prefix="/admin", tags=["audit"])
router.include_router(warning_rules.router, prefix="/admin/warning-rules", tags=["warning-rules"])
router.include_router(admin_settings.router, prefix="/admin", tags=["admin-settings"])
