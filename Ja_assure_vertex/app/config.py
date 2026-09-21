from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # API Keys
    TAVILY_API_KEY: str
    GROQ_API_KEY: str
    GROQ_MODEL: str = "groq/compound"
    
    # Supabase
    SUPABASE_URL: str
    SUPABASE_SERVICE_ROLE_KEY: str
    
    # App Config
    APP_NAME: str = "JA Assure Discover Agent"
    ENVIRONMENT: str = "development"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
