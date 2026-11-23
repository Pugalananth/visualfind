from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_db_name: str = "visualfind"

    data_dir: Path = Path("./data")
    jwt_secret: str = ""
    token_ttl_minutes: int = 480
    cors_origins: str = "http://localhost:5173"
    frontend_url: str = "http://localhost:5173"

    encoder_checkpoint: Path = Path("./models/encoder_se_epoch30.pth")
    encoder_input_h: int = 224
    encoder_input_w: int = 224
    yolo_weights: str = "yolov8n.pt"
    device: str = "auto"
    detector_conf: float = 0.25
    load_models_on_startup: bool = True

    search_concurrency: int = 1
    url_use_env_proxy: bool = False

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def smtp_configured(self) -> bool:
        return bool(self.smtp_host and self.smtp_from)


@lru_cache
def get_settings() -> Settings:
    return Settings()
