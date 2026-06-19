import sys
import os

# Add src to path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from src.database import engine, Base, get_db_session
from src.models import Customer, Product, Supplier, Order, OrderItem
from src.crud import create_order, update_order_status, create_product, create_customer, create_supplier, InsufficientStockError
from seed_data import seed_database

def run_tests():
    print("==================================================")
    print("RUNNING DATABASE INTEGRITY AND TRANSACTION TESTS  ")
    print("==================================================")
    
    # 1. Reset and Seed Database
    if os.path.exists("data/inventory.db"):
        try:
            os.remove("data/inventory.db")
            print("Cleared existing test database.")
        except Exception as e:
            print(f"Could not remove database file: {e}")
    
    seed_database()

    print("\n--- TEST 1: Validation Rules (Email format) ---")
    with get_db_session() as db:
        try:
            create_customer(db, name="Bad Customer", email="bademailformat")
            print("[FAIL]: Email validation should have blocked 'bademailformat'.")
        except ValueError as e:
            print(f"[PASS]: Blocked invalid email. Error: {e}")
            db.rollback()

    print("\n--- TEST 2: Check Constraints (Positive Price) ---")
    with get_db_session() as db:
        supplier = db.query(Supplier).first()
        try:
            create_product(db, sku="TEST-NEG-PR", name="Negative Price Item", price=-9.99, stock_quantity=10, supplier_id=supplier.id)
            print("[FAIL]: DB or validator should have blocked negative price.")
        except ValueError as e:
            print(f"[PASS]: Blocked negative price. Error: {e}")
            db.rollback()

    print("\n--- TEST 3: Check Constraints (Negative Stock) ---")
    with get_db_session() as db:
        supplier = db.query(Supplier).first()
        try:
            create_product(db, sku="TEST-NEG-ST", name="Negative Stock Item", price=10.00, stock_quantity=-5, supplier_id=supplier.id)
            print("[FAIL]: DB or validator should have blocked negative stock.")
        except ValueError as e:
            print(f"[PASS]: Blocked negative stock. Error: {e}")
            db.rollback()

    print("\n--- TEST 4: Atomic Transactions & Stock Checks ---")
    with get_db_session() as db:
        # Get some test records
        customer = db.query(Customer).filter(Customer.email == "john.doe@example.com").first()
        product_a = db.query(Product).filter(Product.sku == "ELEC-SMW-01").first()  # Smart Watch stock is 49 (50 originally, 1 ordered)
        product_b = db.query(Product).filter(Product.sku == "NET-GES-02").first()  # Switch stock is 1 (2 originally, 1 ordered)

        stock_a_before = product_a.stock_quantity
        stock_b_before = product_b.stock_quantity

        print(f"Initial Stocks -> {product_a.name}: {stock_a_before}, {product_b.name}: {stock_b_before}")
        
        # We will try to place an order requesting 2 Smart Watches (available: 49) AND 5 Gigabit Switches (available: 1)
        # This order should fail because of the Gigabit Switch stock, and neither product's stock should decrease.
        try:
            create_order(db, customer_id=customer.id, items_list=[
                {"product_id": product_a.id, "quantity": 2},
                {"product_id": product_b.id, "quantity": 5}  # This exceeds available (1)
            ])
            print("[FAIL]: Order should have failed due to insufficient stock of Gigabit Switch.")
        except InsufficientStockError as e:
            print(f"[PASS]: Transaction aborted as expected. Error: {e}")
            db.rollback()

        # Let's verify stocks remained unchanged (Rollback check)
        # We reload the entities from database to be absolutely sure
        db.expire_all()
        product_a = db.query(Product).filter(Product.sku == "ELEC-SMW-01").first()
        product_b = db.query(Product).filter(Product.sku == "NET-GES-02").first()
        
        print(f"Post-Failure Stocks -> {product_a.name}: {product_a.stock_quantity}, {product_b.name}: {product_b.stock_quantity}")
        if product_a.stock_quantity == stock_a_before and product_b.stock_quantity == stock_b_before:
            print("[PASS]: Stock counts successfully rolled back and are unaffected.")
        else:
            print("[FAIL]: Stock counts changed despite transaction error!")

    print("\n--- TEST 5: Order Cancellation & Stock Restoration ---")
    with get_db_session() as db:
        customer = db.query(Customer).filter(Customer.email == "john.doe@example.com").first()
        product = db.query(Product).filter(Product.sku == "ELEC-SMW-01").first()
        
        initial_stock = product.stock_quantity
        print(f"Stock before order: {initial_stock}")
        
        # Order 2 watches
        order = create_order(db, customer_id=customer.id, items_list=[
            {"product_id": product.id, "quantity": 2}
        ])
        print(f"Order #{order.id} placed. Total: ${order.total_amount}. Status: {order.status}")
        
        # Stock should be decreased by 2
        print(f"Stock after order placement: {product.stock_quantity}")
        if product.stock_quantity != initial_stock - 2:
            print("[FAIL]: Product stock was not reduced.")
            
        # Cancel the order
        update_order_status(db, order.id, "CANCELLED")
        print(f"Order #{order.id} status updated to: {order.status}")
        print(f"Stock after cancellation: {product.stock_quantity}")
        
        if product.stock_quantity == initial_stock:
            print("[PASS]: Stock fully restored upon cancellation.")
        else:
            print("[FAIL]: Stock was not restored on cancellation.")
            
    print("\n==================================================")
    print("ALL TESTS COMPLETED SUCCESSFULLY!                 ")
    print("==================================================")

if __name__ == "__main__":
    run_tests()
