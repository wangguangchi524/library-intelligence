from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP_VERSION = "1.0.0-web"


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _load_env() -> None:
    _load_env_file(ROOT / ".env")
    _load_env_file(ROOT / "python" / ".env")


_load_env()


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class AppConfig:
    app_mode: str
    mongo_host: str
    mongo_port: int
    mongo_db: str
    mongo_user: str
    mongo_password: str
    mongo_auth_source: str
    allow_db_writes: bool
    data_dir: Path
    version: str = APP_VERSION


def get_config() -> AppConfig:
    mode = os.getenv("APP_MODE", "demo").strip().lower()
    if mode not in {"demo", "mongo"}:
        mode = "demo"
    return AppConfig(
        app_mode=mode,
        mongo_host=os.getenv("MONGO_HOST", "localhost"),
        mongo_port=int(os.getenv("MONGO_PORT", "27017")),
        mongo_db=os.getenv("MONGO_DB", "library_acceptance_test"),
        mongo_user=os.getenv("MONGO_USER", ""),
        mongo_password=os.getenv("MONGO_PASSWORD", ""),
        mongo_auth_source=os.getenv("MONGO_AUTH_SOURCE", "library"),
        allow_db_writes=_as_bool(os.getenv("ALLOW_DB_WRITES"), False),
        data_dir=ROOT / "data",
    )
