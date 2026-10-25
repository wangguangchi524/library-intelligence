from __future__ import annotations

from pathlib import Path

import streamlit as st

from web.services.demo_repository import DemoRepository
from web.services.mongo_repository import MongoRepository
from web.utils.config import ROOT, AppConfig


@st.cache_resource(show_spinner=False)
def _cached_mongo(host: str, port: int, db: str, user: str, password: str,
                  auth_source: str, allow_writes: bool) -> MongoRepository:
    config = AppConfig(
        app_mode="mongo", mongo_host=host, mongo_port=port, mongo_db=db,
        mongo_user=user, mongo_password=password, mongo_auth_source=auth_source,
        allow_db_writes=allow_writes, data_dir=ROOT / "data",
    )
    return MongoRepository(config)


def build_repo(config: AppConfig) -> tuple[object | None, str | None]:
    if config.app_mode == "demo":
        if "demo_repo" not in st.session_state:
            st.session_state.demo_repo = DemoRepository(config.data_dir)
        return st.session_state.demo_repo, None
    try:
        repo = _cached_mongo(config.mongo_host, config.mongo_port, config.mongo_db,
                             config.mongo_user, config.mongo_password,
                             config.mongo_auth_source, config.allow_db_writes)
        return repo, None
    except Exception as exc:
        return None, str(exc)


def clear_mongo_cache() -> None:
    _cached_mongo.clear()


def require_repo():
    repo = st.session_state.get("repo")
    if repo is None:
        st.error("当前没有可用的数据源，请检查侧边栏连接状态。")
        st.stop()
    return repo
