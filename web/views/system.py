from __future__ import annotations

import sys

import pymongo
import streamlit as st

from web.components.layout import empty_state, page_header, render_dataframe, section_title, to_dataframe
from web.components.state import flash, repo_mode, show_flash
from web.services.factory import clear_mongo_cache, require_repo
from web.utils.config import APP_VERSION

repo = require_repo()
info = repo.get_system_info()
page_header("系统信息", "运行版本、集合、索引与 TTL 配置；不展示密码和完整连接串。",
            repo_mode(repo), "Demo" if repo.is_demo else "MongoDB", f"应用版本 v{APP_VERSION}")
show_flash()

section_title("运行信息")
c1, c2, c3, c4 = st.columns(4)
c1.metric("数据模式", "Demo Mode" if repo.is_demo else "MongoDB Mode")
c2.metric("Python", sys.version.split()[0])
c3.metric("Streamlit", st.__version__)
c4.metric("PyMongo", pymongo.version)
c5, c6 = st.columns(2)
c5.metric("MongoDB 版本", info.get("mongo_version", "-"))
c6.metric("数据库", info.get("db_name", "-"))

section_title("集合与视图", "仅展示当前账号可读取的集合；系统内部集合已过滤")
collections = info.get("collections", [])
if collections:
    df = to_dataframe([{"集合": c["name"], "类型": c.get("type", "collection"),
                        "文档数": c.get("count", "-"),
                        "选项": str(c.get("options", {}))} for c in collections])
    render_dataframe(df, height=300)
else:
    empty_state("没有集合信息", "当前数据源没有可展示的集合。")

section_title("索引", "来自 books 集合的索引清单；无权限时为空")
indexes = info.get("indexes", [])
if indexes:
    df = to_dataframe([{"索引": i["name"], "字段": str(i.get("key")), "唯一": i.get("unique", False)}
                       for i in indexes])
    render_dataframe(df, height=240)
else:
    st.caption("当前数据源没有索引信息（Demo 模式不提供 MongoDB 索引）。")

section_title("TTL 配置")
ttl = info.get("ttl")
if ttl is None:
    st.info("当前数据源未提供 TTL（Demo 模式）或 borrow_logs 不是时间序列集合。")
else:
    st.write(f"borrow_logs 的 `expireAfterSeconds` = **{ttl}** 秒（约 {float(ttl) / 86400 / 365:.1f} 年）。")
st.caption("教学任务书要求 2 年 TTL（63072000 秒）；完整历史分析环境使用 5 年 TTL（157680000 秒）。TTL 由 MongoDB 后台线程周期执行，不是立即删除。")

st.divider()
section_title("维护")
if repo.is_demo:
    st.caption("Demo 数据仅保存在当前浏览器会话；重置会恢复 data/ 中的原始合成数据，不会修改 JSON 文件。")
    if st.button("重置演示数据", type="primary"):
        repo.reset()
        flash("success", "演示数据已重置为 data/ 中的初始状态。")
        st.rerun()
else:
    st.caption("MongoDB 模式不提供清空数据库按钮；正式 library 禁止 Web 写入。")
    if st.button("重新连接 MongoDB"):
        clear_mongo_cache()
        st.session_state.repo = None
        st.rerun()
