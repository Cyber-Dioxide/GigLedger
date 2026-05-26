from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from ..models import Transaction, db

transactions_bp = Blueprint('transactions', __name__)


@transactions_bp.route('/transactions')
@login_required
def list_transactions():
    uid = current_user.id
    category = request.args.get('category', '')
    tx_type = request.args.get('type', '')
    month = request.args.get('month', '')
    year = request.args.get('year', '')

    all_tx = Transaction.query.filter_by(user_id=uid).order_by(Transaction.date.desc()).all()

    transactions = all_tx
    if category:
        transactions = [t for t in transactions if t.category == category]
    if tx_type == 'income':
        transactions = [t for t in transactions if t.amount > 0]
    elif tx_type == 'expense':
        transactions = [t for t in transactions if t.amount < 0]
    if month:
        try:
            m = int(month)
            transactions = [t for t in transactions if t.date.month == m]
        except: pass
    if year:
        try:
            y = int(year)
            transactions = [t for t in transactions if t.date.year == y]
        except: pass

    categories = current_user.get_all_categories()
    categories.sort()

    return render_template('transactions/index.html',
        transactions=transactions, categories=categories,
        selected_category=category, selected_type=tx_type,
        selected_month=month, selected_year=year,
        currency=current_user.currency,
        user_categories=current_user.get_all_categories())


@transactions_bp.route('/transactions/add', methods=['POST'])
@login_required
def add():
    try: amount = float(request.form.get('amount', '0'))
    except ValueError:
        flash('Invalid amount.', 'error')
        return redirect(request.referrer or url_for('transactions.list_transactions'))

    tx_type = request.form.get('type', 'income')
    if tx_type == 'expense' and amount > 0: amount = -amount
    elif tx_type == 'income' and amount < 0: amount = abs(amount)

    date_str = request.form.get('date', '')
    try: date = datetime.strptime(date_str, '%Y-%m-%d')
    except: date = datetime.now()

    tx = Transaction(
        user_id=current_user.id, amount=amount, date=date,
        category=request.form.get('category', 'Uncategorized'),
        description=request.form.get('description', ''),
        is_tax_deductible=request.form.get('is_tax_deductible') == 'on',
        source='manual')
    db.session.add(tx)
    db.session.commit()

    # Calculate the tax impact of this transaction and give feedback
    if tx.is_tax_deductible and tx.amount < 0:
        deduction = abs(tx.amount)
        tax_saving = deduction * current_user.default_tax_rate
        sym = {'USD':'$','EUR':'€','GBP':'£','CAD':'C$','AUD':'A$','INR':'₹','JPY':'¥'}.get(current_user.currency, '$')
        flash(f'Transaction added! Tax deductible saves you ~{sym}{tax_saving:,.2f} in taxes at {current_user.default_tax_rate*100:.0f}% rate.', 'success')
    else:
        flash('Transaction added!', 'success')

    return redirect(request.referrer or url_for('dashboard.index'))


@transactions_bp.route('/transactions/edit/<int:id>', methods=['POST'])
@login_required
def edit(id):
    tx = Transaction.query.filter_by(id=id, user_id=current_user.id).first()
    if not tx:
        flash('Transaction not found.', 'error')
        return redirect(url_for('transactions.list_transactions'))

    try: amount = float(request.form.get('amount', '0'))
    except ValueError:
        flash('Invalid amount.', 'error')
        return redirect(url_for('transactions.list_transactions'))

    tx_type = request.form.get('type', 'income')
    if tx_type == 'expense' and amount > 0: amount = -amount
    elif tx_type == 'income' and amount < 0: amount = abs(amount)

    date_str = request.form.get('date', '')
    try: tx.date = datetime.strptime(date_str, '%Y-%m-%d')
    except: pass

    tx.amount = amount
    tx.category = request.form.get('category', 'Uncategorized')
    tx.description = request.form.get('description', '')
    tx.is_tax_deductible = request.form.get('is_tax_deductible') == 'on'

    db.session.commit()
    flash('Transaction updated!', 'success')
    return redirect(url_for('transactions.list_transactions'))


@transactions_bp.route('/transactions/delete/<int:id>', methods=['POST'])
@login_required
def delete(id):
    tx = Transaction.query.filter_by(id=id, user_id=current_user.id).first()
    if tx:
        db.session.delete(tx)
        db.session.commit()
        flash('Transaction deleted. Tax estimates will update on next calculation.', 'success')
    else:
        flash('Transaction not found.', 'error')
    return redirect(url_for('transactions.list_transactions'))


@transactions_bp.route('/transactions/export/csv')
@login_required
def export_csv():
    import csv, io
    uid = current_user.id

    # Apply same filters as list view
    category = request.args.get('category', '')
    tx_type = request.args.get('type', '')
    month = request.args.get('month', '')
    year = request.args.get('year', '')

    all_tx = Transaction.query.filter_by(user_id=uid).order_by(Transaction.date.desc()).all()

    transactions = all_tx
    if category:
        transactions = [t for t in transactions if t.category == category]
    if tx_type == 'income':
        transactions = [t for t in transactions if t.amount > 0]
    elif tx_type == 'expense':
        transactions = [t for t in transactions if t.amount < 0]
    if month:
        try:
            m = int(month)
            transactions = [t for t in transactions if t.date.month == m]
        except: pass
    if year:
        try:
            y = int(year)
            transactions = [t for t in transactions if t.date.year == y]
        except: pass

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Date', 'Type', 'Category', 'Description', 'Amount', 'Tax Deductible'])

    sym = {'USD':'$','EUR':'€','GBP':'£','CAD':'C$','AUD':'A$','INR':'₹','JPY':'¥'}.get(current_user.currency, '$')

    for tx in transactions:
        writer.writerow([
            tx.date.strftime('%Y-%m-%d'),
            'Income' if tx.amount > 0 else 'Expense',
            tx.category or 'Other',
            tx.description or '',
            f"{abs(tx.amount):.2f}",
            'Yes' if tx.is_tax_deductible else 'No'
        ])

    # Add summary rows
    total_income = sum(t.amount for t in transactions if t.amount > 0)
    total_expenses = sum(abs(t.amount) for t in transactions if t.amount < 0)
    total_deductible = sum(abs(t.amount) for t in transactions if t.amount < 0 and t.is_tax_deductible)
    net = total_income - total_expenses
    tax_saving = total_deductible * current_user.default_tax_rate

    writer.writerow([])
    writer.writerow(['--- SUMMARY ---'])
    writer.writerow(['Total Income', '', '', '', f"{total_income:.2f}"])
    writer.writerow(['Total Expenses', '', '', '', f"{total_expenses:.2f}"])
    writer.writerow(['Deductible Expenses', '', '', '', f"{total_deductible:.2f}"])
    writer.writerow(['Net', '', '', '', f"{net:.2f}"])
    writer.writerow(['Tax Saving from Deductions', '', '', '', f"{tax_saving:.2f}"])
    writer.writerow(['Tax Rate Used', '', '', '', f"{current_user.default_tax_rate*100:.0f}%"])

    output.seek(0)
    from flask import Response
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename=transactions_{datetime.now().strftime("%Y%m%d")}.csv'})


@transactions_bp.route('/transactions/export/pdf')
@login_required
def export_pdf():
    from flask import Response
    uid = current_user.id

    # Apply same filters
    category = request.args.get('category', '')
    tx_type = request.args.get('type', '')
    month = request.args.get('month', '')
    year = request.args.get('year', '')

    all_tx = Transaction.query.filter_by(user_id=uid).order_by(Transaction.date.desc()).all()
    transactions = all_tx
    if category:
        transactions = [t for t in transactions if t.category == category]
    if tx_type == 'income':
        transactions = [t for t in transactions if t.amount > 0]
    elif tx_type == 'expense':
        transactions = [t for t in transactions if t.amount < 0]
    if month:
        try:
            m = int(month)
            transactions = [t for t in transactions if t.date.month == m]
        except: pass
    if year:
        try:
            y = int(year)
            transactions = [t for t in transactions if t.date.year == y]
        except: pass

    # Build HTML for PDF
    sym = {'USD':'$','EUR':'€','GBP':'£','CAD':'C$','AUD':'A$','INR':'₹','JPY':'¥'}.get(current_user.currency, '$')

    total_income = sum(t.amount for t in transactions if t.amount > 0)
    total_expenses = sum(abs(t.amount) for t in transactions if t.amount < 0)
    total_deductible = sum(abs(t.amount) for t in transactions if t.amount < 0 and t.is_tax_deductible)
    net = total_income - total_expenses
    tax_saving = total_deductible * current_user.default_tax_rate

    html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<style>
  body {{ font-family: 'Helvetica Neue', Arial, sans-serif; color: #1a1a1a; margin: 40px; font-size: 12px; }}
  h1 {{ font-size: 24px; color: #16a34a; margin-bottom: 4px; }}
  h2 {{ font-size: 16px; color: #374151; margin-top: 24px; border-bottom: 2px solid #e5e7eb; padding-bottom: 6px; }}
  .subtitle {{ color: #6b7280; font-size: 13px; margin-bottom: 20px; }}
  .summary-grid {{ display: flex; gap: 16px; margin-bottom: 20px; }}
  .summary-card {{ flex: 1; background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 8px; padding: 12px; }}
  .summary-card .label {{ font-size: 11px; color: #6b7280; text-transform: uppercase; letter-spacing: 0.5px; }}
  .summary-card .value {{ font-size: 18px; font-weight: 700; margin-top: 4px; }}
  .green {{ color: #16a34a; }}
  .red {{ color: #dc2626; }}
  .amber {{ color: #d97706; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 8px; }}
  th {{ background: #f3f4f6; text-align: left; padding: 8px 10px; font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; color: #6b7280; border-bottom: 2px solid #e5e7eb; }}
  td {{ padding: 7px 10px; border-bottom: 1px solid #f3f4f6; }}
  tr:nth-child(even) {{ background: #fafafa; }}
  .amount-pos {{ color: #16a34a; font-weight: 600; }}
  .amount-neg {{ color: #dc2626; font-weight: 600; }}
  .badge {{ display: inline-block; padding: 2px 6px; border-radius: 4px; font-size: 10px; font-weight: 600; }}
  .badge-ded {{ background: #dcfce7; color: #16a34a; }}
  .badge-nd {{ background: #f3f4f6; color: #9ca3af; }}
  .footer {{ margin-top: 30px; padding-top: 12px; border-top: 1px solid #e5e7eb; color: #9ca3af; font-size: 10px; }}
</style></head><body>
  <h1>FreelanceCash</h1>
  <p class="subtitle">Transaction Report &middot; {current_user.email} &middot; Generated {datetime.now().strftime('%B %d, %Y at %I:%M %p')}</p>

  <h2>Summary</h2>
  <div class="summary-grid">
    <div class="summary-card"><div class="label">Total Income</div><div class="value green">{sym}{total_income:,.2f}</div></div>
    <div class="summary-card"><div class="label">Total Expenses</div><div class="value red">{sym}{total_expenses:,.2f}</div></div>
    <div class="summary-card"><div class="label">Deductible</div><div class="value amber">{sym}{total_deductible:,.2f}</div></div>
    <div class="summary-card"><div class="label">Net</div><div class="value {'green' if net >= 0 else 'red'}">{sym}{net:,.2f}</div></div>
  </div>

  <div class="summary-grid">
    <div class="summary-card"><div class="label">Tax Rate</div><div class="value">{current_user.default_tax_rate*100:.0f}%</div></div>
    <div class="summary-card"><div class="label">Tax Saving from Deductions</div><div class="value green">{sym}{tax_saving:,.2f}</div></div>
  </div>

  <h2>Transactions ({len(transactions)} records)</h2>
  <table>
    <thead><tr><th>Date</th><th>Description</th><th>Category</th><th style="text-align:right">Amount</th><th style="text-align:center">Deductible</th></tr></thead>
    <tbody>"""

    for tx in transactions:
        cls = 'amount-pos' if tx.amount > 0 else 'amount-neg'
        sign = '+' if tx.amount > 0 else '-'
        ded_badge = '<span class="badge badge-ded">Yes</span>' if tx.is_tax_deductible else '<span class="badge badge-nd">No</span>'
        html += f"""<tr>
            <td>{tx.date.strftime('%b %d, %Y')}</td>
            <td>{tx.description or '-'}</td>
            <td>{tx.category or 'Other'}</td>
            <td style="text-align:right" class="{cls}">{sign}{sym}{abs(tx.amount):,.2f}</td>
            <td style="text-align:center">{ded_badge}</td>
        </tr>"""

    html += f"""
    </tbody>
  </table>
  <div class="footer">FreelanceCash &middot; This report is for informational purposes only and does not constitute tax advice.</div>
</body></html>"""

    # Use weasyprint to convert HTML to PDF if available, else use a simpler approach
    try:
        from weasyprint import HTML as WeasyHTML
        pdf_bytes = WeasyHTML(string=html).write_pdf()
        return Response(pdf_bytes, mimetype='application/pdf',
            headers={'Content-Disposition': f'attachment; filename=transactions_{datetime.now().strftime("%Y%m%d")}.pdf'})
    except ImportError:
        # Fallback: return the HTML as a downloadable file
        return Response(html, mimetype='text/html',
            headers={'Content-Disposition': f'attachment; filename=transactions_{datetime.now().strftime("%Y%m%d")}.html'})
