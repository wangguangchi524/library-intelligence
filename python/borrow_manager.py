from datetime import datetime, timedelta, timezone

from mongodb_connect import fmt_dt

DEFAULT_LOAN_DAYS = 30
ACTIVE_STATUSES = ["借出", "逾期"]


def _now():
    return datetime.now(timezone.utc)


def _as_aware(value):
    if value and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _compensate_stock(db, isbn):
    result = db.books.update_one({"isbn": isbn}, {"$inc": {"stock": 1, "borrow_count": -1}})
    return result.modified_count == 1


def borrow_book(db, card_no, isbn, due_date=None, loan_days=DEFAULT_LOAN_DAYS):
    reader = db.readers.find_one({"card_no": card_no}, {"_id": 0, "name": 1, "college": 1})
    if not reader:
        return {"ok": False, "message": f"未找到借阅证号 {card_no} 的读者。"}
    book = db.books.find_one({"isbn": isbn}, {"_id": 0, "title": 1, "stock": 1})
    if not book:
        return {"ok": False, "message": f"未找到 ISBN {isbn} 的图书。"}

    active = db.borrow_records.find_one({
        "reader_card": card_no,
        "book_isbn": isbn,
        "status": {"$in": ACTIVE_STATUSES},
        "return_date": None,
    })
    if active:
        return {"ok": False, "message": "该读者已有一本相同的在借图书，请先归还。"}

    now = _now()
    due_date = _as_aware(due_date) or (now + timedelta(days=loan_days))
    if due_date <= now:
        return {"ok": False, "message": "应还日期必须晚于借阅时间。"}
    stock_result = db.books.update_one(
        {"isbn": isbn, "stock": {"$gt": 0}},
        {"$inc": {"stock": -1, "borrow_count": 1}},
    )
    if stock_result.modified_count != 1:
        return {"ok": False, "message": f"《{book['title']}》库存不足或并发借阅失败，借阅未完成。"}

    record = {
        "borrow_date": now,
        "due_date": due_date,
        "return_date": None,
        "reader_card": card_no,
        "book_isbn": isbn,
        "status": "借出",
        "loan_days": loan_days,
    }

    try:
        record_id = db.borrow_records.insert_one(dict(record)).inserted_id
    except Exception as exc:
        stock_ok = _compensate_stock(db, isbn)
        return {
            "ok": False,
            "message": f"借阅记录写入失败，库存已尝试回滚：{exc}",
            "needs_repair": not stock_ok,
            "repair_hint": None if stock_ok else "请人工核对 books.stock 与 borrow_records。",
        }

    try:
        log_id = db.borrow_logs.insert_one(dict(record)).inserted_id
    except Exception as exc:
        record_deleted = db.borrow_records.delete_one({"_id": record_id}).deleted_count == 1
        stock_ok = _compensate_stock(db, isbn)
        return {
            "ok": False,
            "message": f"借阅事件写入失败，已尝试回滚业务记录与库存：{exc}",
            "needs_repair": not (record_deleted and stock_ok),
            "repair_hint": None if (record_deleted and stock_ok) else "请人工核对 borrow_records 与 books.stock。",
        }

    latest = db.books.find_one({"isbn": isbn}, {"_id": 0, "stock": 1})
    return {
        "ok": True,
        "message": f"借阅成功：{reader['name']} 借出《{book['title']}》。应还日期 {fmt_dt(due_date)}。",
        "log_id": log_id,
        "record_id": record_id,
        "book_modified": stock_result.modified_count,
        "stock_left": latest["stock"] if latest else None,
        "due_date": due_date,
    }


def return_book(db, card_no, isbn):
    record = db.borrow_records.find_one(
        {
            "reader_card": card_no,
            "book_isbn": isbn,
            "status": {"$in": ACTIVE_STATUSES},
            "return_date": None,
        },
        sort=[("borrow_date", -1)],
    )
    if not record:
        return {"ok": False, "message": "未找到该读者对应的未归还记录，可能已归还或从未借阅。"}

    now = _now()
    due_date = _as_aware(record.get("due_date"))
    returned_late = bool(due_date and now > due_date)
    result = db.borrow_records.update_one(
        {"_id": record["_id"], "status": {"$in": ACTIVE_STATUSES}, "return_date": None},
        {"$set": {"status": "已归还", "return_date": now, "returned_late": returned_late}},
    )
    if result.modified_count != 1:
        return {"ok": False, "message": "归还状态转换失败，可能已被其他操作归还，库存未增加。"}

    book_result = db.books.update_one({"isbn": isbn}, {"$inc": {"stock": 1}})
    if book_result.modified_count != 1:
        db.borrow_records.update_one(
            {"_id": record["_id"], "status": "已归还", "return_date": now},
            {"$set": {"status": record.get("status", "借出")}, "$unset": {"return_date": "", "returned_late": ""}},
        )
        return {
            "ok": False,
            "message": "图书不存在，归还状态已回滚，库存未增加，请人工核对。",
            "needs_repair": True,
        }

    book = db.books.find_one({"isbn": isbn}, {"_id": 0, "title": 1, "stock": 1})
    return {
        "ok": True,
        "message": f"归还成功：《{book['title']}》，归还时间 {fmt_dt(now)}。",
        "matched": result.matched_count,
        "modified": result.modified_count,
        "book_modified": book_result.modified_count,
        "stock": book["stock"],
        "returned_late": returned_late,
        "note": "borrow_logs 是借阅事件流，不随归还修改；年度借阅量按借阅事件计数，不重复累计归还事件。",
    }


def overdue_records(db):
    now = _now()
    rows = []
    query = {
        "status": {"$in": ACTIVE_STATUSES},
        "return_date": None,
        "due_date": {"$lt": now},
    }
    for r in db.borrow_records.find(query, {"_id": 0}).sort("due_date", 1):
        due_date = _as_aware(r.get("due_date"))
        r["days"] = max((now - due_date).days, 0) if due_date else None
        reader = db.readers.find_one({"card_no": r.get("reader_card")}, {"_id": 0, "name": 1, "college": 1})
        book = db.books.find_one({"isbn": r.get("book_isbn")}, {"_id": 0, "title": 1})
        r["reader_name"] = reader.get("name") if reader else "-"
        r["college"] = reader.get("college") if reader else "-"
        r["book_title"] = book.get("title") if book else "-"
        rows.append(r)
    return rows


def historical_overdue_records(db):
    query = {"status": "逾期", "return_date": {"$ne": None}}
    return list(db.borrow_records.find(query, {"_id": 0}).sort("return_date", -1))


def unknown_due_date_count(db):
    return db.borrow_records.count_documents({
        "status": {"$in": ACTIVE_STATUSES},
        "return_date": None,
        "due_date": {"$exists": False},
    })


def overdue_summary(db):
    return {
        "current": db.borrow_records.count_documents({
            "status": {"$in": ACTIVE_STATUSES},
            "return_date": None,
            "due_date": {"$lt": _now()},
        }),
        "historical": db.borrow_records.count_documents({"status": "逾期", "return_date": {"$ne": None}}),
        "unknown_due_date": unknown_due_date_count(db),
    }


def borrow_history(db, card_no):
    return list(db.borrow_records.find({"reader_card": card_no}, {"_id": 0}).sort("borrow_date", -1))


def _print_overdue(rows, summary):
    if not rows:
        print("当前没有逾期未还记录。")
    else:
        print(f"\n{'借阅证号':<12} {'读者':<8} {'图书':<30} {'应还日期':<17} {'逾期天数':>6}")
        print("-" * 84)
        for r in rows:
            print(f"{r.get('reader_card', ''):<12} {r.get('reader_name', ''):<8} {r.get('book_title', '')[:28]:<30} "
                  f"{fmt_dt(r.get('due_date')):<17} {r.get('days', 0):>6}")
    print(f"\n统计：当前逾期未还 {summary['current']} 条；历史逾期且已归还 {summary['historical']} 条；"
          f"缺少应还日期的在借记录 {summary['unknown_due_date']} 条（无法判定是否逾期）。")


def borrow_menu(db):
    while True:
        print("\n--- 借阅管理 ---")
        print("1 借阅登记")
        print("2 归还处理")
        print("3 逾期查询（当前逾期 / 历史逾期分开）")
        print("4 读者借阅历史")
        print("0 返回")
        choice = input("请选择: ").strip()
        if choice == "0":
            return
        if choice == "1":
            card_no = input("借阅证号: ").strip()
            isbn = input("ISBN: ").strip()
            result = borrow_book(db, card_no, isbn)
            print(result["message"])
            if result["ok"]:
                print(f"事件日志 _id={result['log_id']}  业务记录 _id={result['record_id']}  库存剩余={result['stock_left']}")
            elif result.get("needs_repair"):
                print(result.get("repair_hint"))
        elif choice == "2":
            card_no = input("借阅证号: ").strip()
            isbn = input("ISBN: ").strip()
            result = return_book(db, card_no, isbn)
            print(result["message"])
            if result["ok"]:
                print(f"匹配 {result['matched']} 条，修改 {result['modified']} 条，图书库存 {result['stock']}")
                print(result["note"])
        elif choice == "3":
            _print_overdue(overdue_records(db), overdue_summary(db))
        elif choice == "4":
            card_no = input("借阅证号: ").strip()
            rows = borrow_history(db, card_no)
            if not rows:
                print("未找到该读者的借阅记录。")
                continue
            for r in rows:
                print(f"{fmt_dt(r.get('borrow_date'))}  {r.get('book_isbn')}  {r.get('status')}  "
                      f"应还={fmt_dt(r.get('due_date'))}  归还={fmt_dt(r.get('return_date'))}")
        else:
            print("无效选项。")
