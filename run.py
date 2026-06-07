from app import create_app

# Gọi hàm factory để khởi tạo ứng dụng Flask
app = create_app()

if __name__ == "__main__":
    # Khởi chạy server Flask ở cổng 5000
    # Cấu hình host="0.0.0.0" để container Docker bên ngoài có thể truy cập được ứng dụng bên trong.
    app.run(host="0.0.0.0", port=5000, debug=True)
