import os


class Config:
    # Ключ подписи сессий Flask.
    # Значение по умолчанию — только для локального запуска и демо.
    # В продакшене задавайте SECRET_KEY через переменную окружения.
    SECRET_KEY = os.environ.get('SECRET_KEY', 'your-secret-key-change-in-production')

    # Файл базы данных. Создаётся автоматически при первом запуске.
    DB_PATH = os.environ.get('DB_PATH', 'huita_bd.db')
