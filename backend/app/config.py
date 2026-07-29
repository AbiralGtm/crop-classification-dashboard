"""App configuration loaded from environment variables / .env file."""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    gee_project_id: str = "your-gcp-project-id"
    gee_service_account_json: str | None = None

    app_env: str = "development"
    database_url: str = "sqlite:///./crop_classification.db"
    data_dir: str = "./data"
    cors_origins: str = "http://localhost:3000"

    # Rupandehi District, Lumbini Province -- flat Terai farmland near
    # Siddharthanagar/Bhairahawa, chosen over the original Pokhara Valley pilot
    # because field sizes here are large and rectangular (a much better match
    # for Sentinel-2's 10m pixels than Pokhara's small hillside terraces), and
    # because this is where Nepal's actual institutional crop-area-mapping
    # program (ICIMOD/SERVIR-HKH with the Ministry of Agriculture and
    # Livestock Development) has done field data collection.
    default_aoi_lat: float = 27.4833
    default_aoi_lon: float = 83.4500

    # Crop classes for the Rupandehi (Terai) pilot. Order defines the numeric
    # label ids used when training the classifier (0 = non-crop / background).
    crop_classes: list[str] = [
        "non_crop",
        "rice",
        "wheat",
        "maize",
        "sugarcane",
        "lentil",
        "mustard",
        "vegetables",
    ]


@lru_cache
def get_settings() -> Settings:
    return Settings()
