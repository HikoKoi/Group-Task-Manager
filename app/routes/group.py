from flask import Blueprint, render_template, request, redirect, url_for, session
import random
import string
from app.db import get_connection, get_db_cursor

groups_bp = Blueprint('groups', __name__)

@groups_bp.route("/create_group", methods=["GET", "POST"])
def create_group():
    if "userID" not in session:
        return redirect(url_for("auth.login"))

    if request.method == "GET":
        return render_template("create_group.html")

    group_name = request.form.get("groupName", "").strip()
    description = request.form.get("description", "").strip()

    if not group_name:
        return redirect(url_for("main.index"))

    user_id = session["userID"]
    conn = get_connection()
    cursor = get_db_cursor(conn)

    # Sinh joinCode gồm 6 ký tự viết hoa và số, đảm bảo không trùng lặp
    while True:
        join_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        cursor.execute("SELECT group_id FROM groups WHERE join_code = %s", (join_code,))
        if cursor.fetchone() is None:
            break

    try:
        # Tạo Group mới - Dùng RETURNING group_id để lấy ID tự động tăng trong PostgreSQL
        cursor.execute(
            """
            INSERT INTO groups (group_name, join_code, description, created_by)
            VALUES (%s, %s, %s, %s)
            RETURNING group_id
            """,
            (group_name, join_code, description if description else None, user_id)
        )
        group_id = cursor.fetchone()["group_id"]

        # Thêm người tạo nhóm vào danh sách thành viên với vai trò là 'admin'
        cursor.execute(
            """
            INSERT INTO group_members (group_id, user_id, role)
            VALUES (%s, %s, 'admin')
            """,
            (group_id, user_id)
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        # Log lỗi hoặc xử lý trả về nếu cần thiết
        return redirect(url_for("main.index"))
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for("main.index"))


@groups_bp.route("/group/<int:group_id>")
def inside_group(group_id):
    if "userID" not in session:
        return redirect(url_for("auth.login"))

    conn = get_connection()
    cursor = get_db_cursor(conn)

    # Lấy thông tin chi tiết của Group
    cursor.execute("SELECT * FROM groups WHERE group_id = %s", (group_id,))
    group = cursor.fetchone()

    if not group:
        cursor.close()
        conn.close()
        return "Nhóm không tồn tại hoặc đã bị xóa!"

    # Kiểm tra quyền truy cập: Người dùng hiện tại có phải thành viên của nhóm không?
    cursor.execute(
        """
        SELECT role 
        FROM group_members 
        WHERE group_id = %s AND user_id = %s
        """,
        (group_id, session["userID"])
    )
    user_membership = cursor.fetchone()

    if not user_membership:
        cursor.close()
        conn.close()
        # Chuyển hướng về trang chủ nếu cố tình truy cập trái phép nhóm khác
        return redirect(url_for("main.index"))

    # Lấy danh sách thành viên của Group cùng vai trò của họ
    cursor.execute(
        """
        SELECT gm.group_id, gm.user_id, gm.role, u.username, u.full_name
        FROM group_members gm
        JOIN users u ON gm.user_id = u.user_id
        WHERE gm.group_id = %s
        ORDER BY gm.role, u.username
        """,
        (group_id,)
    )
    members = cursor.fetchall()

    # Lấy danh sách các Task thuộc nhóm này kèm thông tin người tạo và xem có được giao cho user hiện tại không
    cursor.execute(
        """
        SELECT t.*, u.username as creator_name,
               (SELECT COUNT(*) FROM task_assignments ta 
                WHERE ta.task_id = t.task_id AND ta.user_id = %s) > 0 as is_assigned_to_me
        FROM tasks t
        LEFT JOIN users u ON t.created_by = u.user_id
        WHERE t.group_id = %s
        ORDER BY t.deadline
        """,
        (session["userID"], group_id)
    )
    tasks = cursor.fetchall()


    # Xác định người dùng hiện tại có phải admin của nhóm này hay không
    is_admin = False
    for m in members:
        if m["user_id"] == session["userID"] and m["role"] == "admin":
            is_admin = True
            break

    # Lấy danh sách các yêu cầu tham gia nhóm chờ duyệt (chỉ dành cho Admin)
    requests_list = []
    if is_admin:
        cursor.execute(
            """
            SELECT jr.request_id, u.user_id, u.username, u.full_name, jr.created_at
            FROM group_join_requests jr
            JOIN users u ON jr.user_id = u.user_id
            WHERE jr.group_id = %s AND jr.status = 'pending'
            ORDER BY jr.created_at
            """,
            (group_id,)
        )
        requests_list = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        "inside_group.html",
        group=group,
        members=members,
        tasks=tasks,
        is_admin=is_admin,
        requests=requests_list
    )


@groups_bp.route("/join_group/<string:join_code>")
@groups_bp.route("/join_group", methods=["POST"])
def join_group(join_code=None):
    if "userID" not in session:
        return redirect(url_for("auth.login"))

    # Lấy mã mời từ URL hoặc từ Form nhập liệu
    if request.method == "POST":
        join_code = request.form.get("joinCode", "").strip().upper()

    if not join_code:
        return redirect(url_for("main.index"))

    user_id = session["userID"]
    conn = get_connection()
    cursor = get_db_cursor(conn)

    # Kiểm tra xem nhóm có tồn tại với mã mời này không
    cursor.execute("SELECT group_id FROM groups WHERE join_code = %s", (join_code,))
    group = cursor.fetchone()

    if not group:
        cursor.close()
        conn.close()
        return "Mã mời nhóm không chính xác hoặc nhóm đã bị xóa!"

    group_id = group["group_id"]

    # Kiểm tra xem user đã là thành viên nhóm chưa
    cursor.execute(
        "SELECT * FROM group_members WHERE group_id = %s AND user_id = %s",
        (group_id, user_id)
    )
    member = cursor.fetchone()

    if member:
        cursor.close()
        conn.close()
        # Nếu đã là thành viên -> Vào thẳng nhóm
        return redirect(url_for("groups.inside_group", group_id=group_id))

    # Kiểm tra xem đã gửi yêu cầu tham gia và đang chờ duyệt chưa
    cursor.execute(
        "SELECT status FROM group_join_requests WHERE group_id = %s AND user_id = %s AND status = 'pending'",
        (group_id, user_id)
    )
    existing_request = cursor.fetchone()

    if existing_request:
        cursor.close()
        conn.close()
        return "Yêu cầu gia nhập nhóm của bạn đang chờ Admin phê duyệt!"

    # Gửi yêu cầu gia nhập nhóm mới (trạng thái mặc định là 'pending')
    try:
        cursor.execute(
            """
            INSERT INTO group_join_requests (group_id, user_id)
            VALUES (%s, %s)
            """,
            (group_id, user_id)
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        return "Có lỗi xảy ra khi gửi yêu cầu xin vào nhóm!"
    finally:
        cursor.close()
        conn.close()

    return "Gửi yêu cầu gia nhập thành công! Vui lòng đợi Admin phê duyệt."


@groups_bp.route("/make_admin/<int:user_id>/<int:group_id>")
def make_admin(user_id, group_id):
    if "userID" not in session:
        return redirect(url_for("auth.login"))

    current_user_id = session["userID"]
    conn = get_connection()
    cursor = get_db_cursor(conn)

    # Kiểm tra nhóm có tồn tại hay không
    cursor.execute("SELECT group_id FROM groups WHERE group_id = %s", (group_id,))
    if not cursor.fetchone():
        cursor.close()
        conn.close()
        return "Nhóm không tồn tại!"

    # Kiểm tra xem người nhận quyền admin có phải thành viên nhóm đó không
    cursor.execute(
        "SELECT role FROM group_members WHERE group_id = %s AND user_id = %s",
        (group_id, user_id)
    )
    target_user = cursor.fetchone()
    if not target_user:
        cursor.close()
        conn.close()
        return "Người nhận không thuộc thành viên của nhóm này!"

    # Kiểm tra xem người dùng hiện tại có phải Admin của nhóm đó hay không
    cursor.execute(
        "SELECT role FROM group_members WHERE group_id = %s AND user_id = %s",
        (group_id, current_user_id)
    )
    current_user = cursor.fetchone()

    if current_user and current_user["role"] == "admin":
        try:
            # Cấp quyền admin cho thành viên mới
            cursor.execute(
                "UPDATE group_members SET role = 'admin' WHERE group_id = %s AND user_id = %s",
                (group_id, user_id)
            )
            # Hạ quyền của bản thân xuống thành 'member'
            cursor.execute(
                "UPDATE group_members SET role = 'member' WHERE group_id = %s AND user_id = %s",
                (group_id, current_user_id)
            )
            conn.commit()
        except Exception as e:
            conn.rollback()

    cursor.close()
    conn.close()
    return redirect(url_for("groups.inside_group", group_id=group_id))


@groups_bp.route("/kick_member/<int:user_id>/<int:group_id>")
def kick_member(user_id, group_id):
    if "userID" not in session:
        return redirect(url_for("auth.login"))

    current_user_id = session["userID"]
    conn = get_connection()
    cursor = get_db_cursor(conn)

    # Kiểm tra nhóm có tồn tại hay không
    cursor.execute("SELECT group_id FROM groups WHERE group_id = %s", (group_id,))
    if not cursor.fetchone():
        cursor.close()
        conn.close()
        return "Nhóm không tồn tại!"

    # Kiểm tra xem thành viên cần kích có thuộc nhóm không
    cursor.execute(
        "SELECT role FROM group_members WHERE group_id = %s AND user_id = %s",
        (group_id, user_id)
    )
    target_user = cursor.fetchone()
    if not target_user:
        cursor.close()
        conn.close()
        return "Thành viên cần xóa không nằm trong nhóm này!"

    # Kiểm tra quyền: Chỉ admin nhóm mới được kích thành viên
    cursor.execute(
        "SELECT role FROM group_members WHERE group_id = %s AND user_id = %s",
        (group_id, current_user_id)
    )
    current_user = cursor.fetchone()

    if current_user and current_user["role"] == "admin" and current_user_id != user_id:
        try:
            # Xóa thành viên khỏi bảng group_members
            cursor.execute(
                "DELETE FROM group_members WHERE group_id = %s AND user_id = %s",
                (group_id, user_id)
            )
            # Xóa các phân công task của thành viên đó trong nhóm này
            cursor.execute(
                """
                DELETE FROM task_assignments 
                WHERE user_id = %s 
                  AND task_id IN (SELECT task_id FROM tasks WHERE group_id = %s)
                """,
                (user_id, group_id)
            )
            conn.commit()
        except Exception as e:
            conn.rollback()

    cursor.close()
    conn.close()
    return redirect(url_for("groups.inside_group", group_id=group_id))


@groups_bp.route("/member_out/<int:user_id>/<int:group_id>")
def member_out(user_id, group_id):
    if "userID" not in session:
        return redirect(url_for("auth.login"))

    # Đảm bảo chỉ tự rời khỏi nhóm chính mình chứ không rời hộ người khác
    if session["userID"] != user_id:
        return redirect(url_for("main.index"))

    conn = get_connection()
    cursor = get_db_cursor(conn)

    # Kiểm tra nhóm có tồn tại hay không
    cursor.execute("SELECT group_id FROM groups WHERE group_id = %s", (group_id,))
    if not cursor.fetchone():
        cursor.close()
        conn.close()
        return "Nhóm không tồn tại!"

    # Kiểm tra xem bản thân có nằm trong nhóm không
    cursor.execute(
        "SELECT role FROM group_members WHERE group_id = %s AND user_id = %s",
        (group_id, user_id)
    )
    current_user = cursor.fetchone()
    if not current_user:
        cursor.close()
        conn.close()
        return "Bạn không nằm trong nhóm này!"

    try:
        is_leaving_admin = (current_user["role"] == "admin")

        # Rời khỏi nhóm
        cursor.execute(
            "DELETE FROM group_members WHERE group_id = %s AND user_id = %s",
            (group_id, user_id)
        )
        # Xóa các phân công task liên quan của thành viên này trong nhóm
        cursor.execute(
            """
            DELETE FROM task_assignments 
            WHERE user_id = %s 
              AND task_id IN (SELECT task_id FROM tasks WHERE group_id = %s)
            """,
            (user_id, group_id)
        )

        # Kiểm tra các thành viên còn lại
        cursor.execute(
            "SELECT user_id, role FROM group_members WHERE group_id = %s ORDER BY join_date ASC",
            (group_id,)
        )
        remaining_members = cursor.fetchall()

        if not remaining_members:
            # Nếu nhóm không còn ai -> Xóa luôn nhóm để dọn dẹp DB
            cursor.execute("DELETE FROM groups WHERE group_id = %s", (group_id,))
        elif is_leaving_admin:
            # Nếu người out là Admin, kiểm tra xem còn Admin nào khác không
            has_other_admin = any(m["role"] == "admin" for m in remaining_members)
            if not has_other_admin:
                # Tự động chỉ định người tham gia nhóm sớm nhất làm Admin mới
                new_admin_id = remaining_members[0]["user_id"]
                cursor.execute(
                    "UPDATE group_members SET role = 'admin' WHERE group_id = %s AND user_id = %s",
                    (group_id, new_admin_id)
                )
        
        conn.commit()
    except Exception as e:
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for("main.index"))



@groups_bp.route("/approve_request/<int:request_id>")
def approve_request(request_id):
    if "userID" not in session:
        return redirect(url_for("auth.login"))

    current_user_id = session["userID"]
    conn = get_connection()
    cursor = get_db_cursor(conn)

    # Lấy thông tin yêu cầu gia nhập
    cursor.execute("SELECT * FROM group_join_requests WHERE request_id = %s", (request_id,))
    req = cursor.fetchone()

    if not req:
        cursor.close()
        conn.close()
        return "Yêu cầu không tồn tại!"

    group_id = req["group_id"]
    target_user_id = req["user_id"]

    # Kiểm tra xem người dùng hiện tại có phải Admin của nhóm đó hay không
    cursor.execute(
        "SELECT role FROM group_members WHERE group_id = %s AND user_id = %s",
        (group_id, current_user_id)
    )
    membership = cursor.fetchone()

    if membership and membership["role"] == "admin":
        try:
            # Thêm thành viên mới vào nhóm
            cursor.execute(
                """
                INSERT INTO group_members (group_id, user_id, role)
                VALUES (%s, %s, 'member')
                """,
                (group_id, target_user_id)
            )
            # Xóa yêu cầu gia nhập sau khi đã duyệt thành công
            cursor.execute("DELETE FROM group_join_requests WHERE request_id = %s", (request_id,))
            conn.commit()
        except Exception as e:
            conn.rollback()
            return "Có lỗi xảy ra khi phê duyệt thành viên!"
        finally:
            cursor.close()
            conn.close()
    else:
        cursor.close()
        conn.close()
        return "Bạn không có quyền thực hiện hành động này!"

    return redirect(url_for("groups.inside_group", group_id=group_id))


@groups_bp.route("/reject_request/<int:request_id>")
def reject_request(request_id):
    if "userID" not in session:
        return redirect(url_for("auth.login"))

    current_user_id = session["userID"]
    conn = get_connection()
    cursor = get_db_cursor(conn)

    # Lấy thông tin yêu cầu gia nhập
    cursor.execute("SELECT * FROM group_join_requests WHERE request_id = %s", (request_id,))
    req = cursor.fetchone()

    if not req:
        cursor.close()
        conn.close()
        return "Yêu cầu không tồn tại!"

    group_id = req["group_id"]

    # Kiểm tra xem người dùng hiện tại có phải Admin của nhóm đó hay không
    cursor.execute(
        "SELECT role FROM group_members WHERE group_id = %s AND user_id = %s",
        (group_id, current_user_id)
    )
    membership = cursor.fetchone()

    if membership and membership["role"] == "admin":
        try:
            # Xóa (từ chối) yêu cầu gia nhập
            cursor.execute("DELETE FROM group_join_requests WHERE request_id = %s", (request_id,))
            conn.commit()
        except Exception as e:
            conn.rollback()
            return "Có lỗi xảy ra khi từ chối yêu cầu!"
        finally:
            cursor.close()
            conn.close()
    else:
        cursor.close()
        conn.close()
        return "Bạn không có quyền thực hiện hành động này!"

    return redirect(url_for("groups.inside_group", group_id=group_id))
