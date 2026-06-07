import psycopg2
from psycopg2.extras import RealDictCursor
from flask import current_app

def get_connection():
    """Tạo kết nối tới cơ sở dữ liệu Supabase PostgreSQL."""
    return psycopg2.connect(
        host=current_app.config['DB_HOST'],
        port=current_app.config['DB_PORT'],
        database=current_app.config['DB_NAME'],
        user=current_app.config['DB_USER'],
        password=current_app.config['DB_PASSWORD']
    )

def get_db_cursor(conn):
    """
    Tạo cursor trả về kết quả dạng Dictionary thay vì Tuple.
    """
    return conn.cursor(cursor_factory=RealDictCursor)
