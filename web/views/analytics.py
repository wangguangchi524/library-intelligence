from __future__ import annotations

import pandas as pd
import streamlit as st

from web.components.charts import bar, box_groups, donut, histogram, line
from web.components.layout import (
    csv_download, empty_state, fmt_int, fmt_money, fmt_rating, kpi_cards,
    page_header, render_dataframe, section_title, to_dataframe,
)
from web.components.state import repo_mode
from web.services.factory import require_repo

repo = require_repo()
page_header("统计分析", "分类、评分、价格、趋势、学院与借阅热度；销售额为模拟指标。",
            repo_mode(repo), "只读分析", "图表随筛选重新计算")

section_title("分析筛选")
c1, c2 = st.columns([2, 2])
with c1:
    category = st.selectbox("图书类别", ["全部"] + repo.get_categories())
with c2:
    year_rows = repo.get_year_trend(None if category == "全部" else category)
    year = st.selectbox("趋势年份", ["全部"] + [str(r["year"]) for r in year_rows])
selected_category = None if category == "全部" else category

categories = repo.get_category_stats()
price = repo.get_price_summary(selected_category)
avg_rating = round(sum(r["avg_rating"] for r in categories if r["avg_rating"]) / max(len([r for r in categories if r["avg_rating"]]), 1), 2)
kpi_cards([
    {"label": "类别数", "value": fmt_int(len(categories)), "hint": "distinct category"},
    {"label": "平均价格", "value": fmt_money(price["mean"]), "hint": "当前类别筛选"},
    {"label": "中位价格", "value": fmt_money(price["median"]), "hint": "当前类别筛选"},
    {"label": "类别平均评分", "value": fmt_rating(avg_rating), "hint": "各类别均分的均值"},
])

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["分类统计", "评分分析", "价格分析", "借阅趋势", "学院统计", "借阅热度"])

with tab1:
    left, right = st.columns(2)
    with left:
        if categories:
            st.plotly_chart(bar([r["category"] for r in categories], [r["count"] for r in categories],
                                title="各类别图书数量", color="#2563EB", height=340), use_container_width=True)
        else:
            empty_state("暂无分类数据")
    with right:
        if categories:
            st.plotly_chart(donut([r["category"] for r in categories], [r["stock"] for r in categories],
                                  title="各类别库存数量", height=340), use_container_width=True)
        else:
            empty_state("暂无库存数据")
    if categories:
        df = to_dataframe([{"类别": r["category"], "图书数": r["count"], "库存": r["stock"],
                            "平均价格": r["avg_price"], "平均评分": r["avg_rating"]} for r in categories])
        render_dataframe(df, height=280)
        csv_download(df, "category_stats.csv", "导出分类统计 CSV")

with tab2:
    ratings = repo.get_rating_distribution(selected_category)
    left, right = st.columns(2)
    with left:
        st.plotly_chart(bar([r["range"] for r in ratings], [r["count"] for r in ratings],
                            title="评分分布（0.5 分箱）", color="#14B8A6", height=340), use_container_width=True)
    with right:
        top_rated = repo.get_top_books(10, selected_category)
        df = to_dataframe([{"排名": i + 1, "书名": b["title"], "评分": b["rating"],
                            "借阅次数": b["borrow_count"]} for i, b in enumerate(top_rated)])
        section_title("评分最高 Top 10")
        render_dataframe(df, height=340)
    if categories:
        df = to_dataframe([{"类别": r["category"], "平均评分": r["avg_rating"]} for r in categories])
        section_title("类别平均评分")
        render_dataframe(df, height=220)

with tab3:
    left, right = st.columns(2)
    with left:
        st.plotly_chart(histogram(price["prices"], "价格分布", "价格（元）", nbins=12,
                                  color="#2563EB", height=340), use_container_width=True)
    with right:
        st.plotly_chart(box_groups(price["by_category"], "各类别价格箱线图", height=340),
                        use_container_width=True)
    st.caption("价格分布基于当前类别筛选；箱线图展示中位数、四分位数和离群值。")

with tab4:
    trend = repo.get_year_trend(selected_category)
    if year != "全部":
        trend = [r for r in trend if str(r["year"]) == year]
    months = repo.get_month_trend(selected_category)
    if year != "全部":
        months = [r for r in months if r["month"].startswith(year)]
    left, right = st.columns(2)
    with left:
        if trend:
            st.plotly_chart(bar([f"{r['year']}年" for r in trend], [r["count"] for r in trend],
                                title="年度借阅量", color="#2563EB", height=340), use_container_width=True)
        else:
            empty_state("暂无年度借阅数据")
    with right:
        if months:
            st.plotly_chart(line([r["month"] for r in months], [r["count"] for r in months],
                                 title="月度借阅趋势", height=340), use_container_width=True)
        else:
            empty_state("暂无月度借阅数据")
    statuses = repo.get_status_distribution()
    if statuses:
        st.plotly_chart(donut([r["status"] for r in statuses], [r["count"] for r in statuses],
                              title="借阅状态分布", height=300), use_container_width=True)

with tab5:
    colleges = repo.get_college_stats()
    if colleges:
        st.plotly_chart(bar([r["college"] for r in colleges], [r["borrows"] for r in colleges],
                            title="学院借阅量", horizontal=True, color="#7C3AED", height=340),
                        use_container_width=True)
        df = to_dataframe([{"学院": r["college"], "读者数": r["readers"], "借阅量": r["borrows"],
                            "人均借阅": r["avg_borrows"]} for r in colleges])
        render_dataframe(df, height=280)
        csv_download(df, "college_stats.csv", "导出学院统计 CSV")
        st.caption("人均借阅 = 学院借阅量 / 学院读者数；分母是读者数，不是借阅记录数。")
    else:
        empty_state("暂无学院借阅数据")

with tab6:
    top_books = repo.get_top_books(10, selected_category)
    top_categories = repo.get_top_categories(5)
    left, right = st.columns(2)
    with left:
        df = to_dataframe([{"排名": i + 1, "书名": b["title"], "作者": b["author"],
                            "类别": b["category"], "借阅次数": b["borrow_count"]}
                           for i, b in enumerate(top_books)])
        section_title("热门图书 Top 10")
        render_dataframe(df, height=340)
    with right:
        if top_categories:
            st.plotly_chart(bar([r["category"] for r in top_categories], [r["borrows"] for r in top_categories],
                                title="热门类别 Top 5", horizontal=True, color="#D97706", height=340),
                            use_container_width=True)
        else:
            empty_state("暂无类别借阅数据")
    values = repo.get_simulated_values(10)
    section_title("模拟借阅价值（price × borrow_count）", "教学模拟指标，不代表真实营业收入")
    df = to_dataframe([{"排名": i + 1, "书名": r["title"], "类别": r["category"],
                        "模拟价值": fmt_money(r["value"])} for i, r in enumerate(values)])
    render_dataframe(df, height=280)
