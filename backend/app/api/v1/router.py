from fastapi import APIRouter

from app.api.v1 import (
    admin,
    admin_ops,
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
    radar,
    research,
    search,
    security,
    tools,
)

api_router = APIRouter()
for module in (
    auth, dashboard, news, models, tools, research, github, bugs, security, incidents,
    radar, search, briefings, bookmarks, notifications, preferences, catalog, admin, admin_ops,
):  # fmt: skip
    api_router.include_router(module.router)
