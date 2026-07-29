from __future__ import annotations

from fastapi import FastAPI

from src.interfaces.api.exception_handlers import register_exception_handlers
from src.interfaces.api.routers.communities import router as communities_router

app = FastAPI(title="Vecinio")

register_exception_handlers(app)

app.include_router(communities_router)
