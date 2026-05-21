from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    kimi_api_key: str = ""
    kimi_base_url: str = "https://api.moonshot.cn/v1"
    kimi_text_model: str = "moonshot-v1-8k"
    kimi_vision_model: str = "moonshot-v1-8k-vision-preview"
    max_tokens: int = 4000
    temperature: float = 0.7

    class Config:
        env_file = ".env"

settings = Settings()
