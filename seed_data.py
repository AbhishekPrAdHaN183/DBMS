import sys
import os

# Add the src directory to path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from src.database import engine, Base, get_db_session
from src.models import Supplier, Product, Customer, Order, OrderItem, StockTransaction
from src.crud import create_supplier, create_product, create_customer, create_order, update_order_status

def seed_database():
    print("Initializing Database tables...")
    # Create tables
    Base.metadata.create_all(bind=engine)
    print("Database tables initialized.")

    with get_db_session() as db:
        # Check if database is already seeded
        if db.query(Supplier).first() is not None:
            print("Database already contains data. Skipping seeding.")
            return

        print("Seeding database with realistic mock data...")

        # 1. Seed Suppliers
        s1 = create_supplier(db, name="Apex Electronics", email="sales@apexelectronics.com", phone="+1-555-0199")
        s2 = create_supplier(db, name="Vertex Wholesale", email="info@vertexwholesale.com", phone="+1-555-0182")
        s3 = create_supplier(db, name="Prime Components", email="orders@primecomponents.com", phone="+1-555-0155")
        s4 = create_supplier(db, name="Nova Logistics", email="support@novalogistics.com", phone="+1-555-0141")
        
        # 2. Seed Products
        p1 = create_product(db, sku="ELEC-SMW-01", name="Smart Watch V2", price=199.99, stock_quantity=50, supplier_id=s1.id, description="Fitness tracker with OLED screen")
        p2 = create_product(db, sku="ELEC-NCH-02", name="Noise Cancelling Headphones", price=299.99, stock_quantity=30, supplier_id=s1.id, description="Over-ear active noise cancelling headphones")
        p3 = create_product(db, sku="ELEC-WLC-03", name="Wireless Charger Pad", price=39.99, stock_quantity=150, supplier_id=s1.id, description="15W Fast charging wireless dock")
        
        p4 = create_product(db, sku="OFFC-EGC-01", name="Ergonomic Office Chair", price=249.99, stock_quantity=12, supplier_id=s2.id, description="Mesh back adjustable lumbar support chair")
        p5 = create_product(db, sku="OFFC-STD-02", name="Standing Desk", price=450.00, stock_quantity=8, supplier_id=s2.id, description="Motorized dual-motor height adjustable desk")
        p6 = create_product(db, sku="OFFC-LDL-03", name="LED Desk Lamp", price=45.99, stock_quantity=40, supplier_id=s2.id, description="Dimmable desk light with USB charging port")
        
        p7 = create_product(db, sku="HARD-MTS-01", name="Mechanic Tool Set (120pc)", price=129.99, stock_quantity=25, supplier_id=s3.id, description="Chrome vanadium sockets and wrenches")
        p8 = create_product(db, sku="HARD-CRD-02", name="Cordless Drill 20V", price=89.99, stock_quantity=35, supplier_id=s3.id, description="2-speed drill driver with 2 batteries")
        p9 = create_product(db, sku="HARD-HDT-03", name="Heavy Duty Toolbox", price=59.99, stock_quantity=4, supplier_id=s3.id, description="Steel cantilever toolbox 20-inch") # Low stock
        
        p10 = create_product(db, sku="NET-WFR-01", name="AC1200 Wi-Fi Router", price=79.99, stock_quantity=60, supplier_id=s4.id, description="Dual-band wireless router for home")
        p11 = create_product(db, sku="NET-GES-02", name="Gigabit Ethernet Switch 8-Port", price=49.99, stock_quantity=2, supplier_id=s4.id, description="Metal desktop fanless switch") # Low stock
        p12 = create_product(db, sku="NET-C6C-03", name="Cat6 Ethernet Cable 50ft", price=19.99, stock_quantity=100, supplier_id=s4.id, description="High-speed RJ45 patch cable blue")

        # 3. Seed Customers
        c1 = create_customer(db, name="John Doe", email="john.doe@example.com", phone="+1-555-0200", address="123 Maple St, Seattle, WA")
        c2 = create_customer(db, name="Jane Smith", email="jane.smith@example.com", phone="+1-555-0211", address="456 Oak Ave, Portland, OR")
        c3 = create_customer(db, name="Alice Johnson", email="alice.j@example.com", phone="+1-555-0222", address="789 Pine Rd, San Francisco, CA")
        c4 = create_customer(db, name="Bob Brown", email="bob.brown@example.com", phone="+1-555-0233", address="101 Cedar Ln, Austin, TX")
        c5 = create_customer(db, name="Charlie Green", email="charlie.g@example.com", phone="+1-555-0244", address="202 Birch Dr, Denver, CO")

        # 4. Seed Orders (uses transaction logic from crud.py)
        # Order 1: John Doe buys a Smart Watch and a Wireless Charger
        o1 = create_order(db, customer_id=c1.id, items_list=[
            {"product_id": p1.id, "quantity": 1},
            {"product_id": p3.id, "quantity": 2}
        ])
        
        # Order 2: Jane Smith buys an Ergonomic Chair. Mark it as SHIPPED.
        o2 = create_order(db, customer_id=c2.id, items_list=[
            {"product_id": p4.id, "quantity": 1}
        ])
        update_order_status(db, o2.id, "SHIPPED")

        # Order 3: Alice Johnson buys Noise Cancelling Headphones and a Desk Lamp. Mark it as DELIVERED.
        o3 = create_order(db, customer_id=c3.id, items_list=[
            {"product_id": p2.id, "quantity": 1},
            {"product_id": p6.id, "quantity": 1}
        ])
        update_order_status(db, o3.id, "DELIVERED")

        # Order 4: Bob Brown buys a Cordless Drill. We will mark it CANCELLED.
        # This will test whether the cancellation restores stock (35 drill stock before -> 34 after order -> 35 after cancellation)
        o4 = create_order(db, customer_id=c4.id, items_list=[
            {"product_id": p8.id, "quantity": 1}
        ])
        update_order_status(db, o4.id, "CANCELLED")

        # Order 5: Charlie Green buys a Standing Desk and Gigabit Switch.
        o5 = create_order(db, customer_id=c5.id, items_list=[
            {"product_id": p5.id, "quantity": 1},
            {"product_id": p11.id, "quantity": 1}
        ])

        print("Database successfully seeded.")

if __name__ == "__main__":
    seed_database()
