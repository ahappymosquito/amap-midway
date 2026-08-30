"""前端配置路由模块。

本文件提供页面初始化所需配置接口，包括高德 Key 是否已设置和前端 JS API Key。
"""

from fastapi import APIRouter, Depends

from app.schemas import ConfigResponse
from app.settings import Settings, get_settings

router = APIRouter(prefix="/api", tags=["config"])


@router.get("/config", response_model=ConfigResponse)
async def get_config(settings: Settings = Depends(get_settings)) -> ConfigResponse:
    """返回前端加载地图所需配置。"""

    return ConfigResponse(
        amap_key_configured=bool(settings.amap_web_key),
        amap_js_key=settings.amap_web_key,
    )
