"""
GigLedger - Invoices Blueprint
"""
from datetime import datetime, timedelta
from flask import Blueprint, render_template, redirect, url_for, request, flash, Response
from flask_login import login_required, current_user
from ..models import db, Invoice, InvoiceLineItem, Client, Transaction

invoices_bp = Blueprint('invoices', __name__)


@invoices_bp.route('/invoices')
@login_required
def list_invoices():
    uid = current_user.id
    status_filter = request.args.get('status', 'all')

    query = Invoice.query.filter_by(user_id=uid)
    if status_filter and status_filter != 'all':
        query = query.filter_by(status=status_filter)
    invoices = query.order_by(Invoice.created_at.desc()).all()

    # Summary calculations
    now = datetime.now()
    total_outstanding = sum(inv.total for inv in Invoice.query.filter_by(
        user_id=uid).all() if inv.status in ('sent', 'overdue'))
    paid_this_month = sum(inv.total for inv in Invoice.query.filter_by(
        user_id=uid, status='paid').all()
        if inv.paid_date and inv.paid_date.year == now.year and inv.paid_date.month == now.month)
    total_overdue = sum(inv.total for inv in Invoice.query.filter_by(
        user_id=uid, status='overdue').all())

    clients = Client.query.filter_by(user_id=uid, is_active=True).order_by(Client.name).all()

    return render_template('invoices/index.html',
        invoices=invoices,
        status_filter=status_filter,
        total_outstanding=total_outstanding,
        paid_this_month=paid_this_month,
        total_overdue=total_overdue,
        clients=clients,
        currency=current_user.currency)


@invoices_bp.route('/invoices/create', methods=['GET'])
@login_required
def create_form():
    uid = current_user.id
    clients = Client.query.filter_by(user_id=uid, is_active=True).order_by(Client.name).all()
    today = datetime.now().strftime('%Y-%m-%d')
    default_due = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')

    return render_template('invoices/create.html',
        clients=clients,
        today=today,
        default_due=default_due,
        tax_rate=current_user.default_tax_rate,
        currency=current_user.currency)


@invoices_bp.route('/invoices/create', methods=['POST'])
@login_required
def create_invoice():
    uid = current_user.id
    client_id = request.form.get('client_id', '')
    issue_date_str = request.form.get('issue_date', '')
    due_date_str = request.form.get('due_date', '')
    notes = request.form.get('notes', '')
    action = request.form.get('action', 'draft')

    # Parse dates
    try:
        issue_date = datetime.strptime(issue_date_str, '%Y-%m-%d') if issue_date_str else datetime.now()
    except ValueError:
        issue_date = datetime.now()

    try:
        due_date = datetime.strptime(due_date_str, '%Y-%m-%d') if due_date_str else issue_date + timedelta(days=30)
    except ValueError:
        due_date = issue_date + timedelta(days=30)

    # Parse line items
    descriptions = request.form.getlist('description[]')
    quantities = request.form.getlist('quantity[]')
    rates = request.form.getlist('rate[]')

    if not descriptions or not descriptions[0]:
        flash('Please add at least one line item.', 'error')
        return redirect(url_for('invoices.create_form'))

    # Calculate totals
    line_items_data = []
    subtotal = 0
    for i in range(len(descriptions)):
        desc = descriptions[i].strip()
        if not desc:
            continue
        try:
            qty = float(quantities[i]) if i < len(quantities) else 1
        except (ValueError, IndexError):
            qty = 1
        try:
            rate = float(rates[i]) if i < len(rates) else 0
        except (ValueError, IndexError):
            rate = 0
        amount = qty * rate
        subtotal += amount
        line_items_data.append({'description': desc, 'quantity': qty, 'rate': rate, 'amount': amount})

    if not line_items_data:
        flash('Please add at least one line item with a description.', 'error')
        return redirect(url_for('invoices.create_form'))

    tax_amount = subtotal * current_user.default_tax_rate
    total = subtotal + tax_amount

    # Generate invoice number
    invoice_number = current_user.get_next_invoice_number()

    # Set status
    status = 'sent' if action == 'send' else 'draft'

    # Create invoice
    invoice = Invoice(
        user_id=uid,
        client_id=int(client_id) if client_id else None,
        invoice_number=invoice_number,
        status=status,
        issue_date=issue_date,
        due_date=due_date,
        notes=notes,
        subtotal=subtotal,
        tax_amount=tax_amount,
        total=total)
    db.session.add(invoice)
    db.session.flush()  # Get the invoice ID

    # Create line items
    for item in line_items_data:
        li = InvoiceLineItem(
            invoice_id=invoice.id,
            description=item['description'],
            quantity=item['quantity'],
            rate=item['rate'],
            amount=item['amount'])
        db.session.add(li)

    db.session.commit()

    if status == 'sent':
        flash(f'Invoice {invoice_number} created and marked as sent!', 'success')
    else:
        flash(f'Invoice {invoice_number} saved as draft.', 'success')

    return redirect(url_for('invoices.detail', id=invoice.id))


@invoices_bp.route('/invoices/status/<int:id>', methods=['POST'])
@login_required
def update_status(id):
    invoice = Invoice.query.filter_by(id=id, user_id=current_user.id).first()
    if not invoice:
        flash('Invoice not found.', 'error')
        return redirect(url_for('invoices.list_invoices'))

    new_status = request.form.get('status', '')
    valid_statuses = ['draft', 'sent', 'paid', 'overdue', 'cancelled']
    if new_status not in valid_statuses:
        flash('Invalid status.', 'error')
        return redirect(url_for('invoices.detail', id=id))

    # If marking as paid, create a transaction and set paid_date
    if new_status == 'paid' and invoice.status != 'paid':
        invoice.paid_date = datetime.now()

        # Create an income transaction linked to this invoice
        client_name = invoice.client.name if invoice.client else 'Unknown Client'
        transaction = Transaction(
            user_id=current_user.id,
            amount=invoice.total,
            date=datetime.now(),
            category='Client Payment',
            description=f'Payment for Invoice {invoice.invoice_number} - {client_name}',
            is_tax_deductible=False,
            source='invoice',
            invoice_id=invoice.id)
        db.session.add(transaction)

    # If moving away from paid, remove the linked transaction
    if invoice.status == 'paid' and new_status != 'paid':
        invoice.paid_date = None
        linked_tx = Transaction.query.filter_by(invoice_id=invoice.id).first()
        if linked_tx:
            db.session.delete(linked_tx)

    invoice.status = new_status
    db.session.commit()

    status_labels = {
        'draft': 'Draft', 'sent': 'Sent', 'paid': 'Paid',
        'overdue': 'Overdue', 'cancelled': 'Cancelled'
    }
    flash(f'Invoice {invoice.invoice_number} marked as {status_labels.get(new_status, new_status)}.', 'success')
    return redirect(url_for('invoices.detail', id=id))


@invoices_bp.route('/invoices/delete/<int:id>', methods=['POST'])
@login_required
def delete(id):
    invoice = Invoice.query.filter_by(id=id, user_id=current_user.id).first()
    if not invoice:
        flash('Invoice not found.', 'error')
        return redirect(url_for('invoices.list_invoices'))

    # Delete linked transactions
    linked_txs = Transaction.query.filter_by(invoice_id=invoice.id).all()
    for tx in linked_txs:
        db.session.delete(tx)

    inv_num = invoice.invoice_number
    db.session.delete(invoice)
    db.session.commit()
    flash(f'Invoice {inv_num} deleted.', 'success')
    return redirect(url_for('invoices.list_invoices'))


@invoices_bp.route('/invoices/<int:id>')
@login_required
def detail(id):
    invoice = Invoice.query.filter_by(id=id, user_id=current_user.id).first()
    if not invoice:
        flash('Invoice not found.', 'error')
        return redirect(url_for('invoices.list_invoices'))

    # Eagerly load line items
    line_items = InvoiceLineItem.query.filter_by(invoice_id=invoice.id).all()

    return render_template('invoices/detail.html',
        invoice=invoice,
        line_items=line_items,
        currency=current_user.currency,
        tax_rate=current_user.default_tax_rate,
        business_name=current_user.business_name,
        business_address=current_user.business_address,
        business_phone=current_user.business_phone,
        invoice_note=current_user.invoice_note)


@invoices_bp.route('/invoices/<int:id>/pdf')
@login_required
def generate_pdf(id):
    invoice = Invoice.query.filter_by(id=id, user_id=current_user.id).first()
    if not invoice:
        flash('Invoice not found.', 'error')
        return redirect(url_for('invoices.list_invoices'))

    line_items = InvoiceLineItem.query.filter_by(invoice_id=invoice.id).all()

    sym = {'USD': '$', 'EUR': '\u20ac', 'GBP': '\u00a3',
           'CAD': 'C$', 'AUD': 'A$', 'INR': '\u20b9', 'JPY': '\u00a5'
           }.get(current_user.currency, '$')

    status_colors = {
        'draft': '#6b7280', 'sent': '#3b82f6', 'paid': '#16a34a',
        'overdue': '#dc2626', 'cancelled': '#9ca3af'
    }
    status_color = status_colors.get(invoice.status, '#6b7280')

    # Build HTML for PDF
    li_rows = ''
    for li in line_items:
        li_rows += f"""<tr>
            <td style="padding: 10px 12px; border-bottom: 1px solid #f3f4f6; color: #1f2937; font-weight: 500;">{li.description}</td>
            <td style="padding: 10px 12px; border-bottom: 1px solid #f3f4f6; text-align: center; color: #374151;">{li.quantity:.1f}</td>
            <td style="padding: 10px 12px; border-bottom: 1px solid #f3f4f6; text-align: right; color: #374151;">{sym}{li.rate:,.2f}</td>
            <td style="padding: 10px 12px; border-bottom: 1px solid #f3f4f6; text-align: right; font-weight: 600; color: #1f2937;">{sym}{li.amount:,.2f}</td>
        </tr>"""

    client_info = ''
    if invoice.client:
        c = invoice.client
        client_info = f"""<div style="margin-bottom: 4px; font-weight: 600; color: #111827; font-size: 15px;">{c.name}</div>"""
        if c.company:
            client_info += f"""<div style="color: #374151; font-size: 13px;">{c.company}</div>"""
        if c.email:
            client_info += f"""<div style="color: #6b7280; font-size: 13px;">{c.email}</div>"""
        if c.address:
            client_info += f"""<div style="color: #6b7280; font-size: 13px; white-space: pre-line;">{c.address}</div>"""
    else:
        client_info = '<div style="color: #9ca3af;">No client assigned</div>'

    html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<style>
  body {{ font-family: 'Helvetica Neue', Arial, sans-serif; color: #1a1a1a; margin: 40px; font-size: 13px; }}
  .invoice-header {{ display: flex; justify-content: space-between; margin-bottom: 40px; }}
  .invoice-title {{ font-size: 32px; font-weight: 800; color: #111827; }}
  .invoice-meta {{ text-align: right; }}
  .invoice-meta .inv-num {{ font-size: 18px; font-weight: 700; color: #111827; }}
  .invoice-meta .date {{ color: #6b7280; font-size: 13px; margin-top: 4px; }}
  .status-badge {{ display: inline-block; padding: 4px 14px; border-radius: 99px; font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; color: white; background: {status_color}; margin-top: 8px; }}
  .parties {{ display: flex; justify-content: space-between; margin-bottom: 36px; gap: 40px; }}
  .party-section {{ flex: 1; }}
  .party-label {{ font-size: 11px; text-transform: uppercase; letter-spacing: 1px; color: #9ca3af; margin-bottom: 8px; font-weight: 600; }}
  table {{ width: 100%; border-collapse: collapse; margin-bottom: 24px; }}
  th {{ background: #f9fafb; text-align: left; padding: 10px 12px; font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; color: #6b7280; border-bottom: 2px solid #e5e7eb; }}
  th.num {{ text-align: right; }}
  th.center {{ text-align: center; }}
  .totals-section {{ display: flex; justify-content: flex-end; }}
  .totals-table {{ width: 280px; }}
  .totals-table td {{ padding: 8px 12px; }}
  .totals-table .label {{ color: #6b7280; }}
  .totals-table .value {{ text-align: right; font-weight: 600; color: #1f2937; }}
  .totals-table .total-row {{ border-top: 2px solid #111827; font-size: 18px; }}
  .totals-table .total-row .label {{ font-weight: 700; color: #111827; }}
  .totals-table .total-row .value {{ font-weight: 800; color: #111827; }}
  .notes {{ margin-top: 40px; padding-top: 16px; border-top: 1px solid #e5e7eb; }}
  .notes .notes-label {{ font-size: 11px; text-transform: uppercase; letter-spacing: 1px; color: #9ca3af; margin-bottom: 6px; font-weight: 600; }}
  .notes .notes-text {{ color: #374151; font-size: 13px; }}
  .footer {{ margin-top: 48px; text-align: center; color: #9ca3af; font-size: 11px; }}
</style></head><body>
  <div class="invoice-header">
    <div>
      <div class="invoice-title">INVOICE</div>
    </div>
    <div class="invoice-meta">
      <div class="inv-num">{invoice.invoice_number}</div>
      <div class="date">Issued: {invoice.issue_date.strftime('%B %d, %Y')}</div>
      <div class="date">Due: {invoice.due_date.strftime('%B %d, %Y') if invoice.due_date else 'N/A'}</div>
      <div class="status-badge">{invoice.status.upper()}</div>
    </div>
  </div>

  <div class="parties">
    <div class="party-section">
      <div class="party-label">From</div>
      <div style="font-weight: 600; color: #111827; font-size: 15px;">{current_user.business_name or current_user.email}</div>
      {"<div style='color: #6b7280; font-size: 13px; white-space: pre-line;'>" + current_user.business_address + "</div>" if current_user.business_address else ""}
      {"<div style='color: #6b7280; font-size: 13px;'>" + current_user.business_phone + "</div>" if current_user.business_phone else ""}
    </div>
    <div class="party-section">
      <div class="party-label">Bill To</div>
      {client_info}
    </div>
  </div>

  <table>
    <thead><tr>
      <th>Description</th>
      <th class="center">Qty</th>
      <th class="num">Rate</th>
      <th class="num">Amount</th>
    </tr></thead>
    <tbody>{li_rows}</tbody>
  </table>

  <div class="totals-section">
    <div class="totals-table">
      <table style="margin:0;">
        <tr><td class="label">Subtotal</td><td class="value">{sym}{invoice.subtotal:,.2f}</td></tr>
        <tr><td class="label">Tax ({current_user.default_tax_rate*100:.0f}%)</td><td class="value">{sym}{invoice.tax_amount:,.2f}</td></tr>
        <tr class="total-row"><td class="label">Total</td><td class="value">{sym}{invoice.total:,.2f}</td></tr>
      </table>
    </div>
  </div>

  {"<div class='notes'><div class='notes-label'>Notes</div><div class='notes-text'>" + (invoice.notes or current_user.invoice_note or '') + "</div></div>" if (invoice.notes or current_user.invoice_note) else ""}

  <div class="footer">Thank you for your business!</div>
</body></html>"""

    try:
        from weasyprint import HTML as WeasyHTML
        pdf_bytes = WeasyHTML(string=html).write_pdf()
        return Response(pdf_bytes, mimetype='application/pdf',
            headers={'Content-Disposition': f'attachment; filename=invoice_{invoice.invoice_number}.pdf'})
    except ImportError:
        return Response(html, mimetype='text/html',
            headers={'Content-Disposition': f'attachment; filename=invoice_{invoice.invoice_number}.html'})
