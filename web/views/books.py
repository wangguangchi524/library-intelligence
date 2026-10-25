from __future__ import annotations

from datetime import date, datetime, timezone

import streamlit as st

from web.components.layout import (
    csv_download, empty_state, fmt_int, fmt_money, fmt_rating, page_header,
    render_dataframe, section_title, to_dataframe,
)
from web.components.state import flash, repo_mode, show_flash, write_hint
from web.services.factory import require_repo
from web.utils.validators import ValidationError, validate_book_payload

repo = require_repo()
mode = repo_mode(repo)
page_header("图书管理", "组合检索、详情、受控新增、编辑与删除。",
            mode, "可写" if repo.can_write else "只读", write_hint(repo))
show_flash()

if "book_page" not in st.session_state:
    st.session_state.book_page = 1

section_title("组合检索", "关键词转义后执行；MongoDB 模式使用服务端查询。")
with st.container():
    c1, c2, c3 = st.columns([2.2, 1.2, 1.2])
    with c1:
        keyword = st.text_input("书名 / 作者 / ISBN", placeholder="例如 MongoDB、Python、978...")
    with c2:
        categories = st.multiselect("类别", repo.get_categories(), placeholder="全部类别")
    with c3:
        publisher = st.selectbox("出版社", ["全部"] + repo.get_publishers())
    c4, c5, c6, c7 = st.columns(4)
    with c4:
        price_min = st.number_input("最低价格", min_value=0.0, value=0.0, step=1.0)
    with c5:
        price_max = st.number_input("最高价格（0=不限）", min_value=0.0, value=0.0, step=1.0)
    with c6:
        rating_min = st.slider("最低评分", 0.0, 5.0, 0.0, 0.1)
    with c7:
        stock_status = st.selectbox("库存状态", ["全部", "有库存", "无库存"])
    c8, c9, c10, c11 = st.columns([1.5, 1, 1, 1.2])
    with c8:
        tags_text = st.text_input("标签（逗号分隔，需全部匹配）", placeholder="入门,数据库")
    with c9:
        sort_by_label = st.selectbox("排序", ["评分", "价格", "库存", "借阅次数", "出版日期", "书名"])
    with c10:
        desc = st.selectbox("顺序", ["降序", "升序"]) == "降序"
    with c11:
        page_size = st.selectbox("每页", [5, 10, 20, 50], index=1)

sort_map = {"评分": "rating", "价格": "price", "库存": "stock",
            "借阅次数": "borrow_count", "出版日期": "publish_date", "书名": "title"}
filters = {
    "keyword": keyword,
    "category": categories,
    "publisher": None if publisher == "全部" else publisher,
    "price_min": price_min if price_min > 0 else None,
    "price_max": price_max if price_max > 0 else None,
    "rating_min": rating_min if rating_min > 0 else None,
    "stock_status": None if stock_status == "全部" else stock_status,
    "tags": [t.strip() for t in tags_text.split(",") if t.strip()],
}
total, rows = repo.get_books(filters, st.session_state.book_page, page_size, sort_map[sort_by_label], desc)
pages = max(1, (total + page_size - 1) // page_size)
if st.session_state.book_page > pages:
    st.session_state.book_page = pages
    total, rows = repo.get_books(filters, pages, page_size, sort_map[sort_by_label], desc)

st.caption(f"共 {fmt_int(total)} 条匹配 · 第 {st.session_state.book_page}/{pages} 页")
page_cols = st.columns([1, 1, 4])
with page_cols[0]:
    if st.button("上一页", disabled=st.session_state.book_page <= 1):
        st.session_state.book_page -= 1
        st.rerun()
with page_cols[1]:
    if st.button("下一页", disabled=st.session_state.book_page >= pages):
        st.session_state.book_page += 1
        st.rerun()

table_rows = [{
    "书名": b["title"], "ISBN": b["isbn"], "作者": b["author"], "类别": b["category"],
    "出版社": b["publisher"], "价格": b["price"], "评分": b["rating"],
    "库存": b["stock"], "借阅次数": b["borrow_count"],
} for b in rows]
df = to_dataframe(table_rows)
if not df.empty:
    render_dataframe(df, height=390)
    csv_download(df, "books.csv", "导出当前结果 CSV")
else:
    empty_state("没有匹配的图书", "调整关键词、类别或价格/评分条件。")

if rows:
    with st.expander("查看图书详情", expanded=False):
        selected_isbn = st.selectbox("选择 ISBN", [b["isbn"] for b in rows],
                                     format_func=lambda x: f"{x} · {next((b['title'] for b in rows if b['isbn'] == x), '')}")
        book = next((b for b in rows if b["isbn"] == selected_isbn), None)
        if book:
            a, b = st.columns([2, 1])
            with a:
                st.markdown(f"**{book['title']}**")
                st.write(f"作者：{book['author']}　类别：{book['category']}　出版社：{book['publisher']}")
                st.write(f"ISBN：{book['isbn']}　出版日期：{book['publish_date'].date() if book['publish_date'] else '-'}")
                st.write("标签：" + (" / ".join(book["tags"]) if book["tags"] else "无"))
            with b:
                st.metric("价格", fmt_money(book["price"]))
                st.metric("库存", fmt_int(book["stock"]))
                st.metric("评分", fmt_rating(book["rating"]))
            st.caption("可借阅" if book["stock"] > 0 else "当前无可借库存")

st.divider()
add_tab, manage_tab = st.tabs(["新增图书", "编辑 / 删除"])
with add_tab:
    if not repo.can_write:
        st.info("当前为只读模式，新增按钮不会写入数据库。")
    with st.form("add_book_form", clear_on_submit=False):
        c1, c2 = st.columns(2)
        with c1:
            isbn = st.text_input("ISBN *")
            title = st.text_input("书名 *")
            author = st.text_input("作者")
            publisher_input = st.text_input("出版社")
            category_input = st.text_input("类别", value="计算机")
        with c2:
            price = st.number_input("价格", min_value=0.0, value=59.0, step=1.0)
            rating = st.number_input("评分", min_value=0.0, max_value=5.0, value=4.0, step=0.1)
            stock = st.number_input("库存", min_value=0, value=1, step=1)
            tags = st.text_input("标签（逗号分隔）", placeholder="数据库,入门")
            publish_date = st.date_input("出版日期", value=date.today())
        submitted = st.form_submit_button("新增图书", type="primary", disabled=not repo.can_write)
    if submitted:
        try:
            payload = validate_book_payload({
                "isbn": isbn, "title": title, "author": author, "publisher": publisher_input,
                "category": category_input, "price": price, "rating": rating, "stock": stock,
                "tags": tags, "publish_date": datetime.combine(publish_date, datetime.min.time(), tzinfo=timezone.utc),
            })
            repo.add_book(payload)
            flash("success", f"新增成功：{payload['title']}")
            st.rerun()
        except ValidationError as exc:
            st.error(str(exc))
        except Exception as exc:
            st.error(f"新增失败：{exc}")

with manage_tab:
    if not repo.can_write:
        st.info("当前为只读模式；编辑与删除按钮不会写入数据库。")
    isbn_edit = st.text_input("要编辑/删除的 ISBN", key="edit_isbn")
    current = repo.get_book(isbn_edit) if isbn_edit else None
    if isbn_edit and not current:
        st.warning("未找到该 ISBN 的图书。")
    if current:
        with st.form("edit_book_form"):
            c1, c2 = st.columns(2)
            with c1:
                new_title = st.text_input("书名", value=current["title"])
                new_author = st.text_input("作者", value=current["author"])
                new_publisher = st.text_input("出版社", value=current["publisher"])
                new_category = st.text_input("类别", value=current["category"])
            with c2:
                new_price = st.number_input("价格", min_value=0.0, value=float(current["price"]), step=1.0)
                new_rating = st.number_input("评分", min_value=0.0, max_value=5.0, value=float(current["rating"]), step=0.1)
                new_stock = st.number_input("库存", min_value=0, value=int(current["stock"]), step=1)
                new_tags = st.text_input("标签", value=",".join(current["tags"]))
            save = st.form_submit_button("保存修改", type="primary", disabled=not repo.can_write)
        if save:
            try:
                repo.update_book(isbn_edit, {
                    "title": new_title, "author": new_author, "publisher": new_publisher,
                    "category": new_category, "price": new_price, "rating": new_rating,
                    "stock": new_stock, "tags": new_tags,
                })
                flash("success", "修改成功。")
                st.rerun()
            except ValidationError as exc:
                st.error(str(exc))
            except Exception as exc:
                st.error(f"修改失败：{exc}")
        confirm = st.checkbox("我确认删除该图书（存在未完成借阅时会被拒绝）")
        if st.button("删除图书", type="primary", disabled=not repo.can_write or not confirm):
            try:
                repo.delete_book(isbn_edit)
                flash("success", "删除成功。")
                st.rerun()
            except ValidationError as exc:
                st.error(str(exc))
            except Exception as exc:
                st.error(f"删除失败：{exc}")
