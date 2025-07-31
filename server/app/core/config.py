from pydantic import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    app_name: str = "SP Website API"
    debug: bool = False
    secret_key: str = "your-secret-key-here"
    database_url: Optional[str] = None
    
    class Config:
        env_file = ".env"

settings = Settings()
