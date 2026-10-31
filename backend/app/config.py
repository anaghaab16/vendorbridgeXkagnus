import os
from pathlib import Path


class Settings:
    def __init__(self) -> None:
        env_values: dict[str, str] = {}
        env_file = Path(".env")
        if env_file.is_file():
            for line in env_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    env_values[key.strip().lower()] = value.strip().strip("\"'")

        self.database_url = os.getenv(
            "database_url", env_values.get("database_url", "")
        )
        self.secret_key = os.getenv("secret_key", env_values.get("secret_key", ""))
        token_minutes = os.getenv(
            "access_token_minutes", env_values.get("access_token_minutes", "60")
        )

        if not self.database_url:
            raise ValueError("database_url is required")
        if not self.secret_key:
            raise ValueError("secret_key is required")
        try:
            self.access_token_minutes = int(token_minutes)
        except ValueError as exc:
            raise ValueError("access_token_minutes must be an integer") from exc


settings = Settings()
