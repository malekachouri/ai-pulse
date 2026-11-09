from fastapi import APIRouter

from app.api.v1 import admin, auth, bookmarks, briefings, catalog, dashboard, news, notifications, preferences

api_router = APIRouter()
for module in (auth, dashboard, news, catalog, bookmarks, notifications, preferences, briefings, admin):
    api_router.include_router(module.router)
