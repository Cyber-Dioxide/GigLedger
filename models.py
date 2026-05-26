"""
FreelanceCash - SQLAlchemy Models
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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    transactions = db.relationship('Transaction', backref='user', lazy=True)
    tax_estimates = db.relationship('TaxEstimate', backref='user', lazy=True)

    def get_income_categories(self):
        """Return list of income categories (custom or default)."""
        if self.custom_income_categories:
            return [c.strip() for c in self.custom_income_categories.split(',') if c.strip()]
        return DEFAULT_INCOME_CATEGORIES.copy()

    def get_expense_categories(self):
        """Return list of expense categories (custom or default)."""
        if self.custom_expense_categories:
            return [c.strip() for c in self.custom_expense_categories.split(',') if c.strip()]
        return DEFAULT_EXPENSE_CATEGORIES.copy()

    def get_all_categories(self):
        """Return combined unique categories."""
        return list(dict.fromkeys(self.get_income_categories() + self.get_expense_categories()))


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
