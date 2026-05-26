<div align="center">

# 💰 GigLedger

### Freelance Finance Dashboard — Income, Expenses & Quarterly Taxes in One Place

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.1-000000?style=flat-square&logo=flask&logoColor=white)](https://flask.palletsprojects.com)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)

</div>

---

> **Stop guessing how much tax you owe.** GigLedger is a self-hosted finance dashboard built for freelancers, contractors, and gig workers who want a clear picture of income, expenses, and quarterly tax obligations — without the complexity of full accounting software.
<img width="3441" height="1356" alt="Screenshot from 2026-05-26 08-02-48" src="https://github.com/user-attachments/assets/55177c29-82c6-4a9b-9d7c-0aaf07670152" />


---

## ✨ Why GigLedger?

Freelancers have unique financial challenges that personal finance apps don't solve and accounting software overcomplicates. GigLedger fills that gap with three core questions answered at a glance:

| Question | Answer |
|---|---|
| **How much can I safely spend?** | **Safe to Spend** = Bank Balance − Tax Obligation |
| **What do I owe this quarter?** | **Quarterly Tax Estimator** = Net Income × Tax Rate |
| **How long can I survive?** | **Runway Calculator** = Balance ÷ Avg Monthly Expenses |

No more setting aside random percentages. No more spreadsheet gymnastics. Just clarity.

---

## 🚀 Features

### 📊 Smart Dashboard
- **Hero Cards** — Monthly Income, Monthly Expenses, Safe to Spend, Tax Reserve
- **Trend Indicators** — Month-over-month % change at a glance
- **6-Month Bar Chart** — Income vs. Expenses trend (Chart.js)
- **Expense Breakdown** — Doughnut chart by category for the current month
- **Quick Add** — Add income or expenses right from the dashboard
- **Runway Calculator** — Color-coded survival months (green ≥6, yellow ≥3, red <3)
- **Bank Balance & Net This Month** cards


### 💸 Transactions
- **Full transaction table** with filter bar (type, category, month, year)
- **Tax Impact column** — See how each transaction affects your tax burden
- **Deductible highlighting** — Green rows for tax-deductible expenses
- **Summary bar** — Total Income, Expenses, Deductible amount, Tax Saving, Net
- **Add Transaction modal** — Dynamic categories, real-time tax savings preview
- **Export to PDF or CSV** — Filtered reports with full detail and summary rows


### 🧾 Quarterly Tax Estimator
- **Q1–Q4 breakdown cards** — Income, Deductions, Net Income, Estimated Tax per quarter
- **Current quarter highlight** with underfunded warnings
- **One-click recalculate** — Persists estimates to the database
- **"How taxes are calculated" explainer** — Transparent methodology section



### ⚙️ Settings
- **Tax Rate** — Custom percentage with quick presets (25%, 30%, 35%)
- **Currency** — 7 supported: USD, EUR, GBP, CAD, AUD, INR, JPY
- **Custom Categories** — Add, remove, or reset income and expense categories
- **Profile** — Email and member-since display



### 🔐 Authentication
- Secure login with Flask-Login + Flask-Bcrypt
- "Remember me" session support
- Demo account pre-loaded with 6 months of realistic data

---

## 🧠 Core Algorithms

### 1. Safe to Spend
```
Safe Balance = Bank Balance − Total Tax Obligation
```
Your bank balance minus every dollar you already owe in taxes this year. This is the number you can actually spend without getting into trouble.

### 2. Quarterly Tax Estimator
```
Quarterly Net Income = Income − Deductible Expenses
Estimated Tax = max(0, Quarterly Net Income × Tax Rate)
```
Only expenses marked as **tax-deductible** reduce your taxable income. The app calculates this automatically per quarter and shows the real-time impact on every transaction.

### 3. Runway Calculator
```
Runway (months) = Current Balance ÷ Average Monthly Expenses (last 3 months)
```
Tells you how many months you can survive at your current spending rate. Color-coded for instant awareness.

---

## 🛠 Tech Stack

| Layer | Technology | Why |
|---|---|---|
| **Backend** | Flask 3.1 | Lightweight, Pythonic, perfect for solo-dev tools |
| **Database** | SQLite via SQLAlchemy | Zero-config, portable, great for self-hosted |
| **Auth** | Flask-Login + Flask-Bcrypt | Secure session management with hashed passwords |
| **Templates** | Jinja2 | Server-rendered, fast, no build step |
| **Styling** | TailwindCSS (CDN) | Utility-first, no CSS files to manage |
| **Charts** | Chart.js 4.4 | Beautiful bar + doughnut charts |
| **PDF Export** | WeasyPrint | Professional-quality PDF reports |
| **CSV Export** | Python csv + StringIO | Lightweight, no extra dependencies |

---

## 📦 Quick Start

### Prerequisites
- Python 3.11 or higher
- pip

### Installation

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/gigledger.git
cd gigledger

# Create a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r freelancecash/requirements.txt

# Run the app
python freelancecash/run.py
```

The app starts at **http://localhost:3030**

### Demo Account

Log in instantly with pre-loaded data:

| Field | Value |
|---|---|
| **Email** | `demo@freelancecash.com` |
| **Password** | `demo1234` |

The demo account includes ~40 transactions across 6 months with a realistic mix of income, deductible expenses, and non-deductible expenses.

---

## 📁 Project Structure

```
gigledger/
├── freelancecash/
│   ├── app.py                  # Flask app factory, config, seed data
│   ├── models.py               # SQLAlchemy models (User, Transaction, TaxEstimate)
│   ├── finance.py              # Core financial calculation engine
│   ├── run.py                  # Entry point (port 3030)
│   ├── requirements.txt        # Python dependencies
│   ├── freelancecash.db        # SQLite database (auto-created)
│   ├── routes/
│   │   ├── auth.py             # Login / Signup / Logout
│   │   ├── dashboard.py        # Main dashboard + Quick Add
│   │   ├── transactions.py     # CRUD + CSV/PDF export
│   │   ├── taxes.py            # Quarterly tax estimator
│   │   └── settings.py         # Tax rate, currency, category management
│   └── templates/
│       ├── base.html           # Layout: sidebar + mobile nav
│       ├── auth/
│       │   ├── login.html
│       │   └── signup.html
│       ├── dashboard/
│       │   └── index.html      # Full dashboard with charts
│       ├── transactions/
│       │   └── index.html      # Transaction table + filters + export
│       ├── taxes/
│       │   └── index.html      # Quarterly tax cards
│       └── settings/
│           └── index.html      # Profile, tax rate, currency, categories
└── README.md
```

---

## 🔌 API Endpoints

| Method | Route | Description |
|---|---|---|
| `GET/POST` | `/auth/login` | User login |
| `GET/POST` | `/auth/signup` | User registration |
| `GET` | `/auth/logout` | User logout |
| `GET/POST` | `/dashboard` | Dashboard view + Quick Add |
| `GET` | `/transactions` | Transaction list with filters |
| `POST` | `/transactions/add` | Add new transaction |
| `POST` | `/transactions/delete/<id>` | Delete a transaction |
| `GET` | `/transactions/export/csv` | Export filtered transactions as CSV |
| `GET` | `/transactions/export/pdf` | Export filtered transactions as PDF |
| `GET/POST` | `/taxes` | Quarterly tax breakdown + recalculate |
| `GET/POST` | `/settings` | Tax rate, currency, categories |

---

## 🖼 Screenshots

> **Tip:** Add your own screenshots by placing images in a `screenshots/` folder at the repo root and updating the image paths above.

<img width="3441" height="1356" alt="Screenshot from 2026-05-26 08-03-40" src="https://github.com/user-attachments/assets/204e71a6-d31f-4ec4-a524-696aebf4a520" />
<img width="3441" height="1356" alt="Screenshot from 2026-05-26 08-03-16" src="https://github.com/user-attachments/assets/7223debc-b58e-42e5-aa17-84fdc293c665" />
<img width="3441" height="1356" alt="Screenshot from 2026-05-26 08-02-54" src="https://github.com/user-attachments/assets/cb9f0649-6803-4e37-b5e1-3b53466c8fd7" />
<img width="3441" height="1356" alt="Screenshot from 2026-05-26 08-02-48" src="https://github.com/user-attachments/assets/7f06ba6d-6b7d-4e54-a397-aabbb0297958" />
<img width="3441" height="1356" alt="Screenshot from 2026-05-26 08-02-06" src="https://github.com/user-attachments/assets/b084738a-157d-4fd3-ac88-078ed72ecc18" />
<img width="2290" height="1356" alt="Screenshot from 2026-05-26 08-01-29" src="https://github.com/user-attachments/assets/cf53958b-d1b6-474a-b566-9165cc7c7a6a" />


---

## 🎯 Roadmap

- [ ] **Bank integration** — Auto-import via Plaid or Open Banking
- [ ] **Multi-currency conversion** — Real-time exchange rates
- [ ] **Recurring transactions** — Auto-add monthly subscriptions
- [ ] **Invoice generator** — Create and send invoices from tracked income
- [ ] **Mobile app** — React Native companion
- [ ] **Dark mode** — Because freelancers work at night
- [ ] **Multi-user / Team** — Shared workspaces for small studios

---

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

---

<div align="center">

**Built for freelancers, by a freelancer.**

⭐ Star this repo if it helped you!

## Contact
For any help/support, feel free to contact me on Telegram @cyberoxide, Instagram @coding_memz, Whatsapp +447598820751
</div>
