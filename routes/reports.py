"""
GigLedger - Reports Route

Provides yearly financial reports with monthly breakdowns,
top clients, expense categories, and key insights.
"""
from datetime import datetime
from flask import Blueprint, render_template, request
from flask_login import login_required, current_user
from ..models import Transaction, Client, Invoice, db
from ..finance import calculate_monthly_summary, get_quarter, get_quarter_date_range

reports_bp = Blueprint('reports', __name__)


@reports_bp.route('/reports')
@login_required
def index():
    uid = current_user.id
    tax_rate = current_user.default_tax_rate

    # Year selector - default to current year
    now = datetime.now()
    selected_year = request.args.get('year', now.year, type=int)

    # Determine available years from transactions
    year_result = db.session.query(db.func.strftime('%Y', Transaction.date)).filter(
        Transaction.user_id == uid
    ).distinct().all()
    available_years = sorted([int(r[0]) for r in year_result if r[0]], reverse=True)
    if not available_years:
        available_years = [now.year]
    if selected_year not in available_years:
        available_years.append(selected_year)
        available_years.sort(reverse=True)

    # ── Yearly summary ──
    year_start = datetime(selected_year, 1, 1)
    year_end = datetime(selected_year + 1, 1, 1)
    year_txs = db.session.query(Transaction).filter(
        Transaction.user_id == uid,
        Transaction.date >= year_start,
        Transaction.date < year_end,
    ).all()

    yearly_income = sum(t.amount for t in year_txs if t.amount > 0)
    yearly_expenses = sum(abs(t.amount) for t in year_txs if t.amount < 0)
    yearly_net = yearly_income - yearly_expenses
    yearly_deductible = sum(abs(t.amount) for t in year_txs if t.amount < 0 and t.is_tax_deductible)
    effective_tax_rate = (yearly_deductible / yearly_income * 100) if yearly_income > 0 else 0

    # ── Monthly breakdown (12 months) ──
    month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                   'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    monthly_data = []
    chart_labels = []
    chart_income = []
    chart_expenses = []

    for m in range(1, 13):
        income, expenses = calculate_monthly_summary(uid, selected_year, m)
        net = income - expenses
        savings_rate = ((income - expenses) / income * 100) if income > 0 else 0
        monthly_data.append({
            'month': month_names[m - 1],
            'month_num': m,
            'income': income,
            'expenses': expenses,
            'net': net,
            'savings_rate': savings_rate,
        })
        chart_labels.append(month_names[m - 1])
        chart_income.append(income)
        chart_expenses.append(expenses)

    # ── Average monthly income & expenses ──
    months_with_data = [m for m in monthly_data if m['income'] > 0 or m['expenses'] > 0]
    num_months = len(months_with_data) if months_with_data else 1
    avg_monthly_income = yearly_income / num_months
    avg_monthly_expenses = yearly_expenses / num_months
    avg_savings_rate = ((avg_monthly_income - avg_monthly_expenses) / avg_monthly_income * 100) if avg_monthly_income > 0 else 0

    # ── Top 5 income clients (from Client model, sum of paid invoices) ──
    top_clients = db.session.query(
        Client.name,
        db.func.sum(Invoice.total).label('total_earned')
    ).join(
        Invoice, Invoice.client_id == Client.id
    ).filter(
        Client.user_id == uid,
        Invoice.user_id == uid,
        Invoice.status == 'paid',
        db.func.strftime('%Y', Invoice.paid_date) == str(selected_year),
    ).group_by(Client.id).order_by(db.func.sum(Invoice.total).desc()).limit(5).all()

    # ── Top 5 expense categories ──
    expense_categories = db.session.query(
        Transaction.category,
        db.func.sum(Transaction.amount).label('total')
    ).filter(
        Transaction.user_id == uid,
        Transaction.amount < 0,
        Transaction.date >= year_start,
        Transaction.date < year_end,
    ).group_by(Transaction.category).order_by(
        db.func.sum(Transaction.amount).asc()
    ).limit(5).all()

    top_expense_categories = [
        {'category': cat or 'Uncategorized', 'total': abs(float(total))}
        for cat, total in expense_categories
    ]

    # ── Quarterly comparison ──
    quarterly_data = []
    for q in range(1, 5):
        q_start, q_end = get_quarter_date_range(q, selected_year)
        q_txs = db.session.query(Transaction).filter(
            Transaction.user_id == uid,
            Transaction.date >= q_start,
            Transaction.date < q_end,
        ).all()
        q_income = sum(t.amount for t in q_txs if t.amount > 0)
        q_expenses = sum(abs(t.amount) for t in q_txs if t.amount < 0)
        q_net = q_income - q_expenses
        quarterly_data.append({
            'quarter': q,
            'label': f'Q{q}',
            'income': q_income,
            'expenses': q_expenses,
            'net': q_net,
            'savings_rate': ((q_income - q_expenses) / q_income * 100) if q_income > 0 else 0,
        })

    # ── Key Insights ──
    # Best month (highest net)
    best_month = max(monthly_data, key=lambda m: m['net'])
    # Worst month (lowest net)
    worst_month = min(monthly_data, key=lambda m: m['net'])

    # Average invoice size
    paid_invoices = Invoice.query.filter(
        Invoice.user_id == uid,
        Invoice.status == 'paid',
    ).all()
    avg_invoice_size = (sum(inv.total for inv in paid_invoices) / len(paid_invoices)) if paid_invoices else 0

    # Most profitable client (all-time, not just this year)
    most_profitable = db.session.query(
        Client.name,
        db.func.sum(Invoice.total).label('total_earned')
    ).join(
        Invoice, Invoice.client_id == Client.id
    ).filter(
        Client.user_id == uid,
        Invoice.user_id == uid,
        Invoice.status == 'paid',
    ).group_by(Client.id).order_by(db.func.sum(Invoice.total).desc()).first()

    # Highest expense category
    highest_expense_cat = top_expense_categories[0] if top_expense_categories else None

    return render_template('reports/index.html',
        selected_year=selected_year,
        available_years=available_years,
        yearly_income=yearly_income,
        yearly_expenses=yearly_expenses,
        yearly_net=yearly_net,
        yearly_deductible=yearly_deductible,
        effective_tax_rate=effective_tax_rate,
        tax_rate=tax_rate,
        monthly_data=monthly_data,
        chart_labels=chart_labels,
        chart_income=chart_income,
        chart_expenses=chart_expenses,
        top_clients=top_clients,
        top_expense_categories=top_expense_categories,
        quarterly_data=quarterly_data,
        avg_monthly_income=avg_monthly_income,
        avg_monthly_expenses=avg_monthly_expenses,
        avg_savings_rate=avg_savings_rate,
        best_month=best_month,
        worst_month=worst_month,
        avg_invoice_size=avg_invoice_size,
        most_profitable=most_profitable,
        highest_expense_cat=highest_expense_cat,
        currency=current_user.currency,
    )
