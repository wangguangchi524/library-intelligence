from __future__ import annotations

import streamlit as st


def repo_mode(repo) -> str:
    return "Demo Mode" if getattr(repo, "is_demo", False) else "MongoDB Mode"


def repo_status(repo) -> str:
    if getattr(repo, "is_demo", False):
        return "会话内存"
    return "已连接" if repo is not None else "未连接"


def write_hint(repo) -> str:
    if getattr(repo, "is_demo", False):
        return "Demo 修改仅保存在当前会话，刷新或重置后恢复。"
    if getattr(repo, "can_write", False):
        return "已授权写入测试库；正式 library 仍只读。"
    return "MongoDB 当前为只读模式；未授权写入不会发送到数据库。"


def flash(kind: str, message: str) -> None:
    st.session_state["_flash"] = (kind, message)


def show_flash() -> None:
    item = st.session_state.pop("_flash", None)
    if not item:
        return
    kind, message = item
    if kind == "success":
        st.success(message)
    elif kind == "error":
        st.error(message)
    else:
        st.info(message)
