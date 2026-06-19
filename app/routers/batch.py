import json
from collections import defaultdict
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AnalysisResult, RuleConfig
from app.db_session import get_db
from app.engine import analyze_sentiment
from app.models import (
    BatchCommentItem,
    BatchReviewResponse,
    BatchSubmitRequest,
    BatchSubmitResponse,
    IgnitingComment,
    SentimentResponse,
    SentimentTrendPoint,
)
from app.models import EmotionCategory as EC

router = APIRouter(prefix="/batch", tags=["批量回查"])


async def _get_thresholds(scene: str, db: AsyncSession) -> dict:
    result = await db.execute(select(RuleConfig).where(RuleConfig.scene == scene))
    rule = result.scalar_one_or_none()
    if rule:
        return {
            "observe_threshold": rule.observe_threshold,
            "review_threshold": rule.review_threshold,
            "block_threshold": rule.block_threshold,
        }
    return {
        "observe_threshold": 0.4,
        "review_threshold": 0.7,
        "block_threshold": 0.9,
    }


@router.post("/submit", response_model=BatchSubmitResponse, summary="批量提交评论分析")
async def batch_submit(
    data: BatchSubmitRequest,
    db: AsyncSession = Depends(get_db),
):
    thresholds = await _get_thresholds(data.scene, db)
    results: list[SentimentResponse] = []

    for item in data.comments:
        existing = await db.execute(
            select(AnalysisResult).where(AnalysisResult.comment_id == item.comment_id)
        )
        if existing.scalar_one_or_none():
            continue

        analysis = analyze_sentiment(
            content=item.content,
            post_title=item.post_title,
            scene=data.scene,
            thresholds=thresholds,
        )

        record = AnalysisResult(
            comment_id=item.comment_id,
            post_id=item.post_id,
            post_title=item.post_title,
            content=item.content,
            author_id=item.author_id,
            author_name=item.author_name,
            published_at=item.published_at,
            scene=data.scene,
            emotion_category=analysis["emotion_category"].value,
            emotion_label=analysis["emotion_label"],
            intensity_score=analysis["intensity_score"],
            risk_reasons_json=json.dumps(
                [r.model_dump() for r in analysis["risk_reasons"]], ensure_ascii=False
            ),
            suggested_action=analysis["suggested_action"].value,
            action_label=analysis["action_label"],
        )
        db.add(record)

        resp = SentimentResponse(
            comment_id=item.comment_id,
            emotion_category=analysis["emotion_category"],
            emotion_label=analysis["emotion_label"],
            intensity_score=analysis["intensity_score"],
            risk_reasons=analysis["risk_reasons"],
            suggested_action=analysis["suggested_action"],
            action_label=analysis["action_label"],
            analyzed_at=datetime.now(),
        )
        results.append(resp)

    await db.commit()
    return BatchSubmitResponse(total=len(results), results=results)


@router.get("/review/{post_id}", response_model=BatchReviewResponse, summary="查看帖子情绪变化趋势")
async def batch_review(
    post_id: str,
    interval_minutes: int = Query(default=60, ge=5, description="趋势时间粒度(分钟)"),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AnalysisResult)
        .where(AnalysisResult.post_id == post_id)
        .order_by(AnalysisResult.published_at)
    )
    records = result.scalars().all()

    if not records:
        raise HTTPException(status_code=404, detail=f"帖子 [{post_id}] 无分析记录")

    buckets: dict[str, list[AnalysisResult]] = defaultdict(list)
    for r in records:
        dt = r.published_at
        bucket_start = dt.replace(
            minute=(dt.minute // (interval_minutes)) * interval_minutes,
            second=0,
            microsecond=0,
        )
        key = bucket_start.strftime("%Y-%m-%d %H:%M")
        buckets[key].append(r)

    trend: list[SentimentTrendPoint] = []
    for key in sorted(buckets.keys()):
        items = buckets[key]
        scores = [i.intensity_score for i in items]
        neg_count = sum(
            1
            for i in items
            if i.emotion_category
            in (EC.NEGATIVE_MILD.value, EC.NEGATIVE_MODERATE.value, EC.NEGATIVE_SEVERE.value)
        )
        trend.append(
            SentimentTrendPoint(
                time_bucket=key,
                avg_intensity=round(sum(scores) / len(scores), 4),
                negative_ratio=round(neg_count / len(items), 4),
                comment_count=len(items),
            )
        )

    igniting: list[IgnitingComment] = []
    neg_records = [
        r
        for r in records
        if r.emotion_category
        in (EC.NEGATIVE_MODERATE.value, EC.NEGATIVE_SEVERE.value)
    ]
    neg_records.sort(key=lambda r: r.published_at)
    for r in neg_records[:5]:
        igniting.append(
            IgnitingComment(
                comment_id=r.comment_id,
                content=r.content[:200],
                author_name=r.author_name,
                published_at=r.published_at,
                intensity_score=r.intensity_score,
                emotion_category=EC(r.emotion_category),
            )
        )

    return BatchReviewResponse(
        post_id=post_id,
        total_comments=len(records),
        trend=trend,
        igniting_comments=igniting,
    )
