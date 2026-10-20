from flask_login import LoginManager
from config import Config
import sqlite3

login_manager = LoginManager()
login_manager.login_view = 'auth.login'   # имя blueprint + точка
login_manager.login_message = 'Пожалуйста, войдите, чтобы продолжить.'

def get_db_connection():
    """Возвращает соединение с БД с row_factory = sqlite3.Row."""
    conn = sqlite3.connect(Config.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn