"""
GigLedger - Projects Blueprint
"""
from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from ..models import Project, Client, Transaction, db

projects_bp = Blueprint('projects', __name__, url_prefix='/projects')


@projects_bp.route('/')
@login_required
def list_projects():
    uid = current_user.id
    status_filter = request.args.get('status', 'all')

    all_projects = Project.query.filter_by(user_id=uid).order_by(Project.created_at.desc()).all()

    if status_filter and status_filter != 'all':
        projects = [p for p in all_projects if p.status == status_filter]
    else:
        projects = all_projects

    # Summary stats
    active_count = len([p for p in all_projects if p.status == 'active'])
    total_earned = sum(p.earned for p in all_projects)

    now = datetime.now()
    hours_this_month = sum(
        p.hours_logged for p in all_projects
        if p.start_date and p.start_date.month == now.month and p.start_date.year == now.year
    )

    clients = Client.query.filter_by(user_id=uid, is_active=True).order_by(Client.name).all()

    return render_template('projects/index.html',
        projects=projects,
        all_projects=all_projects,
        clients=clients,
        active_count=active_count,
        total_earned=total_earned,
        hours_this_month=hours_this_month,
        status_filter=status_filter,
        now=datetime.now(),
        currency=current_user.currency)


@projects_bp.route('/add', methods=['POST'])
@login_required
def add():
    name = request.form.get('name', '').strip()
    if not name:
        flash('Project name is required.', 'error')
        return redirect(url_for('projects.list_projects'))

    client_id = request.form.get('client_id', '')
    client_id = int(client_id) if client_id else None

    rate_type = request.form.get('rate_type', 'hourly')
    try:
        rate = float(request.form.get('rate', '0'))
    except ValueError:
        rate = 0

    start_date_str = request.form.get('start_date', '')
    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
    except (ValueError, TypeError):
        start_date = datetime.now()

    deadline_str = request.form.get('deadline', '')
    try:
        deadline = datetime.strptime(deadline_str, '%Y-%m-%d')
    except (ValueError, TypeError):
        deadline = None

    color = request.form.get('color', '#34d399')
    if not color.startswith('#'):
        color = '#34d399'

    project = Project(
        user_id=current_user.id,
        client_id=client_id,
        name=name,
        description=request.form.get('description', ''),
        status='active',
        rate_type=rate_type,
        rate=rate,
        start_date=start_date,
        deadline=deadline,
        color=color)
    db.session.add(project)
    db.session.commit()

    flash(f'Project "{name}" created!', 'success')
    return redirect(url_for('projects.list_projects'))


@projects_bp.route('/edit/<int:id>', methods=['POST'])
@login_required
def edit(id):
    project = Project.query.filter_by(id=id, user_id=current_user.id).first()
    if not project:
        flash('Project not found.', 'error')
        return redirect(url_for('projects.list_projects'))

    name = request.form.get('name', '').strip()
    if not name:
        flash('Project name is required.', 'error')
        return redirect(url_for('projects.list_projects'))

    client_id = request.form.get('client_id', '')
    project.client_id = int(client_id) if client_id else None
    project.name = name
    project.description = request.form.get('description', '')
    project.rate_type = request.form.get('rate_type', 'hourly')
    try:
        project.rate = float(request.form.get('rate', '0'))
    except ValueError:
        pass

    start_date_str = request.form.get('start_date', '')
    try:
        project.start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
    except (ValueError, TypeError):
        pass

    deadline_str = request.form.get('deadline', '')
    try:
        project.deadline = datetime.strptime(deadline_str, '%Y-%m-%d')
    except (ValueError, TypeError):
        project.deadline = None

    color = request.form.get('color', project.color)
    if color.startswith('#'):
        project.color = color

    db.session.commit()
    flash(f'Project "{name}" updated!', 'success')
    return redirect(url_for('projects.list_projects'))


@projects_bp.route('/log-hours/<int:id>', methods=['POST'])
@login_required
def log_hours(id):
    project = Project.query.filter_by(id=id, user_id=current_user.id).first()
    if not project:
        flash('Project not found.', 'error')
        return redirect(url_for('projects.list_projects'))

    try:
        hours = float(request.form.get('hours', '0'))
    except ValueError:
        flash('Invalid hours value.', 'error')
        return redirect(url_for('projects.list_projects'))

    if hours <= 0:
        flash('Hours must be greater than zero.', 'error')
        return redirect(url_for('projects.list_projects'))

    project.hours_logged = (project.hours_logged or 0) + hours

    # Optionally create a transaction for the earned amount
    create_transaction = request.form.get('create_transaction') == 'on'
    if create_transaction and project.earned > 0:
        earned = project.earned
        tx = Transaction(
            user_id=current_user.id,
            amount=earned,
            date=datetime.now(),
            category='Freelance Project',
            description=f'Hours logged on project: {project.name}',
            is_tax_deductible=False,
            source='project')
        db.session.add(tx)

    db.session.commit()
    flash(f'{hours}h logged on "{project.name}"!', 'success')
    return redirect(url_for('projects.list_projects'))


@projects_bp.route('/update-status/<int:id>', methods=['POST'])
@login_required
def update_status(id):
    project = Project.query.filter_by(id=id, user_id=current_user.id).first()
    if not project:
        flash('Project not found.', 'error')
        return redirect(url_for('projects.list_projects'))

    new_status = request.form.get('status', 'active')
    valid_statuses = ['active', 'completed', 'on_hold', 'cancelled']
    if new_status not in valid_statuses:
        flash('Invalid status.', 'error')
        return redirect(url_for('projects.list_projects'))

    project.status = new_status
    if new_status == 'completed':
        project.end_date = datetime.now()

    db.session.commit()
    flash(f'Project "{project.name}" marked as {new_status.replace("_", " ").title()}.', 'success')
    return redirect(url_for('projects.list_projects'))


@projects_bp.route('/delete/<int:id>', methods=['POST'])
@login_required
def delete(id):
    project = Project.query.filter_by(id=id, user_id=current_user.id).first()
    if project:
        db.session.delete(project)
        db.session.commit()
        flash('Project deleted.', 'success')
    else:
        flash('Project not found.', 'error')
    return redirect(url_for('projects.list_projects'))
