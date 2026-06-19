import json
import re
from datetime import datetime

from app.config import EMOTION_LABELS, KEYWORD_CATEGORIES, SUGGESTED_ACTIONS
from app.models import (
    EmotionCategory,
    RiskReason,
    SentimentResponse,
    SuggestedAction,
)

_NEGATIVE_BOOST_WORDS = {
    "都": 0.06,
    "全": 0.06,
    "太": 0.1,
    "极其": 0.12,
    "非常": 0.1,
    "特别": 0.08,
    "真的": 0.06,
    "简直": 0.1,
    "绝对": 0.08,
    "再也不": 0.12,
}

_NEGATION_WORDS = {"不", "没", "没有", "无", "别", "莫", "未", "非"}

_POSITIVE_PATTERNS = [
    r"好评", r"点赞", r"推荐", r"喜欢", r"棒", r"优秀", r"不错",
    r"满意", r"感谢", r"辛苦", r"支持", r"加油", r"厉害",
]


def _match_keywords(content: str) -> list[tuple[str, list[str]]]:
    matched = []
    for category, keywords in KEYWORD_CATEGORIES.items():
        hits = [kw for kw in keywords if kw in content]
        if hits:
            matched.append((category, hits))
    return matched


def _check_negative_exclamation(content: str) -> float:
    exclamation_count = content.count("！") + content.count("!")
    if exclamation_count >= 3:
        return 0.08
    if exclamation_count >= 1:
        return 0.03
    return 0.0


def _check_caps_ratio(content: str) -> float:
    if not content:
        return 0.0
    upper_count = sum(1 for c in content if c.isupper())
    alpha_count = sum(1 for c in content if c.isalpha())
    if alpha_count == 0:
        return 0.0
    ratio = upper_count / alpha_count
    if ratio > 0.6:
        return 0.05
    return 0.0


def _check_boost_words(content: str) -> float:
    boost = 0.0
    for word, score in _NEGATIVE_BOOST_WORDS.items():
        if word in content:
            boost += score
    return min(boost, 0.3)


def _check_positive_patterns(content: str) -> float:
    for pattern in _POSITIVE_PATTERNS:
        if re.search(pattern, content):
            return -0.15
    return 0.0


def _check_negation(content: str) -> float:
    for neg in _NEGATION_WORDS:
        if neg in content:
            return -0.08
    return 0.0


def analyze_sentiment(
    content: str,
    post_title: str = "",
    scene: str = "default",
    thresholds: dict | None = None,
) -> dict:
    if thresholds is None:
        thresholds = {
            "observe_threshold": 0.4,
            "review_threshold": 0.7,
            "block_threshold": 0.9,
        }

    matched_categories = _match_keywords(content)

    base_score = 0.0
    risk_reasons: list[RiskReason] = []

    category_weights = {
        "personal_attack": 0.6,
        "collective_rights": 0.5,
        "brand_boycott": 0.45,
        "complaint": 0.3,
    }

    per_keyword_bonus = {
        "personal_attack": 0.06,
        "collective_rights": 0.05,
        "brand_boycott": 0.05,
        "complaint": 0.04,
    }

    for category, keywords in matched_categories:
        weight = category_weights.get(category, 0.3)
        keyword_ratio = min(len(keywords) / max(len(KEYWORD_CATEGORIES.get(category, [])), 1), 1.0)
        bonus = per_keyword_bonus.get(category, 0.04) * len(keywords)
        base_score += weight * (0.5 + 0.5 * keyword_ratio) + bonus

        risk_reasons.append(
            RiskReason(
                category=category,
                matched_keywords=keywords,
                description=f"命中【{category}】类关键词: {', '.join(keywords)}",
            )
        )

    if post_title:
        title_matches = _match_keywords(post_title)
        for category, keywords in title_matches:
            if category not in [r.category for r in risk_reasons]:
                base_score += 0.05

    boost = _check_boost_words(content)
    exclamation_boost = _check_negative_exclamation(content)
    caps_boost = _check_caps_ratio(content)
    positive_offset = _check_positive_patterns(content)
    negation_offset = _check_negation(content)

    intensity_score = base_score + boost + exclamation_boost + caps_boost + positive_offset + negation_offset
    intensity_score = round(max(0.0, min(1.0, intensity_score)), 4)

    if intensity_score < 0.15:
        emotion_category = EmotionCategory.POSITIVE
    elif intensity_score < thresholds["observe_threshold"]:
        emotion_category = EmotionCategory.NEUTRAL
    elif intensity_score < thresholds["review_threshold"]:
        emotion_category = EmotionCategory.NEGATIVE_MILD
    elif intensity_score < thresholds["block_threshold"]:
        emotion_category = EmotionCategory.NEGATIVE_MODERATE
    else:
        emotion_category = EmotionCategory.NEGATIVE_SEVERE

    if emotion_category in (EmotionCategory.POSITIVE, EmotionCategory.NEUTRAL):
        suggested_action = SuggestedAction.OBSERVE
    elif emotion_category == EmotionCategory.NEGATIVE_MILD:
        suggested_action = SuggestedAction.OBSERVE
    elif emotion_category == EmotionCategory.NEGATIVE_MODERATE:
        suggested_action = SuggestedAction.REVIEW
    else:
        if any(r.category in ("personal_attack", "collective_rights", "brand_boycott") for r in risk_reasons):
            suggested_action = SuggestedAction.BLOCK
        else:
            suggested_action = SuggestedAction.ALERT

    return {
        "emotion_category": emotion_category,
        "emotion_label": EMOTION_LABELS.get(emotion_category.value, "未知"),
        "intensity_score": intensity_score,
        "risk_reasons": risk_reasons,
        "suggested_action": suggested_action,
        "action_label": SUGGESTED_ACTIONS.get(suggested_action.value, "未知"),
    }


def build_response(comment_data: dict, analysis: dict) -> SentimentResponse:
    return SentimentResponse(
        comment_id=comment_data["comment_id"],
        emotion_category=analysis["emotion_category"],
        emotion_label=analysis["emotion_label"],
        intensity_score=analysis["intensity_score"],
        risk_reasons=analysis["risk_reasons"],
        suggested_action=analysis["suggested_action"],
        action_label=analysis["action_label"],
        analyzed_at=datetime.now(),
    )


def is_negative(emotion_category: EmotionCategory) -> bool:
    return emotion_category in (
        EmotionCategory.NEGATIVE_MILD,
        EmotionCategory.NEGATIVE_MODERATE,
        EmotionCategory.NEGATIVE_SEVERE,
    )
