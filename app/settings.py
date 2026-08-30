"""应用配置模块。

本文件负责从环境变量读取高德 Key、API 地址和请求超时等配置，供后端接口和高德客户端复用。
"""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """运行时配置。"""

    amap_web_key: str | None = Field(default=None, alias="AMAP_WEB_KEY")
    amap_web_api_base_url: str = "https://restapi.amap.com/v3"
    amap_request_timeout: float = 15.0

    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    """返回缓存后的配置实例。"""

    return Settings()
