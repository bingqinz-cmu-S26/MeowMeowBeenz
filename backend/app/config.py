from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    mongodb_uri: str = ""
    mongodb_db: str = "meowmeowbeenz"
    port: int = 8000
    cors_origins: str = "http://localhost:4173,http://localhost:8081,exp://localhost:8081"

    minimax_api_key: str = ""
    minimax_api_url: str = "https://api.minimax.io/v1/chat/completions"
    minimax_model: str = "M2-her"
    gemini_api_key: str = ""
    gemini_api_url: str = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    gemini_model: str = "gemini-3.5-flash"

    livekit_url: str = ""
    livekit_api_key: str = ""
    livekit_api_secret: str = ""

    jwt_secret: str = "change-me-in-production"
    jwt_expire_hours: int = 168

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
