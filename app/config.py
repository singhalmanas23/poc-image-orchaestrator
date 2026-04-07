from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    fal_key: str = ""
    ideogram_api_key: str = ""
    recraft_api_key: str = ""
    openai_api_key: str = ""
    google_cloud_project: str = ""

    # Brain LLM config
    brain_model: str = "gpt-5.4-mini"
    brain_max_tokens: int = 1024

    # Storage
    image_storage_dir: str = "generated_images"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
