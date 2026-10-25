import sys

from pymongo.errors import PyMongoError

import book_manager
import borrow_manager
import reader_manager
import stat_manager
from mongodb_connect import close, connect, get_db, print_connection

MENU = """
┌──────────────────────────────────────────────┐
│        图书情报检索与统计平台                │
├──────────────────────────────────────────────┤
│  1. 图书检索          2. 新增图书            │
│  3. 修改图书          4. 删除图书            │
│  5. 评分排行          6. 读者管理与统计      │
│  7. 借阅管理          8. 分类统计            │
│  9. 借阅趋势         10. 畅销榜              │
│ 11. 学院借阅排行      0. 退出                │
└──────────────────────────────────────────────┘
"""


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    client = None
    try:
        print("正在连接 MongoDB ...")
        client = connect()
        db = get_db(client)
        print_connection(db)

        while True:
            print(MENU)
            choice = input("请选择功能: ").strip()
            if choice == "0":
                print("退出程序。")
                break
            if choice == "1":
                book_manager.interactive_search(db)
            elif choice == "2":
                book_manager.interactive_add(db)
            elif choice == "3":
                book_manager.interactive_update(db)
            elif choice == "4":
                book_manager.interactive_delete(db)
            elif choice == "5":
                book_manager.interactive_top_rated(db)
            elif choice == "6":
                reader_manager.reader_menu(db)
            elif choice == "7":
                borrow_manager.borrow_menu(db)
            elif choice == "8":
                stat_manager.print_category(stat_manager.category_stats(db))
            elif choice == "9":
                stat_manager.print_trend(stat_manager.borrow_trend(db))
            elif choice == "10":
                rows = stat_manager.bestsellers(db, 5)
                if not rows:
                    print("暂无图书数据。")
                for i, r in enumerate(rows, 1):
                    print(f"{i}. {r['title']}  借阅次数={r['borrow_count']}  类别={r['category']}  评分={r['rating']}")
            elif choice == "11":
                rows = stat_manager.college_ranking(db)
                if not rows:
                    print("暂无借阅数据。")
                for r in rows:
                    print(f"{r['college']:<18}{r['borrowCount']}")
            else:
                print("无效选项，请重新选择。")
    except (PyMongoError, RuntimeError) as exc:
        print(f"数据库错误: {exc}")
        return 1
    except KeyboardInterrupt:
        print("\n已取消。")
    finally:
        if client is not None:
            close(client)
            print("数据库连接已关闭。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
