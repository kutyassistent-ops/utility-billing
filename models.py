import sqlite3
from datetime import date, datetime
from flask_login import UserMixin
import bcrypt
from extensions import get_db_connection
from config import Config

# ---------- Класс пользователя ----------
class User(UserMixin):
    def __init__(self, id, username, role, full_name=None):
        self.id = id
        self.username = username
        self.role = role
        self.full_name = full_name

# ---------- Загрузчик пользователя для Flask-Login ----------
def load_user(user_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT id, username, role, full_name FROM users WHERE id = ?', (user_id,))
    row = cur.fetchone()
    conn.close()
    if row:
        return User(row['id'], row['username'], row['role'], row['full_name'])
    return None

# ---------- Хеширование паролей ----------
def hash_password(password):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def check_password(password, hashed):
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

# ---------- Инициализация и миграция БД ----------
def migrate_db():
    """Добавляет колонку paid в таблицу invoices, если её нет."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(invoices)")
    columns = [row[1] for row in cur.fetchall()]
    if 'paid' not in columns:
        print("Миграция: добавляем колонку paid в таблицу invoices...")
        cur.execute("ALTER TABLE invoices ADD COLUMN paid BOOLEAN DEFAULT 0")
        conn.commit()
        print("Колонка paid добавлена.")
    conn.close()

def init_db():
    """Создаёт таблицы, если их нет, и запускает миграцию."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('owner', 'tenant')),
            full_name TEXT,
            email TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS properties (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_id INTEGER NOT NULL,
            address TEXT NOT NULL,
            tariff_el REAL NOT NULL DEFAULT 2.73,
            tariff_water REAL NOT NULL DEFAULT 31.21,
            tariff_com1 REAL NOT NULL DEFAULT 72.83,
            tariff_com2 REAL NOT NULL DEFAULT 21.95,
            fixed_fee REAL NOT NULL DEFAULT 17000,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS tenant_properties (
            tenant_id INTEGER NOT NULL,
            property_id INTEGER NOT NULL,
            PRIMARY KEY (tenant_id, property_id),
            FOREIGN KEY (tenant_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (property_id) REFERENCES properties(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS meter_readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            property_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            hot_water INTEGER NOT NULL,
            cool_water INTEGER NOT NULL,
            electricity INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (property_id) REFERENCES properties(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            UNIQUE(property_id, date)
        );
        CREATE TABLE IF NOT EXISTS invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            property_id INTEGER NOT NULL,
            reading_id INTEGER NOT NULL,
            total REAL NOT NULL,
            details TEXT,
            paid BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (property_id) REFERENCES properties(id) ON DELETE CASCADE,
            FOREIGN KEY (reading_id) REFERENCES meter_readings(id) ON DELETE CASCADE,
            UNIQUE(property_id, reading_id)
        );
    ''')
    conn.commit()
    conn.close()
    migrate_db()

# ---------- Основные функции для работы с данными ----------
def get_last_reading(property_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('''
        SELECT hot_water, cool_water, electricity, date
        FROM meter_readings
        WHERE property_id = ?
        ORDER BY date DESC, id DESC
        LIMIT 1
    ''', (property_id,))
    row = cur.fetchone()
    conn.close()
    if row:
        return dict(row)
    return None

def get_property_tariffs(property_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('''
        SELECT tariff_el, tariff_water, tariff_com1, tariff_com2, fixed_fee
        FROM properties WHERE id = ?
    ''', (property_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None

def calculate_total(reading, prev_reading, tariffs):
    curr_hv = reading['cool_water']
    curr_gv = reading['hot_water']
    curr_el = reading['electricity']
    prev_hv = prev_reading['cool_water'] if prev_reading else 0
    prev_gv = prev_reading['hot_water'] if prev_reading else 0
    prev_el = prev_reading['electricity'] if prev_reading else 0

    consumption_el = (curr_el - prev_el) * tariffs['tariff_el']
    consumption_hv = (curr_hv - prev_hv) * tariffs['tariff_water']
    consumption_gv = (curr_gv - prev_gv) * tariffs['tariff_water']
    com_1 = (curr_hv - prev_hv) * tariffs['tariff_com1']
    com_2 = ((curr_hv - prev_hv) + (curr_gv - prev_gv)) * tariffs['tariff_com2']
    com_3 = consumption_el + consumption_hv + consumption_gv + com_1 + com_2
    total = com_3 + tariffs['fixed_fee']
    details = {
        'consumption_el': consumption_el,
        'consumption_hv': consumption_hv,
        'consumption_gv': consumption_gv,
        'com_1': com_1,
        'com_2': com_2,
        'com_3': com_3,
        'total': total
    }
    return details

def get_debt(property_id):
    """Возвращает общую сумму неоплаченных счетов для объекта."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('''
        SELECT SUM(total) as debt
        FROM invoices
        WHERE property_id = ? AND paid = 0
    ''', (property_id,))
    row = cur.fetchone()
    conn.close()
    return row['debt'] if row and row['debt'] else 0.0

def get_stats_data(property_id, months_back):
    conn = get_db_connection()
    cur = conn.cursor()
    if months_back > 0:
        cur.execute('''
            SELECT 
                strftime('%Y-%m', date) as month,
                SUM(total) as month_total,
                SUM(hot_water - COALESCE(
                    (SELECT hot_water FROM meter_readings r2 
                     WHERE r2.property_id = r.property_id AND r2.date < r.date 
                     ORDER BY r2.date DESC LIMIT 1), 0
                )) as hot_diff,
                SUM(cool_water - COALESCE(
                    (SELECT cool_water FROM meter_readings r2 
                     WHERE r2.property_id = r.property_id AND r2.date < r.date 
                     ORDER BY r2.date DESC LIMIT 1), 0
                )) as cold_diff,
                SUM(electricity - COALESCE(
                    (SELECT electricity FROM meter_readings r2 
                     WHERE r2.property_id = r.property_id AND r2.date < r.date 
                     ORDER BY r2.date DESC LIMIT 1), 0
                )) as el_diff
            FROM meter_readings r
            JOIN invoices i ON r.id = i.reading_id
            WHERE r.property_id = ?
              AND date >= date('now', ? || ' months')
            GROUP BY month
            ORDER BY month
        ''', (property_id, f'-{months_back}'))
    else:
        cur.execute('''
            SELECT 
                strftime('%Y-%m', date) as month,
                SUM(total) as month_total,
                SUM(hot_water - COALESCE(
                    (SELECT hot_water FROM meter_readings r2 
                     WHERE r2.property_id = r.property_id AND r2.date < r.date 
                     ORDER BY r2.date DESC LIMIT 1), 0
                )) as hot_diff,
                SUM(cool_water - COALESCE(
                    (SELECT cool_water FROM meter_readings r2 
                     WHERE r2.property_id = r.property_id AND r2.date < r.date 
                     ORDER BY r2.date DESC LIMIT 1), 0
                )) as cold_diff,
                SUM(electricity - COALESCE(
                    (SELECT electricity FROM meter_readings r2 
                     WHERE r2.property_id = r.property_id AND r2.date < r.date 
                     ORDER BY r2.date DESC LIMIT 1), 0
                )) as el_diff
            FROM meter_readings r
            JOIN invoices i ON r.id = i.reading_id
            WHERE r.property_id = ?
            GROUP BY month
            ORDER BY month
        ''', (property_id,))
    rows = cur.fetchall()
    conn.close()
    if not rows:
        return {
            'labels': [],
            'totals': [],
            'hot_water': [],
            'cold_water': [],
            'electricity': [],
            'summary': {'total_sum': 0, 'avg_month': 0, 'avg_hot': 0, 'avg_cold': 0, 'avg_el': 0}
        }
    labels = [row['month'] for row in rows]
    totals = [row['month_total'] for row in rows]
    hot = [row['hot_diff'] if row['hot_diff'] else 0 for row in rows]
    cold = [row['cold_diff'] if row['cold_diff'] else 0 for row in rows]
    el = [row['el_diff'] if row['el_diff'] else 0 for row in rows]
    total_sum = sum(totals)
    avg_month = total_sum / len(totals) if totals else 0
    avg_hot = sum(hot) / len(hot) if hot else 0
    avg_cold = sum(cold) / len(cold) if cold else 0
    avg_el = sum(el) / len(el) if el else 0
    summary = {
        'total_sum': total_sum,
        'avg_month': avg_month,
        'avg_hot': avg_hot,
        'avg_cold': avg_cold,
        'avg_el': avg_el
    }
    return {
        'labels': labels,
        'totals': totals,
        'hot_water': hot,
        'cold_water': cold,
        'electricity': el,
        'summary': summary
    }