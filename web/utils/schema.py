from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from bson import ObjectId


def parse_date(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day, tzinfo=timezone.utc)
    if isinstance(value, dict) and "$date" in value:
        return parse_date(value["$date"])
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            try:
                parsed = datetime.strptime(text, "%Y-%m-%d")
            except ValueError:
                return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    return None


def fmt_date(value: Any) -> str:
    dt = parse_date(value)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%d") if dt else "-"


def fmt_datetime(value: Any) -> str:
    dt = parse_date(value)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M") if dt else "-"


def as_float(value: Any, default: float | None = None) -> float | None:
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def as_int(value: Any, default: int = 0) -> int:
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def as_str(value: Any, default: str = "") -> str:
    return default if value is None else str(value)


def as_id(value: Any) -> str:
    if isinstance(value, ObjectId):
        return str(value)
    return "" if value is None else str(value)


def to_object_id(value: str) -> ObjectId | None:
    try:
        return ObjectId(value)
    except Exception:
        return None


def mask_name(name: Any) -> str:
    text = as_str(name).strip()
    if not text:
        return "-"
    if len(text) == 1:
        return text + "*"
    if len(text) == 2:
        return text[0] + "*"
    return text[0] + "*" * (len(text) - 2) + text[-1]


def normalize_book(doc: dict[str, Any]) -> dict[str, Any]:
    return {
        "_id": as_id(doc.get("_id")),
        "isbn": as_str(doc.get("isbn")),
        "title": as_str(doc.get("title")),
        "author": as_str(doc.get("author")),
        "publisher": as_str(doc.get("publisher")),
        "category": as_str(doc.get("category")),
        "price": as_float(doc.get("price"), 0.0) or 0.0,
        "stock": as_int(doc.get("stock"), 0),
        "rating": as_float(doc.get("rating"), 0.0) or 0.0,
        "tags": [str(t) for t in (doc.get("tags") or [])],
        "publish_date": parse_date(doc.get("publish_date")),
        "borrow_count": as_int(doc.get("borrow_count"), 0),
    }


def normalize_reader(doc: dict[str, Any]) -> dict[str, Any]:
    return {
        "_id": as_id(doc.get("_id")),
        "card_no": as_str(doc.get("card_no")),
        "name": as_str(doc.get("name")),
        "name_masked": mask_name(doc.get("name")),
        "college": as_str(doc.get("college")),
        "email": doc.get("email"),
        "phone": doc.get("phone"),
        "level": as_str(doc.get("level"), "普通"),
        "register_date": parse_date(doc.get("register_date")),
        "fav_categories": [str(t) for t in (doc.get("fav_categories") or [])],
    }


def normalize_record(doc: dict[str, Any]) -> dict[str, Any]:
    return {
        "_id": as_id(doc.get("_id")),
        "borrow_date": parse_date(doc.get("borrow_date")),
        "due_date": parse_date(doc.get("due_date")),
        "return_date": parse_date(doc.get("return_date")),
        "reader_card": as_str(doc.get("reader_card")),
        "book_isbn": as_str(doc.get("book_isbn")),
        "status": as_str(doc.get("status"), "未知"),
        "returned_late": bool(doc.get("returned_late", False)),
    }


def record_state(record: dict[str, Any], now: datetime | None = None) -> tuple[str, str, str]:
    now = now or datetime.now(timezone.utc)
    status = record.get("status") or "未知"
    returned = record.get("return_date")
    due = parse_date(record.get("due_date"))
    if status == "已归还":
        return "已归还", "success", "returned"
    if status == "逾期" and returned:
        return "历史逾期已归还", "muted", "historical_overdue"
    if status in {"借出", "逾期"}:
        if returned:
            return "已归还", "success", "returned"
        if not due:
            return "在借（应还日期未知）", "warning", "unknown_due"
        if due < now:
            return "逾期未还", "danger", "current_overdue"
        return "在借", "info", "active"
    return status, "muted", "unknown"


def overdue_days(record: dict[str, Any], now: datetime | None = None) -> int | None:
    due = parse_date(record.get("due_date"))
    if not due:
        return None
    now = now or datetime.now(timezone.utc)
    return max((now - due).days, 0)


def display_value(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, (datetime, date)):
        return fmt_datetime(value)
    if isinstance(value, Decimal):
        return f"{float(value):.2f}"
    return str(value)
