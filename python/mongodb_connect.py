import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from pymongo import MongoClient

TZ = timezone(timedelta(hours=8))


def _load_env_file():
    env_path = Path(__file__).with_name(".env")
    if not env_path.exists():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_env_file()

MONGO_HOST = os.getenv("MONGO_HOST", "localhost")
MONGO_PORT = int(os.getenv("MONGO_PORT", "27017"))
MONGO_DB = os.getenv("MONGO_DB", "library")
MONGO_USER = os.getenv("MONGO_USER", "libWriter")
MONGO_PASSWORD = os.getenv("MONGO_PASSWORD", "")
MONGO_AUTH_SOURCE = os.getenv("MONGO_AUTH_SOURCE", "library")

COLLECTIONS = ["books", "readers", "borrow_logs", "borrow_records", "category_stats", "book_logs", "book_in_stock"]


def connect():
    if not MONGO_PASSWORD:
        raise RuntimeError("未设置 MONGO_PASSWORD。请通过环境变量或 python/.env 提供密码，参考 .env.example。")
    client = MongoClient(
        host=MONGO_HOST,
        port=MONGO_PORT,
        username=MONGO_USER,
        password=MONGO_PASSWORD,
        authSource=MONGO_AUTH_SOURCE,
        directConnection=True,
        retryWrites=False,
        serverSelectionTimeoutMS=5000,
        tz_aware=True,
        appname="library-platform",
    )
    client[MONGO_DB].command("ping")
    return client


def get_db(client):
    return client[MONGO_DB]


def fmt_dt(value):
    if not value:
        return "-"
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(TZ).strftime("%Y-%m-%d %H:%M")


def collection_counts(db):
    result = {}
    for name in COLLECTIONS:
        try:
            result[name] = db[name].count_documents({})
        except Exception:
            result[name] = "-"
    return result


def print_connection(db):
    info = collection_counts(db)
    print("\n" + "=" * 66)
    print("数据库连接成功")
    print(f"地址: {MONGO_HOST}:{MONGO_PORT}    数据库: {MONGO_DB}    账号: {MONGO_USER}")
    print("-" * 66)
    for name in COLLECTIONS:
        print(f"  {name:<16} {info.get(name)}")
    print("=" * 66)


def close(client):
    if client is not None:
        client.close()

