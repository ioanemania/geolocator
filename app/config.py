from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="APP_", env_file=".env", extra="ignore")

    app_name: str = "IP Geolocation Service"
    app_version: str = "0.1.0"

    ip_api_base_url: str = "http://ip-api.com/json"
    request_timeout: float = 10.0


settings = Settings()
