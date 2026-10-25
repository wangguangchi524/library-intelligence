from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from web.utils.schema import parse_date

LEVELS = {"普通", "高级", "教师"}


class ValidationError(ValueError):
    pass


def require_text(value: Any, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValidationError(f"{field}不能为空。")
    return text


def parse_number(value: Any, field: str, minimum: float | None = None,
                 maximum: float | None = None) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValidationError(f"{field}必须是数字。") from None
    if minimum is not None and number < minimum:
        raise ValidationError(f"{field}不能小于 {minimum}。")
    if maximum is not None and number > maximum:
        raise ValidationError(f"{field}不能大于 {maximum}。")
    return number


def parse_integer(value: Any, field: str, minimum: int | None = None) -> int:
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError):
        raise ValidationError(f"{field}必须是整数。") from None
    if minimum is not None and number < minimum:
        raise ValidationError(f"{field}不能小于 {minimum}。")
    return number


def validate_book_payload(payload: dict[str, Any], is_update: bool = False) -> dict[str, Any]:
    isbn = require_text(payload.get("isbn"), "ISBN")
    title = require_text(payload.get("title"), "书名")
    price = parse_number(payload.get("price", 0), "价格", 0)
    stock = parse_integer(payload.get("stock", 0), "库存", 0)
    rating = parse_number(payload.get("rating", 0), "评分", 0, 5)
    tags = payload.get("tags") or []
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]
    if not isinstance(tags, list) or any(not isinstance(t, str) for t in tags):
        raise ValidationError("标签必须是字符串数组。")
    publish_date = parse_date(payload.get("publish_date")) if payload.get("publish_date") else None
    return {
        "isbn": isbn,
        "title": title,
        "author": str(payload.get("author") or "").strip(),
        "publisher": str(payload.get("publisher") or "").strip(),
        "category": str(payload.get("category") or "未分类").strip() or "未分类",
        "price": price,
        "stock": stock,
        "rating": rating,
        "tags": tags,
        "publish_date": publish_date or datetime.now(timezone.utc),
        "borrow_count": parse_integer(payload.get("borrow_count", 0), "借阅次数", 0),
    }


def validate_reader_payload(payload: dict[str, Any]) -> dict[str, Any]:
    card_no = require_text(payload.get("card_no"), "借阅证号")
    name = require_text(payload.get("name"), "姓名")
    level = str(payload.get("level") or "普通").strip()
    if level not in LEVELS:
        raise ValidationError("借阅等级只能是 普通/高级/教师。")
    register_date = parse_date(payload.get("register_date")) if payload.get("register_date") else None
    return {
        "card_no": card_no,
        "name": name,
        "college": str(payload.get("college") or "未填写").strip() or "未填写",
        "email": str(payload.get("email") or "").strip() or None,
        "phone": str(payload.get("phone") or "").strip() or None,
        "level": level,
        "register_date": register_date or datetime.now(timezone.utc),
        "fav_categories": payload.get("fav_categories") or [],
    }


def validate_due_date(value: Any, borrow_date: datetime | None = None) -> datetime:
    due = parse_date(value)
    if not due:
        raise ValidationError("应还日期格式无效。")
    base = borrow_date or datetime.now(timezone.utc)
    if due <= base:
        raise ValidationError("应还日期必须晚于借阅时间。")
    return due
