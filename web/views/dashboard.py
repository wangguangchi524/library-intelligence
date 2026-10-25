from __future__ import annotations

import pandas as pd
import streamlit as st

from web.components.charts import bar, donut, line
from web.components.layout import (
    csv_download,
    empty_state,
    fmt_date,
    fmt_int,
    kpi_cards,
    page_header,
    render_dataframe,
    section_title,
    to_dataframe,
)
from web.components.state import repo_mode
from web.services.factory import require_repo

repo = require_repo()
metrics = repo.get_dashboard_metrics()
mode = repo_mode(repo)
page_header(
    "数据总览", "馆藏、读者与借阅关键指标；所有数值来自当前数据源实时计算。",
    mode, "已连接" if not repo.is_demo else "会话内存",
    f"图书 {metrics['book_titles']} 种 · 读者 {metrics['readers']} 位",
)

kpi_cards([
    {"label": "馆藏图书种类", "value": fmt_int(metrics["book_titles"]), "hint": "books 文档数；非册数"},
    {"label": "注册读者", "value": fmt_int(metrics["readers"]), "hint": "readers 文档数"},
    {"label": "历史借阅事件", "value": fmt_int(metrics["borrow_events"]), "hint": "borrow_logs 时间序列"},
    {"label": "当前可借种类", "value": fmt_int(metrics["available_titles"]), "hint": "stock > 0 的图书"},
    {"label": "当前在借记录", "value": fmt_int(metrics["active_loans"]), "hint": "状态为借出/未归还"},
    {"label": "图书类别", "value": fmt_int(metrics["categories"]), "hint": "distinct category"},
])

section_title("筛选与口径", "类别筛选影响分类分布、热门排行和最近借阅；年份筛选影响趋势图。")
f1, f2, f3, f4 = st.columns([2.2, 1.1, 1.1, 1.2])
with f1:
    categories = st.multiselect("图书类别", repo.get_categories(), placeholder="全部类别")
with f2:
    top_n = st.selectbox("热门排行数量", [5, 8, 10, 12], index=2)
with f3:
    year_rows = repo.get_year_trend(categories[0] if len(categories) == 1 else None)
    years = ["全部"] + [str(r["year"]) for r in year_rows]
    year = st.selectbox("趋势年份", years)
with f4:
    st.caption("指标口径：种类 ≠ 册数；历史事件 ≠ 当前在借。")
    st.caption(f"馆藏总册数（stock 求和）：{fmt_int(metrics['total_copies'])}")

selected_category = categories[0] if len(categories) == 1 else None
category_stats = repo.get_category_stats()
trend = repo.get_year_trend(selected_category)
if year != "全部":
    trend = [r for r in trend if str(r["year"]) == year]
top_books = repo.get_top_books(top_n, selected_category)
recent = repo.get_recent_loans(10, selected_category)

left, right = st.columns([1.05, 1])
with left:
    section_title("图书分类分布", "按 books.category 自动分组")
    if category_stats:
        st.plotly_chart(donut([r["category"] for r in category_stats], [r["count"] for r in category_stats],
                              height=330), use_container_width=True)
    else:
        empty_state("暂无分类数据", "请检查 books 集合或示例数据。")
with right:
    section_title("年度借阅趋势", "基于 borrow_logs.borrow_date，+08:00")
    if trend:
        st.plotly_chart(bar([f"{r['year']}年" for r in trend], [r["count"] for r in trend],
                            color="#14B8A6", height=330), use_container_width=True)
    else:
        empty_state("暂无借阅日期", "缺少 borrow_date 的记录不会归入当前年份。")

lower_left, lower_right = st.columns([1.05, 1])
with lower_left:
    section_title(f"热门图书 Top {top_n}", "按 borrow_count 排序")
    if top_books:
        df = to_dataframe([{
            "排名": i + 1, "书名": b["title"], "作者": b["author"],
            "类别": b["category"], "借阅次数": b["borrow_count"],
        } for i, b in enumerate(top_books)])
        render_dataframe(df, height=480, key=f"dash_top_books_{mode}")
    else:
        empty_state("暂无图书", "当前筛选条件下没有图书。")
with lower_right:
    section_title("最近借阅记录", "不展示读者邮箱和电话")
    if recent:
        df = to_dataframe([{
            "图书": r["title"], "借阅日期": fmt_date(r["borrow_date"]),
            "状态": r["status"], "应还日期": fmt_date(r["due_date"]),
            "归还日期": fmt_date(r["return_date"]),
        } for r in recent])
        render_dataframe(df, height=480, key=f"dash_recent_loans_{mode}")
        csv_download(df, "recent_loans.csv", "导出最近借阅 CSV")
    else:
        empty_state("暂无借阅记录", "当前筛选条件下没有流水。")

if metrics["active_loans"]:
    st.caption("提示：当前在借记录包含状态为“借出”且未归还的记录；历史逾期已归还不会计入当前在借。")
