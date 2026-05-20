import os
  from pydantic_settings import BaseSettings

  class Settings(BaseSettings):
      kimi_api_key: str = os.getenv("KIMI_API_KEY", "")
      kimi_base_url: str = os.getenv("KIMI_BASE_URL", "https://api.moonshot.cn/v1")
      kimi_text_model: str = os.getenv("KIMI_TEXT_MODEL", "moonshot-v1-8k")
      kimi_vision_model: str = os.getenv("KIMI_VISION_MODEL", "moonshot-v1-8k-vision-preview")
      max_tokens: int = int(os.getenv("MAX_TOKENS", "4000"))
      temperature: float = float(os.getenv("TEMPERATURE", "0.7"))

      class Config:
          env_file = ".env"

  settings = Settings()
