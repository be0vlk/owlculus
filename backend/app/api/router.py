from fastapi import APIRouter
from . import (
    auth,
    users,
    cases,
    clients,
    plugins,
    evidence,
)

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(cases.router, prefix="/cases", tags=["cases"])
api_router.include_router(clients.router, prefix="/clients", tags=["clients"])
api_router.include_router(plugins.router, prefix="/plugins", tags=["plugins"])
api_router.include_router(evidence.router, prefix="/evidence", tags=["evidence"])
