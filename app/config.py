import os
from datetime import timedelta

class Config:
    # Đọc Secret Key từ file .env, nếu không tìm thấy sẽ dùng chuỗi mặc định để tránh lỗi crash
    SECRET_KEY = os.environ.get('SECRET_KEY', 'default-fallback-key')
    
    # Cấu hình thời gian sống của session (ví dụ: tự động đăng xuất sau 30 phút không hoạt động)
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=30)
    
    # Đọc các thông số cấu hình kết nối Database Supabase từ .env
    DB_HOST = os.environ.get('DB_HOST')
    DB_PORT = os.environ.get('DB_PORT', '5432')
    DB_NAME = os.environ.get('DB_NAME')
    DB_USER = os.environ.get('DB_USER')
    DB_PASSWORD = os.environ.get('DB_PASSWORD')
