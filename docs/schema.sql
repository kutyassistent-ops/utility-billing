-- Учёт коммунальных платежей — схема базы данных (SQLite)
--
-- Справочный файл: приложение создаёт эти таблицы само при первом запуске
-- (models.init_db()), а база данных в git не хранится.
--
-- Создать вручную:
--   sqlite3 huita_bd.db < docs/schema.sql

PRAGMA foreign_keys = ON;

-- Пользователи: арендодатель (owner) и арендатор (tenant)
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('owner', 'tenant')),
    full_name TEXT,
    email TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Объекты с индивидуальными тарифами
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

-- Связь арендатора с объектом
CREATE TABLE IF NOT EXISTS tenant_properties (
    tenant_id INTEGER NOT NULL,
    property_id INTEGER NOT NULL,
    PRIMARY KEY (tenant_id, property_id),
    FOREIGN KEY (tenant_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (property_id) REFERENCES properties(id) ON DELETE CASCADE
);

-- Показания счётчиков: одно на объект и дату
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

-- Счета, созданные автоматически при вводе показаний
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

-- Миграция для баз, созданных до появления отметки об оплате.
-- Выполняется автоматически (models.migrate_db()), приведена здесь для справки:
--
--   ALTER TABLE invoices ADD COLUMN paid BOOLEAN DEFAULT 0;
