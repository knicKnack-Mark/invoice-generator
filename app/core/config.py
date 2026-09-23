from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- App identity (no hard-coded strings in routes/services) ---
    app_name: str = "VA Invoice & Expense Tracker"
    app_version: str = "0.1.0"
    environment: str = "development"
    api_prefix: str = "/api/v1"

    # --- Database ---
    database_url: str

    # --- Cache / rate limiting (either a standard Redis URL, or Upstash REST credentials) ---
    redis_url: str = "redis://localhost:6379/0"
    upstash_redis_rest_url: str | None = None
    upstash_redis_rest_token: str | None = None

    # --- Auth ---
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30

    # --- CORS ---
    cors_origins: str = "http://localhost:3000"

    # --- Pagination defaults (centralized so no endpoint hard-codes these) ---
    default_page_size: int = 25
    max_page_size: int = 100

    # --- Rate limiting ---
    rate_limit_enabled: bool = True
    rate_limit_per_minute: int = 60
    rate_limit_auth_per_minute: int = 10  # stricter limit for login/register

    # --- Account lockout (per-account, distinct from IP-based rate limiting) ---
    login_lockout_threshold: int = 5       # failed attempts before lockout
    login_lockout_minutes: int = 15        # lockout duration

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
