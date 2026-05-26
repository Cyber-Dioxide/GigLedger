"""
FreelanceCash - Flask Application Factory
"""
import os
from flask import Flask, request as req, url_for as _url_for
from flask_login import LoginManager
from flask_bcrypt import Bcrypt
from .models import db, User

login_manager = LoginManager()
bcrypt = Bcrypt()
login_manager.login_view = 'auth.login'
login_manager.login_message_category = 'info'

# Use lower bcrypt rounds for the sandbox environment
bcrypt._bcrypt_rounds = 4

CURRENCY_SYMBOLS = {
    'USD': '$', 'EUR': '€', 'GBP': '£',
    'CAD': 'C$', 'AUD': 'A$', 'INR': '₹', 'JPY': '¥'
}


def create_app():
    app = Flask(__name__, template_folder='templates', static_folder='static')

    base_dir = os.path.abspath(os.path.dirname(__file__))
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(base_dir, 'freelancecash.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'freelancecash-dev-secret-key-2024')

    db.init_app(app)
    login_manager.init_app(app)
    bcrypt.init_app(app)

    # Custom Jinja2 filters
    @app.template_filter('money')
    def money_format(value):
        try:
            return f"{float(value):,.2f}"
        except Exception:
            return "0.00"

    @app.template_filter('decimal1')
    def decimal1_format(value):
        try:
            return f"{float(value):.1f}"
        except Exception:
            return "0.0"

    @app.template_filter('currency_symbol')
    def currency_symbol(code):
        return CURRENCY_SYMBOLS.get(code, '$')

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # After-request: inject XTransformPort into redirects
    @app.after_request
    def inject_transform_port(response):
        port = req.args.get('XTransformPort')
        if port and response.status_code in (301, 302, 303, 307, 308):
            location = response.headers.get('Location', '')
            if location and 'XTransformPort' not in location:
                sep = '&' if '?' in location else '?'
                response.headers['Location'] = f"{location}{sep}XTransformPort={port}"
        return response

    # Template context: url_port helper and xport variable
    @app.context_processor
    def inject_port():
        port = req.args.get('XTransformPort', '')

        def url_port(endpoint, **kwargs):
            url = _url_for(endpoint, **kwargs)
            if port:
                sep = '&' if '?' in url else '?'
                return f"{url}{sep}XTransformPort={port}"
            return url

        return {'xport': port, 'url_port': url_port, 'currency_symbols': CURRENCY_SYMBOLS}

    # Register blueprints
    from .routes.auth import auth_bp
    from .routes.dashboard import dashboard_bp
    from .routes.transactions import transactions_bp
    from .routes.taxes import taxes_bp
    from .routes.settings import settings_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(transactions_bp)
    app.register_blueprint(taxes_bp)
    app.register_blueprint(settings_bp)

    with app.app_context():
        db.create_all()
        _migrate_db(db)
        _seed_demo_data()

    return app


def _migrate_db(db):
    """Add new columns to existing tables if they don't exist."""
    import sqlite3
    base_dir = os.path.abspath(os.path.dirname(__file__))
    db_path = os.path.join(base_dir, 'freelancecash.db')
    if not os.path.exists(db_path):
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Check existing columns in users table
    cursor.execute("PRAGMA table_info(users)")
    existing_columns = {row[1] for row in cursor.fetchall()}

    if 'custom_income_categories' not in existing_columns:
        cursor.execute("ALTER TABLE users ADD COLUMN custom_income_categories TEXT DEFAULT ''")
    if 'custom_expense_categories' not in existing_columns:
        cursor.execute("ALTER TABLE users ADD COLUMN custom_expense_categories TEXT DEFAULT ''")
    if 'theme' not in existing_columns:
        cursor.execute("ALTER TABLE users ADD COLUMN theme VARCHAR(20) DEFAULT 'emerald'")
    if 'dark_mode' not in existing_columns:
        cursor.execute("ALTER TABLE users ADD COLUMN dark_mode BOOLEAN DEFAULT 0")

    conn.commit()
    conn.close()


def _seed_demo_data():
    from .models import User, Transaction
    from flask_bcrypt import generate_password_hash

    if User.query.filter_by(email='demo@freelancecash.com').first():
        return

    password_hash = generate_password_hash('demo1234').decode('utf-8')
    demo_user = User(email='demo@freelancecash.com', password_hash=password_hash,
                     default_tax_rate=0.30, currency='USD')
    db.session.add(demo_user)
    db.session.commit()

    from datetime import datetime, timedelta
    import random

    cat_income = ['Client Payment', 'Consulting', 'Freelance Project', 'Royalty']
    cat_expense_deductible = ['Software', 'Internet', 'Office Supplies', 'Marketing']
    cat_expense_nondeduct = ['Travel', 'Equipment', 'Meal', 'Entertainment']

    desc_income = [
        'Website redesign for Acme Corp', 'Monthly retainer - StartupXYZ',
        'Logo design - Brew Co', 'Backend API - TechFlow', 'UI/UX audit - HealthApp',
        'Consulting call - FinGroup', 'E-commerce setup - ShopLocal', 'App prototype - EduTech',
        'Brand guidelines - GreenCo', 'Data visualization - AnalyticsPro',
        'Mobile app - FitTracker', 'SEO audit - LawFirm Associates',
        'Content strategy - MediaBuzz', 'WordPress theme - BakerDelight',
        'API integration - PayGate Inc'
    ]
    desc_expense_ded = [
        'Figma subscription', 'AWS hosting', 'Adobe Creative Cloud', 'Domain renewal',
        'Co-working space', 'Internet bill', 'Slack subscription', 'Notion Pro',
        'Email hosting', 'GitHub Pro', 'VS Code extensions', 'Cloud storage'
    ]
    desc_expense_non = [
        'Uber to client meeting', 'LinkedIn Premium', 'Conference ticket',
        'New mechanical keyboard', 'Coffee meetings', 'Printing services',
        'Team lunch', 'Co-working day pass', 'Uber ride', 'Parking fee'
    ]

    transactions = []
    now = datetime.now()

    # Generate 6 months of data
    for month_offset in range(5, -1, -1):
        month_date = now - timedelta(days=month_offset * 30)
        year = month_date.year
        month = month_date.month

        # 2-4 income transactions per month
        num_income = random.randint(2, 4)
        for _ in range(num_income):
            day = random.randint(1, min(28, month_date.day))
            tx_date = datetime(year, month, day, random.randint(9, 17), random.randint(0, 59))
            transactions.append(Transaction(
                user_id=demo_user.id,
                amount=round(random.uniform(800, 4500), 2),
                date=tx_date,
                category=random.choice(cat_income),
                description=random.choice(desc_income),
                is_tax_deductible=False,
                source='manual'
            ))

        # 2-3 deductible expenses per month
        for _ in range(random.randint(2, 3)):
            day = random.randint(1, min(28, month_date.day))
            tx_date = datetime(year, month, day, random.randint(9, 17), random.randint(0, 59))
            transactions.append(Transaction(
                user_id=demo_user.id,
                amount=-round(random.uniform(15, 250), 2),
                date=tx_date,
                category=random.choice(cat_expense_deductible),
                description=random.choice(desc_expense_ded),
                is_tax_deductible=True,
                source='manual'
            ))

        # 1-2 non-deductible expenses per month
        for _ in range(random.randint(1, 2)):
            day = random.randint(1, min(28, month_date.day))
            tx_date = datetime(year, month, day, random.randint(9, 17), random.randint(0, 59))
            transactions.append(Transaction(
                user_id=demo_user.id,
                amount=-round(random.uniform(10, 150), 2),
                date=tx_date,
                category=random.choice(cat_expense_nondeduct),
                description=random.choice(desc_expense_non),
                is_tax_deductible=False,
                source='manual'
            ))

    db.session.add_all(transactions)
    db.session.commit()
