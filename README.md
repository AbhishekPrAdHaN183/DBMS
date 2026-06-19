# Nexus OMS: Warehouse Inventory & Order Management System

Nexus OMS is an industry-grade, database-driven Python backend application that serves as a **Warehouse Inventory & Order Management System**. It leverages **SQLAlchemy 2.0 ORM** on top of **SQLite** with custom check constraints, programmatically enforced foreign keys, and atomic transaction management. 

It provides two user-facing interfaces:
1. **Interactive Rich CLI Dashboard** — A colorized, command-menu application.
2. **Glassmorphic Web Dashboard** — A fast, modern single-page dashboard built using **FastAPI**, HTML5, CSS Variables, and **Chart.js** telemetry charts.

---

## 🏗️ System Architecture & Schema Design

### 1. Unified Architecture
```
    ┌──────────────────────┐      ┌─────────────────────────┐
    │  Glassmorphic Web    │      │    Interactive Rich     │
    │  Dashboard (HTML/JS) │      │      CLI Interface      │
    └──────────┬───────────┘      └────────────┬────────────┘
               │ (REST API)                    │ (Direct Service Call)
               ▼                               │
    ┌──────────────────────────────────────────┼────────────┐
    │             FastAPI Backend              │            │
    └──────────────────┬───────────────────────┼────────────┘
                       │                       │
                       ▼                       ▼
    ┌───────────────────────────────────────────────────────┐
    │                 CRUD Repository Layer                 │
    └──────────────────────────┬────────────────────────────┘
                               ▼
    ┌───────────────────────────────────────────────────────┐
    │                 SQLAlchemy 2.0 ORM                    │
    └──────────────────────────┬────────────────────────────┘
                               ▼ (PRAGMA foreign_keys=ON)
    ┌───────────────────────────────────────────────────────┐
    │                  SQLite Database File                 │
    └───────────────────────────────────────────────────────┘
```

### 2. Database Entities & Relationships
- **Supplier** (One-to-Many with `Product`): Stores warehouse distributors.
- **Product** (One-to-Many with `OrderItem`, `StockTransaction`): Stores catalog items. Contains indexing on `sku` and constraints checking that `price > 0` and `stock_quantity >= 0`.
- **Customer** (One-to-Many with `Order`): Stores client files with email syntax verification.
- **Order** (One-to-Many with `OrderItem`): Tracks billing files (`PENDING`, `SHIPPED`, `DELIVERED`, `CANCELLED`).
- **OrderItem** (Many-to-One with `Order` and `Product`): Junction entity representing line item transactions.
- **StockTransaction** (Many-to-One with `Product`): Automated audit logs tracking stock adjustments (`IN` or `OUT`).

---

## ⚡ Key Technical Features & Implementations

### 🔒 Atomic Transaction Boundaries
When a customer places an order, the system executes the entire operation inside a single database transaction:
1. Verifies customer existence.
2. Loops through order items:
   - Queries product and verifies stock limits.
   - Throws `InsufficientStockError` and **aborts/rolls back** the entire session if stock is insufficient (so other items in the cart are not deducted).
   - Deducts product stock.
   - Creates a transaction log of type `OUT` for the product.
   - Creates `OrderItem` record.
3. Calculates total amount and updates the main `Order` header.
4. Commits the session cleanly.

If any line validation fails, the transaction is immediately rolled back, ensuring stock counts and order ledgers are never left in inconsistent states.

### 📈 Query Optimizations
- **N+1 Query Elimination**: Pre-fetches related objects using SQLAlchemy's loading strategies:
  - `joinedload(Order.customer)`: fetches customer profile via a SQL JOIN.
  - `selectinload(Order.items).joinedload(OrderItem.product)`: fetches order items and product descriptions using optimized subqueries.
- **Aggregate DB Metrics**: Statistics like Total Revenue, Inventory Valuation, and Top-Selling Products are calculated directly on the database engine using `func.sum`, `func.count`, and `group_by`, minimizing Python-side memory footprint.
- **Constraints & Indexes**: Database-level `CheckConstraint` blocks invalid inserts/updates, while indexes on `sku` and `email` optimize search speeds.

---

## 📁 Repository Structure
```
pg4/
├── data/
│   └── inventory.db       # Generated SQLite database file
├── src/
│   ├── database.py       # Connection setup & SQLite FK event listeners
│   ├── models.py         # SQLAlchemy ORM models & validation constraints
│   ├── crud.py           # CRUD repository layer & transactional logic
│   ├── cli.py            # Rich Console CLI application
│   ├── app.py            # FastAPI REST API controller
│   └── static/           # SPA Web UI assets
│       ├── index.html    # Single-page dashboard interface
│       ├── styles.css    # Premium CSS design (Dark theme)
│       └── app.js        # API endpoints integration & Chart.js drawing
├── seed_data.py          # Data seeding script
├── verify_db.py          # Automated transaction & constraint validation suite
├── requirements.txt      # Python dependencies list
└── README.md             # Project documentation (this file)
```

---

## 🚀 Installation & Local Operations Guide

### 1. Setup Environment
Ensure Python 3.10+ is installed on your system. Navigate to the project root directory and run:
```bash
# Install required dependencies
pip install -r requirements.txt
```

### 2. Run Database Constraint Tests
Execute the automated test suite to confirm database integrity constraints, validations, and transaction rollback properties are functioning:
```bash
python verify_db.py
```

### 3. Launch Interactive CLI Dashboard
Start the colorized CLI console menu:
```bash
python src/cli.py
```
**Features in CLI:**
- Analytics overview.
- Add products and adjust stock manually.
- Add customers/suppliers.
- Place customer orders with real-time stock checks.
- Review complete inventory audit log.

### 4. Launch Glassmorphic Web Dashboard
Start the FastAPI local server:
```bash
python src/app.py
```
Open your web browser and navigate to:
👉 **[http://127.0.0.1:8000](http://127.0.0.1:8000)**

**Features in Web UI:**
- **Dynamic Stats**: Counters for Revenue, Active Orders, and Stock Valuation.
- **Live Visual Charts**: Bar and line charts tracking stock levels and product pricing.
- **Live Search**: Product lists with filter checkboxes for low-stock items.
- **Operations Panel**: Add products/customers/suppliers via modal forms.
- **Order Placement builder**: Dynamic item rows adder with automatic stock checks.
- **Audit Logs Tab**: Complete inventory transaction history viewer.
- **Live Status toggler**: Update order status via dropdown (e.g. mark SHIPPED, DELIVERED, or CANCELLED to restore stock) with instant page updates.
