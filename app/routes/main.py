from flask import Blueprint, render_template, request, redirect, url_for, session
from app.db import get_connection, get_db_cursor

main_bp = Blueprint('main', __name__)

@main_bp.route("/")
def home():
    # Điều hướng tự động
    if "userID" in session:
        return redirect(url_for("main.index"))
    return redirect(url_for("auth.login"))


@main_bp.route("/index")
def index():
    if "userID" not in session:
        return redirect(url_for("auth.login"))

    user_id = session["userID"]
    conn = get_connection()
    cursor = get_db_cursor(conn)

    try:
        # Lấy thông tin chi tiết người dùng
        cursor.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
        user = cursor.fetchone()

        # Lấy danh sách các nhóm người dùng đã tham gia
        cursor.execute(
            """
            SELECT g.group_id, g.group_name, g.description, gm.role
            FROM groups g
            JOIN group_members gm ON g.group_id = gm.group_id
            WHERE gm.user_id = %s
            ORDER BY g.group_name
            """,
            (user_id,)
        )
        groups = cursor.fetchall()

        groups_with_tasks = []

        # Với mỗi nhóm, lấy danh sách task và kiểm tra xem task đó có được giao cho user này không
        for group in groups:
            cursor.execute(
                """
                SELECT t.*,
                       (SELECT COUNT(*) FROM task_assignments ta 
                        WHERE ta.task_id = t.task_id AND ta.user_id = %s) > 0 as is_assigned_to_me
                FROM tasks t
                WHERE t.group_id = %s
                ORDER BY t.deadline
                """,
                (user_id, group["group_id"])
            )
            tasks = cursor.fetchall()

            group_data = {
                "group_id": group["group_id"],
                "group_name": group["group_name"],
                "description": group["description"],
                "is_admin": (group["role"] == "admin"),
                "tasks": tasks
            }
            groups_with_tasks.append(group_data)


    except Exception as e:
        # Nếu có lỗi, trả về danh sách rỗng để tránh crash trang chủ
        user = None
        groups_with_tasks = []
    finally:
        cursor.close()
        conn.close()

    return render_template(
        "index.html",
        user=user,
        groups_with_tasks=groups_with_tasks
    )


@main_bp.route("/search")
def search():
    if "userID" not in session:
        return redirect(url_for("auth.login"))

    keyword = request.args.get("keyword", "").strip()
    if not keyword:
        return redirect(url_for("main.index"))

    user_id = session["userID"]
    conn = get_connection()
    cursor = get_db_cursor(conn)

    # Đưa từ khóa về dạng tìm kiếm tương đối trong SQL (%từ_khóa%)
    search_keyword = f"%{keyword}%"

    try:
        # Tìm kiếm nhóm theo tên hoặc mã mời (sử dụng ILIKE để tìm kiếm không phân biệt hoa thường trong Postgres)
        cursor.execute(
            """
            SELECT * FROM groups 
            WHERE group_name ILIKE %s OR join_code ILIKE %s
            ORDER BY group_name
            """,
            (search_keyword, search_keyword)
        )
        groups = cursor.fetchall()

        # Tìm kiếm các task khớp từ khóa, nhưng bảo mật: chỉ tìm trong các nhóm mà người dùng đang tham gia
        cursor.execute(
            """
            SELECT t.*, g.group_name
            FROM tasks t
            JOIN groups g ON t.group_id = g.group_id
            JOIN group_members gm ON g.group_id = gm.group_id
            WHERE gm.user_id = %s 
              AND (t.title ILIKE %s OR t.description ILIKE %s)
            ORDER BY t.deadline
            """,
            (user_id, search_keyword, search_keyword)
        )
        tasks = cursor.fetchall()

    except Exception as e:
        groups = []
        tasks = []
    finally:
        cursor.close()
        conn.close()

    return render_template(
        "search.html",
        keyword=keyword,
        groups=groups,
        tasks=tasks
    )


# Xử lý lỗi 404 (Truy cập đường dẫn linh tinh không tồn tại) -> Tự động chuyển về Home
@main_bp.app_errorhandler(404)
def page_not_found(e):
    return redirect(url_for("main.home"))


# Xử lý lỗi 500 (Lỗi hệ thống/máy chủ) -> Tự động chuyển về Home
@main_bp.app_errorhandler(500)
def internal_server_error(e):
    return redirect(url_for("main.home"))
