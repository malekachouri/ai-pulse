from fastapi import APIRouter

from app.api.v1 import (
    admin,
    auth,
    bookmarks,
    briefings,
    bugs,
    catalog,
    dashboard,
    github,
    incidents,
    models,
    news,
    notifications,
    preferences,
    research,
    search,
    security,
    tools,
)

api_router = APIRouter()
for module in (
    auth, dashboard, news, models, tools, research, github, bugs, security, incidents,
    search, briefings, bookmarks, notifications, preferences, catalog, admin,
):  # fmt: skip
    api_router.include_router(module.router)
