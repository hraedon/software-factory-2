from __future__ import annotations

import logging
import os
from pathlib import Path

import yaml

log = logging.getLogger(__name__)

DEFAULT_CREDENTIALS_PATH = Path.home() / ".config" / "factory" / "credentials.yaml"


def load_credentials(path: Path | None = None) -> dict[str, dict[str, str]]:
    creds_path = path or DEFAULT_CREDENTIALS_PATH
    if not creds_path.exists():
        log.debug("credentials_file_not_found", path=str(creds_path))
        return {}
    raw = yaml.safe_load(creds_path.read_text())
    if not isinstance(raw, dict):
        log.warning("credentials_file_invalid_format", path=str(creds_path))
        return {}
    providers = raw.get("providers")
    if not isinstance(providers, dict):
        return {}
    return {k: v for k, v in providers.items() if isinstance(v, dict)}


def get_provider_credential(
    credentials: dict[str, dict[str, str]], provider: str, key: str = "api_key"
) -> str | None:
    provider_creds = credentials.get(provider)
    if not provider_creds:
        return None
    return provider_creds.get(key)


def inject_credentials_into_env(
    credentials: dict[str, dict[str, str]], provider: str, env: dict[str, str] | None = None
) -> dict[str, str]:
    if env is not None:
        merged = dict(env)
    else:
        merged = dict(os.environ)
    provider_creds = credentials.get(provider)
    if not provider_creds:
        return merged
    provider_key = get_provider_credential(credentials, provider)
    if provider_key:
        env_var = f"{provider.upper().replace('-', '_')}_API_KEY"
        merged[env_var] = provider_key
    return merged


CREDENTIAL_KEY_PREFIXES = ("fk-", "zai-", "sk-", "gsk-", "pk-", "AIza")


def redact_value(value: str) -> str:
    for prefix in CREDENTIAL_KEY_PREFIXES:
        if value.startswith(prefix):
            visible = max(0, min(4, len(value) - 4))
            return f"{value[:visible]}{'*' * 8}"
    if len(value) > 8:
        return f"{value[:4]}{'*' * 8}"
    return "****"
