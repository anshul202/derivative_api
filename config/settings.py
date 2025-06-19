from pydantic_settings import BaseSettings
from pydantic import ConfigDict

class Settings(BaseSettings):
    # Add this line to ignore extra fields
    model_config = ConfigDict(extra='ignore', env_file=".env")
    
    # Application
    app_name: str = "Solar PVWatts API"
    app_version: str = "1.0.0"
    debug: bool = False
    
    # NREL PVWatts API
    nrel_api_key: str = "DEMO_KEY"

def get_settings() -> Settings:
    return Settings()
