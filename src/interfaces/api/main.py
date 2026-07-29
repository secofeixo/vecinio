from __future__ import annotations

from fastapi import FastAPI

from src.interfaces.api.exception_handlers import register_exception_handlers
from src.interfaces.api.routers.auth import router as auth_router
from src.interfaces.api.routers.communities import router as communities_router
from src.interfaces.api.routers.owners import router as owners_router

app = FastAPI(title="Vecinio")

register_exception_handlers(app)

app.include_router(auth_router)
app.include_router(communities_router)
app.include_router(owners_router)
