from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- App identity ---
    app_name: str = "VA Invoice & Expense Tracker"
    app_version: str = "0.1.0"
    environment: str = "development"
    api_prefix: str = "/api/v1"

    # --- Database ---
    database_url: str

    # --- Cache / rate limiting (standard Redis URL, or Upstash REST credentials) ---
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

    # --- Pagination ---
    default_page_size: int = 25
    max_page_size: int = 100

    # --- Rate limiting ---
    rate_limit_enabled: bool = True
    rate_limit_per_minute: int = 60
    rate_limit_auth_per_minute: int = 10

    # --- Account lockout ---
    login_lockout_threshold: int = 5
    login_lockout_minutes: int = 15

    # --- File storage ---
    storage_backend: str = "local"
    storage_local_dir: str = "./uploads"
    storage_bucket: str | None = None
    storage_region: str = "us-east-1"
    storage_endpoint_url: str | None = None
    storage_access_key_id: str | None = None
    storage_secret_access_key: str | None = None
    max_upload_size_mb: int = 10
    allowed_upload_mime_types: str = "image/jpeg,image/png,application/pdf,image/heic"

    # --- Email ---
    email_backend: str = "console"
    email_from_address: str = "billing@example.com"
    resend_api_key: str | None = None
    gmail_email: str | None = None
    gmail_app_password: str | None = None

    # --- Invoices ---
    invoice_number_prefix: str = "INV"
    default_payment_terms_days: int = 15

    # --- Account tokens (password reset / email verification) ---
    frontend_base_url: str = "http://localhost:3000"
    password_reset_token_minutes: int = 60
    email_verification_token_hours: int = 24
    account_email_cooldown_seconds: int = 60

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def allowed_upload_mime_type_list(self) -> list[str]:
        return [t.strip() for t in self.allowed_upload_mime_types.split(",") if t.strip()]


settings = Settings()