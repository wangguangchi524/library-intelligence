from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import streamlit as st

from web.components.layout import (
    empty_state, fmt_date, fmt_int, kpi_cards, page_header, render_dataframe,
    section_title, to_dataframe,
)
from web.components.state import flash, repo_mode, show_flash, write_hint
from web.services.factory import require_repo
from web.utils.validators import ValidationError, validate_due_date

repo = require_repo()
summary = repo.get_borrow_summary()
page_header("借阅管理", "借阅登记、归还与逾期状态；时间序列事件与可更新状态分离。",
            repo_mode(repo), "可写" if repo.can_write else "只读", write_hint(repo))
show_flash()

kpi_cards([
    {"label": "当前逾期未还", "value": fmt_int(summary["current_overdue"]), "hint": "以 due_date 为基准"},
    {"label": "历史逾期已归还", "value": fmt_int(summary["historical_overdue"]), "hint": "status=逾期 且已归还"},
    {"label": "应还日期未知", "value": fmt_int(summary["unknown_due"]), "hint": "在借但缺少 due_date"},
])

if "borrow_page" not in st.session_state:
    st.session_state.borrow_page = 1

section_title("借阅记录查询", "读者仅显示借阅证号与脱敏姓名，不展示联系方式")
c1, c2, c3, c4 = st.columns([1.3, 1.3, 1.2, 1.2])
with c1:
    isbn_filter = st.text_input("ISBN 包含", key="borrow_isbn")
with c2:
    card_filter = st.text_input("借阅证号包含", key="borrow_card")
with c3:
    categories = st.multiselect("图书类别", repo.get_categories(), placeholder="全部类别", key="borrow_categories")
with c4:
    query_state = st.selectbox("状态筛选", ["全部", "在借", "当前逾期", "已归还", "应还日期未知"])
c5, c6 = st.columns(2)
with c5:
    start_date = st.date_input("借阅开始日期", value=None, key="borrow_start")
with c6:
    end_date = st.date_input("借阅结束日期", value=None, key="borrow_end")
filters = {
    "isbn": isbn_filter or None,
    "card_no": card_filter or None,
    "category": categories or None,
    "query_state": query_state,
    "start_date": datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc) if start_date else None,
    "end_date": datetime.combine(end_date, datetime.max.time(), tzinfo=timezone.utc) if end_date else None,
}
total, rows = repo.get_borrow_records(filters, st.session_state.borrow_page, 20)
pages = max(1, (total + 19) // 20)
if st.session_state.borrow_page > pages:
    st.session_state.borrow_page = pages
    total, rows = repo.get_borrow_records(filters, pages, 20)
st.caption(f"共 {fmt_int(total)} 条记录 · 第 {st.session_state.borrow_page}/{pages} 页")
p1, p2, _ = st.columns([1, 1, 4])
with p1:
    if st.button("上一页", disabled=st.session_state.borrow_page <= 1, key="borrow_prev"):
        st.session_state.borrow_page -= 1
        st.rerun()
with p2:
    if st.button("下一页", disabled=st.session_state.borrow_page >= pages, key="borrow_next"):
        st.session_state.borrow_page += 1
        st.rerun()

table = to_dataframe([{
    "图书": r["title"], "借阅证号": r["reader_card"], "读者": r["reader_name"],
    "借阅日期": fmt_date(r["borrow_date"]), "应还日期": fmt_date(r["due_date"]),
    "归还日期": fmt_date(r["return_date"]), "状态": r["status"],
    "逾期天数": r["overdue_days"] if r["overdue_days"] is not None else "-",
} for r in rows])
if table.empty:
    empty_state("没有匹配的借阅记录", "调整筛选条件或日期范围。")
else:
    render_dataframe(table, height=360)

st.divider()
left, right = st.columns(2)
with left:
    section_title("借阅登记", "库存条件扣减；失败会返回原因，不伪装成功")
    if not repo.can_write:
        st.info("当前为只读模式，借阅按钮不会写入数据库。")
    readers = repo.get_readers({}, 1, 1000)[1]
    books = repo.get_books({"stock_status": "有库存"}, 1, 1000)[1]
    reader_map = {r["card_no"]: f"{r['card_no']} · {r['name']}" for r in readers}
    book_map = {b["isbn"]: f"{b['title']} · 库存 {b['stock']}" for b in books}
    with st.form("borrow_form"):
        card = st.selectbox("读者", list(reader_map), format_func=lambda x: reader_map.get(x, x)) if reader_map else None
        isbn = st.selectbox("可借图书", list(book_map), format_func=lambda x: book_map.get(x, x)) if book_map else None
        due = st.date_input("应还日期", value=date.today() + timedelta(days=30))
        submitted = st.form_submit_button("确认借阅", type="primary", disabled=not repo.can_write or not reader_map or not book_map)
    if submitted:
        try:
            due_dt = validate_due_date(datetime.combine(due, datetime.min.time(), tzinfo=timezone.utc))
            result = repo.borrow_book(card, isbn, due_dt)
            stock = result.get("stock", result.get("stock_left", "-"))
            flash("success", f"借阅成功：{result.get('title', isbn)}；记录 {result.get('record_id')}；库存 {stock}；应还 {fmt_date(due_dt)}")
            st.rerun()
        except ValidationError as exc:
            st.error(str(exc))
        except Exception as exc:
            st.error(f"借阅失败：{exc}")

with right:
    section_title("归还处理", "只允许当前在借/逾期未还记录；重复归还不会重复加库存")
    if not repo.can_write:
        st.info("当前为只读模式，归还按钮不会写入数据库。")
    active_total, active_rows = repo.get_borrow_records({"query_state": "在借"}, 1, 500)
    active_map = {r["record_id"]: f"{r['title']} · {r['reader_card']} · {r['status']}" for r in active_rows}
    with st.form("return_form"):
        record_id = st.selectbox("选择活动借阅记录", list(active_map), format_func=lambda x: active_map.get(x, x)) if active_map else None
        returned = st.form_submit_button("确认归还", type="primary", disabled=not repo.can_write or not active_map)
    if returned:
        try:
            result = repo.return_book(record_id)
            flash("success", f"归还成功：{result.get('title', '')}；库存 {result.get('stock', '-')}；记录 {record_id}")
            st.rerun()
        except ValidationError as exc:
            st.error(str(exc))
        except Exception as exc:
            st.error(f"归还失败：{exc}")
    if not active_map:
        st.caption("当前没有可归还的活动记录。")

st.caption("说明：borrow_logs 为不可变借阅事件流；borrow_records 为当前业务状态。逾期天数只按 due_date 计算，缺少 due_date 的记录不自动归类为逾期。")
