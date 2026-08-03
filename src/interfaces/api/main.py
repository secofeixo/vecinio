from __future__ import annotations

from fastapi import FastAPI

from src.interfaces.api.exception_handlers import register_exception_handlers
from src.interfaces.api.routers.auth import router as auth_router
from src.interfaces.api.routers.communities import router as communities_router
from src.interfaces.api.routers.community_groups import (
    router as community_groups_router,
)
from src.interfaces.api.routers.owners import router as owners_router
from src.interfaces.api.routers.quotas import router as quotas_router
from src.interfaces.api.routers.vote import router as vote_router

app = FastAPI(
    title="Vecinio",
    description=(
        "API for managing homeowners associations (comunidades de propietarios): "
        "communities and their units, owners, login accounts, community groups "
        "(mancomunidades de propietarios), and quota splits."
    ),
    version="0.1.0",
    docs_url="/docs",
    openapi_url="/openapi.json",
)

register_exception_handlers(app)

app.include_router(auth_router)
app.include_router(communities_router)
app.include_router(community_groups_router)
app.include_router(owners_router)
app.include_router(quotas_router)
app.include_router(vote_router)
