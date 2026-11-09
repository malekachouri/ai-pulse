from fastapi import APIRouter

from app.api.v1 import admin, auth, dashboard, news

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(dashboard.router)
api_router.include_router(news.router)
api_router.include_router(admin.router)
