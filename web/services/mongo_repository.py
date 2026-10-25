from __future__ import annotations

import math
import re
import sys
from datetime import datetime, timezone
from typing import Any

from bson import ObjectId
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError, PyMongoError

from web.utils.config import ROOT, AppConfig
from web.utils.permissions import can_write_mongo, require_mongo_write
from web.utils.schema import (
    normalize_book,
    normalize_reader,
    normalize_record,
    overdue_days,
    parse_date,
    record_state,
)
from web.utils.validators import ValidationError, validate_book_payload, validate_reader_payload

sys.path.insert(0, str(ROOT / "python"))
import borrow_manager  # noqa: E402


class MongoRepository:
    is_demo = False

    def __init__(self, config: AppConfig):
        self.config = config
        self.db_name = config.mongo_db
        self.can_write = can_write_mongo(config, config.mongo_db)
        kwargs: dict[str, Any] = {
            "host": config.mongo_host,
            "port": config.mongo_port,
            "directConnection": True,
            "retryWrites": False,
            "serverSelectionTimeoutMS": 4000,
            "tz_aware": True,
            "appname": "library-intelligence-web",
        }
        if config.mongo_user:
            kwargs.update(username=config.mongo_user, password=config.mongo_password,
                          authSource=config.mongo_auth_source)
        self.client = MongoClient(**kwargs)
        self.db = self.client[config.mongo_db]
        self.db.command("ping")

    @property
    def source_name(self) -> str:
        return f"MongoDB / {self.db_name}"

    def _require_write(self) -> None:
        require_mongo_write(self.config, self.db_name)

    def _book_query(self, filters: dict[str, Any] | None) -> dict[str, Any]:
        filters = filters or {}
        query: dict[str, Any] = {}
        keyword = str(filters.get("keyword") or "").strip()
        if keyword:
            regex = {"$regex": re.escape(keyword), "$options": "i"}
            query["$or"] = [{"title": regex}, {"author": regex}, {"isbn": regex}]
        categories = filters.get("category") or []
        if isinstance(categories, str):
            categories = [categories]
        if categories:
            query["category"] = {"$in": categories}
        if filters.get("publisher"):
            query["publisher"] = filters["publisher"]
        price = {}
        if filters.get("price_min") is not None:
            price["$gte"] = filters["price_min"]
        if filters.get("price_max") is not None:
            price["$lte"] = filters["price_max"]
        if price:
            query["price"] = price
        rating = {}
        if filters.get("rating_min") is not None:
            rating["$gte"] = filters["rating_min"]
        if filters.get("rating_max") is not None:
            rating["$lte"] = filters["rating_max"]
        if rating:
            query["rating"] = rating
        if filters.get("stock_status") == "有库存":
            query["stock"] = {"$gt": 0}
        elif filters.get("stock_status") == "无库存":
            query["stock"] = {"$lte": 0}
        tags = filters.get("tags") or []
        if tags:
            query["tags"] = {"$all": tags}
        return query

    def get_categories(self) -> list[str]:
        return sorted(x for x in self.db.books.distinct("category") if x)

    def get_publishers(self) -> list[str]:
        return sorted(x for x in self.db.books.distinct("publisher") if x)

    def get_book(self, isbn: str) -> dict[str, Any] | None:
        doc = self.db.books.find_one({"isbn": isbn})
        return normalize_book(doc) if doc else None

    def get_reader(self, card_no: str) -> dict[str, Any] | None:
        doc = self.db.readers.find_one({"card_no": card_no}, {"email": 0, "phone": 0})
        return normalize_reader(doc) if doc else None

    def get_books(self, filters: dict[str, Any] | None = None, page: int = 1,
                  page_size: int = 10, sort_by: str = "rating", desc: bool = True):
        query = self._book_query(filters)
        total = self.db.books.count_documents(query)
        cursor = (self.db.books.find(query)
                  .sort([(sort_by, -1 if desc else 1), ("isbn", 1)])
                  .skip(max(page - 1, 0) * page_size)
                  .limit(page_size))
        return total, [normalize_book(x) for x in cursor]

    def get_readers(self, filters: dict[str, Any] | None = None, page: int = 1,
                    page_size: int = 10):
        filters = filters or {}
        query: dict[str, Any] = {}
        keyword = str(filters.get("keyword") or "").strip()
        if keyword:
            regex = {"$regex": re.escape(keyword), "$options": "i"}
            query["$or"] = [{"card_no": regex}, {"name": regex}, {"college": regex}]
        if filters.get("college"):
            query["college"] = filters["college"]
        if filters.get("level"):
            query["level"] = filters["level"]
        start_date = parse_date(filters.get("start_date"))
        end_date = parse_date(filters.get("end_date"))
        if start_date or end_date:
            date_query = {}
            if start_date:
                date_query["$gte"] = start_date
            if end_date:
                date_query["$lte"] = end_date
            query["register_date"] = date_query
        total = self.db.readers.count_documents(query)
        cursor = (self.db.readers.find(query, {"email": 0, "phone": 0})
                  .sort("card_no", 1)
                  .skip(max(page - 1, 0) * page_size)
                  .limit(page_size))
        counts = {row["_id"]: row["n"] for row in self.db.borrow_records.aggregate([
            {"$group": {"_id": "$reader_card", "n": {"$sum": 1}}}
        ])}
        rows = []
        for doc in cursor:
            reader = normalize_reader(doc)
            rows.append({
                "card_no": reader["card_no"],
                "name": reader["name_masked"],
                "college": reader["college"],
                "level": reader["level"],
                "register_date": reader["register_date"],
                "borrow_count": counts.get(reader["card_no"], 0),
            })
        return total, rows

    def get_borrow_records(self, filters: dict[str, Any] | None = None, page: int = 1,
                           page_size: int = 20):
        filters = filters or {}
        query: dict[str, Any] = {}
        if filters.get("isbn"):
            query["book_isbn"] = {"$regex": re.escape(filters["isbn"])}
        if filters.get("card_no"):
            query["reader_card"] = {"$regex": re.escape(filters["card_no"])}
        if filters.get("status"):
            query["status"] = filters["status"]
        start_date = parse_date(filters.get("start_date"))
        end_date = parse_date(filters.get("end_date"))
        if start_date or end_date:
            date_query = {}
            if start_date:
                date_query["$gte"] = start_date
            if end_date:
                date_query["$lte"] = end_date
            query["borrow_date"] = date_query
        all_rows = [normalize_record(x) for x in self.db.borrow_records.find(query).sort("borrow_date", -1)]
        books = {b["isbn"]: b for b in (normalize_book(x) for x in self.db.books.find({}, {"isbn": 1, "title": 1, "category": 1, "author": 1}))}
        readers = {r["card_no"]: r for r in (normalize_reader(x) for x in self.db.readers.find({}, {"card_no": 1, "name": 1, "college": 1}))}
        rows = []
        for rec in all_rows:
            book = books.get(rec["book_isbn"], {})
            reader = readers.get(rec["reader_card"], {})
            category = book.get("category", "未分类")
            if filters.get("category") and category not in filters["category"]:
                continue
            label, kind, state = record_state(rec)
            selected = filters.get("query_state") or "全部"
            if selected != "全部":
                if selected == "当前逾期" and state != "current_overdue":
                    continue
                if selected == "已归还" and state not in {"returned", "historical_overdue"}:
                    continue
                if selected == "在借" and state not in {"active", "unknown_due", "current_overdue"}:
                    continue
                if selected == "应还日期未知" and state != "unknown_due":
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
        total = len(rows)
        start = max(page - 1, 0) * page_size
        return total, rows[start:start + page_size]

    def get_dashboard_metrics(self) -> dict[str, Any]:
        active = self.db.borrow_records.count_documents({
            "status": {"$in": ["借出", "逾期"]},
            "return_date": None,
        })
        total_copies = list(self.db.books.aggregate([{"$group": {"_id": None, "total": {"$sum": "$stock"}}}]))
        return {
            "book_titles": self.db.books.count_documents({}),
            "readers": self.db.readers.count_documents({}),
            "borrow_events": self.db.borrow_logs.count_documents({}),
            "available_titles": self.db.books.count_documents({"stock": {"$gt": 0}}),
            "active_loans": active,
            "categories": len(self.get_categories()),
            "total_copies": total_copies[0]["total"] if total_copies else 0,
        }

    def get_category_stats(self) -> list[dict[str, Any]]:
        rows = list(self.db.books.aggregate([
            {"$group": {"_id": "$category", "count": {"$sum": 1}, "stock": {"$sum": "$stock"},
                        "avg_price": {"$avg": "$price"}, "avg_rating": {"$avg": "$rating"}}},
            {"$sort": {"count": -1, "_id": 1}},
        ]))
        return [{"category": r["_id"] or "未分类", "count": r["count"], "stock": r["stock"],
                 "avg_price": round(r["avg_price"] or 0, 2), "avg_rating": round(r["avg_rating"] or 0, 2)} for r in rows]

    def _logs_pipeline(self, group_stage: dict[str, Any], category: str | None = None) -> list[dict[str, Any]]:
        pipeline: list[dict[str, Any]] = []
        if category:
            pipeline.extend([
                {"$lookup": {"from": "books", "localField": "book_isbn", "foreignField": "isbn", "as": "book"}},
                {"$unwind": "$book"},
                {"$match": {"book.category": category}},
            ])
        pipeline.append(group_stage)
        return pipeline

    def get_year_trend(self, category: str | None = None) -> list[dict[str, Any]]:
        pipeline = self._logs_pipeline({
            "$group": {"_id": {"$year": {"date": "$borrow_date", "timezone": "+08:00"}}, "count": {"$sum": 1}}
        }, category)
        pipeline.append({"$sort": {"_id": 1}})
        return [{"year": r["_id"], "count": r["count"]} for r in self.db.borrow_logs.aggregate(pipeline)]

    def get_month_trend(self, category: str | None = None) -> list[dict[str, Any]]:
        pipeline = self._logs_pipeline({
            "$group": {"_id": {"$dateToString": {"format": "%Y-%m", "date": "$borrow_date", "timezone": "+08:00"}}, "count": {"$sum": 1}}
        }, category)
        pipeline.append({"$sort": {"_id": 1}})
        return [{"month": r["_id"], "count": r["count"]} for r in self.db.borrow_logs.aggregate(pipeline)]

    def get_top_books(self, limit: int = 10, category: str | None = None) -> list[dict[str, Any]]:
        query = {"category": category} if category else {}
        return [normalize_book(x) for x in self.db.books.find(query).sort([("borrow_count", -1), ("isbn", 1)]).limit(limit)]

    def get_recent_loans(self, limit: int = 10, category: str | None = None) -> list[dict[str, Any]]:
        _, rows = self.get_borrow_records({"category": [category] if category else None}, 1, limit)
        return rows

    def get_rating_distribution(self, category: str | None = None) -> list[dict[str, Any]]:
        query = {"category": category} if category else {}
        docs = list(self.db.books.find(query, {"rating": 1}))
        bins = {f"{i / 2:.1f}-{(i + 1) / 2:.1f}": 0 for i in range(10)}
        for doc in docs:
            rating = float(doc.get("rating") or 0)
            index = min(max(int(math.floor(rating * 2)), 0), 9)
            bins[f"{index / 2:.1f}-{(index + 1) / 2:.1f}"] += 1
        return [{"range": k, "count": v} for k, v in bins.items()]

    def get_price_summary(self, category: str | None = None) -> dict[str, Any]:
        query = {"category": category} if category else {}
        docs = list(self.db.books.find(query, {"price": 1, "category": 1}))
        prices = sorted(float(x.get("price") or 0) for x in docs)
        if not prices:
            return {"mean": 0, "median": 0, "prices": [], "by_category": []}
        groups: dict[str, list[float]] = {}
        for doc in docs:
            groups.setdefault(doc.get("category") or "未分类", []).append(float(doc.get("price") or 0))
        return {
            "mean": round(sum(prices) / len(prices), 2),
            "median": round(prices[len(prices) // 2], 2),
            "prices": prices,
            "by_category": [{"category": k, "prices": v} for k, v in sorted(groups.items())],
        }

    def get_status_distribution(self) -> list[dict[str, Any]]:
        rows = list(self.db.borrow_records.aggregate([{"$group": {"_id": "$status", "count": {"$sum": 1}}}, {"$sort": {"_id": 1}}]))
        return [{"status": r["_id"] or "未知", "count": r["count"]} for r in rows]

    def get_level_stats(self) -> list[dict[str, Any]]:
        rows = self.db.readers.aggregate([{"$group": {"_id": "$level", "count": {"$sum": 1}}}, {"$sort": {"count": -1, "_id": 1}}])
        return [{"level": r["_id"] or "未填写", "count": r["count"]} for r in rows]

    def get_college_stats(self) -> list[dict[str, Any]]:
        reader_counts = {r["_id"]: r["n"] for r in self.db.readers.aggregate([{"$group": {"_id": "$college", "n": {"$sum": 1}}}])}
        borrow_rows = list(self.db.borrow_logs.aggregate([
            {"$lookup": {"from": "readers", "localField": "reader_card", "foreignField": "card_no", "as": "reader"}},
            {"$unwind": "$reader"},
            {"$group": {"_id": "$reader.college", "borrows": {"$sum": 1}}},
        ]))
        groups = []
        for row in borrow_rows:
            readers = reader_counts.get(row["_id"], 0)
            groups.append({"college": row["_id"] or "未填写", "readers": readers, "borrows": row["borrows"],
                           "avg_borrows": round(row["borrows"] / readers, 2) if readers else 0})
        return sorted(groups, key=lambda r: (-r["borrows"], r["college"]))

    def get_reader_ranking(self, limit: int = 5) -> list[dict[str, Any]]:
        rows = list(self.db.borrow_records.aggregate([
            {"$group": {"_id": "$reader_card", "borrow_count": {"$sum": 1}}},
            {"$sort": {"borrow_count": -1, "_id": 1}},
            {"$limit": limit},
            {"$lookup": {"from": "readers", "localField": "_id", "foreignField": "card_no", "as": "reader"}},
            {"$project": {"card_no": "$_id", "borrow_count": 1,
                          "name": {"$first": "$reader.name"}, "college": {"$first": "$reader.college"}}},
        ]))
        return [{"card_no": r["card_no"], "name": (r.get("name") or "-")[0] + "*" * min(max(len(r.get("name") or "") - 1, 1), 2) if r.get("name") else "-",
                 "college": r.get("college") or "-", "borrow_count": r["borrow_count"]} for r in rows]

    def get_top_categories(self, limit: int = 5) -> list[dict[str, Any]]:
        rows = list(self.db.borrow_logs.aggregate([
            {"$lookup": {"from": "books", "localField": "book_isbn", "foreignField": "isbn", "as": "book"}},
            {"$unwind": "$book"},
            {"$group": {"_id": "$book.category", "borrows": {"$sum": 1}}},
            {"$sort": {"borrows": -1}},
            {"$limit": limit},
        ]))
        return [{"category": r["_id"] or "未分类", "borrows": r["borrows"]} for r in rows]

    def get_simulated_values(self, limit: int = 10) -> list[dict[str, Any]]:
        rows = list(self.db.books.aggregate([
            {"$project": {"isbn": 1, "title": 1, "category": 1,
                          "value": {"$round": [{"$multiply": ["$price", "$borrow_count"]}, 2]}}},
            {"$sort": {"value": -1}},
            {"$limit": limit},
        ]))
        return [{"isbn": r.get("isbn"), "title": r.get("title"), "category": r.get("category"), "value": r.get("value", 0)} for r in rows]

    def get_system_info(self) -> dict[str, Any]:
        collections = []
        for info in self.db.list_collections():
            name = info["name"]
            if name.startswith("system."):
                continue
            try:
                count = self.db[name].count_documents({})
            except Exception:
                count = "-"
            collections.append({"name": name, "type": info.get("type", "collection"),
                                "count": count, "options": info.get("options", {})})
        try:
            indexes = [{"name": k, "key": v.get("key"), "unique": bool(v.get("unique")),
                        "sparse": bool(v.get("sparse"))} for k, v in self.db.books.index_information().items()]
        except Exception:
            indexes = []
        try:
            version = self.client.server_info().get("version", "-")
        except Exception:
            version = "-"
        ttl = None
        try:
            info = self.db.list_collections(filter={"name": "borrow_logs"})
            options = list(info)[0].get("options", {}) if info else {}
            ttl = options.get("expireAfterSeconds")
        except Exception:
            ttl = None
        return {"mode": "MongoDB Mode", "db_name": self.db_name, "collections": collections,
                "indexes": indexes, "ttl": ttl, "mongo_version": version}

    def add_book(self, payload: dict[str, Any]) -> dict[str, Any]:
        self._require_write()
        data = validate_book_payload(payload)
        if self.db.books.find_one({"isbn": data["isbn"]}):
            raise ValidationError("ISBN 已存在。")
        try:
            result = self.db.books.insert_one(data)
        except DuplicateKeyError:
            raise ValidationError("ISBN 已存在。") from None
        doc = self.db.books.find_one({"_id": result.inserted_id})
        return normalize_book(doc)

    def update_book(self, isbn: str, payload: dict[str, Any]) -> dict[str, Any]:
        self._require_write()
        book = self.db.books.find_one({"isbn": isbn})
        if not book:
            raise ValidationError("图书不存在。")
        merged = {**normalize_book(book), **payload, "isbn": isbn}
        data = validate_book_payload(merged)
        self.db.books.update_one({"isbn": isbn}, {"$set": data})
        return normalize_book(self.db.books.find_one({"isbn": isbn}))

    def delete_book(self, isbn: str) -> None:
        self._require_write()
        if self.db.borrow_records.count_documents({"book_isbn": isbn, "status": {"$in": ["借出", "逾期"]}, "return_date": None}):
            raise ValidationError("该图书存在未完成借阅，不能删除。")
        result = self.db.books.delete_one({"isbn": isbn})
        if result.deleted_count != 1:
            raise ValidationError("图书不存在。")

    def add_reader(self, payload: dict[str, Any]) -> dict[str, Any]:
        self._require_write()
        data = validate_reader_payload(payload)
        if self.db.readers.find_one({"card_no": data["card_no"]}):
            raise ValidationError("借阅证号已存在。")
        result = self.db.readers.insert_one(data)
        return normalize_reader(self.db.readers.find_one({"_id": result.inserted_id}))

    def update_reader(self, card_no: str, payload: dict[str, Any]) -> dict[str, Any]:
        self._require_write()
        reader = self.db.readers.find_one({"card_no": card_no})
        if not reader:
            raise ValidationError("读者不存在。")
        data = validate_reader_payload({**normalize_reader(reader), **payload, "card_no": card_no})
        self.db.readers.update_one({"card_no": card_no}, {"$set": data})
        return normalize_reader(self.db.readers.find_one({"card_no": card_no}))

    def delete_reader(self, card_no: str) -> None:
        self._require_write()
        if self.db.borrow_records.count_documents({"reader_card": card_no, "status": {"$in": ["借出", "逾期"]}, "return_date": None}):
            raise ValidationError("该读者尚有未归还图书，不能删除。")
        result = self.db.readers.delete_one({"card_no": card_no})
        if result.deleted_count != 1:
            raise ValidationError("读者不存在。")

    def borrow_book(self, card_no: str, isbn: str, due_date: datetime) -> dict[str, Any]:
        self._require_write()
        result = borrow_manager.borrow_book(self.db, card_no, isbn, due_date=due_date)
        if not result.get("ok"):
            raise ValidationError(result.get("message", "借阅失败。"))
        return result

    def return_book(self, record_id: str) -> dict[str, Any]:
        self._require_write()
        oid = ObjectId(record_id) if ObjectId.is_valid(record_id) else None
        record = self.db.borrow_records.find_one({"_id": oid}) if oid else None
        if not record:
            raise ValidationError("借阅记录不存在。")
        result = borrow_manager.return_book(self.db, record.get("reader_card", ""), record.get("book_isbn", ""))
        if not result.get("ok"):
            raise ValidationError(result.get("message", "归还失败。"))
        return result

    def get_borrow_summary(self) -> dict[str, int]:
        now = datetime.now(timezone.utc)
        return {
            "current_overdue": self.db.borrow_records.count_documents({"status": {"$in": ["借出", "逾期"]}, "return_date": None, "due_date": {"$lt": now}}),
            "historical_overdue": self.db.borrow_records.count_documents({"status": "逾期", "return_date": {"$ne": None}}),
            "unknown_due": self.db.borrow_records.count_documents({"status": {"$in": ["借出", "逾期"]}, "return_date": None, "due_date": {"$exists": False}}),
        }
