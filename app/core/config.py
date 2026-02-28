from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///./app.db"
    secret_key: str = "change-me-in-production"
    llm_provider: str = "cursor"  # openai | cursor
    llm_model: str = "gpt-4o-mini"
    llm_base_url: str = ""
    openai_api_key: str = ""
    cursor_api_key: str = ""
    cursor_base_url: str = "https://api.cursor.com/v1"
    cursor_model: str = "gpt-4o-mini"
    langfuse_secret_key: str = ""
    langfuse_public_key: str = ""

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
