"""FastAPI application: /health, /chat and /sessions/{id}/messages."""
from __future__ import annotations

import logging
import time
from typing import Callable

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import Settings, load_settings
from .db import Database
from .llm import AllProvidersUnavailable, LLMGateway
from .schemas import ChatRequest

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("chatbot")

SIMULATABLE_STATUSES = {429, 500, 502, 503}


def parse_failure_header(value: str | None) -> dict[str, int]:
    """'key_1=429,key_2=500' or '*=429' -> {'key_1': 429, 'key_2': 500}."""
    rules: dict[str, int] = {}
    for part in (value or "").split(","):
        target, sep, status = part.partition("=")
        target, status = target.strip(), status.strip()
        if sep and target and status.isdigit() and int(status) in SIMULATABLE_STATUSES:
            rules[target] = int(status)
    return rules


def create_app(
    settings: Settings | None = None,
    completion_fn: Callable | None = None,
) -> FastAPI:
    settings = settings or load_settings()
    db = Database(settings.database_path)
    db.init()
    gateway = LLMGateway(settings, completion_fn)

    # Docs/OpenAPI routes are disabled: the contract exposes exactly three endpoints.
    app = FastAPI(title="Chat API", docs_url=None, redoc_url=None, openapi_url=None)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.allowed_origins),
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    if not settings.api_keys:
        log.warning("LLM_API_KEYS is empty: /health will report unavailable")
    elif len(settings.api_keys) < 2:
        log.warning("Only one API key configured; failover needs at least two")

    # ---- error handling: always JSON with a `detail`, never a stack trace ----
    @app.exception_handler(RequestValidationError)
    async def validation_handler(_: Request, exc: RequestValidationError):
        errors = [
            {"loc": list(e.get("loc", [])), "msg": str(e.get("msg", "")), "type": e.get("type", "")}
            for e in exc.errors()
        ]
        return JSONResponse(status_code=422, content={"detail": errors})

    @app.exception_handler(Exception)
    async def unhandled_handler(_: Request, exc: Exception):
        log.exception("unhandled error", exc_info=exc)
        return JSONResponse(status_code=500, content={"detail": "internal server error"})

    # ---- endpoints ----
    @app.get("/health")
    def health():
        try:
            db.ping()
        except Exception:
            raise HTTPException(status_code=503, detail="database unavailable")
        if not settings.api_keys:
            raise HTTPException(status_code=503, detail="no api keys configured")
        return {
            "status": "ok",
            "keys_configured": len(settings.api_keys),
            "cache_enabled": gateway.cache_enabled,
        }

    # Sync endpoint: FastAPI runs it in a worker thread, so the blocking LLM call
    # does not stall other requests.
    @app.post("/chat")
    def chat(body: ChatRequest, x_simulate_failure: str | None = Header(default=None)):
        started = time.perf_counter()

        system_prompt = (
            body.system_prompt
            or db.get_system_prompt(body.session_id)
            or settings.default_system_prompt
        )
        history = db.get_history(body.session_id)[-settings.max_history_messages:]
        messages = (
            [{"role": "system", "content": system_prompt}]
            + history
            + [{"role": "user", "content": body.message}]
        )

        simulate = (
            parse_failure_header(x_simulate_failure)
            if settings.enable_failure_simulation
            else {}
        )

        try:
            result = gateway.complete(messages, simulate)
        except AllProvidersUnavailable:
            raise HTTPException(status_code=503, detail="all providers unavailable")

        metadata = {
            "resolution_source": "LLM_CACHE" if result.cache_hit else "LIVE_INFERENCE",
            "model": result.model,
            "latency_ms": max(1, round((time.perf_counter() - started) * 1000)),
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
            "key_id": result.key_id,
            "fallback_attempts": result.fallback_attempts,
        }
        db.save_exchange(body.session_id, body.system_prompt, body.message, result.reply, metadata)
        return {"session_id": body.session_id, "reply": result.reply, "metadata": metadata}

    @app.get("/sessions/{session_id}/messages")
    def session_messages(session_id: str):
        messages = db.get_messages(session_id)
        if messages is None:
            raise HTTPException(status_code=404, detail="session not found")
        return {"session_id": session_id, "messages": messages}

    return app


app = create_app()
