import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # Model configuration
    MAX_LEN: int = int(os.getenv("MAX_LEN", 100))
    MODEL_BASE_DIR: str = os.getenv("MODEL_DIR", "ml_/saved_models")

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT: str = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"

    # API
    APP_TITLE: str = os.getenv("APP_TITLE", "Resume Screening API")
    APP_VERSION: str = os.getenv("APP_VERSION", "1.0.0")
    APP_DESCRIPTION: str = (
        "Predict job roles from resume text using TF-IDF and BiLSTM ensemble."
    )

    # File upload limits
    MAX_UPLOAD_SIZE_MB: int = int(os.getenv("MAX_UPLOAD_SIZE_MB", "5"))
    ALLOWED_EXTENSIONS: tuple = (".pdf", ".txt", ".docx")

    def model_path(self, filename: str) -> Path:
        return Path(self.MODEL_BASE_DIR) / filename


settings = Settings()