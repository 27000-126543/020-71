from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class EmotionCategory(str, Enum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE_MILD = "negative_mild"
    NEGATIVE_MODERATE = "negative_moderate"
    NEGATIVE_SEVERE = "negative_severe"


class SuggestedAction(str, Enum):
    OBSERVE = "observe"
    REVIEW = "review"
    BLOCK = "block"
    ALERT = "alert"


class CommentSubmitRequest(BaseModel):
    comment_id: str = Field(..., description="评论唯一ID")
    post_id: str = Field(..., description="帖子ID")
    post_title: str = Field(default="", description="帖子标题")
    content: str = Field(..., description="评论内容")
    author_id: str = Field(..., description="作者ID")
    author_name: str = Field(default="", description="作者昵称")
    published_at: datetime = Field(default_factory=datetime.now, description="发布时间")
    scene: str = Field(default="default", description="业务场景标识")


class RiskReason(BaseModel):
    category: str = Field(..., description="风险类别")
    matched_keywords: list[str] = Field(default_factory=list, description="命中关键词")
    description: str = Field(..., description="风险描述")


class SentimentResponse(BaseModel):
    comment_id: str
    emotion_category: EmotionCategory
    emotion_label: str
    intensity_score: float = Field(..., ge=0, le=1, description="情绪强度分值 0-1")
    risk_reasons: list[RiskReason] = Field(default_factory=list)
    suggested_action: SuggestedAction
    action_label: str
    analyzed_at: datetime = Field(default_factory=datetime.now)


class RuleConfigCreate(BaseModel):
    scene: str = Field(..., description="业务场景标识")
    observe_threshold: float = Field(default=0.4, ge=0, le=1)
    review_threshold: float = Field(default=0.7, ge=0, le=1)
    block_threshold: float = Field(default=0.9, ge=0, le=1)
    negative_consecutive_count: int = Field(default=3, ge=1)
    negative_consecutive_window_minutes: int = Field(default=30, ge=1)


class RuleConfigUpdate(BaseModel):
    observe_threshold: Optional[float] = Field(default=None, ge=0, le=1)
    review_threshold: Optional[float] = Field(default=None, ge=0, le=1)
    block_threshold: Optional[float] = Field(default=None, ge=0, le=1)
    negative_consecutive_count: Optional[int] = Field(default=None, ge=1)
    negative_consecutive_window_minutes: Optional[int] = Field(default=None, ge=1)


class RuleConfigResponse(BaseModel):
    id: int
    scene: str
    observe_threshold: float
    review_threshold: float
    block_threshold: float
    negative_consecutive_count: int
    negative_consecutive_window_minutes: int
    created_at: datetime
    updated_at: datetime


class BatchCommentItem(BaseModel):
    comment_id: str
    post_id: str
    post_title: str = ""
    content: str
    author_id: str
    author_name: str = ""
    published_at: datetime


class BatchSubmitRequest(BaseModel):
    scene: str = Field(default="default", description="业务场景标识")
    comments: list[BatchCommentItem] = Field(..., min_length=1)


class BatchSubmitResponse(BaseModel):
    total: int
    results: list[SentimentResponse]


class SentimentTrendPoint(BaseModel):
    time_bucket: str = Field(..., description="时间区间标识")
    avg_intensity: float
    negative_ratio: float
    comment_count: int


class IgnitingComment(BaseModel):
    comment_id: str
    content: str
    author_name: str
    published_at: datetime
    intensity_score: float
    emotion_category: EmotionCategory


class BatchReviewResponse(BaseModel):
    post_id: str
    total_comments: int
    trend: list[SentimentTrendPoint]
    igniting_comments: list[IgnitingComment]


class NotificationRecord(BaseModel):
    id: int
    post_id: str
    scene: str
    negative_count: int
    window_minutes: int
    summary: str
    target_roles: list[str]
    sent_at: datetime
    status: str


class NotificationQueryResponse(BaseModel):
    total: int
    notifications: list[NotificationRecord]
