from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./luka.db"

    # ── LLM ────────────────────────────────────────────────
    # provider: "auto" sceglie gemini -> anthropic -> demo in base alle chiavi.
    llm_provider: str = "auto"  # "auto" | "gemini" | "anthropic" | "demo"
    # Gemini: chiave gratuita da https://aistudio.google.com (NESSUNA carta).
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-3.6-flash"  # fallback automatico se non disponibile
    # Anthropic: qualità migliore, ma a consumo.
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-5"

    # ── Discovery ──────────────────────────────────────────
    # "free"   : Hacker News + Reddit (segnale di nicchia, zero chiavi) — DEFAULT
    # "sample" : dataset locale incluso (offline, deterministico)
    # "apify"  : post LinkedIn reali via Apify actor (richiede APIFY_TOKEN, a pagamento)
    discovery_provider: str = "free"
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
    def has_gemini(self) -> bool:
        return bool(self.gemini_api_key)

    @property
    def has_anthropic(self) -> bool:
        return bool(self.anthropic_api_key)

    @property
    def active_llm(self) -> str:
        """Provider effettivo: 'gemini' | 'anthropic' | 'demo'."""
        if self.llm_provider == "gemini":
            return "gemini" if self.has_gemini else "demo"
        if self.llm_provider == "anthropic":
            return "anthropic" if self.has_anthropic else "demo"
        if self.llm_provider == "demo":
            return "demo"
        # auto
        if self.has_gemini:
            return "gemini"
        if self.has_anthropic:
            return "anthropic"
        return "demo"

    @property
    def has_llm(self) -> bool:
        return self.active_llm != "demo"

    @property
    def active_model(self) -> str | None:
        return {
            "gemini": self.gemini_model,
            "anthropic": self.anthropic_model,
        }.get(self.active_llm)

    @property
    def has_apify(self) -> bool:
        return self.discovery_provider == "apify" and bool(self.apify_token)

    @property
    def discovery_label(self) -> str:
        if self.has_apify:
            return "apify"
        return "sample" if self.discovery_provider == "sample" else "free"

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
