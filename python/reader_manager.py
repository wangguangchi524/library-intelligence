from datetime import datetime, timezone

from mongodb_connect import fmt_dt

LEVELS = {"普通", "高级", "教师"}


def _print_readers(docs):
    if not docs:
        print("未找到读者。")
        return
    print(f"\n{'借阅证号':<12} {'姓名':<8} {'学院':<16} {'等级':<6} {'邮箱':<28} {'注册时间':<17}")
    print("-" * 95)
    for r in docs:
        print(f"{str(r.get('card_no', '')):<12} {str(r.get('name', '')):<8} {str(r.get('college', '')):<16} "
              f"{str(r.get('level', '')):<6} {str(r.get('email') or '-'):<28} {fmt_dt(r.get('register_date')):<17}")


def list_readers(db, keyword=None):
    query = {}
    if keyword:
        query = {"$or": [
            {"card_no": {"$regex": keyword, "$options": "i"}},
            {"name": {"$regex": keyword, "$options": "i"}},
            {"college": {"$regex": keyword, "$options": "i"}},
            {"email": {"$regex": keyword, "$options": "i"}},
        ]}
    return list(db.readers.find(query, {"_id": 0}).sort("card_no", 1))


def add_reader(db, doc):
    return db.readers.insert_one(doc)


def college_stats(db):
    pipeline = [
        {"$group": {"_id": "$college", "readerCount": {"$sum": 1}}},
        {"$sort": {"readerCount": -1, "_id": 1}},
        {"$project": {"_id": 0, "college": "$_id", "readerCount": 1}},
    ]
    return list(db.readers.aggregate(pipeline))


def level_distribution(db):
    pipeline = [
        {"$group": {"_id": "$level", "count": {"$sum": 1}}},
        {"$sort": {"count": -1, "_id": 1}},
        {"$project": {"_id": 0, "level": "$_id", "count": 1}},
    ]
    return list(db.readers.aggregate(pipeline))


def _input_reader(db):
    print("\n--- 新增读者 ---")
    card_no = input("借阅证号: ").strip()
    name = input("姓名: ").strip()
    if not card_no or not name:
        print("借阅证号和姓名不能为空，已取消。")
        return
    if db.readers.find_one({"card_no": card_no}):
        print("新增失败：借阅证号已存在。")
        return
    level = input("借阅等级（普通/高级/教师）: ").strip() or "普通"
    if level not in LEVELS:
        print("借阅等级不合法，只能是 普通/高级/教师。")
        return
    doc = {
        "card_no": card_no,
        "name": name,
        "college": input("学院: ").strip(),
        "email": input("邮箱（回车为空）: ").strip() or None,
        "phone": input("电话: ").strip(),
        "level": level,
        "register_date": datetime.now(timezone.utc),
        "fav_categories": [t.strip() for t in input("偏好类别（逗号分隔）: ").split(",") if t.strip()],
    }
    result = add_reader(db, doc)
    print(f"新增读者成功，inserted_id={result.inserted_id}")


def reader_menu(db):
    while True:
        print("\n--- 读者管理 ---")
        print("1 读者列表/检索")
        print("2 新增读者")
        print("3 学院统计")
        print("4 借阅等级分布")
        print("0 返回")
        choice = input("请选择: ").strip()
        if choice == "0":
            return
        if choice == "1":
            keyword = input("关键词（证号/姓名/学院/邮箱，回车全部）: ").strip() or None
            docs = list_readers(db, keyword)
            if not docs:
                print("未找到读者。")
            else:
                print(f"共 {len(docs)} 位读者")
                _print_readers(docs)
        elif choice == "2":
            _input_reader(db)
        elif choice == "3":
            rows = college_stats(db)
            if not rows:
                print("暂无读者数据。")
                continue
            print("\n学院  人数")
            for r in rows:
                print(f"{r['college']:<16} {r['readerCount']}")
        elif choice == "4":
            rows = level_distribution(db)
            if not rows:
                print("暂无读者数据。")
                continue
            print("\n等级  人数")
            for r in rows:
                print(f"{r['level']:<8} {r['count']}")
        else:
            print("无效选项。")
