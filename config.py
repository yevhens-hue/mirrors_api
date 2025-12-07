# config.py

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Ключ для Serper.dev
    SERPER_API_KEY: str

    # URL к базе данных (из .env: DATABASE_URL=...)
    DATABASE_URL: str = "sqlite:///./mirrors.db"

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

    @property
    def database_url(self) -> str:
        """
        Удобное свойство, чтобы в коде можно было обращаться как
        settings.database_url, хотя поле называется DATABASE_URL.
        """
        return self.DATABASE_URL


_settings = Settings()


def get_settings() -> Settings:
    """
    Единая точка доступа к настройкам.
    """
    return _settings
