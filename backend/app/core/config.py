from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"

    backend_url: str = "http://127.0.0.1:8000"
    frontend_url: str = "http://localhost:5173"

    database_url: str
    local_database_url: str = ""
    redis_url: str = "redis://localhost:6379"

    secret_key: str
    spotify_client_id: str
    spotify_client_secret: str
    spotify_redirect_uri: str

    anthropic_api_key: str = ""
    demo_user_id: str = ""

    lastfm_api_key: str = ""
    lastfm_api_secret: str = ""

    @property
    def active_database_url(self) -> str:
        if self.environment == "development" and self.local_database_url:
            return self.local_database_url
        return self.database_url


settings = Settings()
