from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent  # adjust as needed

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        extra="ignore",
    )

    APP_TITLE: str = "HireIQ API"
    APP_VERSION: str = "1.0.0"
    APP_DESCRIPTION: str = "Resume intelligence and hiring pipeline API."
    ENV: str = "development"

    DATABASE_URL: str
    SYNC_DATABASE_URL: str

    REDIS_URL: str 
    CACHE_TTL_SECONDS: int = 300
    ANALYTICS_CACHE_TTL: int = 60

    SECRET_KEY: str = "dev-secret-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    ALLOWED_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:3001"]

    MAX_UPLOAD_SIZE_MB: int = 10
    MAX_BATCH_FILES: int = 50
    ALLOWED_EXTENSIONS: tuple[str, ...] = (".pdf", ".txt", ".docx")

    MODEL_BASE_DIR: str = "ml_/saved_models"
    MAX_LEN: int = 100

    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"

    @property
    def is_production(self) -> bool:
        return self.ENV == "production"

    @property
    def cors_origins(self) -> list[str]:
        return self.ALLOWED_ORIGINS if self.is_production else ["*"]


@lru_cache
def get_settings() -> Settings:
    return Settings()

settings = get_settings()