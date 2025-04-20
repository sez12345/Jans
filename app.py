from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file  # Add flash and send_file
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate  # Импортируем Migrate
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import requests  # Add this import for Telegram API
from flask_apscheduler import APScheduler  # Add this import for scheduling tasks
from flask_weasyprint import render_pdf  # Add this import for PDF generation
from weasyprint import HTML  # Add this import for PDF generation

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///tax_platform.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

migrate = Migrate(app, db)  # Перемещаем сюда

app.secret_key = 'your_secret_key'

BOT_TOKEN = '7535906677:AAFr3UtqWhxSNGONTqpTmTv01gAZMVgGXUk'
CHAT_ID = '1131108787'  # Replace with your actual chat ID

def send_telegram_notification(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {
        "chat_id": CHAT_ID,
        "text": message
    }
    requests.post(url, data=data)

scheduler = APScheduler()
scheduler.init_app(app)
scheduler.start()

def send_daily_reminders():
    today = datetime.now().date()
    taxes = Tax.query.all()

    for tax in taxes:
        try:
            due_date = datetime.strptime(tax.due_date, '%d.%m.%Y').date()
        except ValueError:
            continue

        days_left = (due_date - today).days

        if tax.status == 'Не оплачен' and 0 <= days_left <= 7:
            send_telegram_notification(f"⏰ Напоминание: Срок оплаты налога \"{tax.type}\" истекает {tax.due_date}.")
        elif tax.status == 'Не оплачен' and days_left < 0:
            send_telegram_notification(f"⚠️ Просрочен налог: \"{tax.type}\". Срок оплаты был {tax.due_date}.")

def send_benefit_notifications():
    requests = BenefitRequest.query.filter(BenefitRequest.status.in_(['Принято', 'Отклонено'])).all()

    for request in requests:
        user = User.query.get(request.user_id)
        if request.status == 'Принято':
            send_telegram_notification(f"✅ Ваша заявка на льготу \"{request.description}\" была одобрена.")
        elif request.status == 'Отклонено':
            send_telegram_notification(f"❌ Ваша заявка на льготу \"{request.description}\" была отклонена.")

# Schedule tasks
scheduler.add_job(id='daily_reminders', func=send_daily_reminders, trigger='cron', hour=9)  # Every day at 9:00 AM
scheduler.add_job(id='benefit_notifications', func=send_benefit_notifications, trigger='interval', minutes=30)  # Every 30 minutes

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class BenefitRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    description = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='На рассмотрении')

class Tax(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(100), nullable=False)
    rate = db.Column(db.Float, nullable=False)  # Изменяем тип на Float
    due_date = db.Column(db.String(20), nullable=False)  # Срок оплаты
    status = db.Column(db.String(20), default='Не оплачен')  # Статус налога
    base_income = db.Column(db.Float, default=100000)  # Доход налогоплательщика (по умолчанию 100 000 ₸)

    def calculate_tax(self):
        return round((self.rate / 100) * self.base_income, 2)  # Рассчитываем сумму налога

@app.before_request
def initialize_database():
    if not hasattr(app, 'db_initialized'):
        db.create_all()  # Создает все таблицы, определенные в моделях
        app.db_initialized = True

@app.context_processor
def inject_user_role():
    role = session.get('role', None)
    return {'user_role': role}

@app.route('/logout')
def logout():
    session.clear()  # Очищаем сессию
    return redirect(url_for('index'))  # Перенаправляем на главную страницу

@app.route('/')                     
def index():
    return render_template('index.html')            

@app.route('/home')
def home():
    if 'user_id' not in session:
        return redirect(url_for('index'))
    
    # Render the home page for all logged-in users
    return render_template('home.html')

@app.route('/taxpayer')
def taxpayer():
    if session.get('role') != 'taxpayer':
        return redirect(url_for('index'))
    return render_template('taxpayer.html')

@app.route('/employee')
def employee():
    if session.get('role') != 'employee':
        return redirect(url_for('index'))
    return render_template('employee.html')

# Маршруты для налогоплательщиков
@app.route('/taxpayer/taxes', methods=['GET', 'POST'])
def taxpayer_taxes():
    if session.get('role') != 'taxpayer':
        return redirect(url_for('index'))
    taxes = Tax.query.all()
    for tax in taxes:
        tax.amount = tax.calculate_tax()  # Рассчитываем сумму налога
    if request.method == 'POST':
        tax_id = request.form['tax_id']
        tax = Tax.query.get(tax_id)
        tax.status = 'Оплачен'
        db.session.commit()
    return render_template('taxes.html', taxes=taxes)

@app.route('/taxpayer/notifications')
def taxpayer_notifications():
    if session.get('role') != 'taxpayer':
        return redirect(url_for('index'))

    # Получаем текущую дату
    today = datetime.now().date()

    # Генерация уведомлений
    notifications = []
    taxes = Tax.query.all()
    for tax in taxes:
        try:
            # Попытка преобразовать дату в формате дд.мм.гггг
            due_date = datetime.strptime(tax.due_date, '%d.%m.%Y').date()
        except ValueError as e:
            print(f"Ошибка преобразования даты для налога {tax.type}: {e}")
            continue

        days_left = (due_date - today).days

        if tax.status == 'Не оплачен' and days_left < 0:
            notifications.append({"message": f"Просрочен налог: {tax.type}. Срок оплаты был {tax.due_date}."})
        elif tax.status == 'Не оплачен' and 0 <= days_left <= 7:
            notifications.append({"message": f"Срок оплаты налога {tax.type} истекает {tax.due_date}."})
        elif tax.status == 'Оплачен':
            notifications.append({"message": f"Налог \"{tax.type}\" успешно оплачен."})

    # Debugging: Log notifications to ensure they are generated
    print(f"Сгенерированные уведомления: {notifications}")
    return render_template('notifications.html', notifications=notifications)

@app.route('/taxpayer/payment_history')
def taxpayer_payment_history():
    if session.get('role') != 'taxpayer':
        return redirect(url_for('index'))
    
    # Fetch payment history dynamically from the database
    history = Tax.query.filter_by(status='Оплачен').all()
    payment_history = [
        {
            "date": tax.due_date,
            "type": tax.type,
            "amount": f"{tax.calculate_tax():,.2f}₸".replace(",", " ")
        }
        for tax in history
    ]
    
    return render_template('payment_history.html', history=payment_history)

@app.route('/taxpayer/benefit_requests', methods=['GET', 'POST'])
def taxpayer_benefit_requests():
    if session.get('role') != 'taxpayer':
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        description = request.form.get('description')  # Get the description from the form
        if not description:
            return "Описание заявки не может быть пустым", 400  # Handle empty description
        
        # Create a new benefit request
        new_request = BenefitRequest(user_id=session['user_id'], description=description)
        db.session.add(new_request)
        db.session.commit()
    
    # Fetch all benefit requests for the logged-in user
    requests = BenefitRequest.query.filter_by(user_id=session['user_id']).all()
    return render_template('benefit_requests.html', requests=requests)

# Маршруты для сотрудников
@app.route('/employee/manage_taxes', methods=['GET', 'POST'])
def employee_manage_taxes():
    if session.get('role') != 'employee':
        return redirect(url_for('index'))
    if request.method == 'POST':
        tax_type = request.form['type']
        tax_rate = float(request.form['rate'])  # Убедимся, что ставка преобразована в число
        due_date = request.form['due_date']
        new_tax = Tax(type=tax_type, rate=tax_rate, due_date=due_date)
        db.session.add(new_tax)
        db.session.commit()

        # Send Telegram notification
        send_telegram_notification(f"📢 Новый налог добавлен: {tax_type} со ставкой {tax_rate}% и сроком оплаты {due_date}.")

    taxes = Tax.query.all()
    return render_template('manage_taxes.html', taxes=taxes)

@app.route('/employee/process_benefits', methods=['GET', 'POST'])
def employee_process_benefits():
    if session.get('role') != 'employee':
        return redirect(url_for('index'))
    if request.method == 'POST':
        request_id = request.form['request_id']
        action = request.form['action']
        benefit_request = BenefitRequest.query.get(request_id)
        benefit_request.status = 'Принято' if action == 'accept' else 'Отклонено'
        db.session.commit()
    requests = BenefitRequest.query.all()
    return render_template('process_benefits.html', benefits=requests)

@app.route('/employee/reports', methods=['GET'])
def employee_reports():
    if session.get('role') != 'employee':
        return redirect(url_for('index'))

    # Подсчёт собранных налогов
    taxes_paid = db.session.query(Tax).filter_by(status='Оплачен').all()
    total_taxes_collected = sum(tax.calculate_tax() for tax in taxes_paid)

    # Подсчёт ожидаемых налогов
    taxes_pending = db.session.query(Tax).filter_by(status='Не оплачен').all()
    pending_taxes = sum(tax.calculate_tax() for tax in taxes_pending)

    # Подсчёт заявок на льготы
    benefit_requests = db.session.query(BenefitRequest).count()

    # Формируем отчёт
    report = {
        "total_taxes_collected": f"{total_taxes_collected:,.2f}₸".replace(",", " "),
        "pending_taxes": f"{pending_taxes:,.2f}₸".replace(",", " "),
        "benefit_requests": benefit_requests,
    }

    return render_template('reports.html', report=report)

@app.route('/employee/reports/download', methods=['GET'])
def download_report():
    if session.get('role') != 'employee':
        return redirect(url_for('index'))

    # Fetch data from the database
    taxes_paid = db.session.query(Tax).filter_by(status='Оплачен').all()
    total_taxes_collected = sum(tax.calculate_tax() for tax in taxes_paid)

    taxes_pending = db.session.query(Tax).filter_by(status='Не оплачен').all()
    pending_taxes = sum(tax.calculate_tax() for tax in taxes_pending)

    benefit_requests = db.session.query(BenefitRequest).count()

    # Prepare the report data
    report = {
        "total_taxes_collected": f"{total_taxes_collected:,.2f}₸".replace(",", " "),
        "pending_taxes": f"{pending_taxes:,.2f}₸".replace(",", " "),
        "benefit_requests": benefit_requests,
    }

    # Render the PDF template
    html = render_template('report_pdf.html', report=report)

    # Return the PDF
    return render_pdf(HTML(string=html), download_filename="report.pdf")

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        role = request.form['role']

        # Проверка на существование пользователя
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash(f"Пользователь с именем '{username}' уже существует. Пожалуйста, выберите другое имя.", "error")
            return redirect(url_for('register'))

        # Создание нового пользователя
        user = User(username=username, role=role)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        flash("Регистрация прошла успешно! Теперь вы можете войти.", "success")
        return redirect(url_for('login'))  # Перенаправление на страницу логина
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Проверка пользователя
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            session['user_id'] = user.id
            session['role'] = user.role
            flash('Вы успешно вошли!', 'success')
            return redirect(url_for('home'))  # Перенаправление на главную страницу

        flash('Неверное имя пользователя или пароль.', 'error')
        return redirect(url_for('login'))
    return render_template('index.html')

if __name__ == '__main__':
    from os import environ
    port = int(environ.get('PORT', 5000))  # Use the PORT environment variable or default to 5000
    app.run(host='0.0.0.0', port=port)