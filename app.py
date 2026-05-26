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
    from .routes.clients import clients_bp
    from .routes.projects import projects_bp
    from .routes.reports import reports_bp
    from .routes.invoices import invoices_bp
    from .routes.goals import goals_bp
    from .routes.recurring import recurring_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(transactions_bp)
    app.register_blueprint(taxes_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(clients_bp)
    app.register_blueprint(projects_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(invoices_bp)
    app.register_blueprint(goals_bp)
    app.register_blueprint(recurring_bp)

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
    if 'business_name' not in existing_columns:
        cursor.execute("ALTER TABLE users ADD COLUMN business_name VARCHAR(200) DEFAULT ''")
    if 'business_address' not in existing_columns:
        cursor.execute("ALTER TABLE users ADD COLUMN business_address TEXT DEFAULT ''")
    if 'business_phone' not in existing_columns:
        cursor.execute("ALTER TABLE users ADD COLUMN business_phone VARCHAR(50) DEFAULT ''")
    if 'invoice_note' not in existing_columns:
        cursor.execute("ALTER TABLE users ADD COLUMN invoice_note TEXT DEFAULT 'Thank you for your business!'")
    if 'invoice_prefix' not in existing_columns:
        cursor.execute("ALTER TABLE users ADD COLUMN invoice_prefix VARCHAR(10) DEFAULT 'INV'")
    if 'next_invoice_number' not in existing_columns:
        cursor.execute("ALTER TABLE users ADD COLUMN next_invoice_number INTEGER DEFAULT 1")

    # Migrate transactions table
    cursor.execute("PRAGMA table_info(transactions)")
    tx_columns = {row[1] for row in cursor.fetchall()}
    if 'invoice_id' not in tx_columns:
        cursor.execute("ALTER TABLE transactions ADD COLUMN invoice_id INTEGER REFERENCES invoices(id)")

    # Migrate tax_estimates table - fix foreign key
    cursor.execute("PRAGMA table_info(tax_estimates)")
    te_columns = {row[1] for row in cursor.fetchall()}
    if 'user_id' not in te_columns:
        cursor.execute("ALTER TABLE tax_estimates ADD COLUMN user_id INTEGER REFERENCES users(id)")

    conn.commit()
    conn.close()


def _seed_demo_data():
    from .models import (User, Transaction, Client, Invoice, InvoiceLineItem,
                          Project, Goal, RecurringTransaction)
    from flask_bcrypt import generate_password_hash

    if User.query.filter_by(email='demo@freelancecash.com').first():
        return

    password_hash = generate_password_hash('demo1234').decode('utf-8')
    demo_user = User(email='demo@freelancecash.com', password_hash=password_hash,
                     default_tax_rate=0.30, currency='USD',
                     business_name='Demo Freelance Studio',
                     business_address='123 Creative Ave, San Francisco, CA 94102',
                     business_phone='+1 (555) 123-4567',
                     invoice_note='Payment due within 30 days. Thank you for your business!')
    db.session.add(demo_user)
    db.session.commit()

    from datetime import datetime, timedelta
    import random

    # ---- Create Clients ----
    clients_data = [
        {'name': 'Acme Corp', 'email': 'billing@acmecorp.com', 'phone': '+1 (555) 100-2000',
         'company': 'Acme Corporation', 'address': '456 Business Blvd, New York, NY 10001',
         'notes': 'Large enterprise client. Net-30 payment terms.'},
        {'name': 'StartupXYZ', 'email': 'finance@startupxyz.io', 'phone': '+1 (555) 200-3000',
         'company': 'StartupXYZ Inc', 'address': '789 Innovation Way, Austin, TX 73301',
         'notes': 'Monthly retainer. Fast-growing SaaS startup.'},
        {'name': 'Brew Co', 'email': 'hello@brewco.com', 'phone': '+1 (555) 300-4000',
         'company': 'Brew Co', 'address': '12 Hops Lane, Portland, OR 97201',
         'notes': 'Craft brewery. Logo and branding work.'},
        {'name': 'TechFlow', 'email': 'accounts@techflow.dev', 'phone': '+1 (555) 400-5000',
         'company': 'TechFlow Solutions', 'address': '321 Dev Street, Seattle, WA 98101',
         'notes': 'Backend API development project.'},
        {'name': 'HealthApp', 'email': 'design@healthapp.co', 'phone': '+1 (555) 500-6000',
         'company': 'HealthApp Inc', 'address': '55 Wellness Dr, Denver, CO 80201',
         'notes': 'UI/UX audit and redesign project.'},
        {'name': 'GreenCo', 'email': 'media@greenco.org', 'phone': '+1 (555) 600-7000',
         'company': 'GreenCo Sustainability', 'address': '88 Eco Lane, Boulder, CO 80301',
         'notes': 'Brand guidelines and sustainability report design.'},
        {'name': 'FinGroup', 'email': 'ops@fingroup.com', 'phone': '+1 (555) 700-8000',
         'company': 'FinGroup Advisory', 'address': '200 Finance St, Chicago, IL 60601',
         'notes': 'Weekly consulting calls.'},
        {'name': 'EduTech', 'email': 'dev@edutech.io', 'phone': '+1 (555) 800-9000',
         'company': 'EduTech Learning', 'address': '77 Campus Way, Boston, MA 02101',
         'notes': 'App prototype development.'},
    ]
    client_objects = []
    for cd in clients_data:
        c = Client(user_id=demo_user.id, **cd)
        db.session.add(c)
        client_objects.append(c)
    db.session.commit()

    # ---- Create Projects ----
    project_colors = ['#34d399', '#60a5fa', '#fbbf24', '#fb7185', '#a78bfa', '#f472b6', '#2dd4bf', '#fb923c']
    projects_data = [
        {'name': 'Website Redesign', 'client_id': client_objects[0].id, 'description': 'Complete redesign of corporate website with modern UI/UX',
         'status': 'completed', 'rate_type': 'fixed', 'rate': 12000, 'hours_logged': 100, 'color': project_colors[0],
         'start_date': datetime.now() - timedelta(days=120), 'end_date': datetime.now() - timedelta(days=30), 'deadline': datetime.now() - timedelta(days=30)},
        {'name': 'Monthly Retainer', 'client_id': client_objects[1].id, 'description': 'Ongoing development and design support',
         'status': 'active', 'rate_type': 'hourly', 'rate': 125, 'hours_logged': 84, 'color': project_colors[1],
         'start_date': datetime.now() - timedelta(days=90), 'deadline': datetime.now() + timedelta(days=60)},
        {'name': 'Brand Identity', 'client_id': client_objects[2].id, 'description': 'Logo, brand guidelines, and packaging design',
         'status': 'active', 'rate_type': 'fixed', 'rate': 8000, 'hours_logged': 60, 'color': project_colors[2],
         'start_date': datetime.now() - timedelta(days=45), 'deadline': datetime.now() + timedelta(days=15)},
        {'name': 'API Development', 'client_id': client_objects[3].id, 'description': 'RESTful API for payment processing system',
         'status': 'active', 'rate_type': 'hourly', 'rate': 150, 'hours_logged': 42, 'color': project_colors[3],
         'start_date': datetime.now() - timedelta(days=60), 'deadline': datetime.now() + timedelta(days=30)},
        {'name': 'UX Audit & Redesign', 'client_id': client_objects[4].id, 'description': 'Full UX audit with redesign recommendations',
         'status': 'on_hold', 'rate_type': 'fixed', 'rate': 5500, 'hours_logged': 20, 'color': project_colors[4],
         'start_date': datetime.now() - timedelta(days=30), 'deadline': datetime.now() + timedelta(days=45)},
        {'name': 'Consulting', 'client_id': client_objects[6].id, 'description': 'Weekly strategy and tech consulting',
         'status': 'active', 'rate_type': 'hourly', 'rate': 200, 'hours_logged': 36, 'color': project_colors[5],
         'start_date': datetime.now() - timedelta(days=60), 'deadline': None},
        {'name': 'App Prototype', 'client_id': client_objects[7].id, 'description': 'Interactive prototype for educational app',
         'status': 'active', 'rate_type': 'fixed', 'rate': 6500, 'hours_logged': 35, 'color': project_colors[6],
         'start_date': datetime.now() - timedelta(days=20), 'deadline': datetime.now() + timedelta(days=40)},
    ]
    for pd in projects_data:
        p = Project(user_id=demo_user.id, **pd)
        db.session.add(p)
    db.session.commit()

    # ---- Create Invoices ----
    now = datetime.now()
    invoice_data = [
        # Paid invoices (past)
        {'client_id': client_objects[0].id, 'status': 'paid', 'invoice_number': 'INV-0001',
         'issue_date': now - timedelta(days=90), 'due_date': now - timedelta(days=60),
         'paid_date': now - timedelta(days=55), 'subtotal': 4000, 'tax_amount': 0, 'total': 4000,
         'line_items': [('Website redesign - Phase 1', 1, 4000, 4000)]},
        {'client_id': client_objects[1].id, 'status': 'paid', 'invoice_number': 'INV-0002',
         'issue_date': now - timedelta(days=60), 'due_date': now - timedelta(days=30),
         'paid_date': now - timedelta(days=25), 'subtotal': 5250, 'tax_amount': 0, 'total': 5250,
         'line_items': [('Development hours - 42hrs', 42, 125, 5250)]},
        {'client_id': client_objects[2].id, 'status': 'paid', 'invoice_number': 'INV-0003',
         'issue_date': now - timedelta(days=45), 'due_date': now - timedelta(days=15),
         'paid_date': now - timedelta(days=10), 'subtotal': 3000, 'tax_amount': 0, 'total': 3000,
         'line_items': [('Logo design & brand guide - Phase 1', 1, 3000, 3000)]},
        {'client_id': client_objects[0].id, 'status': 'paid', 'invoice_number': 'INV-0004',
         'issue_date': now - timedelta(days=30), 'due_date': now,
         'paid_date': now - timedelta(days=5), 'subtotal': 8000, 'tax_amount': 0, 'total': 8000,
         'line_items': [('Website redesign - Phase 2', 1, 8000, 8000)]},
        # Sent (outstanding) invoices
        {'client_id': client_objects[3].id, 'status': 'sent', 'invoice_number': 'INV-0005',
         'issue_date': now - timedelta(days=15), 'due_date': now + timedelta(days=15),
         'subtotal': 6300, 'tax_amount': 0, 'total': 6300,
         'line_items': [('API development - 42hrs', 42, 150, 6300)]},
        {'client_id': client_objects[1].id, 'status': 'sent', 'invoice_number': 'INV-0006',
         'issue_date': now - timedelta(days=10), 'due_date': now + timedelta(days=20),
         'subtotal': 5250, 'tax_amount': 0, 'total': 5250,
         'line_items': [('Development hours - 42hrs (March)', 42, 125, 5250)]},
        # Draft invoice
        {'client_id': client_objects[6].id, 'status': 'draft', 'invoice_number': 'INV-0007',
         'issue_date': now, 'due_date': now + timedelta(days=30),
         'subtotal': 7200, 'tax_amount': 0, 'total': 7200,
         'line_items': [('Consulting hours - 36hrs', 36, 200, 7200)]},
        # Overdue invoice
        {'client_id': client_objects[4].id, 'status': 'overdue', 'invoice_number': 'INV-0008',
         'issue_date': now - timedelta(days=45), 'due_date': now - timedelta(days=15),
         'subtotal': 2750, 'tax_amount': 0, 'total': 2750,
         'line_items': [('UX Audit - Phase 1', 1, 2750, 2750)]},
    ]
    invoice_objects = []
    for inv_data in invoice_data:
        li_data = inv_data.pop('line_items')
        inv = Invoice(user_id=demo_user.id, **inv_data)
        db.session.add(inv)
        db.session.flush()
        for desc, qty, rate, amt in li_data:
            db.session.add(InvoiceLineItem(invoice_id=inv.id, description=desc, quantity=qty, rate=rate, amount=amt))
        invoice_objects.append(inv)

        # Create transaction for paid invoices
        if inv.status == 'paid':
            tx = Transaction(user_id=demo_user.id, amount=inv.total, date=inv.paid_date or inv.issue_date,
                           category='Client Payment', description=f'Payment for {inv.invoice_number}',
                           is_tax_deductible=False, source='invoice', invoice_id=inv.id)
            db.session.add(tx)
    db.session.commit()

    # ---- Create Transactions (same as before but more) ----
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

    # ---- Create Goals ----
    goals_data = [
        {'name': 'Emergency Fund', 'target_amount': 10000, 'current_amount': 4200,
         'deadline': now + timedelta(days=180), 'icon': 'shield', 'color': '#34d399',
         'is_completed': False},
        {'name': 'New Laptop', 'target_amount': 2500, 'current_amount': 1800,
         'deadline': now + timedelta(days=60), 'icon': 'laptop', 'color': '#60a5fa',
         'is_completed': False},
        {'name': 'Vacation Fund', 'target_amount': 5000, 'current_amount': 5000,
         'deadline': now + timedelta(days=90), 'icon': 'palm_tree', 'color': '#fbbf24',
         'is_completed': True},
        {'name': 'Tax Reserve Q2', 'target_amount': 8000, 'current_amount': 5200,
         'deadline': now + timedelta(days=30), 'icon': 'government', 'color': '#fb7185',
         'is_completed': False},
        {'name': 'Conference Budget', 'target_amount': 3000, 'current_amount': 900,
         'deadline': now + timedelta(days=120), 'icon': 'rocket', 'color': '#a78bfa',
         'is_completed': False},
    ]
    for gd in goals_data:
        g = Goal(user_id=demo_user.id, **gd)
        db.session.add(g)
    db.session.commit()

    # ---- Create Recurring Transactions ----
    recurring_data = [
        {'description': 'Figma Subscription', 'amount': -15.00, 'category': 'Software',
         'is_tax_deductible': True, 'frequency': 'monthly', 'day_of_month': 1,
         'is_active': True, 'next_date': datetime(now.year, now.month, 1) if now.day < 1 else datetime(now.year, now.month + 1 if now.month < 12 else 1, 1)},
        {'description': 'AWS Hosting', 'amount': -52.00, 'category': 'Software',
         'is_tax_deductible': True, 'frequency': 'monthly', 'day_of_month': 5,
         'is_active': True, 'next_date': datetime(now.year, now.month, 5) if now.day < 5 else datetime(now.year, now.month + 1 if now.month < 12 else 1, 5)},
        {'description': 'Co-working Space', 'amount': -250.00, 'category': 'Office Supplies',
         'is_tax_deductible': True, 'frequency': 'monthly', 'day_of_month': 1,
         'is_active': True, 'next_date': datetime(now.year, now.month, 1) if now.day < 1 else datetime(now.year, now.month + 1 if now.month < 12 else 1, 1)},
        {'description': 'Internet Bill', 'amount': -79.99, 'category': 'Internet',
         'is_tax_deductible': True, 'frequency': 'monthly', 'day_of_month': 15,
         'is_active': True, 'next_date': datetime(now.year, now.month, 15) if now.day < 15 else datetime(now.year, now.month + 1 if now.month < 12 else 1, 15)},
        {'description': 'Adobe Creative Cloud', 'amount': -54.99, 'category': 'Software',
         'is_tax_deductible': True, 'frequency': 'monthly', 'day_of_month': 10,
         'is_active': True, 'next_date': datetime(now.year, now.month, 10) if now.day < 10 else datetime(now.year, now.month + 1 if now.month < 12 else 1, 10)},
        {'description': 'Domain Renewal', 'amount': -12.99, 'category': 'Software',
         'is_tax_deductible': True, 'frequency': 'yearly', 'day_of_month': 1,
         'is_active': True, 'next_date': datetime(now.year + 1, 1, 1)},
        {'description': 'LinkedIn Premium', 'amount': -29.99, 'category': 'Marketing',
         'is_tax_deductible': False, 'frequency': 'monthly', 'day_of_month': 20,
         'is_active': False, 'next_date': None},
    ]
    for rd in recurring_data:
        rt = RecurringTransaction(user_id=demo_user.id, **rd)
        db.session.add(rt)
    db.session.commit()
