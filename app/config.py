import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./sentiment.db")

SENTIMENT_CONFIG = {
    "default": {
        "observe_threshold": 0.4,
        "review_threshold": 0.7,
        "block_threshold": 0.9,
        "negative_consecutive_count": 3,
        "negative_consecutive_window_minutes": 30,
    }
}

KEYWORD_CATEGORIES = {
    "personal_attack": [
        "垃圾", "废物", "白痴", "蠢货", "滚出", "去死",
        "傻逼", "脑残", "智障", "狗东西", "不要脸",
    ],
    "collective_rights": [
        "维权", "投诉", "举报", "集体", "联名", "上访",
        "拉横幅", "维权群", "消协", "12315",
    ],
    "brand_boycott": [
        "抵制", "封杀", "不买", "退坑", "脱粉", "取关",
        "黑心", "坑钱", "割韭菜", "再也不买", "避雷",
    ],
    "complaint": [
        "差评", "不满", "失望", "垃圾", "难用", "难吃",
        "太差", "不行", "退款", "退货", "坑", "骗",
    ],
}

EMOTION_LABELS = {
    "positive": "正面",
    "neutral": "中性",
    "negative_mild": "轻度负面",
    "negative_moderate": "中度负面",
    "negative_severe": "重度负面",
}

SUGGESTED_ACTIONS = {
    "observe": "观察",
    "review": "人工复核",
    "block": "拦截删除",
    "alert": "预警通知",
}
