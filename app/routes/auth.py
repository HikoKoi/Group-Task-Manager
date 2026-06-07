from flask import Blueprint, render_template, request, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
from app.db import get_connection, get_db_cursor

# Định nghĩa Blueprint cho module Authentication
auth_bp = Blueprint('auth', __name__)

@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    # Nếu đã đăng nhập, tự động chuyển về trang chủ
    if "userID" in session:
        return redirect(url_for("main.index"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        phone = request.form.get("phone", "").strip()
        full_name = request.form.get("full_name", "").strip()

        # Validate dữ liệu đơn giản (Email không còn bắt buộc)
        if not username or not password:
            return render_template("register.html", error="Tên đăng nhập và Mật khẩu không được để trống!")

        if password != confirm_password:
            return render_template("register.html", error="Mật khẩu xác nhận không khớp!")

        # Chuẩn hóa dữ liệu để trống: Nếu rỗng thì lưu thành None (PostgreSQL sẽ hiểu là NULL)
        email_val = email if email else None
        phone_val = phone if phone else None
        full_name_val = full_name if full_name else None

        # Kiểm tra trùng lặp (username là bắt buộc, email và phone là optional)
        # Chúng ta dùng câu lệnh động để kiểm tra đúng các trường được nhập
        conn = get_connection()
        cursor = get_db_cursor(conn)

        query = "SELECT user_id FROM users WHERE username = %s"
        params = [username]

        if email_val:
            query += " OR email = %s"
            params.append(email_val)
        if phone_val:
            query += " OR phone = %s"
            params.append(phone_val)

        cursor.execute(query, tuple(params))
        user = cursor.fetchone()

        if user:
            cursor.close()
            conn.close()
            return render_template("register.html", error="Tên đăng nhập, Email hoặc Số điện thoại đã tồn tại!")

        # Mã hóa mật khẩu bảo mật trước khi lưu vào DB
        hashed_password = generate_password_hash(password)

        try:
            # Thêm user mới vào DB
            cursor.execute(
                """
                INSERT INTO users (username, password_hash, email, phone, full_name)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (username, hashed_password, email_val, phone_val, full_name_val)
            )
            conn.commit()
        except Exception as e:
            conn.rollback()
            return render_template("register.html", error="Có lỗi xảy ra, vui lòng thử lại!")
        finally:
            cursor.close()
            conn.close()

        return redirect(url_for("auth.login"))

    return render_template("register.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if "userID" in session:
        return redirect(url_for("main.index"))

    if request.method == "POST":
        login_input = request.form.get("username", "").strip() # Người dùng có thể nhập Username, Email hoặc Số điện thoại vào ô này
        password = request.form.get("password", "")

        conn = get_connection()
        cursor = get_db_cursor(conn)

        # Hỗ trợ đăng nhập bằng Email, Username hoặc Số điện thoại
        cursor.execute(
            """
            SELECT * FROM users 
            WHERE email = %s OR username = %s OR phone = %s
            """, 
            (login_input, login_input, login_input)
        )
        user = cursor.fetchone()

        cursor.close()
        conn.close()

        # Kiểm tra và giải mã mật khẩu bằng check_password_hash
        if user and check_password_hash(user["password_hash"], password):
            session.permanent = True
            
            # Lưu trữ thông tin đăng nhập vào Session
            session["userID"] = user["user_id"]
            session["userName"] = user["username"]

            return redirect(url_for("main.index"))

        return render_template("login.html", error="Sai tài khoản hoặc mật khẩu!")

    return render_template("login.html")


@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))


@auth_bp.route("/profile", methods=["GET", "POST"])
def profile():
    if "userID" not in session:
        return redirect(url_for("auth.login"))

    user_id = session["userID"]
    conn = get_connection()
    cursor = get_db_cursor(conn)

    error = None
    success = None

    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")

        email_val = email if email else None
        phone_val = phone if phone else None
        full_name_val = full_name if full_name else None

        # Validate confirm password
        if new_password and new_password != confirm_password:
            error = "Mật khẩu xác nhận không khớp!"
        else:
            try:
                # Kiểm tra trùng lặp email/phone
                if email_val or phone_val:
                    cursor.execute(
                        """
                        SELECT user_id FROM users 
                        WHERE (email = %s OR phone = %s) AND user_id != %s
                        """,
                        (email_val, phone_val, user_id)
                    )
                    if cursor.fetchone():
                        error = "Email hoặc Số điện thoại đã tồn tại ở tài khoản khác!"

                if not error:
                    if new_password:
                        hashed_password = generate_password_hash(new_password)
                        cursor.execute(
                            """
                            UPDATE users 
                            SET full_name = %s, email = %s, phone = %s, password_hash = %s
                            WHERE user_id = %s
                            """,
                            (full_name_val, email_val, phone_val, hashed_password, user_id)
                        )
                    else:
                        cursor.execute(
                            """
                            UPDATE users 
                            SET full_name = %s, email = %s, phone = %s
                            WHERE user_id = %s
                            """,
                            (full_name_val, email_val, phone_val, user_id)
                        )
                    conn.commit()
                    success = "Cập nhật thông tin cá nhân thành công!"
            except Exception as e:
                conn.rollback()
                error = "Đã xảy ra lỗi hệ thống, vui lòng thử lại!"

    # Lấy lại thông tin user mới nhất
    cursor.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
    user = cursor.fetchone()

    cursor.close()
    conn.close()

    return render_template("profile.html", user=user, error=error, success=success)

