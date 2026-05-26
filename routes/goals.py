from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from ..models import Goal, db

goals_bp = Blueprint('goals', __name__, url_prefix='/goals')


@goals_bp.route('/')
@login_required
def index():
    goals = Goal.query.filter_by(user_id=current_user.id).order_by(Goal.is_completed, Goal.deadline.asc().nullslast(), Goal.created_at.desc()).all()

    total_saved = sum(g.current_amount for g in goals if not g.is_completed)
    completed_count = sum(1 for g in goals if g.is_completed)

    return render_template('goals/index.html',
        goals=goals,
        total_saved=total_saved,
        completed_count=completed_count,
        currency=current_user.currency,
        now=datetime.now())


@goals_bp.route('/add', methods=['POST'])
@login_required
def add():
    name = request.form.get('name', '').strip()
    try:
        target_amount = float(request.form.get('target_amount', '0'))
    except ValueError:
        flash('Invalid target amount.', 'error')
        return redirect(url_for('goals.index'))

    deadline_str = request.form.get('deadline', '')
    deadline = None
    if deadline_str:
        try:
            deadline = datetime.strptime(deadline_str, '%Y-%m-%d')
        except ValueError:
            flash('Invalid deadline date.', 'error')
            return redirect(url_for('goals.index'))

    icon = request.form.get('icon', 'target')
    color = request.form.get('color', '#34d399')

    if not name:
        flash('Goal name is required.', 'error')
        return redirect(url_for('goals.index'))

    if target_amount <= 0:
        flash('Target amount must be greater than zero.', 'error')
        return redirect(url_for('goals.index'))

    goal = Goal(
        user_id=current_user.id,
        name=name,
        target_amount=target_amount,
        icon=icon,
        color=color,
        deadline=deadline)
    db.session.add(goal)
    db.session.commit()

    flash(f'Goal "{name}" created!', 'success')
    return redirect(url_for('goals.index'))


@goals_bp.route('/update/<int:id>', methods=['POST'])
@login_required
def update(id):
    goal = Goal.query.filter_by(id=id, user_id=current_user.id).first()
    if not goal:
        flash('Goal not found.', 'error')
        return redirect(url_for('goals.index'))

    try:
        amount = float(request.form.get('amount', '0'))
    except ValueError:
        flash('Invalid amount.', 'error')
        return redirect(url_for('goals.index'))

    if amount <= 0:
        flash('Amount must be greater than zero.', 'error')
        return redirect(url_for('goals.index'))

    goal.current_amount = min(goal.target_amount, goal.current_amount + amount)
    if goal.current_amount >= goal.target_amount:
        goal.is_completed = True
        flash(f'Goal "{goal.name}" completed! Congratulations!', 'success')
    else:
        flash(f'Added {currency_symbol(current_user.currency)}{amount:,.2f} to "{goal.name}".', 'success')

    db.session.commit()
    return redirect(url_for('goals.index'))


@goals_bp.route('/edit/<int:id>', methods=['POST'])
@login_required
def edit(id):
    goal = Goal.query.filter_by(id=id, user_id=current_user.id).first()
    if not goal:
        flash('Goal not found.', 'error')
        return redirect(url_for('goals.index'))

    name = request.form.get('name', '').strip()
    if name:
        goal.name = name

    try:
        target_amount = float(request.form.get('target_amount', str(goal.target_amount)))
        if target_amount > 0:
            goal.target_amount = target_amount
    except ValueError:
        pass

    deadline_str = request.form.get('deadline', '')
    if deadline_str:
        try:
            goal.deadline = datetime.strptime(deadline_str, '%Y-%m-%d')
        except ValueError:
            pass
    else:
        goal.deadline = None

    icon = request.form.get('icon', goal.icon)
    if icon:
        goal.icon = icon

    color = request.form.get('color', goal.color)
    if color:
        goal.color = color

    # Re-check completion after edit
    if goal.current_amount >= goal.target_amount:
        goal.is_completed = True
    else:
        goal.is_completed = False

    db.session.commit()
    flash(f'Goal "{goal.name}" updated.', 'success')
    return redirect(url_for('goals.index'))


@goals_bp.route('/delete/<int:id>', methods=['POST'])
@login_required
def delete(id):
    goal = Goal.query.filter_by(id=id, user_id=current_user.id).first()
    if goal:
        name = goal.name
        db.session.delete(goal)
        db.session.commit()
        flash(f'Goal "{name}" deleted.', 'success')
    else:
        flash('Goal not found.', 'error')
    return redirect(url_for('goals.index'))


@goals_bp.route('/complete/<int:id>', methods=['POST'])
@login_required
def complete(id):
    goal = Goal.query.filter_by(id=id, user_id=current_user.id).first()
    if not goal:
        flash('Goal not found.', 'error')
        return redirect(url_for('goals.index'))

    goal.is_completed = not goal.is_completed
    if goal.is_completed:
        goal.current_amount = goal.target_amount
        flash(f'Goal "{goal.name}" marked as completed!', 'success')
    else:
        flash(f'Goal "{goal.name}" marked as incomplete.', 'success')

    db.session.commit()
    return redirect(url_for('goals.index'))


def currency_symbol(code):
    return {'USD': '$', 'EUR': '\u20ac', 'GBP': '\u00a3',
            'CAD': 'C$', 'AUD': 'A$', 'INR': '\u20b9', 'JPY': '\u00a5'}.get(code, '$')
