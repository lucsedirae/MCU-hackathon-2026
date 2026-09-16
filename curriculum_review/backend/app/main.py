import logging

from fastapi import FastAPI, Request, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.database import engine
from app.llm import router as llm_router
from app.auth import router as auth_router, administrator
from app.documents import router as documents_router, recover_runs
from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app):
    recover_runs()
    yield


app = FastAPI(title="Cadence", version="0.2.0", lifespan=lifespan)
logger = logging.getLogger(__name__)
app.include_router(llm_router, dependencies=[Depends(administrator)])
app.include_router(auth_router)
app.include_router(documents_router)


@app.middleware("http")
async def guard_local_api(request: Request, call_next):
    if request.url.path.startswith("/api/"):
        if request.method not in ("GET", "HEAD", "OPTIONS") and request.headers.get(
            "sec-fetch-site"
        ) in ("cross-site", "same-site"):
            return JSONResponse(
                status_code=403,
                content={"detail": "Use this application's page to make changes."},
            )
    response = await call_next(request)
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/api/health")
def health():
    """Readiness check that verifies an actual database connection."""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        logger.exception("Database health check failed")
        return JSONResponse(
            status_code=503,
            content={"status": "degraded", "api": "ok", "database": "unavailable"},
        )
    return {"status": "ok", "api": "ok", "database": "ok"}


@app.get("/api")
def root():
    return {
        "name": "curriculum_review",
        "message": "Document history and team review API.",
    }
