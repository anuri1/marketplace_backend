from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL


class DbSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="DB_", extra="ignore")

    host: str = "localhost"
    port: int = 5432
    username: str = "postgres"
    password: str
    name: str = "postgres"

    @property
    def async_db_url(self) -> URL:
        return URL.create(
            "postgresql+asyncpg",
            host=self.host, port=self.port, username=self.username, password=self.password, database=self.name,
        )


class AuthSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    secret_key: str
    algorithm: str
    expires_in_days: int


db_settings = DbSettings()
auth_settings = AuthSettings()
