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


def _find_rising_negative_chain(
    records_asc: list[AnalysisResult],
    min_chain_length: int,
) -> list[AnalysisResult] | None:
    """
    在按时间升序排列的评论中，寻找**尾部**最近出现的连续负面且强度整体走高的评论链。
    规则：
      1. 从最后一条向前遍历，只要遇到非负面（positive/neutral）就断开
      2. 链内要求：每条的强度 >= 前一条强度的 0.9 倍（允许小波动），
         且整体最后一条强度 > 第一条强度（总体趋势走高）
      3. 链长 >= min_chain_length 即返回这条链（按时间升序）
    """
    if len(records_asc) < min_chain_length:
        return None

    chain: list[AnalysisResult] = []
    for r in reversed(records_asc):
        cat = EmotionCategory(r.emotion_category)
        if not is_negative(cat):
            break
        chain.insert(0, r)

    if len(chain) < min_chain_length:
        return None

    first_score = chain[0].intensity_score
    last_score = chain[-1].intensity_score
    if last_score <= first_score:
        return None

    strictly_rising = True
    for i in range(1, len(chain)):
        if chain[i].intensity_score < chain[i - 1].intensity_score * 0.9:
            strictly_rising = False
            break
    if not strictly_rising:
        return None

    return chain


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
        .order_by(AnalysisResult.published_at.asc())
    )
    records_all = result.scalars().all()

    if not records_all:
        raise HTTPException(status_code=404, detail=f"帖子 [{post_id}] 无分析记录")

    cutoff = datetime.now() - timedelta(minutes=window_minutes)
    records_in_window = [r for r in records_all if r.published_at >= cutoff]

    chain = _find_rising_negative_chain(records_in_window, consecutive_count)

    if chain is None:
        neg_count = sum(
            1 for r in records_in_window if is_negative(EmotionCategory(r.emotion_category))
        )
        return {
            "post_id": post_id,
            "alert_triggered": False,
            "negative_count_in_window": neg_count,
            "threshold": consecutive_count,
            "window_minutes": window_minutes,
            "message": "未发现连续走高的负面情绪链（可能被中性/正面评论打断，或强度未上升）",
        }

    chain_lines = []
    negative_severe_count = 0
    negative_moderate_count = 0
    for idx, r in enumerate(chain, start=1):
        cat = EmotionCategory(r.emotion_category)
        if cat == EmotionCategory.NEGATIVE_SEVERE:
            negative_severe_count += 1
        elif cat == EmotionCategory.NEGATIVE_MODERATE:
            negative_moderate_count += 1
        time_str = r.published_at.strftime("%H:%M:%S")
        chain_lines.append(
            f"  [{idx}] {time_str} {r.author_name or '匿名用户'} (强度{r.intensity_score:.3f}): {r.content[:80]}"
        )
    chain_text = "\n".join(chain_lines)

    stats = []
    if negative_severe_count:
        stats.append(f"重度负面 {negative_severe_count} 条")
    if negative_moderate_count:
        stats.append(f"中度负面 {negative_moderate_count} 条")
    stats_text = "，".join(stats) if stats else "连续负面评论"

    intensity_trend = f"{chain[0].intensity_score:.3f} → {chain[-1].intensity_score:.3f}"

    summary = (
        f"帖子 [{post_id}] 在最近 {window_minutes} 分钟内出现 {len(chain)} 条"
        f"情绪连续走高的负面评论（强度趋势 {intensity_trend}，{stats_text}）。\n"
        f"评论链路如下：\n{chain_text}"
    )

    target_roles = ["moderator", "customer_service"]
    if negative_severe_count:
        target_roles.append("pr_team")

    log = NotificationLog(
        post_id=post_id,
        scene=scene,
        negative_count=len(chain),
        window_minutes=window_minutes,
        summary=summary,
        target_roles_json=json.dumps(target_roles, ensure_ascii=False),
        sent_at=datetime.now(),
        status="sent",
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)

    chain_preview = [
        {
            "comment_id": r.comment_id,
            "published_at": r.published_at.isoformat(),
            "author_name": r.author_name,
            "intensity_score": r.intensity_score,
            "emotion_category": r.emotion_category,
            "content_snippet": r.content[:80],
        }
        for r in chain
    ]

    return {
        "post_id": post_id,
        "alert_triggered": True,
        "negative_count_in_window": len(chain),
        "threshold": consecutive_count,
        "window_minutes": window_minutes,
        "intensity_trend": intensity_trend,
        "summary": summary,
        "target_roles": target_roles,
        "notification_id": log.id,
        "rising_chain": chain_preview,
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
