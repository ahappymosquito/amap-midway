"""FastAPI 应用入口。

本文件创建高德多点选址可视化应用，注册 API 路由，并托管原生 HTML/CSS/JS 静态页面。
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.routers import communities, config, geocode, places

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"


def create_app() -> FastAPI:
    """创建并配置 FastAPI 应用。"""

    app = FastAPI(title="高德多点选址", version="0.1.8")
    app.include_router(config.router)
    app.include_router(geocode.router)
    app.include_router(communities.router)
    app.include_router(places.router)
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/", include_in_schema=False)
    async def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    return app


app = create_app()
