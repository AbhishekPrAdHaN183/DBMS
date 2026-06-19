from datetime import datetime
from sqlalchemy import select, func, desc
from sqlalchemy.orm import Session, joinedload, selectinload
from src.models import Supplier, Product, Customer, Order, OrderItem, StockTransaction

class InsufficientStockError(Exception):
    """Raised when an order request exceeds the current product stock."""
    pass

# ==========================================
# Supplier CRUD
# ==========================================
def get_supplier(db: Session, supplier_id: int):
    return db.query(Supplier).filter(Supplier.id == supplier_id).first()

def get_supplier_by_email(db: Session, email: str):
    return db.query(Supplier).filter(Supplier.email == email).first()

def get_suppliers(db: Session, skip: int = 0, limit: int = 100):
    return db.query(Supplier).offset(skip).limit(limit).all()

def create_supplier(db: Session, name: str, email: str, phone: str = None):
    supplier = Supplier(name=name, email=email, phone=phone)
    db.add(supplier)
    db.flush()  # Gets ID before commit
    return supplier

# ==========================================
# Product CRUD & Inventory Management
# ==========================================
def get_product(db: Session, product_id: int):
    return db.query(Product).filter(Product.id == product_id).first()

def get_product_by_sku(db: Session, sku: str):
    return db.query(Product).filter(Product.sku == sku).first()

def get_products(db: Session, skip: int = 0, limit: int = 100, search: str = "", low_stock_threshold: int = None):
    query = db.query(Product).options(joinedload(Product.supplier))
    if search:
        query = query.filter((Product.name.ilike(f"%{search}%")) | (Product.sku.ilike(f"%{search}%")))
    if low_stock_threshold is not None:
        query = query.filter(Product.stock_quantity <= low_stock_threshold)
    return query.offset(skip).limit(limit).all()

def create_product(db: Session, sku: str, name: str, price: float, stock_quantity: int, supplier_id: int, description: str = None):
    # Create the product
    product = Product(
        sku=sku.upper(),
        name=name,
        price=price,
        stock_quantity=stock_quantity,
        supplier_id=supplier_id,
        description=description
    )
    db.add(product)
    db.flush()

    # Log the initial stock transaction if stock > 0
    if stock_quantity > 0:
        transaction = StockTransaction(
            product_id=product.id,
            transaction_type="IN",
            quantity=stock_quantity,
            reason="Initial Restock"
        )
        db.add(transaction)
    
    return product

def update_product(db: Session, product_id: int, updates: dict):
    product = get_product(db, product_id)
    if not product:
        raise ValueError(f"Product with ID {product_id} not found.")
    
    # Handle stock changes explicitly through inventory logs
    if "stock_quantity" in updates:
        new_stock = updates["stock_quantity"]
        diff = new_stock - product.stock_quantity
        if diff != 0:
            adjust_stock(db, product_id, diff, "Manual Adjustment")
        del updates["stock_quantity"]

    for key, value in updates.items():
        if hasattr(product, key):
            setattr(product, key, value)
    
    db.flush()
    return product

def delete_product(db: Session, product_id: int):
    product = get_product(db, product_id)
    if not product:
        raise ValueError(f"Product with ID {product_id} not found.")
    
    # SQLite will throw foreign key constraint errors if this product has order items,
    # which is the correct behaviour (ondelete="RESTRICT")
    db.delete(product)
    db.flush()
    return product

def adjust_stock(db: Session, product_id: int, quantity_change: int, reason: str):
    """Adjusts stock of a product and creates a StockTransaction log."""
    product = get_product(db, product_id)
    if not product:
        raise ValueError(f"Product with ID {product_id} not found.")

    new_stock = product.stock_quantity + quantity_change
    if new_stock < 0:
        raise InsufficientStockError(
            f"Cannot decrease stock by {abs(quantity_change)} units. "
            f"Current stock of {product.name} is {product.stock_quantity}."
        )

    product.stock_quantity = new_stock
    transaction_type = "IN" if quantity_change > 0 else "OUT"
    
    transaction = StockTransaction(
        product_id=product_id,
        transaction_type=transaction_type,
        quantity=abs(quantity_change),
        reason=reason
    )
    db.add(transaction)
    db.flush()
    return product

# ==========================================
# Customer CRUD
# ==========================================
def get_customer(db: Session, customer_id: int):
    return db.query(Customer).filter(Customer.id == customer_id).first()

def get_customer_by_email(db: Session, email: str):
    return db.query(Customer).filter(Customer.email == email).first()

def get_customers(db: Session, skip: int = 0, limit: int = 100):
    return db.query(Customer).offset(skip).limit(limit).all()

def create_customer(db: Session, name: str, email: str, phone: str = None, address: str = None):
    customer = Customer(name=name, email=email, phone=phone, address=address)
    db.add(customer)
    db.flush()
    return customer

# ==========================================
# Order CRUD & Fulfillment (Atomic Transactions)
# ==========================================
def get_order(db: Session, order_id: int):
    # Optimized load using joinedload and selectinload
    return (
        db.query(Order)
        .options(
            joinedload(Order.customer),
            selectinload(Order.items).joinedload(OrderItem.product)
        )
        .filter(Order.id == order_id)
        .first()
    )

def get_orders(db: Session, skip: int = 0, limit: int = 100, status: str = None):
    query = db.query(Order).options(
        joinedload(Order.customer),
        selectinload(Order.items).joinedload(OrderItem.product)
    ).order_by(desc(Order.order_date))
    
    if status:
        query = query.filter(Order.status == status)
    
    return query.offset(skip).limit(limit).all()

def create_order(db: Session, customer_id: int, items_list: list[dict]):
    """
    Creates an order, adds items, updates stock, logs stock transactions.
    This operation runs inside a db transaction session. If any item validation fails,
    an exception is thrown, causing an automatic rollback.
    
    items_list format: [{"product_id": 1, "quantity": 2}, ...]
    """
    customer = get_customer(db, customer_id)
    if not customer:
        raise ValueError(f"Customer with ID {customer_id} does not exist.")

    if not items_list:
        raise ValueError("Cannot place an order with empty items.")

    # Create base Order
    order = Order(customer_id=customer_id, status="PENDING", total_amount=0.0)
    db.add(order)
    db.flush()  # Populates order.id

    running_total = 0.0

    for item in items_list:
        p_id = item["product_id"]
        qty = item["quantity"]
        
        product = get_product(db, p_id)
        if not product:
            raise ValueError(f"Product with ID {p_id} does not exist.")
        
        if qty <= 0:
            raise ValueError(f"Quantity for product {product.name} must be greater than zero.")

        # Check stock availability
        if product.stock_quantity < qty:
            raise InsufficientStockError(
                f"Insufficient stock for '{product.name}' (SKU: {product.sku}). "
                f"Requested: {qty}, Available: {product.stock_quantity}."
            )

        # Deduct stock and log transaction
        product.stock_quantity -= qty
        
        transaction = StockTransaction(
            product_id=p_id,
            transaction_type="OUT",
            quantity=qty,
            reason="Customer Order"
        )
        db.add(transaction)

        # Create OrderItem
        order_item = OrderItem(
            order_id=order.id,
            product_id=p_id,
            quantity=qty,
            unit_price=product.price
        )
        db.add(order_item)

        running_total += product.price * qty

    order.total_amount = running_total
    db.flush()
    return order

def update_order_status(db: Session, order_id: int, new_status: str):
    order = get_order(db, order_id)
    if not order:
        raise ValueError(f"Order with ID {order_id} not found.")

    old_status = order.status
    if old_status == new_status:
        return order

    # Handle returns/cancellations to restore stock
    if new_status == "CANCELLED" and old_status != "CANCELLED":
        for item in order.items:
            product = item.product
            product.stock_quantity += item.quantity
            
            transaction = StockTransaction(
                product_id=product.id,
                transaction_type="IN",
                quantity=item.quantity,
                reason=f"Order #{order.id} Cancelled"
            )
            db.add(transaction)
    
    # Handle transitioning out of CANCELLED back to active (if needed, but usually not recommended)
    elif old_status == "CANCELLED" and new_status != "CANCELLED":
        for item in order.items:
            product = item.product
            if product.stock_quantity < item.quantity:
                raise InsufficientStockError(
                    f"Cannot restore order. Insufficient stock for product '{product.name}'."
                )
            product.stock_quantity -= item.quantity
            transaction = StockTransaction(
                product_id=product.id,
                transaction_type="OUT",
                quantity=item.quantity,
                reason=f"Order #{order.id} Re-opened"
            )
            db.add(transaction)

    order.status = new_status
    db.flush()
    return order

# ==========================================
# Aggregate & optimized analytics queries
# ==========================================
def get_dashboard_analytics(db: Session):
    """
    Retrieves key operational metrics using optimized aggregations.
    """
    # 1. Total revenue (excluding cancelled orders)
    total_revenue = (
        db.query(func.sum(Order.total_amount))
        .filter(Order.status != "CANCELLED")
        .scalar()
    ) or 0.0

    # 2. Total active orders count (PENDING + SHIPPED)
    active_orders_count = (
        db.query(func.count(Order.id))
        .filter(Order.status.in_(["PENDING", "SHIPPED"]))
        .scalar()
    ) or 0

    # 3. Total products count
    products_count = db.query(func.count(Product.id)).scalar() or 0

    # 4. Low stock products count (<= 5)
    low_stock_count = (
        db.query(func.count(Product.id))
        .filter(Product.stock_quantity <= 5)
        .scalar()
    ) or 0

    # 5. Inventory valuation (Sum of stock * price)
    inventory_value = (
        db.query(func.sum(Product.stock_quantity * Product.price))
        .scalar()
    ) or 0.0

    # 6. Sales by product (Top 5 selling products)
    top_selling = (
        db.query(
            Product.name,
            Product.sku,
            func.sum(OrderItem.quantity).label("total_sold"),
            func.sum(OrderItem.quantity * OrderItem.unit_price).label("revenue")
        )
        .join(OrderItem, OrderItem.product_id == Product.id)
        .join(Order, Order.id == OrderItem.order_id)
        .filter(Order.status != "CANCELLED")
        .group_by(Product.id)
        .order_by(desc("total_sold"))
        .limit(5)
        .all()
    )
    
    top_selling_list = [
        {"name": row[0], "sku": row[1], "quantity": row[2], "revenue": row[3]}
        for row in top_selling
    ]

    # 7. Recent stock transactions (last 10)
    recent_transactions = (
        db.query(StockTransaction)
        .options(joinedload(StockTransaction.product))
        .order_by(desc(StockTransaction.created_at))
        .limit(10)
        .all()
    )

    recent_transactions_list = [
        {
            "id": tx.id,
            "product_name": tx.product.name,
            "sku": tx.product.sku,
            "type": tx.transaction_type,
            "quantity": tx.quantity,
            "reason": tx.reason,
            "created_at": tx.created_at.strftime("%Y-%m-%d %H:%M:%S")
        }
        for tx in recent_transactions
    ]

    return {
        "total_revenue": total_revenue,
        "active_orders_count": active_orders_count,
        "products_count": products_count,
        "low_stock_count": low_stock_count,
        "inventory_value": inventory_value,
        "top_selling": top_selling_list,
        "recent_transactions": recent_transactions_list,
    }
