"""Configuration settings for RECON-X application."""
from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    # Database
    database_url: str = Field(default="postgresql+asyncpg://recon:recon_secret@db:5432/reconx")
    database_url_sync: str = Field(default="postgresql://recon:recon_secret@db:5432/reconx")
    
    # App
    secret_key: str = Field(default="change-me-to-random-secret")
    debug: bool = Field(default=False)
    log_level: str = Field(default="INFO")
    backend_host: str = Field(default="0.0.0.0")
    backend_port: int = Field(default=8000)
    
    # Razorpay
    razorpay_key_id: str = Field(default="")
    razorpay_key_secret: str = Field(default="")
    razorpay_webhook_secret: str = Field(default="")
    razorpay_mode: str = Field(default="mock")  # "mock" or "sandbox"
    
    # LLM
    gemini_api_key: str = Field(default="")
    groq_api_key: str = Field(default="")
    llm_provider: str = Field(default="gemini")
    llm_model: str = Field(default="gemini-2.0-flash")
    
    # Policy thresholds
    auto_resolve_confidence_threshold: float = Field(default=0.85)
    auto_resolve_variance_threshold_paise: int = Field(default=1000)  # 10 INR in paise
    auto_resolve_variance_threshold_pct: float = Field(default=0.5)  # 0.5%
    
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

def get_settings() -> Settings:
    return Settings()
