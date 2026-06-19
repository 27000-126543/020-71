import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AnalysisResult, RuleConfig
from app.db_session import get_db
from app.engine import analyze_sentiment, is_negative
from app.models import CommentSubmitRequest, EmotionCategory, SentimentResponse

router = APIRouter(tags=["情绪研判"])


async def _get_thresholds(scene: str, db: AsyncSession) -> dict:
    result = await db.execute(select(RuleConfig).where(RuleConfig.scene == scene))
    rule = result.scalar_one_or_none()
    if rule:
        return {
            "observe_threshold": rule.observe_threshold,
            "review_threshold": rule.review_threshold,
            "block_threshold": rule.block_threshold,
        }
    return {"observe_threshold": 0.4, "review_threshold": 0.7, "block_threshold": 0.9}


@router.post(
    "/analyze",
    response_model=SentimentResponse,
    summary="单条评论情绪研判",
    description="提交评论内容、帖子标题、作者身份和发布时间，返回情绪类别、强度分值、风险原因和建议动作。",
)
async def analyze_comment(
    data: CommentSubmitRequest,
    db: AsyncSession = Depends(get_db),
):
    existing = await db.execute(
        select(AnalysisResult).where(AnalysisResult.comment_id == data.comment_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"评论 [{data.comment_id}] 已分析过")

    thresholds = await _get_thresholds(data.scene, db)

    analysis = analyze_sentiment(
        content=data.content,
        post_title=data.post_title,
        scene=data.scene,
        thresholds=thresholds,
    )

    record = AnalysisResult(
        comment_id=data.comment_id,
        post_id=data.post_id,
        post_title=data.post_title,
        content=data.content,
        author_id=data.author_id,
        author_name=data.author_name,
        published_at=data.published_at,
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
    await db.commit()

    return SentimentResponse(
        comment_id=data.comment_id,
        emotion_category=analysis["emotion_category"],
        emotion_label=analysis["emotion_label"],
        intensity_score=analysis["intensity_score"],
        risk_reasons=analysis["risk_reasons"],
        suggested_action=analysis["suggested_action"],
        action_label=analysis["action_label"],
        analyzed_at=datetime.now(),
    )


@router.get(
    "/result/{comment_id}",
    response_model=SentimentResponse,
    summary="查询评论分析结果",
)
async def get_analysis_result(
    comment_id: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AnalysisResult).where(AnalysisResult.comment_id == comment_id)
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail=f"评论 [{comment_id}] 无分析记录")

    risk_reasons = json.loads(record.risk_reasons_json) if record.risk_reasons_json else []

    return SentimentResponse(
        comment_id=record.comment_id,
        emotion_category=EmotionCategory(record.emotion_category),
        emotion_label=record.emotion_label,
        intensity_score=record.intensity_score,
        risk_reasons=risk_reasons,
        suggested_action=record.suggested_action,
        action_label=record.action_label,
        analyzed_at=record.analyzed_at,
    )
