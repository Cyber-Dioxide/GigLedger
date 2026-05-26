from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from ..models import RecurringTransaction, Transaction, db

recurring_bp = Blueprint('recurring', __name__, url_prefix='/recurring')


def _calculate_next_date(from_date, frequency, day_of_month=1):
    """Calculate the next occurrence date based on frequency."""
    if frequency == 'weekly':
        return from_date + timedelta(weeks=1)
    elif frequency == 'monthly':
        next_month = from_date + relativedelta(months=1)
        try:
            return next_month.replace(day=day_of_month)
        except ValueError:
            # Day doesn't exist in that month (e.g., 31st in a 30-day month)
            return next_month.replace(day=28)
    elif frequency == 'quarterly':
        next_q = from_date + relativedelta(months=3)
        try:
            return next_q.replace(day=day_of_month)
        except ValueError:
            return next_q.replace(day=28)
    elif frequency == 'yearly':
        next_year = from_date + relativedelta(years=1)
        try:
            return next_year.replace(day=day_of_month)
        except ValueError:
            return next_year.replace(day=28)
    return from_date + relativedelta(months=1)


@recurring_bp.route('/')
@login_required
def index():
    recurring = RecurringTransaction.query.filter_by(user_id=current_user.id).order_by(
        RecurringTransaction.is_active.desc(), RecurringTransaction.next_date.asc().nullslast(),
        RecurringTransaction.created_at.desc()).all()

    # Monthly commitments: sum of active monthly recurring expenses
    monthly_commitments = sum(abs(r.amount) for r in recurring if r.is_active and r.amount < 0 and r.frequency == 'monthly')
    active_count = sum(1 for r in recurring if r.is_active)

    return render_template('recurring/index.html',
        recurring=recurring,
        monthly_commitments=monthly_commitments,
        active_count=active_count,
        currency=current_user.currency,
        user_categories=current_user.get_all_categories(),
        now=datetime.now())


@recurring_bp.route('/add', methods=['POST'])
@login_required
def add():
    tx_type = request.form.get('type', 'expense')
    description = request.form.get('description', '').strip()
    try:
        amount = float(request.form.get('amount', '0'))
    except ValueError:
        flash('Invalid amount.', 'error')
        return redirect(url_for('recurring.index'))

    if not description:
        flash('Description is required.', 'error')
        return redirect(url_for('recurring.index'))

    if amount <= 0:
        flash('Amount must be greater than zero.', 'error')
        return redirect(url_for('recurring.index'))

    # Make expense amounts negative
    if tx_type == 'expense' and amount > 0:
        amount = -amount

    category = request.form.get('category', '')
    frequency = request.form.get('frequency', 'monthly')
    is_tax_deductible = request.form.get('is_tax_deductible') == 'on'

    try:
        day_of_month = int(request.form.get('day_of_month', 1))
        day_of_month = max(1, min(31, day_of_month))
    except ValueError:
        day_of_month = 1

    # Calculate next_date starting from today
    now = datetime.now()
    try:
        next_date = now.replace(day=day_of_month)
    except ValueError:
        next_date = now.replace(day=28)

    # If the day has already passed this month, move to next period
    if next_date <= now:
        next_date = _calculate_next_date(next_date, frequency, day_of_month)

    rt = RecurringTransaction(
        user_id=current_user.id,
        description=description,
        amount=amount,
        category=category,
        is_tax_deductible=is_tax_deductible,
        frequency=frequency,
        day_of_month=day_of_month,
        is_active=True,
        next_date=next_date)
    db.session.add(rt)
    db.session.commit()

    flash(f'Recurring transaction "{description}" created!', 'success')
    return redirect(url_for('recurring.index'))


@recurring_bp.route('/edit/<int:id>', methods=['POST'])
@login_required
def edit(id):
    rt = RecurringTransaction.query.filter_by(id=id, user_id=current_user.id).first()
    if not rt:
        flash('Recurring transaction not found.', 'error')
        return redirect(url_for('recurring.index'))

    description = request.form.get('description', '').strip()
    if description:
        rt.description = description

    try:
        amount = float(request.form.get('amount', str(abs(rt.amount))))
        if amount > 0:
            rt.amount = amount if rt.amount > 0 else -amount
    except ValueError:
        pass

    category = request.form.get('category', rt.category)
    rt.category = category

    frequency = request.form.get('frequency', rt.frequency)
    rt.frequency = frequency

    try:
        day_of_month = int(request.form.get('day_of_month', rt.day_of_month))
        rt.day_of_month = max(1, min(31, day_of_month))
    except ValueError:
        pass

    rt.is_tax_deductible = request.form.get('is_tax_deductible') == 'on'

    # Recalculate next_date if frequency or day changed
    now = datetime.now()
    try:
        next_date = now.replace(day=rt.day_of_month)
    except ValueError:
        next_date = now.replace(day=28)
    if next_date <= now:
        next_date = _calculate_next_date(next_date, rt.frequency, rt.day_of_month)
    rt.next_date = next_date

    db.session.commit()
    flash(f'Recurring transaction "{rt.description}" updated.', 'success')
    return redirect(url_for('recurring.index'))


@recurring_bp.route('/toggle/<int:id>', methods=['POST'])
@login_required
def toggle(id):
    rt = RecurringTransaction.query.filter_by(id=id, user_id=current_user.id).first()
    if not rt:
        flash('Recurring transaction not found.', 'error')
        return redirect(url_for('recurring.index'))

    rt.is_active = not rt.is_active

    if rt.is_active:
        # Recalculate next_date when reactivating
        now = datetime.now()
        try:
            next_date = now.replace(day=rt.day_of_month)
        except ValueError:
            next_date = now.replace(day=28)
        if next_date <= now:
            next_date = _calculate_next_date(next_date, rt.frequency, rt.day_of_month)
        rt.next_date = next_date
        flash(f'"{rt.description}" activated.', 'success')
    else:
        flash(f'"{rt.description}" paused.', 'success')

    db.session.commit()
    return redirect(url_for('recurring.index'))


@recurring_bp.route('/delete/<int:id>', methods=['POST'])
@login_required
def delete(id):
    rt = RecurringTransaction.query.filter_by(id=id, user_id=current_user.id).first()
    if rt:
        name = rt.description
        db.session.delete(rt)
        db.session.commit()
        flash(f'Recurring transaction "{name}" deleted.', 'success')
    else:
        flash('Recurring transaction not found.', 'error')
    return redirect(url_for('recurring.index'))


@recurring_bp.route('/generate', methods=['POST'])
@login_required
def generate():
    """Manually generate pending recurring transactions."""
    now = datetime.now()
    active_recurring = RecurringTransaction.query.filter_by(
        user_id=current_user.id, is_active=True).all()

    generated = 0
    for rt in active_recurring:
        if rt.next_date and rt.next_date <= now:
            # Create a Transaction for this recurring item
            tx = Transaction(
                user_id=current_user.id,
                amount=rt.amount,
                date=rt.next_date,
                category=rt.category or 'Recurring',
                description=rt.description,
                is_tax_deductible=rt.is_tax_deductible,
                source='recurring')
            db.session.add(tx)

            # Update recurring tracking
            rt.last_generated = rt.next_date
            rt.next_date = _calculate_next_date(rt.next_date, rt.frequency, rt.day_of_month)
            generated += 1

    if generated > 0:
        db.session.commit()
        flash(f'Generated {generated} transaction{{"s" if generated != 1 else ""}} from recurring items.', 'success')
    else:
        flash('No pending recurring transactions to generate.', 'info')

    return redirect(url_for('recurring.index'))
