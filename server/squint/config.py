from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SQUINT_", env_file=".env", extra="ignore")

    db_url: str = "sqlite:///./squint.db"
    salt: str = "dev-salt"
    keep_media: bool = False
    max_upload_mb: int = 25
    retention_days: int = 30
    rate_per_minute: int = 60

    hive_key: str = ""
    sightengine_user: str = ""
    sightengine_secret: str = ""
    reality_defender_key: str = ""
    gptzero_key: str = ""
    factcheck_key: str = ""
    local_model: str = ""
    screen_model: str = ""
    text_model: str = ""
    weights_file: str = ""
    provider_timeout: float = 8.0

    partner_keys: str = ""

    telegram_token: str = ""
    whatsapp_token: str = ""
    whatsapp_phone_id: str = ""
    whatsapp_verify: str = "squint"

    apns_key: str = ""
    apns_key_id: str = ""
    apns_team_id: str = ""
    apns_bundle_id: str = ""
    apns_sandbox: bool = True

    @property
    def partner_key_set(self):
        return {k.strip() for k in self.partner_keys.split(",") if k.strip()}


@lru_cache
def settings():
    return Settings()
