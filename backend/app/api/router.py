from fastapi import APIRouter

from . import (
    auth,
    cases,
    clients,
    evidence,
    invites,
    plugins,
    strixy,
    system_config,
    users,
)

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(cases.router, prefix="/cases", tags=["cases"])
api_router.include_router(clients.router, prefix="/clients", tags=["clients"])
api_router.include_router(plugins.router, prefix="/plugins", tags=["plugins"])
api_router.include_router(evidence.router, prefix="/evidence", tags=["evidence"])
api_router.include_router(system_config.router, prefix="/admin", tags=["admin"])
api_router.include_router(invites.router, prefix="/invites", tags=["invites"])
api_router.include_router(strixy.router, prefix="/strixy", tags=["strixy"])
