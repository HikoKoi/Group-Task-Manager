from flask import Flask
from app.config import Config

def create_app():
    # Khởi tạo đối tượng Flask
    app = Flask(__name__)
    
    # Nạp cấu hình từ Class Config trong app/config.py
    app.config.from_object(Config)
    
    # Đăng ký các Blueprint

    
    from app.routes.auth import auth_bp
    app.register_blueprint(auth_bp)
    
    from app.routes.group import groups_bp
    app.register_blueprint(groups_bp)
    
    from app.routes.task import tasks_bp
    app.register_blueprint(tasks_bp)
    
    from app.routes.main import main_bp
    app.register_blueprint(main_bp)
    
    @app.after_request
    def handle_plain_text_responses(response):
        from flask import flash, redirect, request, url_for, make_response
        if response.mimetype == 'text/html' and response.status_code == 200:
            if response.content_length is not None and response.content_length > 1000:
                return response
            
            try:
                text = response.get_data(as_text=True).strip()
                if text and len(text) < 250 and not text.startswith('<'):
                    category = 'success' if any(w in text.lower() for w in ['thành công', 'success', 'hoàn thành']) else 'danger'
                    flash(text, category)
                    
                    ref = request.referrer
                    if not ref or ref == request.url:
                        ref = url_for('main.index')
                    
                    return make_response(redirect(ref))
            except Exception:
                pass
        return response

    return app
