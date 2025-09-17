from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseConfig(BaseSettings):
    """Database configuration"""
    host: str = "localhost"
    port: int = 5432
    username: str = "postgres"
    password: str = "postgres"
    database: str = "ecowhiskey_atc"

    @property
    def url(self) -> str:
        """Get database URL"""
        return f"postgresql+asyncpg://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"

    model_config = SettingsConfigDict(
        env_prefix="DB_",
        env_file=".env",
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


class RabbitMQConfig(BaseSettings):
    """RabbitMQ configuration"""
    host: str = "localhost"
    port: int = 5672
    username: str = "guest"
    password: str = "guest"

    model_config = SettingsConfigDict(
        env_prefix="RABBITMQ_",
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

    # RabbitMQ
    rabbitmq: RabbitMQConfig = Field(default_factory=RabbitMQConfig)
    
    # JWT Secret (for future authentication)
    jwt_secret: str = "your-secret-key-here"
    jwt_algorithm: str = "HS256"
    jwt_expiration_hours: int = 24
    
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
