from fastapi import APIRouter, Depends, Query

from app.api.deps import DbSession, require_staff
from app.services import stats as stats_svc

router = APIRouter(dependencies=[Depends(require_staff)])


@router.get("/overview", summary="大盘指标")
def overview(db: DbSession, college: str | None = None):
    return stats_svc.overview(db, college=college)


@router.get("/warning-trend", summary="按学期分组的预警趋势")
def warning_trend(db: DbSession, semesters: int = Query(6, ge=1, le=24)):
    return stats_svc.warning_trend(db, semesters=semesters)


@router.get("/class-ranking", summary="班级完成度排名（升序）")
def class_ranking(
    db: DbSession,
    college: str | None = None,
    enroll_year: int | None = None,
):
    return stats_svc.class_ranking(db, college=college, enroll_year=enroll_year)


@router.get("/distribution", summary="按维度聚合预警分布")
def distribution(db: DbSession, dim: str = Query("college", pattern="^(college|major|class_name)$")):
    return stats_svc.level_distribution(db, dim=dim)


@router.post("/refresh-snapshots", summary="手动刷新学业进度快照")
def refresh_snapshots(db: DbSession):
    n = stats_svc.refresh_snapshots(db)
    return {"refreshed": n}
