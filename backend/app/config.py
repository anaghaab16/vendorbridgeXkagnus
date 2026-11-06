from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    secret_key: str
    access_token_minutes: int = 60

    # buyer details printed on purchase orders and invoices
    company_name: str = "VendorBridge Procurement"
    company_address: str = ""
    company_gstin: str = ""

    # invoice email delivery (any SMTP service). Leave smtp_host empty to turn email off.
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
