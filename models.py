"""
GigLedger - SQLAlchemy Models
"""
from datetime import datetime
from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
import json

db = SQLAlchemy()

# Default categories that ship with the app
DEFAULT_INCOME_CATEGORIES = ['Client Payment', 'Consulting', 'Freelance Project', 'Royalty']
DEFAULT_EXPENSE_CATEGORIES = ['Software', 'Internet', 'Office Supplies', 'Marketing',
                               'Travel', 'Equipment', 'Meal', 'Entertainment']


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    default_tax_rate = db.Column(db.Float, default=0.30)
    currency = db.Column(db.String(3), default='USD')
    custom_income_categories = db.Column(db.Text, default='')   # comma-separated
    custom_expense_categories = db.Column(db.Text, default='')  # comma-separated
    theme = db.Column(db.String(20), default='emerald')  # theme name
    dark_mode = db.Column(db.Boolean, default=False)      # dark mode toggle
    business_name = db.Column(db.String(200), default='')
    business_address = db.Column(db.Text, default='')
    business_phone = db.Column(db.String(50), default='')
    invoice_note = db.Column(db.Text, default='Thank you for your business!')
    invoice_prefix = db.Column(db.String(10), default='INV')
    next_invoice_number = db.Column(db.Integer, default=1)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    transactions = db.relationship('Transaction', backref='user', lazy=True)
    tax_estimates = db.relationship('TaxEstimate', backref='user', lazy=True)
    clients = db.relationship('Client', backref='user', lazy=True)
    invoices = db.relationship('Invoice', backref='user', lazy=True)
    projects = db.relationship('Project', backref='user', lazy=True)
    goals = db.relationship('Goal', backref='user', lazy=True)
    recurring_transactions = db.relationship('RecurringTransaction', backref='user', lazy=True)

    def get_income_categories(self):
        if self.custom_income_categories:
            return [c.strip() for c in self.custom_income_categories.split(',') if c.strip()]
        return DEFAULT_INCOME_CATEGORIES.copy()

    def get_expense_categories(self):
        if self.custom_expense_categories:
            return [c.strip() for c in self.custom_expense_categories.split(',') if c.strip()]
        return DEFAULT_EXPENSE_CATEGORIES.copy()

    def get_all_categories(self):
        return list(dict.fromkeys(self.get_income_categories() + self.get_expense_categories()))

    def get_next_invoice_number(self):
        num = self.next_invoice_number
        self.next_invoice_number = num + 1
        db.session.commit()
        return f"{self.invoice_prefix}-{num:04d}"


class Transaction(db.Model):
    __tablename__ = 'transactions'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    date = db.Column(db.DateTime, nullable=False)
    category = db.Column(db.String(50))
    description = db.Column(db.String(200))
    is_tax_deductible = db.Column(db.Boolean, default=False)
    source = db.Column(db.String(20), default='manual')
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoices.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class TaxEstimate(db.Model):
    __tablename__ = 'tax_estimates'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    quarter = db.Column(db.Integer)
    year = db.Column(db.Integer)
    total_income = db.Column(db.Float)
    total_deductions = db.Column(db.Float)
    estimated_tax_owed = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Client(db.Model):
    __tablename__ = 'clients'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(200), default='')
    phone = db.Column(db.String(50), default='')
    company = db.Column(db.String(200), default='')
    address = db.Column(db.Text, default='')
    notes = db.Column(db.Text, default='')
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    invoices = db.relationship('Invoice', backref='client', lazy=True)
    projects = db.relationship('Project', backref='client', lazy=True)

    def total_invoiced(self):
        return sum(inv.total for inv in self.invoices if inv.status != 'draft')

    def total_paid(self):
        return sum(inv.total for inv in self.invoices if inv.status == 'paid')

    def total_outstanding(self):
        return sum(inv.total for inv in self.invoices if inv.status in ('sent', 'overdue'))


class Invoice(db.Model):
    __tablename__ = 'invoices'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=True)
    invoice_number = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(20), default='draft')  # draft, sent, paid, overdue, cancelled
    issue_date = db.Column(db.DateTime, default=datetime.utcnow)
    due_date = db.Column(db.DateTime, nullable=True)
    notes = db.Column(db.Text, default='')
    subtotal = db.Column(db.Float, default=0)
    tax_amount = db.Column(db.Float, default=0)
    total = db.Column(db.Float, default=0)
    paid_date = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    line_items = db.relationship('InvoiceLineItem', backref='invoice', lazy=True, cascade='all, delete-orphan')
    transactions = db.relationship('Transaction', backref='invoice_ref', lazy=True)


class InvoiceLineItem(db.Model):
    __tablename__ = 'invoice_line_items'

    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoices.id'), nullable=False)
    description = db.Column(db.String(300), nullable=False)
    quantity = db.Column(db.Float, default=1)
    rate = db.Column(db.Float, default=0)
    amount = db.Column(db.Float, default=0)


class Project(db.Model):
    __tablename__ = 'projects'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default='')
    status = db.Column(db.String(20), default='active')  # active, completed, on_hold, cancelled
    rate_type = db.Column(db.String(20), default='hourly')  # hourly, fixed, daily
    rate = db.Column(db.Float, default=0)
    hours_logged = db.Column(db.Float, default=0)
    start_date = db.Column(db.DateTime, default=datetime.utcnow)
    end_date = db.Column(db.DateTime, nullable=True)
    deadline = db.Column(db.DateTime, nullable=True)
    color = db.Column(db.String(20), default='#34d399')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def earned(self):
        if self.rate_type == 'hourly':
            return self.hours_logged * self.rate
        elif self.rate_type == 'daily':
            return self.hours_logged * self.rate
        else:  # fixed
            if self.status == 'completed':
                return self.rate
            return self.hours_logged * (self.rate / 100) if self.rate > 0 else 0

    @property
    def progress(self):
        if self.rate_type == 'fixed' and self.rate > 0:
            return min(100, (self.hours_logged / 100) * 100)
        return 0


class Goal(db.Model):
    __tablename__ = 'goals'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    target_amount = db.Column(db.Float, nullable=False)
    current_amount = db.Column(db.Float, default=0)
    deadline = db.Column(db.DateTime, nullable=True)
    icon = db.Column(db.String(50), default='target')
    color = db.Column(db.String(20), default='#34d399')
    is_completed = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def progress_percent(self):
        if self.target_amount <= 0:
            return 0
        return min(100, (self.current_amount / self.target_amount) * 100)

    @property
    def remaining(self):
        return max(0, self.target_amount - self.current_amount)


class RecurringTransaction(db.Model):
    __tablename__ = 'recurring_transactions'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    description = db.Column(db.String(200), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(50), default='')
    is_tax_deductible = db.Column(db.Boolean, default=False)
    frequency = db.Column(db.String(20), default='monthly')  # weekly, monthly, quarterly, yearly
    day_of_month = db.Column(db.Integer, default=1)
    is_active = db.Column(db.Boolean, default=True)
    last_generated = db.Column(db.DateTime, nullable=True)
    next_date = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
