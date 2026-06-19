import os
import sys

# Add src and root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.align import Align
from rich.prompt import Prompt, IntPrompt, FloatPrompt
from rich.text import Text
from rich import print as rprint

from src.database import engine, Base, get_db_session
from src.models import Supplier, Product, Customer, Order, StockTransaction
from src.crud import (
    get_products, get_suppliers, get_customers, get_orders, get_dashboard_analytics,
    create_product, adjust_stock, create_order, create_customer, create_supplier,
    get_product_by_sku, get_customer_by_email, get_supplier_by_email,
    InsufficientStockError
)
from seed_data import seed_database

console = Console()

def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")

def show_welcome():
    title = Text("WAREHOUSE INVENTORY & ORDER MANAGEMENT SYSTEM (OMS)", style="bold white on blue", justify="center")
    console.print(Panel(title, subtitle="Python, SQLAlchemy & Rich CLI Interface", style="blue"))

def display_dashboard():
    clear_screen()
    show_welcome()
    
    with get_db_session() as db:
        data = get_dashboard_analytics(db)
        
        # Upper KPI Panel
        kpis = (
            f"[bold cyan]Total Revenue:[/bold cyan] ${data['total_revenue']:.2f}  |  "
            f"[bold green]Active Orders:[/bold green] {data['active_orders_count']}  |  "
            f"[bold yellow]Total Products:[/bold yellow] {data['products_count']}  |  "
            f"[bold red]Low Stock Alerts:[/bold red] {data['low_stock_count']}  |  "
            f"[bold magenta]Inventory Valuation:[/bold magenta] ${data['inventory_value']:.2f}"
        )
        console.print(Panel(Align.center(kpis), title="Key Operational Metrics", border_style="cyan"))

        # Split screen: Top Selling Products and Recent Transactions
        # 1. Top Selling Table
        top_table = Table(title="Top 5 Best-Selling Products", expand=True)
        top_table.add_column("Product Name", style="cyan")
        top_table.add_column("SKU", style="yellow")
        top_table.add_column("Qty Sold", style="green", justify="right")
        top_table.add_column("Revenue", style="bold green", justify="right")
        
        for p in data["top_selling"]:
            top_table.add_row(p["name"], p["sku"], str(p["quantity"]), f"${p['revenue']:.2f}")

        # 2. Recent Transactions Table
        tx_table = Table(title="Recent Inventory Activities", expand=True)
        tx_table.add_column("Product", style="cyan")
        tx_table.add_column("SKU", style="yellow")
        tx_table.add_column("Type", style="bold")
        tx_table.add_column("Qty", justify="right")
        tx_table.add_column("Reason", style="dim")
        tx_table.add_column("Timestamp", style="magenta")

        for tx in data["recent_transactions"][:5]:
            tx_type = f"[bold green]IN[/bold green]" if tx["type"] == "IN" else f"[bold red]OUT[/bold red]"
            qty_color = "green" if tx["type"] == "IN" else "red"
            tx_table.add_row(
                tx["product_name"],
                tx["sku"],
                tx_type,
                f"[{qty_color}]{tx['quantity']}[/{qty_color}]",
                tx["reason"],
                tx["created_at"].split()[1] # show time only
            )

        console.print(top_table)
        console.print(tx_table)
        
    input("\nPress Enter to return to main menu...")

def manage_inventory():
    while True:
        clear_screen()
        show_welcome()
        
        console.print("[bold yellow]Inventory Management Menu:[/bold yellow]")
        console.print("1. View All Products")
        console.print("2. Add New Product")
        console.print("3. Restock Product (Adjust Stock)")
        console.print("4. Back to Main Menu")
        
        choice = Prompt.ask("Select an option", choices=["1", "2", "3", "4"])
        
        if choice == "1":
            with get_db_session() as db:
                products = get_products(db)
                table = Table(title="Inventory Catalog")
                table.add_column("ID", style="dim")
                table.add_column("SKU", style="yellow")
                table.add_column("Name", style="cyan")
                table.add_column("Price", justify="right")
                table.add_column("Stock", justify="right")
                table.add_column("Supplier", style="magenta")
                table.add_column("Status")
                
                for p in products:
                    status = "[bold green]In Stock[/bold green]"
                    if p.stock_quantity <= 0:
                        status = "[bold red]Out of Stock[/bold red]"
                    elif p.stock_quantity <= 5:
                        status = "[bold yellow]Low Stock[/bold yellow]"
                        
                    table.add_row(
                        str(p.id),
                        p.sku,
                        p.name,
                        f"${p.price:.2f}",
                        str(p.stock_quantity),
                        p.supplier.name,
                        status
                    )
                console.print(table)
            input("\nPress Enter to continue...")
            
        elif choice == "2":
            clear_screen()
            console.print("[bold cyan]Add New Product[/bold cyan]\n")
            sku = Prompt.ask("Enter unique SKU (e.g. ELEC-MOU-05)")
            name = Prompt.ask("Enter Product Name")
            price = FloatPrompt.ask("Enter Price ($)")
            stock = IntPrompt.ask("Enter Initial Stock Quantity")
            
            with get_db_session() as db:
                # Check SKU uniqueness
                existing_p = get_product_by_sku(db, sku)
                if existing_p:
                    console.print(f"[bold red]Error: Product with SKU {sku.upper()} already exists.[/bold red]")
                    input("\nPress Enter to continue...")
                    continue

                # Show suppliers list to select
                suppliers = get_suppliers(db)
                if not suppliers:
                    console.print("[bold red]No suppliers found. Please add a supplier first.[/bold red]")
                    input("\nPress Enter to continue...")
                    continue
                
                console.print("\nAvailable Suppliers:")
                for s in suppliers:
                    console.print(f"[{s.id}] {s.name}")
                
                supplier_ids = [str(s.id) for s in suppliers]
                supplier_id = int(Prompt.ask("Select Supplier ID", choices=supplier_ids))
                desc = Prompt.ask("Enter Description (optional)", default="")
                
                try:
                    create_product(db, sku=sku, name=name, price=price, stock_quantity=stock, supplier_id=supplier_id, description=desc)
                    console.print(f"[bold green]Product '{name}' added successfully and transaction logged![/bold green]")
                except Exception as e:
                    console.print(f"[bold red]Failed to create product: {e}[/bold red]")
            input("\nPress Enter to continue...")
            
        elif choice == "3":
            clear_screen()
            console.print("[bold cyan]Restock / Adjust Stock[/bold cyan]\n")
            with get_db_session() as db:
                products = get_products(db)
                for p in products:
                    console.print(f"[{p.id}] {p.sku} - {p.name} (Current Stock: {p.stock_quantity})")
                
                product_ids = [str(p.id) for p in products]
                p_id = int(Prompt.ask("Select Product ID to Adjust", choices=product_ids))
                
                change = IntPrompt.ask("Enter stock change quantity (Positive to restock, Negative to deduct)")
                reason = Prompt.ask("Enter reason for change (e.g., Monthly Restock, Damage)", default="Manual Adjustment")
                
                try:
                    adjust_stock(db, p_id, change, reason)
                    console.print("[bold green]Stock updated successfully and log created![/bold green]")
                except InsufficientStockError as e:
                    console.print(f"[bold red]Transaction rolled back: {e}[/bold red]")
                except Exception as e:
                    console.print(f"[bold red]Error: {e}[/bold red]")
            input("\nPress Enter to continue...")
            
        elif choice == "4":
            break

def place_order():
    clear_screen()
    show_welcome()
    console.print("[bold green]Place New Order[/bold green]\n")
    
    with get_db_session() as db:
        # Step 1: Select Customer
        customers = get_customers(db)
        if not customers:
            console.print("[bold red]No customers found. Add a customer first.[/bold red]")
            input("\nPress Enter to continue...")
            return
            
        console.print("Select Customer:")
        for c in customers:
            console.print(f"[{c.id}] {c.name} ({c.email})")
        
        customer_ids = [str(c.id) for c in customers]
        customer_id = int(Prompt.ask("Select Customer ID", choices=customer_ids))
        
        # Step 2: Build Items List
        items_list = []
        products = get_products(db)
        
        while True:
            console.print("\nAvailable Products:")
            for p in products:
                console.print(f"[{p.id}] {p.sku} - {p.name} (${p.price:.2f} | Available Stock: {p.stock_quantity})")
            
            p_ids = [str(p.id) for p in products]
            p_id = int(Prompt.ask("Select Product ID to add to order (or 0 to complete/cancel)", choices=p_ids + ["0"]))
            
            if p_id == 0:
                break
                
            qty = IntPrompt.ask("Enter quantity")
            
            # Check local selection limits (final check runs at db level)
            prod = next(p for p in products if p.id == p_id)
            if qty > prod.stock_quantity:
                console.print(f"[bold red]Warning: Requested quantity ({qty}) exceeds available stock ({prod.stock_quantity})[/bold red]")
                confirm = Prompt.ask("Add anyway and let database validation handle it?", choices=["y", "n"], default="n")
                if confirm == "n":
                    continue
            
            items_list.append({"product_id": p_id, "quantity": qty})
            console.print(f"[green]Added {qty}x {prod.name} to list.[/green]")
            
            more = Prompt.ask("Add another item?", choices=["y", "n"], default="y")
            if more == "n":
                break
        
        if not items_list:
            console.print("[yellow]Order creation cancelled (no items selected).[/yellow]")
            input("\nPress Enter to continue...")
            return
            
        # Step 3: Run transaction atomic order placement
        try:
            order = create_order(db, customer_id, items_list)
            console.print(f"\n[bold green]Success! Order #{order.id} placed successfully.[/bold green]")
            console.print(f"Total Amount: [bold cyan]${order.total_amount:.2f}[/bold cyan]")
            console.print("All item stocks updated and stock logs registered.")
        except InsufficientStockError as e:
            console.print(f"\n[bold red]ORDER TRANSACTION FAILED: {e}[/bold red]")
            console.print("[bold yellow]Database rolled back. No stock or order changes committed.[/bold yellow]")
        except Exception as e:
            console.print(f"\n[bold red]Transaction Error: {e}[/bold red]")
            
    input("\nPress Enter to continue...")

def manage_customers_suppliers():
    while True:
        clear_screen()
        show_welcome()
        console.print("[bold yellow]Customer & Supplier Management Menu:[/bold yellow]")
        console.print("1. View Customers")
        console.print("2. Add Customer")
        console.print("3. View Suppliers")
        console.print("4. Add Supplier")
        console.print("5. Back to Main Menu")
        
        choice = Prompt.ask("Select an option", choices=["1", "2", "3", "4", "5"])
        
        if choice == "1":
            with get_db_session() as db:
                customers = get_customers(db)
                table = Table(title="Registered Customers")
                table.add_column("ID", style="dim")
                table.add_column("Name", style="cyan")
                table.add_column("Email", style="yellow")
                table.add_column("Phone", style="magenta")
                table.add_column("Address", style="dim")
                for c in customers:
                    table.add_row(str(c.id), c.name, c.email, c.phone or "", c.address or "")
                console.print(table)
            input("\nPress Enter to continue...")
            
        elif choice == "2":
            clear_screen()
            console.print("[bold cyan]Add New Customer[/bold cyan]\n")
            name = Prompt.ask("Enter Full Name")
            email = Prompt.ask("Enter Email Address")
            phone = Prompt.ask("Enter Phone Number (optional)", default="")
            address = Prompt.ask("Enter Address (optional)", default="")
            
            with get_db_session() as db:
                existing_c = get_customer_by_email(db, email)
                if existing_c:
                    console.print(f"[bold red]Error: Customer with email {email} already exists.[/bold red]")
                    input("\nPress Enter to continue...")
                    continue
                try:
                    create_customer(db, name=name, email=email, phone=phone, address=address)
                    console.print("[bold green]Customer registered successfully![/bold green]")
                except Exception as e:
                    console.print(f"[bold red]Failed to add customer: {e}[/bold red]")
            input("\nPress Enter to continue...")

        elif choice == "3":
            with get_db_session() as db:
                suppliers = get_suppliers(db)
                table = Table(title="Registered Suppliers")
                table.add_column("ID", style="dim")
                table.add_column("Name", style="cyan")
                table.add_column("Email", style="yellow")
                table.add_column("Phone", style="magenta")
                for s in suppliers:
                    table.add_row(str(s.id), s.name, s.email, s.phone or "")
                console.print(table)
            input("\nPress Enter to continue...")
            
        elif choice == "4":
            clear_screen()
            console.print("[bold cyan]Add New Supplier[/bold cyan]\n")
            name = Prompt.ask("Enter Company Name")
            email = Prompt.ask("Enter Contact Email")
            phone = Prompt.ask("Enter Phone Number (optional)", default="")
            
            with get_db_session() as db:
                existing_s = get_supplier_by_email(db, email)
                if existing_s:
                    console.print(f"[bold red]Error: Supplier with email {email} already exists.[/bold red]")
                    input("\nPress Enter to continue...")
                    continue
                try:
                    create_supplier(db, name=name, email=email, phone=phone)
                    console.print("[bold green]Supplier registered successfully![/bold green]")
                except Exception as e:
                    console.print(f"[bold red]Failed to add supplier: {e}[/bold red]")
            input("\nPress Enter to continue...")
            
        elif choice == "5":
            break

def view_transactions():
    clear_screen()
    show_welcome()
    with get_db_session() as db:
        txs = db.query(StockTransaction).order_by(StockTransaction.created_at.desc()).all()
        table = Table(title="Complete Inventory Transaction History")
        table.add_column("TX ID", style="dim")
        table.add_column("SKU", style="yellow")
        table.add_column("Product Name", style="cyan")
        table.add_column("Type", style="bold")
        table.add_column("Qty", justify="right")
        table.add_column("Reason")
        table.add_column("Timestamp", style="magenta")

        for tx in txs:
            tx_type = f"[bold green]IN[/bold green]" if tx.transaction_type == "IN" else f"[bold red]OUT[/bold red]"
            qty_color = "green" if tx.transaction_type == "IN" else "red"
            table.add_row(
                str(tx.id),
                tx.product.sku,
                tx.product.name,
                tx_type,
                f"[{qty_color}]{tx.quantity}[/{qty_color}]",
                tx.reason,
                tx.created_at.strftime("%Y-%m-%d %H:%M:%S")
            )
        console.print(table)
    input("\nPress Enter to return to main menu...")

def main():
    # Make sure tables exist and are seeded
    seed_database()

    while True:
        clear_screen()
        show_welcome()
        
        console.print("[bold yellow]Main Menu Options:[/bold yellow]")
        console.print("1. [bold cyan]View Dashboard Analytics[/bold cyan]")
        console.print("2. Manage Products & Inventory")
        console.print("3. Place Customer Order")
        console.print("4. Customer & Supplier Records")
        console.print("5. View Inventory Logs / Transaction History")
        console.print("0. Exit Application")
        
        choice = Prompt.ask("\nSelect option code", choices=["1", "2", "3", "4", "5", "0"])
        
        if choice == "1":
            display_dashboard()
        elif choice == "2":
            manage_inventory()
        elif choice == "3":
            place_order()
        elif choice == "4":
            manage_customers_suppliers()
        elif choice == "5":
            view_transactions()
        elif choice == "0":
            console.print("\n[bold green]Goodbye![/bold green]")
            break

if __name__ == "__main__":
    main()
