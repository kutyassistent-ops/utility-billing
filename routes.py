from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from datetime import date, datetime
from models import (
    get_last_reading, get_property_tariffs, calculate_total,
    get_debt, get_stats_data
)
from extensions import get_db_connection

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def home():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    return redirect(url_for('auth.login'))

@main_bp.route('/dashboard')
@login_required
def dashboard():
    conn = get_db_connection()
    cur = conn.cursor()
    if current_user.role == 'owner':
        cur.execute('SELECT id, address FROM properties WHERE owner_id = ?', (current_user.id,))
        properties = cur.fetchall()
        props_data = []
        for prop in properties:
            last = get_last_reading(prop['id'])
            invoice = None
            if last:
                cur.execute('SELECT total FROM invoices WHERE property_id = ? AND reading_id = (SELECT id FROM meter_readings WHERE property_id = ? ORDER BY date DESC LIMIT 1)', (prop['id'], prop['id']))
                inv = cur.fetchone()
                if inv:
                    invoice = inv['total']
            debt = get_debt(prop['id'])
            props_data.append({
                'id': prop['id'],
                'address': prop['address'],
                'last_reading': last,
                'last_invoice': invoice,
                'debt': debt
            })
        conn.close()
        return render_template('dashboard_owner.html', properties=props_data)
    else:
        cur.execute('''
            SELECT p.id, p.address 
            FROM properties p
            JOIN tenant_properties tp ON p.id = tp.property_id
            WHERE tp.tenant_id = ?
        ''', (current_user.id,))
        prop = cur.fetchone()
        conn.close()
        if prop:
            last = get_last_reading(prop['id'])
            invoice = None
            if last:
                conn2 = get_db_connection()
                cur2 = conn2.cursor()
                cur2.execute('SELECT total FROM invoices WHERE property_id = ? AND reading_id = (SELECT id FROM meter_readings WHERE property_id = ? ORDER BY date DESC LIMIT 1)', (prop['id'], prop['id']))
                inv = cur2.fetchone()
                conn2.close()
                if inv:
                    invoice = inv['total']
            debt = get_debt(prop['id'])
            return render_template('dashboard_tenant.html', property=prop, last_reading=last, last_invoice=invoice, debt=debt)
        else:
            flash('У вас нет привязанных объектов. Обратитесь к арендодателю.', 'warning')
            return render_template('dashboard_tenant.html', property=None, debt=0)

@main_bp.route('/add_property', methods=['GET', 'POST'])
@login_required
def add_property():
    if current_user.role != 'owner':
        flash('Только арендодатели могут добавлять объекты.', 'danger')
        return redirect(url_for('main.dashboard'))
    if request.method == 'POST':
        address = request.form['address'].strip()
        if not address:
            flash('Адрес обязателен.', 'danger')
            return render_template('add_property.html')
        tariff_el = float(request.form.get('tariff_el', 2.73))
        tariff_water = float(request.form.get('tariff_water', 31.21))
        tariff_com1 = float(request.form.get('tariff_com1', 72.83))
        tariff_com2 = float(request.form.get('tariff_com2', 21.95))
        fixed_fee = float(request.form.get('fixed_fee', 17000))
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('''
            INSERT INTO properties (owner_id, address, tariff_el, tariff_water, tariff_com1, tariff_com2, fixed_fee)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (current_user.id, address, tariff_el, tariff_water, tariff_com1, tariff_com2, fixed_fee))
        conn.commit()
        conn.close()
        flash('Объект добавлен.', 'success')
        return redirect(url_for('main.dashboard'))
    return render_template('add_property.html')

@main_bp.route('/edit_property/<int:property_id>', methods=['GET', 'POST'])
@login_required
def edit_property(property_id):
    if current_user.role != 'owner':
        flash('Только арендодатели могут редактировать объекты.', 'danger')
        return redirect(url_for('main.dashboard'))
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT * FROM properties WHERE id = ? AND owner_id = ?', (property_id, current_user.id))
    prop = cur.fetchone()
    if not prop:
        flash('Объект не найден или у вас нет доступа.', 'danger')
        conn.close()
        return redirect(url_for('main.dashboard'))
    if request.method == 'POST':
        address = request.form['address'].strip()
        if not address:
            flash('Адрес обязателен.', 'danger')
            conn.close()
            return render_template('edit_property.html', prop=prop)
        tariff_el = float(request.form.get('tariff_el', 2.73))
        tariff_water = float(request.form.get('tariff_water', 31.21))
        tariff_com1 = float(request.form.get('tariff_com1', 72.83))
        tariff_com2 = float(request.form.get('tariff_com2', 21.95))
        fixed_fee = float(request.form.get('fixed_fee', 17000))
        cur.execute('''
            UPDATE properties
            SET address = ?, tariff_el = ?, tariff_water = ?, tariff_com1 = ?, tariff_com2 = ?, fixed_fee = ?
            WHERE id = ? AND owner_id = ?
        ''', (address, tariff_el, tariff_water, tariff_com1, tariff_com2, fixed_fee, property_id, current_user.id))
        conn.commit()
        conn.close()
        flash('Тарифы и адрес обновлены.', 'success')
        return redirect(url_for('main.dashboard'))
    conn.close()
    return render_template('edit_property.html', prop=prop)

@main_bp.route('/add_reading', methods=['GET', 'POST'])
@login_required
def add_reading():
    conn = get_db_connection()
    cur = conn.cursor()
    if current_user.role == 'owner':
        cur.execute('SELECT id, address FROM properties WHERE owner_id = ?', (current_user.id,))
        properties = cur.fetchall()
    else:
        cur.execute('''
            SELECT p.id, p.address 
            FROM properties p
            JOIN tenant_properties tp ON p.id = tp.property_id
            WHERE tp.tenant_id = ?
        ''', (current_user.id,))
        properties = cur.fetchall()
    conn.close()
    if not properties:
        flash('У вас нет объектов для ввода показаний.', 'warning')
        return redirect(url_for('main.dashboard'))
    if request.method == 'POST':
        property_id = int(request.form['property_id'])
        if property_id not in [p['id'] for p in properties]:
            flash('Нет доступа к этому объекту.', 'danger')
            return render_template('add_reading.html', properties=properties)
        try:
            hot_water = int(request.form['hot_water'])
            cool_water = int(request.form['cool_water'])
            electricity = int(request.form['electricity'])
            input_date = request.form.get('date', '').strip()
            if input_date:
                datetime.strptime(input_date, '%Y-%m-%d')
                reading_date = input_date
            else:
                reading_date = date.today().isoformat()
        except ValueError:
            flash('Неверный формат данных (показания должны быть целыми числами, дата – YYYY-MM-DD).', 'danger')
            return render_template('add_reading.html', properties=properties)
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('SELECT id FROM meter_readings WHERE property_id = ? AND date = ?', (property_id, reading_date))
        if cur.fetchone():
            flash(f'Показания за {reading_date} уже введены для этого объекта.', 'warning')
            conn.close()
            return render_template('add_reading.html', properties=properties)
        prev = get_last_reading(property_id)
        if prev:
            if hot_water < prev['hot_water'] or cool_water < prev['cool_water'] or electricity < prev['electricity']:
                flash('Новые показания не могут быть меньше предыдущих.', 'danger')
                conn.close()
                return render_template('add_reading.html', properties=properties)
        cur.execute('''
            INSERT INTO meter_readings (property_id, user_id, date, hot_water, cool_water, electricity)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (property_id, current_user.id, reading_date, hot_water, cool_water, electricity))
        reading_id = cur.lastrowid
        tariffs = get_property_tariffs(property_id)
        reading = {'hot_water': hot_water, 'cool_water': cool_water, 'electricity': electricity}
        details = calculate_total(reading, prev, tariffs)
        cur.execute('''
            INSERT INTO invoices (property_id, reading_id, total, details)
            VALUES (?, ?, ?, ?)
        ''', (property_id, reading_id, details['total'], str(details)))
        conn.commit()
        conn.close()
        flash('Показания сохранены, сумма рассчитана.', 'success')
        return redirect(url_for('main.dashboard'))
    return render_template('add_reading.html', properties=properties)

@main_bp.route('/history/<int:property_id>')
@login_required
def history(property_id):
    conn = get_db_connection()
    cur = conn.cursor()
    if current_user.role == 'owner':
        cur.execute('SELECT id FROM properties WHERE id = ? AND owner_id = ?', (property_id, current_user.id))
    else:
        cur.execute('''
            SELECT p.id FROM properties p
            JOIN tenant_properties tp ON p.id = tp.property_id
            WHERE p.id = ? AND tp.tenant_id = ?
        ''', (property_id, current_user.id))
    if not cur.fetchone():
        flash('Нет доступа к истории этого объекта.', 'danger')
        conn.close()
        return redirect(url_for('main.dashboard'))
    cur.execute('''
        SELECT r.date, r.hot_water, r.cool_water, r.electricity, i.total, i.id as invoice_id, i.paid, u.username as entered_by
        FROM meter_readings r
        JOIN invoices i ON r.id = i.reading_id
        JOIN users u ON r.user_id = u.id
        WHERE r.property_id = ?
        ORDER BY r.date DESC
    ''', (property_id,))
    records = cur.fetchall()
    conn.close()
    return render_template('history.html', records=records, property_id=property_id, user_role=current_user.role)

@main_bp.route('/pay/<int:invoice_id>', methods=['POST'])
@login_required
def mark_paid(invoice_id):
    # Только владелец может подтверждать оплату
    if current_user.role != 'owner':
        flash('Только арендодатель может подтверждать оплату.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('''
        SELECT i.property_id, p.owner_id
        FROM invoices i
        JOIN properties p ON i.property_id = p.id
        WHERE i.id = ?
    ''', (invoice_id,))
    row = cur.fetchone()
    if not row:
        flash('Счёт не найден.', 'danger')
        conn.close()
        return redirect(url_for('main.dashboard'))
    
    property_id = row['property_id']
    owner_id = row['owner_id']
    
    if current_user.id != owner_id:
        flash('Вы не являетесь владельцем этого объекта.', 'danger')
        conn.close()
        return redirect(url_for('main.dashboard'))
    
    cur.execute('UPDATE invoices SET paid = 1 WHERE id = ?', (invoice_id,))
    conn.commit()
    conn.close()
    flash('Счёт отмечен как оплаченный.', 'success')
    return redirect(url_for('main.history', property_id=property_id))

@main_bp.route('/stats')
@login_required
def stats():
    conn = get_db_connection()
    cur = conn.cursor()
    if current_user.role == 'owner':
        cur.execute('SELECT id, address FROM properties WHERE owner_id = ?', (current_user.id,))
        properties = cur.fetchall()
    else:
        cur.execute('''
            SELECT p.id, p.address 
            FROM properties p
            JOIN tenant_properties tp ON p.id = tp.property_id
            WHERE tp.tenant_id = ?
        ''', (current_user.id,))
        properties = cur.fetchall()
    conn.close()
    if not properties:
        flash('У вас нет объектов для просмотра статистики.', 'warning')
        return redirect(url_for('main.dashboard'))
    property_id = request.args.get('property_id', type=int, default=properties[0]['id'])
    months_back = request.args.get('months', type=int, default=6)
    if property_id not in [p['id'] for p in properties]:
        property_id = properties[0]['id']
    data = get_stats_data(property_id, months_back)
    return render_template('stats.html',
                           properties=properties,
                           selected_property=property_id,
                           selected_months=months_back,
                           data=data)