from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st

from web.components.layout import brand, inject_theme
from web.components.state import repo_mode, repo_status
from web.services.factory import build_repo, clear_mongo_cache
from web.utils.config import APP_VERSION, get_config

st.set_page_config(
    page_title="Library Intelligence Platform",
    layout="wide",
    initial_sidebar_state="auto",
)

inject_theme()
base_config = get_config()

# 公开云端演示版固定为 Demo 模式，绝不连接实际教学数据库。
# 如需生产数据库，请从完整项目另行部署，并配置身份验证与权限。
st.session_state.mode = "demo"
if "repo" not in st.session_state:
    st.session_state.repo = None

with st.sidebar:
    brand()
    st.markdown('<div class="lib-side-label">数据源</div>', unsafe_allow_html=True)
    st.caption("Demo Mode · 在线演示数据")
    new_mode = "demo"

    if new_mode != st.session_state.mode:
        st.session_state.mode = new_mode
        st.session_state.repo = None
        st.session_state.pop("demo_repo", None)
        clear_mongo_cache()
        st.cache_data.clear()
        st.rerun()

    config = replace(base_config, app_mode=st.session_state.mode)
    repo, error = build_repo(config)

    if error:
        st.markdown(
            f'<div class="lib-side-status error"><span></span>连接失败</div>',
            unsafe_allow_html=True,
        )
        st.caption("未回退到 Demo；请修正配置后重试。")
        st.error(error[:260])
    elif repo is not None:
        st.session_state.repo = repo
        status_class = "demo" if getattr(repo, "is_demo", False) else "mongo"
        st.markdown(
            f'<div class="lib-side-status {status_class}"><span></span>{repo_status(repo)}</div>',
            unsafe_allow_html=True,
        )
        if getattr(repo, "is_demo", False):
            st.caption("示例数据 · 刷新后重置")
        else:
            st.caption("当前只读" if not getattr(repo, "can_write", False) else "测试库写入已授权")
            if st.button("重新连接", use_container_width=True):
                clear_mongo_cache()
                st.session_state.repo = None
                st.rerun()

    st.divider()
    st.caption(f"Library Intelligence · v{APP_VERSION}")
    st.caption("MongoDB 6.0 / Streamlit")

if st.session_state.repo is None:
    st.markdown(
        '<div class="lib-page-head"><div><h1>数据源不可用</h1>'
        '<p>请检查 MongoDB 配置，或切换到 Demo Mode 体验完整界面。</p></div></div>',
        unsafe_allow_html=True,
    )
    st.stop()

pages = [
    st.Page("views/dashboard.py", title="数据总览", default=True),
    st.Page("views/books.py", title="图书管理"),
    st.Page("views/readers.py", title="读者管理"),
    st.Page("views/borrowing.py", title="借阅管理"),
    st.Page("views/analytics.py", title="统计分析"),
    st.Page("views/system.py", title="系统信息"),
]
navigation = st.navigation(pages, position="sidebar")
navigation.run()
