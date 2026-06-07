from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    mongodb_uri: str = ""
    mongodb_db: str = "meowmeowbeenz"
    port: int = 8000
    cors_origins: str = "http://localhost:8081,exp://localhost:8081"

    minimax_api_key: str = ""
    minimax_api_url: str = "https://api.minimax.io/v1/chat/completions"
    minimax_model: str = "M2-her"
    minimax_disable_thinking: bool = True
    gemini_api_key: str = ""
    gemini_api_url: str = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    gemini_model: str = "gemini-3.5-flash"

    livekit_url: str = ""
    livekit_api_key: str = ""
    livekit_api_secret: str = ""
    start_voice_worker: bool = False

    moss_project_id: str = ""
    moss_project_key: str = ""
    moss_index_name: str = "cat-voice-moss"
    moss_top_k: int = 6
    moss_alpha: float = 0.8
    moss_query_timeout_seconds: float = 1.0
    moss_auto_seed_index: bool = True

    jwt_secret: str = "change-me-in-production"
    jwt_expire_hours: int = 168

    @property
    def moss_enabled(self) -> bool:
        return bool(self.moss_project_id and self.moss_project_key)

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
