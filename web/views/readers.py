from __future__ import annotations

from datetime import datetime, timezone

import streamlit as st

from web.components.charts import bar, donut
from web.components.layout import (
    csv_download, empty_state, fmt_date, fmt_int, page_header, render_dataframe,
    section_title, to_dataframe,
)
from web.components.state import flash, repo_mode, show_flash, write_hint
from web.services.factory import require_repo
from web.utils.validators import ValidationError

repo = require_repo()
mode = repo_mode(repo)
page_header("读者管理", "检索读者、查看学院与等级分布；联系方式不展示。",
            mode, "可写" if repo.can_write else "只读", write_hint(repo))
show_flash()

if "reader_page" not in st.session_state:
    st.session_state.reader_page = 1

list_tab, stats_tab, manage_tab = st.tabs(["读者列表", "读者统计", "新增 / 维护"])

with list_tab:
    section_title("检索与筛选", "姓名与联系方式在页面中脱敏显示")
    c1, c2, c3 = st.columns([2, 1.2, 1])
    with c1:
        keyword = st.text_input("借阅证号 / 姓名 / 学院", key="reader_keyword")
    with c2:
        college_options = sorted({r["college"] for r in repo.get_readers({}, 1, 1000)[1] if r["college"]})
        college = st.selectbox("学院", ["全部"] + college_options)
    with c3:
        level = st.selectbox("等级", ["全部", "普通", "高级", "教师"])
    filters = {"keyword": keyword, "college": None if college == "全部" else college,
               "level": None if level == "全部" else level}
    total, rows = repo.get_readers(filters, st.session_state.reader_page, 10)
    pages = max(1, (total + 9) // 10)
    if st.session_state.reader_page > pages:
        st.session_state.reader_page = pages
        total, rows = repo.get_readers(filters, pages, 10)
    st.caption(f"共 {fmt_int(total)} 位读者 · 第 {st.session_state.reader_page}/{pages} 页")
    p1, p2, _ = st.columns([1, 1, 4])
    with p1:
        if st.button("上一页", disabled=st.session_state.reader_page <= 1, key="reader_prev"):
            st.session_state.reader_page -= 1
            st.rerun()
    with p2:
        if st.button("下一页", disabled=st.session_state.reader_page >= pages, key="reader_next"):
            st.session_state.reader_page += 1
            st.rerun()
    table = to_dataframe([{
        "借阅证号": r["card_no"], "读者": r["name"], "学院": r["college"],
        "等级": r["level"], "注册时间": fmt_date(r["register_date"]),
        "借阅次数": r["borrow_count"],
    } for r in rows])
    if table.empty:
        empty_state("没有匹配的读者", "调整检索条件。")
    else:
        render_dataframe(table, height=500, key=f"reader_list_{mode}")
        csv_download(table, "readers.csv", "导出读者 CSV")

with stats_tab:
    section_title("读者结构", "等级与学院口径来自 readers；借阅次数来自 borrow_records / borrow_logs")
    levels = repo.get_level_stats()
    colleges = repo.get_college_stats()
    left, right = st.columns(2)
    with left:
        if levels:
            st.plotly_chart(donut([r["level"] for r in levels], [r["count"] for r in levels],
                                  title="读者等级分布", height=320), use_container_width=True)
        else:
            empty_state("暂无等级数据")
    with right:
        if colleges:
            st.plotly_chart(bar([r["college"] for r in colleges], [r["borrows"] for r in colleges],
                                title="学院借阅量", horizontal=True, color="#2563EB", height=320),
                            use_container_width=True)
        else:
            empty_state("暂无学院数据")
    section_title("学院读者与借阅", "平均借阅次数 = 学院借阅量 / 学院读者数")
    if colleges:
        df = to_dataframe([{"学院": r["college"], "读者数": r["readers"],
                            "借阅量": r["borrows"], "人均借阅": r["avg_borrows"]} for r in colleges])
        render_dataframe(df, height=260, key=f"reader_colleges_{mode}")
    ranking = repo.get_reader_ranking(5)
    section_title("活跃读者 Top 5", "按借阅记录数统计；姓名为脱敏形式")
    if ranking:
        df = to_dataframe([{"借阅证号": r["card_no"], "读者": r["name"],
                            "学院": r["college"], "借阅次数": r["borrow_count"]} for r in ranking])
        render_dataframe(df, height=240, key=f"reader_ranking_{mode}")
    else:
        empty_state("暂无活跃读者")

with manage_tab:
    if not repo.can_write:
        st.info("当前为只读模式；维护按钮不会写入数据库。")
    add_col, edit_col = st.columns(2)
    with add_col:
        section_title("新增读者")
        with st.form("add_reader_form"):
            card_no = st.text_input("借阅证号 *")
            name = st.text_input("姓名 *")
            college_input = st.text_input("学院")
            level_input = st.selectbox("等级", ["普通", "高级", "教师"])
            fav = st.text_input("偏好类别（逗号分隔）")
            add_submitted = st.form_submit_button("新增读者", type="primary", disabled=not repo.can_write)
        if add_submitted:
            try:
                repo.add_reader({"card_no": card_no, "name": name, "college": college_input,
                                 "level": level_input, "fav_categories": fav})
                flash("success", "新增读者成功。")
                st.rerun()
            except ValidationError as exc:
                st.error(str(exc))
            except Exception as exc:
                st.error(f"新增失败：{exc}")
    with edit_col:
        section_title("编辑 / 删除读者")
        card_edit = st.text_input("借阅证号", key="reader_edit_card")
        reader = repo.get_reader(card_edit) if card_edit else None
        if card_edit and not reader:
            st.warning("未找到该读者。")
        if reader:
            with st.form("edit_reader_form"):
                edit_name = st.text_input("姓名", value=reader["name"])
                edit_college = st.text_input("学院", value=reader["college"])
                edit_level = st.selectbox("等级", ["普通", "高级", "教师"],
                                          index=["普通", "高级", "教师"].index(reader["level"]) if reader["level"] in ["普通", "高级", "教师"] else 0)
                edit_fav = st.text_input("偏好类别", value=",".join(reader["fav_categories"]))
                save_reader = st.form_submit_button("保存修改", type="primary", disabled=not repo.can_write)
            if save_reader:
                try:
                    repo.update_reader(card_edit, {"name": edit_name, "college": edit_college,
                                                   "level": edit_level, "fav_categories": edit_fav})
                    flash("success", "读者信息已更新。")
                    st.rerun()
                except ValidationError as exc:
                    st.error(str(exc))
                except Exception as exc:
                    st.error(f"修改失败：{exc}")
            confirm_reader = st.checkbox("确认删除该读者（有未归还图书时会被拒绝）")
            if st.button("删除读者", type="primary", disabled=not repo.can_write or not confirm_reader):
                try:
                    repo.delete_reader(card_edit)
                    flash("success", "删除成功。")
                    st.rerun()
                except ValidationError as exc:
                    st.error(str(exc))
                except Exception as exc:
                    st.error(f"删除失败：{exc}")
