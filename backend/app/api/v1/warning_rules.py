from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession, require_admin
from app.models.warning_rule import WarningRuleORM
from app.schemas.warning_rule import WarningRuleCreate, WarningRuleRead, WarningRuleUpdate

router = APIRouter(dependencies=[Depends(require_admin)])


def _is_global(rule: WarningRuleORM) -> bool:
    return not rule.scope_college and not rule.scope_major


@router.get("", response_model=list[WarningRuleRead], summary="预警规则列表")
def list_rules(db: DbSession):
    rules = db.scalars(
        select(WarningRuleORM).order_by(WarningRuleORM.priority.desc(), WarningRuleORM.id.asc())
    )
    return [WarningRuleRead.model_validate(r) for r in rules]


@router.post("", response_model=WarningRuleRead, summary="新建预警规则")
def create_rule(payload: WarningRuleCreate, db: DbSession, current: CurrentUser):
    rule = WarningRuleORM(updated_by=current.id, **payload.model_dump())
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return WarningRuleRead.model_validate(rule)


@router.patch("/{rule_id}", response_model=WarningRuleRead, summary="更新预警规则")
def update_rule(rule_id: int, payload: WarningRuleUpdate, db: DbSession, current: CurrentUser):
    rule = db.get(WarningRuleORM, rule_id)
    if not rule:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "规则不存在")
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(rule, k, v)
    rule.updated_by = current.id
    db.commit()
    db.refresh(rule)
    return WarningRuleRead.model_validate(rule)


@router.delete("/{rule_id}", summary="删除预警规则（全局默认不可删）")
def delete_rule(rule_id: int, db: DbSession):
    rule = db.get(WarningRuleORM, rule_id)
    if not rule:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "规则不存在")
    if _is_global(rule):
        # 确保至少保留一条全局规则
        remaining_global = db.scalar(
            select(WarningRuleORM).where(
                WarningRuleORM.id != rule.id,
                WarningRuleORM.scope_college.is_(None),
                WarningRuleORM.scope_major.is_(None),
            )
        )
        if remaining_global is None:
            raise HTTPException(status.HTTP_409_CONFLICT, "至少保留一条全局规则")
    db.delete(rule)
    db.commit()
    return {"ok": True}
