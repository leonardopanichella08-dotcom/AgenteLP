from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./luka.db"

    # ── LLM ────────────────────────────────────────────────
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-5"

    # ── Discovery ──────────────────────────────────────────
    discovery_provider: str = "sample"  # "sample" | "apify"
    apify_token: str | None = None
    apify_actor: str = "apimaestro/linkedin-posts-search-scraper-no-cookies"

    # ── LinkedIn OAuth (OIDC) ──────────────────────────────
    linkedin_client_id: str | None = None
    linkedin_client_secret: str | None = None
    linkedin_redirect_uri: str = "http://localhost:5173/api/auth/linkedin/callback"
    linkedin_scopes: str = "openid profile email"
    frontend_url: str = "http://localhost:5173"

    # ── Sicurezza ──────────────────────────────────────────
    # Chiave Fernet (urlsafe base64, 32 byte). Se assente ne viene generata una
    # effimera: OK in dev, ma i token cifrati non sopravvivono al riavvio.
    app_encryption_key: str | None = None

    cors_origins: str = "*"

    @property
    def has_llm(self) -> bool:
        return bool(self.anthropic_api_key)

    @property
    def has_apify(self) -> bool:
        return self.discovery_provider == "apify" and bool(self.apify_token)

    @property
    def has_linkedin_oauth(self) -> bool:
        return bool(self.linkedin_client_id and self.linkedin_client_secret)

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def scope_list(self) -> list[str]:
        return [s for s in self.linkedin_scopes.split() if s]


@lru_cache
def get_settings() -> Settings:
    return Settings()
