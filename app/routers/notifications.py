import json
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AnalysisResult, NotificationLog, RuleConfig
from app.db_session import get_db
from app.engine import is_negative
from app.models import (
    EmotionCategory,
    NotificationQueryResponse,
    NotificationRecord,
)

router = APIRouter(prefix="/notifications", tags=["通知分发"])


@router.post("/check/{post_id}", summary="检查帖子负面情绪并发送通知")
async def check_and_notify(
    post_id: str,
    scene: str = Query(default="default", description="业务场景"),
    db: AsyncSession = Depends(get_db),
):
    rule_result = await db.execute(select(RuleConfig).where(RuleConfig.scene == scene))
    rule = rule_result.scalar_one_or_none()

    consecutive_count = rule.negative_consecutive_count if rule else 3
    window_minutes = rule.negative_consecutive_window_minutes if rule else 30

    result = await db.execute(
        select(AnalysisResult)
        .where(AnalysisResult.post_id == post_id)
        .order_by(AnalysisResult.published_at.desc())
    )
    records = result.scalars().all()

    if not records:
        raise HTTPException(status_code=404, detail=f"帖子 [{post_id}] 无分析记录")

    cutoff = datetime.now() - timedelta(minutes=window_minutes)
    recent_negative = [
        r
        for r in records
        if r.published_at >= cutoff
        and is_negative(EmotionCategory(r.emotion_category))
    ]

    if len(recent_negative) < consecutive_count:
        return {
            "post_id": post_id,
            "alert_triggered": False,
            "negative_count_in_window": len(recent_negative),
            "threshold": consecutive_count,
            "message": "负面情绪未达到预警阈值",
        }

    negative_moderate = [
        r for r in recent_negative if r.emotion_category == EmotionCategory.NEGATIVE_MODERATE.value
    ]
    negative_severe = [
        r for r in recent_negative if r.emotion_category == EmotionCategory.NEGATIVE_SEVERE.value
    ]

    summary_parts = []
    if negative_severe:
        summary_parts.append(f"重度负面评论 {len(negative_severe)} 条")
    if negative_moderate:
        summary_parts.append(f"中度负面评论 {len(negative_moderate)} 条")

    top_comments = sorted(recent_negative, key=lambda r: r.intensity_score, reverse=True)[:3]
    snippet_lines = [f"- {r.author_name}: {r.content[:80]}" for r in top_comments]
    snippet_text = "\n".join(snippet_lines)

    summary = f"帖子 [{post_id}] 在最近 {window_minutes} 分钟内出现连续负面情绪。{', '.join(summary_parts)}。代表性评论:\n{snippet_text}"

    target_roles = ["moderator", "customer_service"]
    if negative_severe:
        target_roles.append("pr_team")

    log = NotificationLog(
        post_id=post_id,
        scene=scene,
        negative_count=len(recent_negative),
        window_minutes=window_minutes,
        summary=summary,
        target_roles_json=json.dumps(target_roles, ensure_ascii=False),
        sent_at=datetime.now(),
        status="sent",
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)

    return {
        "post_id": post_id,
        "alert_triggered": True,
        "negative_count_in_window": len(recent_negative),
        "threshold": consecutive_count,
        "summary": summary,
        "target_roles": target_roles,
        "notification_id": log.id,
        "message": "预警通知已发送",
    }


@router.get("/", response_model=NotificationQueryResponse, summary="查询通知记录")
async def query_notifications(
    post_id: str | None = Query(default=None, description="按帖子ID筛选"),
    scene: str | None = Query(default=None, description="按场景筛选"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    query = select(NotificationLog).order_by(NotificationLog.sent_at.desc())

    if post_id:
        query = query.where(NotificationLog.post_id == post_id)
    if scene:
        query = query.where(NotificationLog.scene == scene)

    count_result = await db.execute(query)
    all_records = count_result.scalars().all()
    total = len(all_records)

    query = query.offset(offset).limit(limit)
    result = await db.execute(query)
    records = result.scalars().all()

    notifications = []
    for r in records:
        target_roles = json.loads(r.target_roles_json) if r.target_roles_json else []
        notifications.append(
            NotificationRecord(
                id=r.id,
                post_id=r.post_id,
                scene=r.scene,
                negative_count=r.negative_count,
                window_minutes=r.window_minutes,
                summary=r.summary,
                target_roles=target_roles,
                sent_at=r.sent_at,
                status=r.status,
            )
        )

    return NotificationQueryResponse(total=total, notifications=notifications)
