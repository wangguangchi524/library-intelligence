from datetime import datetime, timezone

from pymongo.errors import DuplicateKeyError


def _print_books(docs):
    if not docs:
        print("未找到符合条件的图书。")
        return
    print(f"\n{'ISBN':<15} {'书名':<32} {'作者':<16} {'类别':<7} {'价格':>7} {'库存':>4} {'评分':>4}")
    print("-" * 100)
    for b in docs:
        price = b.get("price") if b.get("price") is not None else 0
        stock = b.get("stock") if b.get("stock") is not None else 0
        rating = b.get("rating") if b.get("rating") is not None else 0
        print(f"{str(b.get('isbn', '')):<15} {str(b.get('title', ''))[:30]:<32} {str(b.get('author', ''))[:14]:<16} "
              f"{str(b.get('category', '')):<7} {price:>7.2f} {stock:>4} {rating:>4.1f}")


def search_books(db, keyword=None, category=None, price_min=None, price_max=None,
                 rating_min=None, tags=None, sort_by="rating", descending=True,
                 page=1, page_size=10):
    conditions = []
    if keyword:
        conditions.append({"$or": [
            {"title": {"$regex": keyword, "$options": "i"}},
            {"author": {"$regex": keyword, "$options": "i"}},
            {"isbn": {"$regex": keyword, "$options": "i"}},
        ]})
    if category:
        conditions.append({"category": category})
    if price_min is not None or price_max is not None:
        price_filter = {}
        if price_min is not None:
            price_filter["$gte"] = price_min
        if price_max is not None:
            price_filter["$lte"] = price_max
        conditions.append({"price": price_filter})
    if rating_min is not None:
        conditions.append({"rating": {"$gte": rating_min}})
    if tags:
        conditions.append({"tags": {"$all": tags}})

    query = {"$and": conditions} if conditions else {}
    total = db.books.count_documents(query)
    page = max(int(page), 1)
    page_size = min(max(int(page_size), 1), 50)
    projection = {"_id": 0, "isbn": 1, "title": 1, "author": 1, "category": 1,
                  "price": 1, "stock": 1, "rating": 1}
    order = -1 if descending else 1
    cursor = (db.books.find(query, projection)
              .sort([(sort_by, order), ("isbn", 1)])
              .skip((page - 1) * page_size)
              .limit(page_size))
    return total, list(cursor)


def top_rated(db, limit=5):
    return list(db.books.find({}, {"_id": 0, "title": 1, "rating": 1, "borrow_count": 1, "category": 1, "isbn": 1})
                .sort([("rating", -1), ("isbn", 1)]).limit(limit))


def add_book(db, doc):
    return db.books.insert_one(doc)


def update_book(db, isbn, changes):
    return db.books.update_one({"isbn": isbn}, {"$set": changes})


def delete_book(db, isbn):
    return db.books.delete_one({"isbn": isbn})


def _input_float(prompt, default=None, minimum=None, maximum=None):
    text = input(prompt).strip()
    if not text:
        return default
    try:
        value = float(text)
    except ValueError:
        print("输入不是数字。")
        return None
    if minimum is not None and value < minimum:
        print(f"数值不能小于 {minimum}。")
        return None
    if maximum is not None and value > maximum:
        print(f"数值不能大于 {maximum}。")
        return None
    return value


def _input_int(prompt, default=None, minimum=None, maximum=None):
    text = input(prompt).strip()
    if not text:
        return default
    try:
        value = int(text)
    except ValueError:
        print("输入不是整数。")
        return None
    if minimum is not None and value < minimum:
        print(f"数值不能小于 {minimum}。")
        return None
    if maximum is not None and value > maximum:
        print(f"数值不能大于 {maximum}。")
        return None
    return value


def interactive_search(db):
    print("\n--- 图书检索（直接回车跳过条件）---")
    keyword = input("书名/作者/ISBN 关键词: ").strip() or None
    category = input("类别（计算机/经济管理/数学/外语/文学）: ").strip() or None
    price_min = _input_float("最低价格: ", minimum=0)
    price_max = _input_float("最高价格: ", minimum=0)
    rating_min = _input_float("最低评分(0-5): ", minimum=0, maximum=5)
    tag_text = input("标签（多个用逗号分隔）: ").strip()
    tags = [t.strip() for t in tag_text.split(",") if t.strip()] if tag_text else None
    sort_choice = input("排序：1 评分 2 价格 3 库存 4 出版日期 (默认1): ").strip()
    sort_map = {"1": "rating", "2": "price", "3": "stock", "4": "publish_date"}
    sort_by = sort_map.get(sort_choice, "rating")
    order = input("顺序：1 降序 2 升序 (默认1): ").strip()
    descending = order != "2"
    page_text = input("页码 (默认1): ").strip()
    page = int(page_text) if page_text.isdigit() and int(page_text) > 0 else 1

    total, docs = search_books(db, keyword, category, price_min, price_max, rating_min,
                               tags, sort_by, descending, page, 10)
    if total == 0:
        print("未找到符合条件的图书。")
        return
    print(f"\n共 {total} 条结果，第 {page} 页，每页 10 条")
    _print_books(docs)


def interactive_add(db):
    print("\n--- 新增图书 ---")
    isbn = input("ISBN: ").strip()
    title = input("书名: ").strip()
    if not isbn or not title:
        print("ISBN 和书名不能为空，已取消。")
        return
    if db.books.find_one({"isbn": isbn}):
        print("新增失败：ISBN 已存在。")
        return
    price = _input_float("价格: ", default=0.0, minimum=0)
    stock = _input_int("库存: ", default=0, minimum=0)
    rating = _input_float("评分(0-5): ", default=0.0, minimum=0, maximum=5)
    if price is None or stock is None or rating is None:
        print("价格、库存或评分输入无效，已取消。")
        return
    date_text = input("出版日期(YYYY-MM-DD，回车为今天): ").strip()
    if date_text:
        try:
            publish_date = datetime.strptime(date_text, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            print("出版日期格式错误，应为 YYYY-MM-DD。")
            return
    else:
        publish_date = datetime.now(timezone.utc)
    doc = {
        "isbn": isbn,
        "title": title,
        "author": input("作者: ").strip(),
        "publisher": input("出版社: ").strip(),
        "category": input("类别: ").strip(),
        "price": price,
        "stock": stock,
        "rating": rating,
        "tags": [t.strip() for t in input("标签（逗号分隔）: ").split(",") if t.strip()],
        "publish_date": publish_date,
        "borrow_count": 0,
    }
    try:
        result = add_book(db, doc)
        print(f"新增成功，inserted_id={result.inserted_id}")
    except DuplicateKeyError:
        print("新增失败：ISBN 已存在。")


def interactive_update(db):
    print("\n--- 修改图书 ---")
    isbn = input("要修改的 ISBN: ").strip()
    book = db.books.find_one({"isbn": isbn}, {"_id": 0, "title": 1, "price": 1, "stock": 1, "rating": 1})
    if not book:
        print("未找到该 ISBN 的图书。")
        return
    print(f"当前：{book['title']}  价格={book['price']}  库存={book['stock']}  评分={book['rating']}")
    changes = {}
    price = _input_float("新价格（回车跳过）: ", minimum=0)
    if price is not None:
        changes["price"] = price
    stock = _input_int("新库存（回车跳过）: ", minimum=0)
    if stock is not None:
        changes["stock"] = stock
    rating = _input_float("新评分（回车跳过）: ", minimum=0, maximum=5)
    if rating is not None:
        changes["rating"] = rating
    if not changes:
        print("没有需要修改的字段。")
        return
    result = update_book(db, isbn, changes)
    print(f"匹配 {result.matched_count} 条，修改 {result.modified_count} 条。")


def interactive_delete(db):
    print("\n--- 删除图书 ---")
    isbn = input("要删除的 ISBN: ").strip()
    book = db.books.find_one({"isbn": isbn}, {"_id": 0, "title": 1})
    if not book:
        print("未找到该 ISBN 的图书。")
        return
    confirm = input(f"确认删除《{book['title']}》？输入 yes 确认: ").strip().lower()
    if confirm != "yes":
        print("已取消。")
        return
    result = delete_book(db, isbn)
    print(f"删除 {result.deleted_count} 条。")


def interactive_top_rated(db):
    print("\n--- 评分排行 Top 5 ---")
    docs = top_rated(db, 5)
    if not docs:
        print("暂无图书数据。")
        return
    for i, b in enumerate(docs, 1):
        print(f"{i}. {b['title']}  评分={b['rating']}  借阅次数={b['borrow_count']}  类别={b['category']}")
