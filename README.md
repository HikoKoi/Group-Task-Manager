# GTM - Group Task Manager 🚀

Group Task Manager (GTM) là một ứng dụng web quản lý công việc nhóm trực quan, hiện đại được phát triển bằng **Flask framework** (Python) và cơ sở dữ liệu **Supabase PostgreSQL**. Dự án được thiết kế chuẩn cấu trúc mô hình Flask Blueprint, hỗ trợ container hóa bằng Docker giúp triển khai dễ dàng.

---

## 🌟 Tính năng nổi bật

- 🔑 **Xác thực người dùng**: Đăng ký, Đăng nhập (hỗ trợ Username, Email hoặc Số điện thoại) và quản lý thông tin cá nhân.
- 👥 **Quản lý nhóm (Groups)**:
  - Tạo nhóm mới và tự động sinh mã mời (Join Code) ngẫu nhiên 6 ký tự.
  - Gia nhập nhóm bằng mã mời (yêu cầu Admin phê duyệt).
  - Phân quyền Quản trị viên (Admin) / Thành viên (Member). Admin có thể chỉ định Admin mới hoặc kích thành viên khỏi nhóm.
  - Tự động chuyển giao quyền Admin cho thành viên tham gia sớm nhất nếu Admin hiện tại rời nhóm.
- 📋 **Quản lý công việc (Tasks)**:
  - Tạo công việc kèm thông tin: tiêu đề, mô tả, mức độ ưu tiên (Low, Medium, High), ngày bắt đầu, ngày hạn chót và phân công cho nhiều thành viên.
  - Phê duyệt các công việc do thành viên đề xuất (proposed) trước khi đưa vào thực hiện.
  - Chuyển trạng thái linh hoạt (Tiến/Lùi trạng thái) với các quyền kiểm soát chặt chẽ giữa Admin và Người thực hiện.
  - Bình luận trong từng công việc giúp tăng khả năng tương tác nhóm.
- 🔍 **Bộ lọc & Tìm kiếm**: Tìm kiếm tương đối nhóm, công việc và bộ lọc sắp xếp động an toàn (whitelist-safe) tại trang cá nhân.
- 🎨 **Giao diện hiện đại**: Thiết kế tối giản, dark-theme phối màu neon, hiệu ứng kính mờ (Glassmorphic) sang trọng và tối ưu tương phản cao.

---

## 📂 Cấu trúc thư mục dự án

```text
Group-Task-Manager/
├── app/
│   ├── __init__.py          # Hàm factory khởi tạo ứng dụng (App Factory)
│   ├── config.py            # Quản lý cấu hình từ file .env
│   ├── db.py                # Helper kết nối và truy vấn PostgreSQL (Supabase)
│   ├── routes/              # Chứa các file điều hướng Blueprint
│   │   ├── auth.py          # Quăng lý Đăng nhập, Đăng ký, Đăng xuất, Hồ sơ
│   │   ├── group.py         # Quản lý Nhóm và Thành viên
│   │   ├── task.py          # Quản lý Công việc, Comment, Trạng thái
│   │   └── main.py          # Dashboard trang chủ và Tìm kiếm toàn cục
│   ├── static/              # Thư mục chứa tài nguyên tĩnh (Cần di chuyển vào đây)
│   │   └── css/
│   │       └── style.css    # File CSS tùy chỉnh giao diện
│   └── templates/           # Thư mục chứa giao diện Jinja2 HTML
│       ├── base.html        # Khung giao diện chung (Navbar, Alert, Script)
│       ├── index.html       # Trang chủ dashboard nhóm
│       ├── login.html       # Giao diện Đăng nhập
│       ├── register.html    # Giao diện Đăng ký
│       ├── profile.html     # Trang cá nhân
│       ├── create_group.html# Trang tạo nhóm
│       ├── inside_group.html# Trang chi tiết thành viên & công việc của nhóm
│       ├── create_task.html # Trang tạo công việc mới
│       ├── edit_task.html   # Trang sửa công việc & bình luận
│       ├── user.html        # Trang danh sách công việc được giao của cá nhân
│       └── search.html      # Trang kết quả tìm kiếm
├── .env.example             # File mẫu hướng dẫn cấu hình môi trường
├── Dockerfile               # File build Image Docker cho Flask app
├── docker-compose.yml       # Quản lý chạy container Docker ở local
├── requirements.txt         # Khai báo các thư viện Python cần thiết
├── run.py                   # File chạy chính của ứng dụng
├── schema.sql               # File DDL khởi tạo cấu trúc cơ sở dữ liệu
└── README.md                # Tài liệu hướng dẫn dự án
```

---

## 🛠️ Hướng dẫn cài đặt và chạy ứng dụng

### 1. Chuẩn bị Cơ sở dữ liệu (Supabase PostgreSQL)
1. Tạo một dự án mới trên [Supabase](https://supabase.com/).
2. Truy cập vào mục **SQL Editor** trong giao diện quản lý của Supabase.
3. Sao chép nội dung file `schema.sql` và chạy (Run) để tạo các bảng cơ sở dữ liệu cần thiết.

### 2. Cấu hình Biến môi trường
Tạo file `.env` tại thư mục gốc của dự án dựa trên mẫu `.env.example`:
```env
DB_HOST=your-supabase-db-host
DB_PORT=6543 # Mặc định port PostgreSQL Supabase là 6543 hoặc 5432
DB_NAME=postgres
DB_USER=postgres
DB_PASSWORD=your-supabase-db-password
SECRET_KEY=your-secret-random-key
```

### 3. Chạy ứng dụng bằng Docker (Khuyên dùng)
Yêu cầu đã cài đặt **Docker** và **Docker Compose**. Tại thư mục gốc dự án chạy lệnh:
```bash
docker-compose up --build
```
hoặc
```bash
docker compose up --build
```
Ứng dụng sẽ được khởi chạy tại địa chỉ: `http://localhost:5000`

### 4. Chạy trực tiếp ở Local (Không dùng Docker)
1. Cài đặt Python (phiên bản 3.10 trở lên).
2. Tạo môi trường ảo và kích hoạt:
   ```bash
   python -m venv venv
   source venv/bin/activate  # Trên Windows dùng: venv\Scripts\activate
   ```
3. Cài đặt các thư viện cần thiết:
   ```bash
   pip install -r requirements.txt
   ```
4. Khởi chạy ứng dụng Flask:
   ```bash
   python run.py
   ```
   Ứng dụng sẽ chạy ở chế độ Development tại: `http://127.0.0.1:5000`

---

## 👥 Thành viên thực hiện
- Thành viên 1: Phạm Đức Khôi - 2221050315
- Thành viên 2: Nguyễn Đăng Duy - 2221050524
- Thành viên 3: Nguyễn Cúc Mai - 2221050515