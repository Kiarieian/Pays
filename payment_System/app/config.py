"""
Centralized configuration.

All configuration is loaded from environment variables.
Validation happens at import time — the application will not start
with missing or invalid configuration.
"""
import os
import sys
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()


def _require(name: str) -> str:
    """Return env var value or exit with clear error."""
    value = os.getenv(name)
    if not value:
        print(f"FATAL: Required environment variable {name} is not set.", file=sys.stderr)
        sys.exit(1)
    return value


def _optional(name: str, default: str = "") -> str:
    return os.getenv(name, default)


@dataclass(frozen=True)
class DatabaseConfig:
    url: str = field(default_factory=lambda: _require("DATABASE_URL"))

    @property
    def is_sqlite(self) -> bool:
        return self.url.startswith("sqlite")

    @property
    def is_postgresql(self) -> bool:
        return self.url.startswith("postgresql")


@dataclass(frozen=True)
class SecurityConfig:
    credential_encryption_key: str = field(
        default_factory=lambda: _require("CREDENTIAL_ENCRYPTION_KEY")
    )
    admin_secret: str = field(
        default_factory=lambda: _require("ADMIN_SECRET")
    )


@dataclass(frozen=True)
class DarajaConfig:
    default_environment: str = field(
        default_factory=lambda: _optional("DARAJA_ENVIRONMENT", "sandbox")
    )
    connect_timeout: int = field(
        default_factory=lambda: int(_optional("DARAJA_CONNECT_TIMEOUT", "10"))
    )
    read_timeout: int = field(
        default_factory=lambda: int(_optional("DARAJA_READ_TIMEOUT", "30"))
    )
    total_timeout: int = field(
        default_factory=lambda: int(_optional("DARAJA_TOTAL_TIMEOUT", "60"))
    )


@dataclass(frozen=True)
class RateLimitConfig:
    payment_per_minute: int = field(
        default_factory=lambda: int(_optional("PAYMENT_RATE_LIMIT", "10"))
    )
    disbursement_per_minute: int = field(
        default_factory=lambda: int(_optional("DISBURSEMENT_RATE_LIMIT", "5"))
    )
    auth_per_minute: int = field(
        default_factory=lambda: int(_optional("AUTH_RATE_LIMIT", "10"))
    )
    general_api_per_minute: int = field(
        default_factory=lambda: int(_optional("GENERAL_API_RATE_LIMIT", "60"))
    )
    admin_per_minute: int = field(
        default_factory=lambda: int(_optional("ADMIN_RATE_LIMIT", "20"))
    )


@dataclass(frozen=True)
class CORSConfig:
    origins: list[str] = field(default_factory=lambda: [
        o.strip()
        for o in _optional(
            "CORS_ORIGINS",
            "http://localhost:5173,http://localhost:5174,http://127.0.0.1:5173,http://127.0.0.1:5174",
        ).split(",")
        if o.strip()
    ])


@dataclass(frozen=True)
class AppConfig:
    environment: str = field(
        default_factory=lambda: _optional("ENVIRONMENT", "development")
    )
    log_level: str = field(
        default_factory=lambda: _optional("LOG_LEVEL", "INFO")
    )
    api_title: str = "M-Pesa Daraja Gateway"
    api_version: str = "1.0.0"

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def is_development(self) -> bool:
        return self.environment == "development"


@dataclass(frozen=True)
class Settings:
    app: AppConfig = field(default_factory=AppConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    daraja: DarajaConfig = field(default_factory=DarajaConfig)
    rate_limit: RateLimitConfig = field(default_factory=RateLimitConfig)
    cors: CORSConfig = field(default_factory=CORSConfig)


def get_settings() -> Settings:
    """Create and validate settings. Called once at startup."""
    return Settings()
