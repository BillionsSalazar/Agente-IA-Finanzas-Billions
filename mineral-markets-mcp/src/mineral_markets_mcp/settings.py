"""Configuración vía variables de entorno (pydantic-settings).

Cada proveedor premium tiene su propia clase de settings con sus variables de
entorno exactas (ver `.env.example`). Ninguna credencial se hardcodea nunca:
todo se lee de `.env` / entorno de proceso. Una clase de settings se considera
`is_configured` solo si TODOS sus `_required_fields` tienen valor.
"""

from __future__ import annotations

from typing import ClassVar

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ProviderSettingsBase(BaseSettings):
    """Base común para settings de un proveedor premium."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    _required_fields: ClassVar[tuple[str, ...]] = ()
    docs_url: ClassVar[str | None] = None

    @property
    def is_configured(self) -> bool:
        return all(getattr(self, f, None) for f in self._required_fields)

    @property
    def missing_env_vars(self) -> list[str]:
        return [f.upper() for f in self._required_fields if not getattr(self, f, None)]


class FactSetSettings(ProviderSettingsBase):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_prefix="FACTSET_")
    client_id: str | None = None
    client_secret: str | None = None
    base_url: str = "https://api.factset.com"
    _required_fields: ClassVar[tuple[str, ...]] = ("client_id", "client_secret")
    docs_url: ClassVar[str] = "https://developer.factset.com/api-catalog"


class SPGlobalSettings(ProviderSettingsBase):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_prefix="SP_GLOBAL_")
    api_key: str | None = None
    api_secret: str | None = None
    base_url: str = "https://api-ciq.marketintelligence.spglobal.com"
    _required_fields: ClassVar[tuple[str, ...]] = ("api_key", "api_secret")
    docs_url: ClassVar[str] = "https://www.capitaliq.spglobal.com/apidocs/ciqpro/"


class LSEGSettings(ProviderSettingsBase):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_prefix="LSEG_")
    app_key: str | None = None
    rdp_login: str | None = None
    rdp_password: str | None = None
    base_url: str = "https://api.refinitiv.com"
    _required_fields: ClassVar[tuple[str, ...]] = ("app_key", "rdp_login", "rdp_password")
    docs_url: ClassVar[str] = "https://developers.lseg.com/en/api-catalog/refinitiv-data-platform"


class MSCISettings(ProviderSettingsBase):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_prefix="MSCI_")
    client_id: str | None = None
    client_secret: str | None = None
    base_url: str = "https://api.msci.com"
    _required_fields: ClassVar[tuple[str, ...]] = ("client_id", "client_secret")
    docs_url: ClassVar[str] = "https://developer.msci.com/"


class PitchBookSettings(ProviderSettingsBase):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_prefix="PITCHBOOK_")
    api_key: str | None = None
    base_url: str = "https://api.pitchbook.com"
    _required_fields: ClassVar[tuple[str, ...]] = ("api_key",)
    docs_url: ClassVar[str] = "https://pitchbook.com/data/api"


class MorningstarSettings(ProviderSettingsBase):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_prefix="MORNINGSTAR_")
    client_id: str | None = None
    client_secret: str | None = None
    base_url: str = "https://api.morningstar.com"
    _required_fields: ClassVar[tuple[str, ...]] = ("client_id", "client_secret")
    docs_url: ClassVar[str] = "https://developer.morningstar.com/"


class MoodysSettings(ProviderSettingsBase):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_prefix="MOODYS_")
    client_id: str | None = None
    client_secret: str | None = None
    base_url: str = "https://api.moodys.com"
    _required_fields: ClassVar[tuple[str, ...]] = ("client_id", "client_secret")
    docs_url: ClassVar[str] = "https://developer.moodys.com/"


class AieraSettings(ProviderSettingsBase):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_prefix="AIERA_")
    api_key: str | None = None
    base_url: str = "https://api.aiera.com"
    _required_fields: ClassVar[tuple[str, ...]] = ("api_key",)
    docs_url: ClassVar[str] = "https://aiera.com/platform/api/"


class DaloopaSettings(ProviderSettingsBase):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_prefix="DALOOPA_")
    api_key: str | None = None
    base_url: str = "https://api.daloopa.com"
    _required_fields: ClassVar[tuple[str, ...]] = ("api_key",)
    docs_url: ClassVar[str] = "https://www.daloopa.com/api"


class ChronographSettings(ProviderSettingsBase):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_prefix="CHRONOGRAPH_")
    api_key: str | None = None
    base_url: str = "https://api.chronograph.pe"
    _required_fields: ClassVar[tuple[str, ...]] = ("api_key",)
    docs_url: ClassVar[str] = "https://www.chronograph.pe/"


class EgnyteSettings(ProviderSettingsBase):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_prefix="EGNYTE_")
    domain: str | None = None
    api_token: str | None = None
    _required_fields: ClassVar[tuple[str, ...]] = ("domain", "api_token")
    docs_url: ClassVar[str] = "https://developers.egnyte.com/docs"


class Settings(BaseSettings):
    """Configuración global + una instancia de settings por proveedor."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    log_level: str = "INFO"
    http_timeout_seconds: float = 15.0
    cache_ttl_seconds: int = 30
    rate_limit_per_second: float = 5.0
    retry_max_attempts: int = 3

    factset: FactSetSettings = Field(default_factory=FactSetSettings)
    sp_global: SPGlobalSettings = Field(default_factory=SPGlobalSettings)
    lseg: LSEGSettings = Field(default_factory=LSEGSettings)
    msci: MSCISettings = Field(default_factory=MSCISettings)
    pitchbook: PitchBookSettings = Field(default_factory=PitchBookSettings)
    morningstar: MorningstarSettings = Field(default_factory=MorningstarSettings)
    moodys: MoodysSettings = Field(default_factory=MoodysSettings)
    aiera: AieraSettings = Field(default_factory=AieraSettings)
    daloopa: DaloopaSettings = Field(default_factory=DaloopaSettings)
    chronograph: ChronographSettings = Field(default_factory=ChronographSettings)
    egnyte: EgnyteSettings = Field(default_factory=EgnyteSettings)


_settings: Settings | None = None


def get_settings() -> Settings:
    """Singleton perezoso — evita releer `.env` en cada llamada."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
