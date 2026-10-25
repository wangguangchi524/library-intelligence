from __future__ import annotations

from typing import Any


WRITE_DENIED_DATABASES = {"library", "admin", "config", "local"}


def can_write_mongo(config: Any, db_name: str) -> bool:
    if not getattr(config, "allow_db_writes", False):
        return False
    if db_name in WRITE_DENIED_DATABASES:
        return False
    lowered = db_name.lower()
    return "test" in lowered or "demo" in lowered


def require_mongo_write(config: Any, db_name: str) -> None:
    if not can_write_mongo(config, db_name):
        raise PermissionError(
            "当前为只读模式。MongoDB 写入需要 ALLOW_DB_WRITES=true，且目标库名包含 test 或 demo；"
            "正式 library 禁止 Web 写入。"
        )
