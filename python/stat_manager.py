def category_stats(db):
    pipeline = [
        {"$group": {
            "_id": "$category",
            "bookCount": {"$sum": 1},
            "avgPrice": {"$avg": "$price"},
            "totalStock": {"$sum": "$stock"},
            "avgRating": {"$avg": "$rating"},
        }},
        {"$sort": {"totalStock": -1, "bookCount": -1, "_id": 1}},
        {"$project": {
            "_id": 0,
            "category": "$_id",
            "bookCount": 1,
            "avgPrice": {"$round": ["$avgPrice", 2]},
            "totalStock": 1,
            "avgRating": {"$round": ["$avgRating", 2]},
        }},
    ]
    return list(db.books.aggregate(pipeline))


def borrow_trend(db):
    pipeline = [
        {"$group": {
            "_id": {"$year": {"date": "$borrow_date", "timezone": "+08:00"}},
            "borrowCount": {"$sum": 1},
        }},
        {"$sort": {"_id": 1}},
        {"$project": {
            "_id": 0,
            "year": {"$concat": [{"$toString": "$_id"}, "年"]},
            "borrowCount": 1,
        }},
    ]
    return list(db.borrow_logs.aggregate(pipeline))


def bestsellers(db, limit=5):
    return list(db.books.find({}, {"_id": 0, "title": 1, "category": 1, "borrow_count": 1, "rating": 1, "isbn": 1})
                .sort([("borrow_count", -1), ("isbn", 1)]).limit(limit))


def college_ranking(db):
    pipeline = [
        {"$lookup": {"from": "readers", "localField": "reader_card", "foreignField": "card_no", "as": "reader"}},
        {"$unwind": "$reader"},
        {"$group": {"_id": "$reader.college", "borrowCount": {"$sum": 1}}},
        {"$sort": {"borrowCount": -1, "_id": 1}},
        {"$project": {"_id": 0, "college": "$_id", "borrowCount": 1}},
    ]
    return list(db.borrow_logs.aggregate(pipeline))


def print_category(rows):
    if not rows:
        print("暂无图书数据。")
        return
    print(f"\n{'类别':<8} {'图书数':>5} {'平均价格':>9} {'库存总量':>7} {'平均评分':>7}")
    print("-" * 46)
    for r in rows:
        print(f"{r['category']:<8} {r['bookCount']:>5} {r['avgPrice']:>9.2f} {r['totalStock']:>7} {r['avgRating']:>7.2f}")


def print_trend(rows):
    if not rows:
        print("暂无借阅流水。")
        return
    print("\n年份    借阅量")
    for r in rows:
        print(f"{r['year']:<8}{r['borrowCount']}")


_print_category = print_category
_print_trend = print_trend


def stat_menu(db):
    while True:
        print("\n--- 统计分析 ---")
        print("1 分类统计（库存总量/平均价格/图书数）")
        print("2 借阅趋势（按年份）")
        print("3 畅销榜 Top 5")
        print("4 学院借阅排行榜")
        print("0 返回")
        choice = input("请选择: ").strip()
        if choice == "0":
            return
        if choice == "1":
            print_category(category_stats(db))
        elif choice == "2":
            print_trend(borrow_trend(db))
        elif choice == "3":
            rows = bestsellers(db, 5)
            if not rows:
                print("暂无图书数据。")
                continue
            for i, r in enumerate(rows, 1):
                print(f"{i}. {r['title']}  借阅次数={r['borrow_count']}  类别={r['category']}  评分={r['rating']}")
        elif choice == "4":
            rows = college_ranking(db)
            if not rows:
                print("暂无借阅数据。")
                continue
            print("\n学院              借阅量")
            for r in rows:
                print(f"{r['college']:<18}{r['borrowCount']}")
        else:
            print("无效选项。")
