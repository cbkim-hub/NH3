from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "local"
    database_url: str = "postgresql+psycopg://nh3:nh3_dev_password@localhost:5432/nh3"
    jwt_secret_key: str = "change-me-in-production"
    access_token_ttl_minutes: int = 30
    refresh_token_ttl_days: int = 14
    cors_origins: str = "http://localhost:3000"
    first_superadmin_email: str = "admin@nh3.local"
    first_superadmin_password: str = "ChangeMe123!"
    first_superadmin_name: str = "NH3 Super Admin"
    first_superadmin_org_name: str = "NH3 Operations"
    first_superadmin_org_code: str = "NH3"


settings = Settings()
