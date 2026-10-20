from flask import Flask
from config import Config
from extensions import login_manager, get_db_connection
from models import load_user, init_db
from auth import auth_bp
from routes import main_bp

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Инициализация расширений
    login_manager.init_app(app)
    login_manager.user_loader(load_user)

    # Регистрация blueprint
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)

    # Инициализация БД (при первом запуске)
    with app.app_context():
        init_db()

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=5000)