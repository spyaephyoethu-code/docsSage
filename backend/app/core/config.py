from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    supabase_url: str
    supabase_service_role_key: str
    supabase_jwt_secret: str
    database_url: str
    groq_api_key: str
    voyage_api_key: str
    pinecone_api_key: str
    pinecone_index_name: str = "docssage"
    pinecone_environment: str = "us-east-1-aws"
    cohere_api_key: str
    backend_port: int = 8000
    environment: str = "development"
    secret_key: str
    allowed_origins: str = "http://localhost:3000"

    # Quotas
    max_kbs_per_user: int = 3

    @property
    def async_database_url(self) -> str:
        return self.database_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",")]


settings = Settings()
