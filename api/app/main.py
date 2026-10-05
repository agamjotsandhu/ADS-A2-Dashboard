"""Rent forecast prediction API.

Run locally (from repo root):
    PYTHONPATH=api uvicorn app.main:app --reload --port 8000
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .schemas import PredictRequest, PredictResponse
from .service import RentService
from .settings import Settings


class RateLimiter:
    """Sliding-window limiter per client IP (in memory, per process)."""

    def __init__(self, per_minute: int):
        self.per_minute = per_minute
        self.hits: dict[str, deque[float]] = defaultdict(deque)
        self.lock = threading.Lock()

    def allow(self, key: str) -> bool:
        if self.per_minute <= 0:
            return True
        now = time.monotonic()
        with self.lock:
            q = self.hits[key]
            while q and now - q[0] > 60:
                q.popleft()
            if len(q) >= self.per_minute:
                return False
            q.append(now)
            return True


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.service = RentService(settings)
        yield

    app = FastAPI(title="Rent forecast API", version="1.0.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )
    limiter = RateLimiter(settings.rate_limit_per_minute)

    @app.middleware("http")
    async def rate_limit(request: Request, call_next):
        if request.url.path == "/predict":
            ip = request.client.host if request.client else "unknown"
            if settings.trust_proxy:
                fwd = request.headers.get("x-forwarded-for")
                if fwd:
                    ip = fwd.split(",")[0].strip()
            if not limiter.allow(ip):
                return JSONResponse({"detail": "Too many requests, please wait a minute."}, status_code=429)
        return await call_next(request)

    @app.get("/health")
    def health(request: Request):
        svc: RentService = request.app.state.service
        return {
            "status": "ok",
            "model": svc.meta["model"],
            "xgboost_version": svc.meta["xgboost_version"],
            "suburbs": len(svc.lookup) - 1,
            "forecasts_loaded": len(svc.forecasts),
        }

    @app.get("/suburbs")
    def suburbs(request: Request):
        return request.app.state.service.suburbs_payload()

    @app.post("/predict", response_model=PredictResponse)
    def predict(body: PredictRequest, request: Request):
        try:
            return request.app.state.service.predict(body)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e)) from e

    return app


app = create_app()
