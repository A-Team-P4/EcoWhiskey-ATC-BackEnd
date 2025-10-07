from typing import Optional
from urllib.parse import quote_plus

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseConfig(BaseSettings):
    """Database configuration"""

    host: str = "localhost"
    port: int = 5432
    username: str = "postgres"
    password: SecretStr = Field(default=SecretStr("postgres"))
    database: str = "ecowhiskey_atc"
    serverless: bool = Field(
        default=True,
        description="If true, disable connection pooling so serverless DBs can pause.",
    )

    @property
    def url(self) -> str:
        """Get database URL"""
        username = quote_plus(self.username)
        password = quote_plus(self.password.get_secret_value())
        return (
            "postgresql+asyncpg://"
            f"{username}:{password}"
            f"@{self.host}:{self.port}/{self.database}"
        )

    model_config = SettingsConfigDict(
        env_prefix="DB_",
        env_file=".env",
        secrets_dir=".secrets",
        case_sensitive=False,
        extra="ignore",
    )


class S3Config(BaseSettings):
    """S3 configuration"""

    access_key: Optional[str] = None
    secret_key: Optional[str] = None
    region: str = "us-east-1"
    bucket_name: str = "ecowhiskey-atc-bucket"

    model_config = SettingsConfigDict(
        env_prefix="S3_",
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )


class PollyConfig(BaseSettings):
    """Amazon Polly configuration."""

    region: str = "us-east-1"
    default_voice_id: str = "Mia"

    model_config = SettingsConfigDict(
        env_prefix="POLLY_",
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )


class SecurityConfig(BaseSettings):
    """JWT and application security configuration."""

    jwt_secret_key: SecretStr = Field(
        default=SecretStr("change-me"),
        validation_alias="JWT_SECRET",
    )
    jwt_algorithm: str = Field(default="HS256", validation_alias="JWT_ALGORITHM")
    access_token_expires_minutes: int = Field(
        default=60,
        validation_alias="JWT_EXPIRATION_MINUTES",
        ge=1,
    )

    model_config = SettingsConfigDict(
        env_prefix="",
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )


class Settings(BaseSettings):
    """Application settings"""

    app_name: str = "EcoWhiskey ATC Backend"
    app_version: str = "1.0.0"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8000

    # Database
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)

    # S3
    s3: S3Config = Field(default_factory=S3Config)

    # Polly
    polly: PollyConfig = Field(default_factory=PollyConfig)

    # Security
    security: SecurityConfig = Field(default_factory=SecurityConfig)

    # CORS
    cors_origins: list[str] = ["*"]
    cors_allow_credentials: bool = True
    cors_allow_methods: list[str] = ["*"]
    cors_allow_headers: list[str] = ["*"]

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )


# Global settings instance
settings = Settings()
