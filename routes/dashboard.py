from datetime import datetime
from flask import Blueprint, render_template
from flask_login import login_required, current_user
from ..models import Goal, Project, Invoice, Client
from ..finance import (calculate_monthly_summary, calculate_safe_to_spend,
                       calculate_runway, get_6_month_chart_data, get_quarter,
                       get_recent_transactions, get_category_breakdown)

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/')
@login_required
def index():
    now = datetime.now()
    uid = current_user.id
    tax_rate = current_user.default_tax_rate

    month_income, month_expenses = calculate_monthly_summary(uid, now.year, now.month)
    balance, tax_obligation, safe_balance = calculate_safe_to_spend(uid, tax_rate)
    runway_balance, avg_monthly_expenses, runway_months = calculate_runway(uid)
    chart_labels, chart_income, chart_expenses = get_6_month_chart_data(uid)
    recent_transactions = get_recent_transactions(uid, limit=5)
    cat_labels, cat_totals = get_category_breakdown(uid)

    # Net savings this month
    net_this_month = month_income - month_expenses

    # Income vs last month (for trend indicator)
    prev_month = now.month - 1
    prev_year = now.year
    if prev_month == 0:
        prev_month = 12
        prev_year -= 1
    prev_income, prev_expenses = calculate_monthly_summary(uid, prev_year, prev_month)
    income_trend = ((month_income - prev_income) / prev_income * 100) if prev_income > 0 else 0
    expense_trend = ((month_expenses - prev_expenses) / prev_expenses * 100) if prev_expenses > 0 else 0

    # Calculate deductible impact this month
    from ..finance import _get_tx_range
    if now.month == 12:
        end = datetime(now.year + 1, 1, 1)
    else:
        end = datetime(now.year, now.month + 1, 1)
    start = datetime(now.year, now.month, 1)
    results = _get_tx_range(uid, start, end)
    deductible_this_month = sum(abs(r[0]) for r in results if r[0] < 0 and r[1])
    tax_saving_this_month = deductible_this_month * tax_rate

    # New: Goals data
    goals = Goal.query.filter_by(user_id=uid, is_completed=False).order_by(Goal.deadline.asc().nulls_last()).limit(3).all()
    total_goals_saved = sum(g.current_amount for g in Goal.query.filter_by(user_id=uid).all())

    # New: Active projects
    active_projects = Project.query.filter_by(user_id=uid, status='active').order_by(Project.deadline.asc().nulls_last()).limit(3).all()
    active_project_count = Project.query.filter_by(user_id=uid, status='active').count()

    # New: Invoice data
    unpaid_invoices = Invoice.query.filter_by(user_id=uid).filter(Invoice.status.in_(['sent', 'overdue'])).order_by(Invoice.due_date.asc()).all()
    total_outstanding = sum(inv.total for inv in unpaid_invoices)
    overdue_count = Invoice.query.filter_by(user_id=uid, status='overdue').count()

    # New: Client count
    client_count = Client.query.filter_by(user_id=uid, is_active=True).count()

    # New: Recurring monthly commitment
    from ..models import RecurringTransaction
    recurring_active = RecurringTransaction.query.filter_by(user_id=uid, is_active=True, frequency='monthly').all()
    monthly_commitment = sum(abs(r.amount) for r in recurring_active if r.amount < 0)

    return render_template('dashboard/index.html',
        month_income=month_income, month_expenses=month_expenses,
        net_this_month=net_this_month,
        balance=balance, tax_obligation=tax_obligation, safe_balance=safe_balance,
        runway_balance=runway_balance, avg_monthly_expenses=avg_monthly_expenses,
        runway_months=runway_months, chart_labels=chart_labels,
        chart_income=chart_income, chart_expenses=chart_expenses,
        current_quarter=get_quarter(now.month), tax_rate=tax_rate,
        currency=current_user.currency,
        recent_transactions=recent_transactions,
        cat_labels=cat_labels, cat_totals=cat_totals,
        income_trend=income_trend, expense_trend=expense_trend,
        deductible_this_month=deductible_this_month,
        tax_saving_this_month=tax_saving_this_month,
        user_categories=current_user.get_all_categories(),
        goals=goals, total_goals_saved=total_goals_saved,
        active_projects=active_projects, active_project_count=active_project_count,
        unpaid_invoices=unpaid_invoices, total_outstanding=total_outstanding,
        overdue_count=overdue_count, client_count=client_count,
        monthly_commitment=monthly_commitment, now=now)
