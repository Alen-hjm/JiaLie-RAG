import traceback
import uuid
from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from .bootstrap import bootstrap
from .config import get_settings
from .db import get_db
from .routers import audits, auth, conversations, jobs, resumes, settings as settings_router
from .services.vectors import vector_stats

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    bootstrap()
    yield


app = FastAPI(title=settings.app_name, version="0.1.0", docs_url="/api/docs", openapi_url="/api/openapi.json", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=[settings.web_origin], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
    try:
        response = await call_next(request)
    except Exception:
        # 500 不能只返回 "服务暂时不可用"——那等于把原因吞掉，排查只能靠猜。
        # 这里把完整堆栈打到控制台（用户盯着的那个窗口），带上 request_id 方便对上。
        print(f"[500] request_id={request_id} path={request.url.path}", flush=True)
        traceback.print_exc()
        response = JSONResponse(status_code=500, content={"detail": {"code": "INTERNAL_ERROR", "message": "服务暂时不可用", "request_id": request_id}})
    response.headers["x-request-id"] = request_id
    return response


@app.get("/api/health")
def health(db: Session = Depends(get_db)):
    # Settings can be changed from the UI without restarting the process.
    settings = get_settings()
    stats = vector_stats(db)
    return {
        "status": "ok",
        "model_mode": settings.model_mode,
        "chat_provider": settings.chat_provider,
        "chat_model": settings.chat_model,
        "orchestration_mode": settings.orchestration_mode,
        "embedding_provider": settings.embedding_provider,
        "embedding_mode": settings.embedding_mode,
        "embedding_model": settings.embedding_model,
        "embedding_dimensions": settings.embedding_dimensions,
        # True means vectors are deterministic hashes, not semantics -- surfaced so
        # the demo never claims "semantic match" while ranking on placeholders.
        "embedding_is_placeholder": settings.embedding_is_placeholder,
        "vectors_need_reindex": stats["needs_reindex"],
        "mismatched_vectors": stats["mismatched_vectors"],
        "total_chunks": stats["total_chunks"],
    }

app.include_router(auth.router)
app.include_router(resumes.router)
app.include_router(jobs.router)
app.include_router(conversations.router)
app.include_router(audits.router)
app.include_router(settings_router.router)
