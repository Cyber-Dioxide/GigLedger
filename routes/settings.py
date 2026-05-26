from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from ..models import db, DEFAULT_INCOME_CATEGORIES, DEFAULT_EXPENSE_CATEGORIES

settings_bp = Blueprint('settings', __name__)

AVAILABLE_THEMES = {
    'emerald': {'name': 'Emerald', 'desc': 'Fresh green, the default'},
    'ocean': {'name': 'Ocean Blue', 'desc': 'Deep and professional'},
    'sunset': {'name': 'Sunset Orange', 'desc': 'Warm and energetic'},
    'rose': {'name': 'Rose Pink', 'desc': 'Bold and vibrant'},
    'midnight': {'name': 'Midnight Slate', 'desc': 'Sleek and sophisticated'},
}


@settings_bp.route('/settings')
@login_required
def index():
    return render_template('settings/index.html', user=current_user,
        tax_rate_percent=int(current_user.default_tax_rate * 100),
        income_categories=current_user.get_income_categories(),
        expense_categories=current_user.get_expense_categories(),
        default_income_categories=DEFAULT_INCOME_CATEGORIES,
        default_expense_categories=DEFAULT_EXPENSE_CATEGORIES,
        available_themes=AVAILABLE_THEMES,
        current_theme=current_user.theme or 'emerald',
        dark_mode=current_user.dark_mode or False)


@settings_bp.route('/settings/tax-rate', methods=['POST'])
@login_required
def update_tax_rate():
    try:
        tax_rate = float(request.form.get('tax_rate', '30'))
        if tax_rate < 0 or tax_rate > 100: raise ValueError
        current_user.default_tax_rate = tax_rate / 100.0
        db.session.commit()
        flash(f'Tax rate updated to {tax_rate}%. All calculations now use this rate.', 'success')
    except ValueError:
        flash('Please enter a valid tax rate between 0 and 100.', 'error')
    return redirect(url_for('settings.index'))


@settings_bp.route('/settings/currency', methods=['POST'])
@login_required
def update_currency():
    currency = request.form.get('currency', 'USD')
    if currency in ['USD', 'EUR', 'GBP', 'CAD', 'AUD', 'INR', 'JPY']:
        current_user.currency = currency
        db.session.commit()
        flash(f'Currency updated to {currency}.', 'success')
    else:
        flash('Unsupported currency.', 'error')
    return redirect(url_for('settings.index'))


@settings_bp.route('/settings/categories/income/add', methods=['POST'])
@login_required
def add_income_category():
    name = request.form.get('category_name', '').strip()
    if not name:
        flash('Category name cannot be empty.', 'error')
    elif name in current_user.get_income_categories():
        flash(f'Category "{name}" already exists.', 'error')
    else:
        cats = current_user.get_income_categories()
        cats.append(name)
        current_user.custom_income_categories = ','.join(cats)
        db.session.commit()
        flash(f'Income category "{name}" added!', 'success')
    return redirect(url_for('settings.index'))


@settings_bp.route('/settings/categories/income/delete', methods=['POST'])
@login_required
def delete_income_category():
    name = request.form.get('category_name', '').strip()
    cats = current_user.get_income_categories()
    if name in cats:
        cats.remove(name)
        current_user.custom_income_categories = ','.join(cats) if cats else ''
        db.session.commit()
        flash(f'Income category "{name}" removed.', 'success')
    else:
        flash(f'Category "{name}" not found.', 'error')
    return redirect(url_for('settings.index'))


@settings_bp.route('/settings/categories/expense/add', methods=['POST'])
@login_required
def add_expense_category():
    name = request.form.get('category_name', '').strip()
    if not name:
        flash('Category name cannot be empty.', 'error')
    elif name in current_user.get_expense_categories():
        flash(f'Category "{name}" already exists.', 'error')
    else:
        cats = current_user.get_expense_categories()
        cats.append(name)
        current_user.custom_expense_categories = ','.join(cats)
        db.session.commit()
        flash(f'Expense category "{name}" added!', 'success')
    return redirect(url_for('settings.index'))


@settings_bp.route('/settings/categories/expense/delete', methods=['POST'])
@login_required
def delete_expense_category():
    name = request.form.get('category_name', '').strip()
    cats = current_user.get_expense_categories()
    if name in cats:
        cats.remove(name)
        current_user.custom_expense_categories = ','.join(cats) if cats else ''
        db.session.commit()
        flash(f'Expense category "{name}" removed.', 'success')
    else:
        flash(f'Category "{name}" not found.', 'error')
    return redirect(url_for('settings.index'))


@settings_bp.route('/settings/theme', methods=['POST'])
@login_required
def update_theme():
    theme = request.form.get('theme', 'emerald')
    if theme in AVAILABLE_THEMES:
        current_user.theme = theme
        db.session.commit()
        flash(f'Theme changed to {AVAILABLE_THEMES[theme]["name"]}.', 'success')
    else:
        flash('Invalid theme selection.', 'error')
    return redirect(url_for('settings.index'))


@settings_bp.route('/settings/dark-mode', methods=['POST'])
@login_required
def toggle_dark_mode():
    dark = request.form.get('dark_mode', 'off')
    current_user.dark_mode = (dark == 'on')
    db.session.commit()
    flash('Dark mode ' + ('enabled' if current_user.dark_mode else 'disabled') + '.', 'success')
    return redirect(url_for('settings.index'))


@settings_bp.route('/settings/categories/reset', methods=['POST'])
@login_required
def reset_categories():
    current_user.custom_income_categories = ''
    current_user.custom_expense_categories = ''
    db.session.commit()
    flash('Categories reset to defaults.', 'success')
    return redirect(url_for('settings.index'))
