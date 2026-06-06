from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "OpenDevFlow"
    environment: str = "development"
    database_url: str
    redis_url: str | None = None
    jwt_secret_key: str = Field(min_length=16)
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    cors_origins: list[str] = ["http://localhost:5173"]
    workspace_root: str = "/data/opendevflow/workspaces"
    model_secret_key: str | None = None


settings = Settings()
