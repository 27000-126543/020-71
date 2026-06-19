from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import RuleConfig
from app.db_session import get_db
from app.models import (
    RuleConfigCreate,
    RuleConfigResponse,
    RuleConfigUpdate,
)

router = APIRouter(prefix="/rules", tags=["规则配置"])


@router.post("/", response_model=RuleConfigResponse, summary="创建规则配置")
async def create_rule(
    data: RuleConfigCreate,
    db: AsyncSession = Depends(get_db),
):
    existing = await db.execute(select(RuleConfig).where(RuleConfig.scene == data.scene))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"场景 [{data.scene}] 的规则已存在")

    rule = RuleConfig(
        scene=data.scene,
        observe_threshold=data.observe_threshold,
        review_threshold=data.review_threshold,
        block_threshold=data.block_threshold,
        negative_consecutive_count=data.negative_consecutive_count,
        negative_consecutive_window_minutes=data.negative_consecutive_window_minutes,
    )
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return rule


@router.get("/", response_model=list[RuleConfigResponse], summary="获取全部规则配置")
async def list_rules(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(RuleConfig).order_by(RuleConfig.id))
    return result.scalars().all()


@router.get("/{scene}", response_model=RuleConfigResponse, summary="按场景获取规则配置")
async def get_rule(scene: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(RuleConfig).where(RuleConfig.scene == scene))
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail=f"场景 [{scene}] 的规则不存在")
    return rule


@router.put("/{scene}", response_model=RuleConfigResponse, summary="更新规则配置")
async def update_rule(
    scene: str,
    data: RuleConfigUpdate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(RuleConfig).where(RuleConfig.scene == scene))
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail=f"场景 [{scene}] 的规则不存在")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(rule, field, value)
    rule.updated_at = datetime.now()

    await db.commit()
    await db.refresh(rule)
    return rule


@router.delete("/{scene}", summary="删除规则配置")
async def delete_rule(scene: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(RuleConfig).where(RuleConfig.scene == scene))
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail=f"场景 [{scene}] 的规则不存在")

    await db.delete(rule)
    await db.commit()
    return {"detail": f"场景 [{scene}] 的规则已删除"}
