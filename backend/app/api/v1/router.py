from fastapi import APIRouter, Depends

from app.api.deps import reject_unknown_query_params
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
    learning,
    models,
    news,
    notifications,
    preferences,
    radar,
    research,
    search,
    security,
    tools,
    watchlist,
)

api_router = APIRouter(dependencies=[Depends(reject_unknown_query_params)])
for module in (
    auth, dashboard, news, models, tools, research, github, bugs, security, incidents,
    radar, search, briefings, bookmarks, notifications, preferences, learning, watchlist, catalog, admin,
    admin_ops,
):  # fmt: skip
    api_router.include_router(module.router)
