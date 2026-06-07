from flask import Blueprint, render_template, request, redirect, url_for, session
from datetime import date
from app.db import get_connection, get_db_cursor

tasks_bp = Blueprint('tasks', __name__)

@tasks_bp.route("/create_task/<int:group_id>", methods=["GET", "POST"])
def create_task(group_id):
    if "userID" not in session:
        return redirect(url_for("auth.login"))

    user_id = session["userID"]
    conn = get_connection()
    cursor = get_db_cursor(conn)

    # Kiểm tra nhóm có tồn tại hay không
    cursor.execute("SELECT * FROM groups WHERE group_id = %s", (group_id,))
    group = cursor.fetchone()
    if not group:
        cursor.close()
        conn.close()
        return "Nhóm không tồn tại!"

    # Kiểm tra người dùng có phải thành viên nhóm không
    cursor.execute(
        "SELECT role FROM group_members WHERE group_id = %s AND user_id = %s",
        (group_id, user_id)
    )
    membership = cursor.fetchone()
    if not membership:
        cursor.close()
        conn.close()
        return "Bạn không có quyền thực hiện hành động này!"

    # GET: Hiển thị Form tạo Task
    if request.method == "GET":
        # Lấy danh sách thành viên trong nhóm để chọn người giao việc
        cursor.execute(
            """
            SELECT u.user_id, u.username, u.full_name
            FROM group_members gm
            JOIN users u ON gm.user_id = u.user_id
            WHERE gm.group_id = %s
            """,
            (group_id,)
        )
        members = cursor.fetchall()
        cursor.close()
        conn.close()
        return render_template("create_task.html", group=group, members=members)

    # POST: Xử lý tạo Task
    title = request.form.get("title", "").strip()
    description = request.form.get("description", "").strip()
    priority = request.form.get("priority", "medium") # low, medium, high
    start_date = request.form.get("startDate", "")
    deadline = request.form.get("deadline", "")
    assigned_users = request.form.getlist("assignedUsers") # Danh sách ID người nhận task

    # Kiểm tra dữ liệu hợp lệ (Chỉ bắt buộc title và deadline)
    if not title or not deadline:
        cursor.close()
        conn.close()
        return "Tiêu đề và Hạn chót không được để trống!"

    # Nếu Ngày bắt đầu trống -> lấy ngày hiện tại
    if not start_date:
        start_date = date.today().strftime('%Y-%m-%d')

    if start_date > deadline:
        cursor.close()
        conn.close()
        return "Ngày bắt đầu phải trước hạn chót!"

    if not assigned_users:
        cursor.close()
        conn.close()
        return "Vui lòng chọn ít nhất một người nhận công việc!"

    # Xác định trạng thái ban đầu của task dựa trên vai trò
    # Admin giao task -> hoạt động ngay ('todo')
    # Member giao task -> ở trạng thái chờ duyệt ('proposed')
    initial_status = "todo" if membership["role"] == "admin" else "proposed"

    try:
        # Tạo Task mới và lấy ID trả về bằng RETURNING
        cursor.execute(
            """
            INSERT INTO tasks (group_id, created_by, title, description, priority, status, start_date, deadline)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING task_id
            """,
            (group_id, user_id, title, description, priority, initial_status, start_date, deadline)
        )
        task_id = cursor.fetchone()["task_id"]

        # Giao việc cho từng thành viên trong danh sách được chọn
        for val_id in assigned_users:
            cursor.execute(
                """
                INSERT INTO task_assignments (task_id, user_id)
                VALUES (%s, %s)
                """,
                (task_id, int(val_id))
            )
        conn.commit()
    except Exception as e:
        conn.rollback()
        return "Có lỗi xảy ra khi tạo công việc!"
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for("groups.inside_group", group_id=group_id))


@tasks_bp.route("/edit_task/<int:task_id>", methods=["GET", "POST"])
def edit_task(task_id):
    if "userID" not in session:
        return redirect(url_for("auth.login"))

    user_id = session["userID"]
    conn = get_connection()
    cursor = get_db_cursor(conn)

    # Kiểm tra task có tồn tại không
    cursor.execute("SELECT * FROM tasks WHERE task_id = %s", (task_id,))
    task = cursor.fetchone()
    if not task:
        cursor.close()
        conn.close()
        return "Công việc không tồn tại!"

    group_id = task["group_id"]

    # Kiểm tra quyền thành viên trong nhóm
    cursor.execute(
        "SELECT role FROM group_members WHERE group_id = %s AND user_id = %s",
        (group_id, user_id)
    )
    membership = cursor.fetchone()
    if not membership:
        cursor.close()
        conn.close()
        return "Bạn không có quyền truy cập công việc này!"

    # GET: Hiển thị giao diện sửa công việc & xem bình luận
    if request.method == "GET":
        # Lấy danh sách thành viên nhóm để chọn phân công lại
        cursor.execute(
            """
            SELECT u.user_id, u.username, u.full_name
            FROM group_members gm
            JOIN users u ON gm.user_id = u.user_id
            WHERE gm.group_id = %s
            """,
            (group_id,)
        )
        members = cursor.fetchall()

        # Lấy danh sách ID của những người đang được giao task này
        cursor.execute("SELECT user_id FROM task_assignments WHERE task_id = %s", (task_id,))
        assigned_users = [row["user_id"] for row in cursor.fetchall()]

        # Lấy danh sách bình luận (comment) của task này
        cursor.execute(
            """
            SELECT tc.*, u.username, u.full_name
            FROM task_comments tc
            JOIN users u ON tc.user_id = u.user_id
            WHERE tc.task_id = %s
            ORDER BY tc.created_at DESC
            """,
            (task_id,)
        )
        comments = cursor.fetchall()

        cursor.close()
        conn.close()
        return render_template(
            "edit_task.html",
            task=task,
            members=members,
            assigned_users=assigned_users,
            comments=comments,
            is_admin=(membership["role"] == "admin")
        )

    # POST: Xử lý lưu thông tin chỉnh sửa Task
    if membership["role"] != "admin":
        cursor.close()
        conn.close()
        return "Chỉ Quản trị viên nhóm mới có quyền chỉnh sửa công việc!"

    title = request.form.get("title", "").strip()
    description = request.form.get("description", "").strip()
    priority = request.form.get("priority", "medium")
    start_date = request.form.get("startDate", "")
    deadline = request.form.get("deadline", "")
    assigned_users = request.form.getlist("assignedUsers")

    # Kiểm tra dữ liệu hợp lệ (Chỉ bắt buộc title, deadline và phân công)
    if not title or not deadline or not assigned_users:
        cursor.close()
        conn.close()
        return "Vui lòng nhập Tiêu đề, Hạn chót và người nhận công việc!"

    # Nếu Ngày bắt đầu trống -> lấy ngày hiện tại
    if not start_date:
        start_date = date.today().strftime('%Y-%m-%d')

    if start_date > deadline:
        cursor.close()
        conn.close()
        return "Ngày bắt đầu phải trước hạn chót!"

    try:
        # Cập nhật thông tin task
        cursor.execute(
            """
            UPDATE tasks 
            SET title = %s, description = %s, priority = %s, start_date = %s, deadline = %s
            WHERE task_id = %s
            """,
            (title, description, priority, start_date, deadline, task_id)
        )
        # Xóa các phân công cũ của task này
        cursor.execute("DELETE FROM task_assignments WHERE task_id = %s", (task_id,))
        # Thêm các phân công mới
        for val_id in assigned_users:
            cursor.execute(
                """
                INSERT INTO task_assignments (task_id, user_id)
                VALUES (%s, %s)
                """,
                (task_id, int(val_id))
            )
        conn.commit()
    except Exception as e:
        conn.rollback()
        return "Có lỗi xảy ra khi cập nhật công việc!"
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for("groups.inside_group", group_id=group_id))


@tasks_bp.route("/delete_task/<int:task_id>")
def delete_task(task_id):
    if "userID" not in session:
        return redirect(url_for("auth.login"))

    user_id = session["userID"]
    conn = get_connection()
    cursor = get_db_cursor(conn)

    # Kiểm tra task có tồn tại không
    cursor.execute("SELECT * FROM tasks WHERE task_id = %s", (task_id,))
    task = cursor.fetchone()
    if not task:
        cursor.close()
        conn.close()
        return "Công việc không tồn tại!"

    group_id = task["group_id"]

    # Chỉ Admin nhóm mới có quyền xóa task
    cursor.execute(
        "SELECT role FROM group_members WHERE group_id = %s AND user_id = %s",
        (group_id, user_id)
    )
    membership = cursor.fetchone()

    if membership and membership["role"] == "admin":
        try:
            cursor.execute("DELETE FROM tasks WHERE task_id = %s", (task_id,))
            conn.commit()
        except Exception as e:
            conn.rollback()
            return "Có lỗi xảy ra khi xóa công việc!"
        finally:
            cursor.close()
            conn.close()
    else:
        cursor.close()
        conn.close()
        return "Bạn không có quyền xóa công việc này!"

    return redirect(url_for("groups.inside_group", group_id=group_id))


@tasks_bp.route("/change_status/<int:task_id>/<int:action_type>")
def change_status(task_id, action_type):
    """
    action_type:
      1: Tiến lên trạng thái tiếp theo (Next status / Accept review)
      2: Quay lại trạng thái trước đó (Reject review / ReWork)
    """
    if "userID" not in session:
        return redirect(url_for("auth.login"))

    user_id = session["userID"]
    conn = get_connection()
    cursor = get_db_cursor(conn)

    # Kiểm tra task tồn tại
    cursor.execute("SELECT * FROM tasks WHERE task_id = %s", (task_id,))
    task = cursor.fetchone()
    if not task:
        cursor.close()
        conn.close()
        return "Công việc không tồn tại!"

    group_id = task["group_id"]
    current_status = task["status"] # proposed, todo, in_progress, pending_review, completed

    # Lấy thông tin quyền trong nhóm
    cursor.execute(
        "SELECT role FROM group_members WHERE group_id = %s AND user_id = %s",
        (group_id, user_id)
    )
    membership = cursor.fetchone()
    if not membership:
        cursor.close()
        conn.close()
        return "Bạn không thuộc nhóm này!"

    is_admin = (membership["role"] == "admin")
    
    # Kiểm tra xem user có được giao task này không
    cursor.execute(
        "SELECT 1 FROM task_assignments WHERE task_id = %s AND user_id = %s",
        (task_id, user_id)
    )
    is_assigned = (cursor.fetchone() is not None)

    # Chỉ Admin hoặc Người được giao task mới được đổi trạng thái
    if not is_admin and not is_assigned:
        cursor.close()
        conn.close()
        return "Bạn không có quyền thay đổi trạng thái công việc này!"

    # Tính toán trạng thái mới
    new_status = current_status

    if action_type == 1: # Tiến lên
        if current_status == "proposed":
            if is_admin:
                new_status = "todo"
            else:
                cursor.close()
                conn.close()
                return "Chỉ Quản trị viên mới được quyền phê duyệt công việc đề xuất!"
        elif current_status == "todo":
            new_status = "in_progress"
        elif current_status == "in_progress":
            new_status = "pending_review"
        elif current_status == "pending_review":
            # Chỉ Admin mới được Duyệt hoàn thành (Accept)
            if is_admin:
                new_status = "completed"
            else:
                cursor.close()
                conn.close()
                return "Chỉ Quản trị viên mới được phê duyệt hoàn thành công việc!"

    elif action_type == 2: # Lùi lại (Từ chối duyệt / Yêu cầu làm lại)
        # Chỉ Admin mới được quyền Từ chối hoặc Yêu cầu làm lại
        if not is_admin:
            cursor.close()
            conn.close()
            return "Chỉ Quản trị viên mới được quyền yêu cầu làm lại!"

        if current_status == "pending_review":
            new_status = "in_progress" # Trả về đang làm
        elif current_status == "completed":
            new_status = "in_progress" # ReWork lại

    # Cập nhật trạng thái mới vào DB
    if new_status != current_status:
        try:
            cursor.execute("UPDATE tasks SET status = %s WHERE task_id = %s", (new_status, task_id))
            conn.commit()
        except Exception as e:
            conn.rollback()
        finally:
            cursor.close()
            conn.close()
    else:
        cursor.close()
        conn.close()

    # Chuyển hướng quay lại trang chi tiết nhóm
    return redirect(url_for("groups.inside_group", group_id=group_id))


@tasks_bp.route("/add_comment/<int:task_id>", methods=["POST"])
def add_comment(task_id):
    if "userID" not in session:
        return redirect(url_for("auth.login"))

    user_id = session["userID"]
    content = request.form.get("content", "").strip()

    if not content:
        return redirect(url_for("tasks.edit_task", task_id=task_id))

    conn = get_connection()
    cursor = get_db_cursor(conn)

    # Kiểm tra task có tồn tại không
    cursor.execute("SELECT group_id FROM tasks WHERE task_id = %s", (task_id,))
    task = cursor.fetchone()
    if not task:
        cursor.close()
        conn.close()
        return "Công việc không tồn tại!"

    # Kiểm tra xem người bình luận có thuộc nhóm đó không
    cursor.execute(
        "SELECT 1 FROM group_members WHERE group_id = %s AND user_id = %s",
        (task["group_id"], user_id)
    )
    if not cursor.fetchone():
        cursor.close()
        conn.close()
        return "Bạn không có quyền bình luận công việc này!"

    try:
        # Lưu bình luận mới
        cursor.execute(
            """
            INSERT INTO task_comments (task_id, user_id, content)
            VALUES (%s, %s, %s)
            """,
            (task_id, user_id, content)
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

    # Quay lại trang xem chi tiết/sửa task để xem comment vừa đăng
    return redirect(url_for("tasks.edit_task", task_id=task_id))


@tasks_bp.route("/my_tasks")
def user_tasks():
    if "userID" not in session:
        return redirect(url_for("auth.login"))

    user_id = session["userID"]
    
    # Đọc tham số sắp xếp từ URL (ví dụ: ?sort_by=deadline&order=desc)
    sort_by = request.args.get("sort_by", "deadline").strip().lower()
    order = request.args.get("order", "asc").strip().lower()

    # Whitelist các cột được phép sắp xếp để chống SQL Injection
    allowed_sort_columns = {
        "title": "t.title",
        "deadline": "t.deadline",
        "status": "t.status",
        "priority": "t.priority",
        "group_name": "g.group_name",
        "start_date": "t.start_date"
    }

    # Chọn cột và thứ tự sắp xếp (mặc định xếp theo hạn chót tăng dần)
    sort_column = allowed_sort_columns.get(sort_by, "t.deadline")
    sort_order = "DESC" if order == "desc" else "ASC"

    conn = get_connection()
    cursor = get_db_cursor(conn)

    # Truy vấn tất cả các công việc được giao của người dùng kèm cột sắp xếp động và thông tin vai trò của user trong nhóm đó
    query = f"""
        SELECT t.*, g.group_name, u.username as creator_name,
               gm.role as my_group_role
        FROM task_assignments ta
        JOIN tasks t ON ta.task_id = t.task_id
        JOIN groups g ON t.group_id = g.group_id
        JOIN users u ON t.created_by = u.user_id
        LEFT JOIN group_members gm ON g.group_id = gm.group_id AND gm.user_id = %s
        WHERE ta.user_id = %s
        ORDER BY {sort_column} {sort_order}
    """
    
    cursor.execute(query, (user_id, user_id))
    tasks = cursor.fetchall()


    cursor.close()
    conn.close()

    # Truyền cả thông tin cột đang sắp xếp sang template để phục vụ logic click tiêu đề cột đổi chiều (ASC/DESC)
    return render_template(
        "user.html", 
        tasks=tasks, 
        current_sort=sort_by, 
        current_order=order
    )
