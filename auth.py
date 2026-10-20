from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from models import User, hash_password, check_password, init_db
from extensions import get_db_connection

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        role = request.form['role']
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip()
        if not username or not password:
            flash('Имя пользователя и пароль обязательны.', 'danger')
            return render_template('register.html')
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('SELECT id FROM users WHERE username = ?', (username,))
        if cur.fetchone():
            flash('Пользователь с таким именем уже существует.', 'danger')
            conn.close()
            return render_template('register.html')
        hashed = hash_password(password)
        cur.execute('''
            INSERT INTO users (username, password_hash, role, full_name, email)
            VALUES (?, ?, ?, ?, ?)
        ''', (username, hashed, role, full_name, email))
        user_id = cur.lastrowid
        if role == 'tenant':
            property_id = request.form.get('property_id')
            if property_id:
                cur.execute('SELECT id FROM properties WHERE id = ?', (property_id,))
                if cur.fetchone():
                    cur.execute('INSERT INTO tenant_properties (tenant_id, property_id) VALUES (?, ?)',
                                (user_id, property_id))
                else:
                    flash('Выбранный объект не найден.', 'danger')
                    conn.close()
                    return render_template('register.html')
            else:
                flash('Для арендатора необходимо выбрать объект.', 'danger')
                conn.close()
                return render_template('register.html')
        conn.commit()
        conn.close()
        flash('Регистрация успешна! Теперь войдите.', 'success')
        return redirect(url_for('auth.login'))
    else:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('SELECT id, address FROM properties ORDER BY address')
        properties = cur.fetchall()
        conn.close()
        return render_template('register.html', properties=properties)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('SELECT id, username, password_hash, role, full_name FROM users WHERE username = ?', (username,))
        user = cur.fetchone()
        conn.close()
        if user and check_password(password, user['password_hash']):
            user_obj = User(user['id'], user['username'], user['role'], user['full_name'])
            login_user(user_obj)
            flash('Вы вошли в систему.', 'success')
            return redirect(url_for('main.dashboard'))
        else:
            flash('Неверное имя пользователя или пароль.', 'danger')
    return render_template('login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Вы вышли из системы.', 'info')
    return redirect(url_for('auth.login'))