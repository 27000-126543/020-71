from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.db_session import init_db
from app.routers import analyze, batch, notifications, rules


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title="评论情绪研判服务",
    description="面向社区平台开发者和内容安全团队的后端评论情绪研判服务。支持单条/批量评论分析、规则配置、情绪趋势回查和预警通知。",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(analyze.router)
app.include_router(rules.router)
app.include_router(batch.router)
app.include_router(notifications.router)


@app.get("/", summary="健康检查")
async def health_check():
    return {"service": "comment-sentiment", "status": "running", "version": "1.0.0"}
