from __future__ import annotations

import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from web.utils.schema import (
    normalize_book,
    normalize_reader,
    normalize_record,
    overdue_days,
    parse_date,
    record_state,
)
from web.utils.validators import ValidationError, validate_book_payload, validate_reader_payload


class DemoRepository:
    is_demo = True
    can_write = True

    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.reset()

    def reset(self) -> None:
        self.books = [normalize_book(x) for x in self._load("books.txt")]
        self.readers = [normalize_reader(x) for x in self._load("readers.txt")]
        self.records = [normalize_record(x) for x in self._load("borrow_logs.txt")]
        self.logs = [normalize_record(x) for x in self._load("borrow_logs.txt")]

    def _load(self, filename: str) -> list[dict[str, Any]]:
        path = self.data_dir / filename
        if not path.exists():
            raise FileNotFoundError(f"示例数据文件不存在：{path}")
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise ValueError(f"示例数据必须是数组：{path}")
        return data

    @property
    def source_name(self) -> str:
        return "Demo Mode"

    def _book_map(self) -> dict[str, dict[str, Any]]:
        return {b["isbn"]: b for b in self.books}

    def _reader_map(self) -> dict[str, dict[str, Any]]:
        return {r["card_no"]: r for r in self.readers}

    def get_categories(self) -> list[str]:
        return sorted({b["category"] for b in self.books if b["category"]})

    def get_publishers(self) -> list[str]:
        return sorted({b["publisher"] for b in self.books if b["publisher"]})

    def get_book(self, isbn: str) -> dict[str, Any] | None:
        return next((dict(b) for b in self.books if b["isbn"] == isbn), None)

    def get_reader(self, card_no: str) -> dict[str, Any] | None:
        return next((dict(r) for r in self.readers if r["card_no"] == card_no), None)

    def get_books(self, filters: dict[str, Any] | None = None, page: int = 1,
                  page_size: int = 10, sort_by: str = "rating", desc: bool = True):
        filters = filters or {}
        rows = list(self.books)
        keyword = str(filters.get("keyword") or "").strip().casefold()
        if keyword:
            rows = [b for b in rows if keyword in f"{b['title']} {b['author']} {b['isbn']}".casefold()]
        categories = filters.get("category") or []
        if isinstance(categories, str):
            categories = [categories]
        if categories:
            rows = [b for b in rows if b["category"] in categories]
        publisher = filters.get("publisher")
        if publisher:
            rows = [b for b in rows if b["publisher"] == publisher]
        if filters.get("price_min") is not None:
            rows = [b for b in rows if b["price"] >= filters["price_min"]]
        if filters.get("price_max") is not None:
            rows = [b for b in rows if b["price"] <= filters["price_max"]]
        if filters.get("rating_min") is not None:
            rows = [b for b in rows if b["rating"] >= filters["rating_min"]]
        if filters.get("rating_max") is not None:
            rows = [b for b in rows if b["rating"] <= filters["rating_max"]]
        stock_status = filters.get("stock_status")
        if stock_status == "有库存":
            rows = [b for b in rows if b["stock"] > 0]
        elif stock_status == "无库存":
            rows = [b for b in rows if b["stock"] <= 0]
        tags = filters.get("tags") or []
        if tags:
            rows = [b for b in rows if all(t in b["tags"] for t in tags)]

        def sort_key(book: dict[str, Any]):
            value = book.get(sort_by)
            if isinstance(value, datetime):
                value = value.timestamp()
            if value is None:
                value = 0
            return (value, book.get("isbn", ""))

        rows.sort(key=sort_key, reverse=desc)
        total = len(rows)
        start = max(page - 1, 0) * page_size
        return total, [dict(b) for b in rows[start:start + page_size]]

    def get_readers(self, filters: dict[str, Any] | None = None, page: int = 1,
                    page_size: int = 10) -> tuple[int, list[dict[str, Any]]]:
        filters = filters or {}
        rows = list(self.readers)
        keyword = str(filters.get("keyword") or "").strip().casefold()
        if keyword:
            rows = [r for r in rows if keyword in f"{r['card_no']} {r['name']} {r['college']}".casefold()]
        college = filters.get("college")
        if college:
            rows = [r for r in rows if r["college"] == college]
        level = filters.get("level")
        if level:
            rows = [r for r in rows if r["level"] == level]
        start_date = parse_date(filters.get("start_date"))
        end_date = parse_date(filters.get("end_date"))
        if start_date:
            rows = [r for r in rows if r["register_date"] and r["register_date"] >= start_date]
        if end_date:
            rows = [r for r in rows if r["register_date"] and r["register_date"] <= end_date]
        counts: dict[str, int] = {}
        for rec in self.records:
            counts[rec["reader_card"]] = counts.get(rec["reader_card"], 0) + 1
        rows = sorted(rows, key=lambda r: (r["card_no"], r["name"]))
        total = len(rows)
        start = max(page - 1, 0) * page_size
        result = []
        for r in rows[start:start + page_size]:
            result.append({
                "card_no": r["card_no"],
                "name": r["name_masked"],
                "college": r["college"],
                "level": r["level"],
                "register_date": r["register_date"],
                "borrow_count": counts.get(r["card_no"], 0),
            })
        return total, result

    def get_borrow_records(self, filters: dict[str, Any] | None = None, page: int = 1,
                           page_size: int = 20) -> tuple[int, list[dict[str, Any]]]:
        filters = filters or {}
        books = self._book_map()
        readers = self._reader_map()
        rows = []
        for rec in self.records:
            book = books.get(rec["book_isbn"], {})
            reader = readers.get(rec["reader_card"], {})
            category = book.get("category", "未分类")
            if filters.get("isbn") and filters["isbn"] not in rec["book_isbn"]:
                continue
            if filters.get("card_no") and filters["card_no"] not in rec["reader_card"]:
                continue
            if filters.get("category") and category not in filters["category"]:
                continue
            start_date = parse_date(filters.get("start_date"))
            end_date = parse_date(filters.get("end_date"))
            if start_date and (not rec["borrow_date"] or rec["borrow_date"] < start_date):
                continue
            if end_date and (not rec["borrow_date"] or rec["borrow_date"] > end_date):
                continue
            label, kind, state = record_state(rec)
            if filters.get("query_state") and filters["query_state"] != "全部":
                if filters["query_state"] == "当前逾期" and state != "current_overdue":
                    continue
                if filters["query_state"] == "已归还" and state not in {"returned", "historical_overdue"}:
                    continue
                if filters["query_state"] == "在借" and state not in {"active", "unknown_due", "current_overdue"}:
                    continue
                if filters["query_state"] == "应还日期未知" and state != "unknown_due":
                    continue
            rows.append({
                "record_id": rec["_id"],
                "title": book.get("title", "未知图书"),
                "isbn": rec["book_isbn"],
                "reader_card": rec["reader_card"],
                "reader_name": reader.get("name_masked", "-"),
                "category": category,
                "borrow_date": rec["borrow_date"],
                "due_date": rec["due_date"],
                "return_date": rec["return_date"],
                "status": label,
                "state": state,
                "overdue_days": overdue_days(rec) if state == "current_overdue" else None,
            })
        rows.sort(key=lambda r: r["borrow_date"] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
        total = len(rows)
        start = max(page - 1, 0) * page_size
        return total, rows[start:start + page_size]

    def get_dashboard_metrics(self) -> dict[str, Any]:
        active = [r for r in self.records if record_state(r)[2] in {"active", "unknown_due", "current_overdue"}]
        return {
            "book_titles": len(self.books),
            "readers": len(self.readers),
            "borrow_events": len(self.logs),
            "available_titles": len([b for b in self.books if b["stock"] > 0]),
            "active_loans": len(active),
            "categories": len(self.get_categories()),
            "total_copies": sum(b["stock"] for b in self.books),
        }

    def get_category_stats(self) -> list[dict[str, Any]]:
        stats: dict[str, dict[str, Any]] = {}
        for b in self.books:
            row = stats.setdefault(b["category"] or "未分类", {"category": b["category"] or "未分类", "count": 0, "stock": 0, "price_sum": 0.0, "rating_sum": 0.0, "rating_n": 0})
            row["count"] += 1
            row["stock"] += b["stock"]
            row["price_sum"] += b["price"]
            if b["rating"] is not None:
                row["rating_sum"] += b["rating"]
                row["rating_n"] += 1
        result = []
        for row in stats.values():
            result.append({
                "category": row["category"],
                "count": row["count"],
                "stock": row["stock"],
                "avg_price": round(row["price_sum"] / row["count"], 2) if row["count"] else 0,
                "avg_rating": round(row["rating_sum"] / row["rating_n"], 2) if row["rating_n"] else 0,
            })
        return sorted(result, key=lambda r: (-r["count"], r["category"]))

    def get_year_trend(self, category: str | None = None) -> list[dict[str, Any]]:
        books = self._book_map()
        counts: dict[int, int] = {}
        for rec in self.logs:
            if category and books.get(rec["book_isbn"], {}).get("category") != category:
                continue
            if rec["borrow_date"]:
                counts[rec["borrow_date"].astimezone(timezone.utc).year] = counts.get(rec["borrow_date"].astimezone(timezone.utc).year, 0) + 1
        return [{"year": year, "count": counts[year]} for year in sorted(counts)]

    def get_month_trend(self, category: str | None = None) -> list[dict[str, Any]]:
        books = self._book_map()
        counts: dict[str, int] = {}
        for rec in self.logs:
            if category and books.get(rec["book_isbn"], {}).get("category") != category:
                continue
            if rec["borrow_date"]:
                dt = rec["borrow_date"].astimezone(timezone.utc)
                key = f"{dt.year}-{dt.month:02d}"
                counts[key] = counts.get(key, 0) + 1
        return [{"month": key, "count": counts[key]} for key in sorted(counts)]

    def get_top_books(self, limit: int = 10, category: str | None = None) -> list[dict[str, Any]]:
        rows = [b for b in self.books if not category or b["category"] == category]
        rows.sort(key=lambda b: (-b["borrow_count"], b["isbn"]))
        return [dict(b) for b in rows[:limit]]

    def get_recent_loans(self, limit: int = 10, category: str | None = None) -> list[dict[str, Any]]:
        _, rows = self.get_borrow_records({"category": [category] if category else None}, 1, limit)
        return rows

    def get_rating_distribution(self, category: str | None = None) -> list[dict[str, Any]]:
        rows = [b for b in self.books if not category or b["category"] == category]
        bins = {f"{i / 2:.1f}-{(i + 1) / 2:.1f}": 0 for i in range(10)}
        for b in rows:
            index = min(max(int(math.floor(b["rating"] * 2)), 0), 9)
            key = f"{index / 2:.1f}-{(index + 1) / 2:.1f}"
            bins[key] += 1
        return [{"range": k, "count": v} for k, v in bins.items()]

    def get_price_summary(self, category: str | None = None) -> dict[str, Any]:
        rows = [b for b in self.books if not category or b["category"] == category]
        prices = sorted(b["price"] for b in rows)
        if not prices:
            return {"mean": 0, "median": 0, "prices": [], "by_category": []}
        groups: dict[str, list[float]] = {}
        for b in rows:
            groups.setdefault(b["category"] or "未分类", []).append(b["price"])
        return {
            "mean": round(sum(prices) / len(prices), 2),
            "median": round(prices[len(prices) // 2], 2),
            "prices": prices,
            "by_category": [{"category": k, "prices": v} for k, v in sorted(groups.items())],
        }

    def get_borrow_summary(self) -> dict[str, int]:
        summary = {"current_overdue": 0, "historical_overdue": 0, "unknown_due": 0}
        for rec in self.records:
            state = record_state(rec)[2]
            if state == "current_overdue":
                summary["current_overdue"] += 1
            elif state == "historical_overdue":
                summary["historical_overdue"] += 1
            elif state == "unknown_due":
                summary["unknown_due"] += 1
        return summary

    def get_status_distribution(self) -> list[dict[str, Any]]:
        counts: dict[str, int] = {}
        for rec in self.records:
            label, _, _ = record_state(rec)
            counts[label] = counts.get(label, 0) + 1
        return [{"status": k, "count": v} for k, v in sorted(counts.items())]

    def get_level_stats(self) -> list[dict[str, Any]]:
        counts: dict[str, int] = {}
        for r in self.readers:
            counts[r["level"] or "未填写"] = counts.get(r["level"] or "未填写", 0) + 1
        return [{"level": k, "count": v} for k, v in sorted(counts.items(), key=lambda x: -x[1])]

    def get_college_stats(self) -> list[dict[str, Any]]:
        readers = self._reader_map()
        borrow_by_card: dict[str, int] = {}
        for rec in self.logs:
            borrow_by_card[rec["reader_card"]] = borrow_by_card.get(rec["reader_card"], 0) + 1
        groups: dict[str, dict[str, Any]] = {}
        for r in self.readers:
            row = groups.setdefault(r["college"], {"college": r["college"], "readers": 0, "borrows": 0})
            row["readers"] += 1
            row["borrows"] += borrow_by_card.get(r["card_no"], 0)
        result = []
        for row in groups.values():
            result.append({**row, "avg_borrows": round(row["borrows"] / row["readers"], 2) if row["readers"] else 0})
        return sorted(result, key=lambda r: (-r["borrows"], r["college"]))

    def get_reader_ranking(self, limit: int = 5) -> list[dict[str, Any]]:
        counts: dict[str, int] = {}
        for rec in self.records:
            counts[rec["reader_card"]] = counts.get(rec["reader_card"], 0) + 1
        readers = self._reader_map()
        rows = []
        for card, n in counts.items():
            reader = readers.get(card, {})
            rows.append({"card_no": card, "name": reader.get("name_masked", "-"),
                         "college": reader.get("college", "-"), "borrow_count": n})
        return sorted(rows, key=lambda r: (-r["borrow_count"], r["card_no"]))[:limit]

    def get_top_categories(self, limit: int = 5) -> list[dict[str, Any]]:
        books = self._book_map()
        counts: dict[str, int] = {}
        for rec in self.logs:
            category = books.get(rec["book_isbn"], {}).get("category", "未分类")
            counts[category] = counts.get(category, 0) + 1
        return [{"category": k, "borrows": v} for k, v in sorted(counts.items(), key=lambda x: -x[1])[:limit]]

    def get_simulated_values(self, limit: int = 10) -> list[dict[str, Any]]:
        rows = [{"isbn": b["isbn"], "title": b["title"], "category": b["category"],
                 "value": round(b["price"] * b["borrow_count"], 2)} for b in self.books]
        return sorted(rows, key=lambda r: -r["value"])[:limit]

    def borrow_book(self, card_no: str, isbn: str, due_date: datetime):
        reader = self.get_reader(card_no)
        book = self.get_book(isbn)
        if not reader:
            raise ValidationError("读者不存在。")
        if not book:
            raise ValidationError("图书不存在。")
        if book["stock"] <= 0:
            raise ValidationError("库存为 0，无法借阅。")
        active = [r for r in self.records if r["reader_card"] == card_no and r["book_isbn"] == isbn
                  and record_state(r)[2] in {"active", "unknown_due", "current_overdue"}]
        if active:
            raise ValidationError("该读者已有一本相同的在借图书。")
        now = datetime.now(timezone.utc)
        record = {
            "_id": "DEMO-" + uuid4().hex[:12],
            "borrow_date": now,
            "due_date": due_date.astimezone(timezone.utc),
            "return_date": None,
            "reader_card": card_no,
            "book_isbn": isbn,
            "status": "借出",
            "returned_late": False,
        }
        self.records.append(record)
        self.logs.append(dict(record))
        for b in self.books:
            if b["isbn"] == isbn:
                b["stock"] -= 1
                b["borrow_count"] += 1
                break
        return {"ok": True, "record_id": record["_id"], "title": book["title"],
                "stock": book["stock"] - 1, "due_date": record["due_date"]}

    def return_book(self, record_id: str):
        record = next((r for r in self.records if r["_id"] == record_id), None)
        if not record:
            raise ValidationError("借阅记录不存在。")
        if record_state(record)[2] not in {"active", "unknown_due", "current_overdue"}:
            raise ValidationError("该记录不是当前在借状态，不能重复归还。")
        now = datetime.now(timezone.utc)
        record["status"] = "已归还"
        record["return_date"] = now
        record["returned_late"] = bool(record["due_date"] and now > record["due_date"])
        book = next((b for b in self.books if b["isbn"] == record["book_isbn"]), None)
        if not book:
            raise ValidationError("关联图书不存在，无法恢复库存。")
        book["stock"] += 1
        return {"ok": True, "record_id": record_id, "title": book["title"],
                "stock": book["stock"], "returned_late": record["returned_late"]}

    def add_book(self, payload: dict[str, Any]) -> dict[str, Any]:
        data = validate_book_payload(payload)
        if any(b["isbn"] == data["isbn"] for b in self.books):
            raise ValidationError("ISBN 已存在。")
        doc = normalize_book({**data, "_id": data["isbn"]})
        self.books.append(doc)
        return doc

    def update_book(self, isbn: str, payload: dict[str, Any]) -> dict[str, Any]:
        book = next((b for b in self.books if b["isbn"] == isbn), None)
        if not book:
            raise ValidationError("图书不存在。")
        data = validate_book_payload({**book, **payload, "isbn": isbn})
        book.update(data)
        return dict(book)

    def delete_book(self, isbn: str) -> None:
        active = [r for r in self.records if r["book_isbn"] == isbn and record_state(r)[2] in {"active", "unknown_due", "current_overdue"}]
        if active:
            raise ValidationError("该图书存在未完成借阅，不能删除。")
        before = len(self.books)
        self.books = [b for b in self.books if b["isbn"] != isbn]
        if len(self.books) == before:
            raise ValidationError("图书不存在。")

    def add_reader(self, payload: dict[str, Any]) -> dict[str, Any]:
        data = validate_reader_payload(payload)
        if any(r["card_no"] == data["card_no"] for r in self.readers):
            raise ValidationError("借阅证号已存在。")
        doc = normalize_reader({**data, "_id": data["card_no"]})
        self.readers.append(doc)
        return doc

    def update_reader(self, card_no: str, payload: dict[str, Any]) -> dict[str, Any]:
        reader = next((r for r in self.readers if r["card_no"] == card_no), None)
        if not reader:
            raise ValidationError("读者不存在。")
        data = validate_reader_payload({**reader, **payload, "card_no": card_no})
        reader.update(data)
        reader["name_masked"] = reader["name"][0] + "*" * min(max(len(reader["name"]) - 1, 1), 2) if reader["name"] else "-"
        return dict(reader)

    def delete_reader(self, card_no: str) -> None:
        active = [r for r in self.records if r["reader_card"] == card_no and record_state(r)[2] in {"active", "unknown_due", "current_overdue"}]
        if active:
            raise ValidationError("该读者尚有未归还图书，不能删除。")
        before = len(self.readers)
        self.readers = [r for r in self.readers if r["card_no"] != card_no]
        if len(self.readers) == before:
            raise ValidationError("读者不存在。")

    def get_system_info(self) -> dict[str, Any]:
        return {
            "mode": "Demo Mode",
            "db_name": "data/ (in-memory)",
            "collections": [
                {"name": "books", "type": "array", "count": len(self.books)},
                {"name": "readers", "type": "array", "count": len(self.readers)},
                {"name": "borrow_logs", "type": "array", "count": len(self.logs)},
                {"name": "borrow_records", "type": "array", "count": len(self.records)},
            ],
            "indexes": [],
            "ttl": None,
            "mongo_version": "未连接",
        }
