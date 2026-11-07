"""FastAPI entry point. External orchestration remains in n8n."""

import logging
import os
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from scheduling.models import OptimizeRequest
from scheduling.service import optimize_schedule

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("ai_thu_ky.scheduling")
app = FastAPI(title="AI Thu Ky Scheduling Engine", version="1.0.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "scheduling-engine"}


@app.post("/schedule/optimize")
def optimize(payload: OptimizeRequest, request: Request) -> dict[str, Any]:
    logger.info("schedule.optimize request_id=%s client=%s", payload.request_id, request.client.host if request.client else "unknown")
    try:
        return optimize_schedule(payload)
    except Exception as exc:
        logger.exception("schedule.optimize failed request_id=%s", payload.request_id)
        return JSONResponse(status_code=500, content={
            "success": False,
            "request_id": payload.request_id,
            "suggestions": [],
            "score": None,
            "score_breakdown": {},
            "explanation": "Scheduling engine gặp lỗi khi xử lý yêu cầu.",
            "constraints_applied": [],
            "error": {"code": "SCHEDULING_ENGINE_ERROR", "message": str(exc)},
        })


@app.exception_handler(Exception)
async def unhandled_error(_: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled API error")
    return JSONResponse(status_code=500, content={"success": False, "error": {"code": "INTERNAL_ERROR", "message": str(exc)}})
