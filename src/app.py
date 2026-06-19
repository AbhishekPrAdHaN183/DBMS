import os
import sys
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Depends, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, EmailStr, field_validator
import uvicorn

# Add src and root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.database import get_db_session
from src.crud import (
    get_products, get_product, get_product_by_sku, create_product, update_product, delete_product, adjust_stock,
    get_customers, get_customer, get_customer_by_email, create_customer,
    get_suppliers, get_supplier, get_supplier_by_email, create_supplier,
    get_orders, get_order, create_order, update_order_status,
    get_dashboard_analytics, InsufficientStockError
)

app = FastAPI(
    title="Warehouse OMS API",
    description="Backend API for Warehouse Inventory & Order Management System",
    version="1.0.0"
)

# Enable CORS for local testing and developer tools
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================
# Pydantic Request Validation Models
# ==========================================
class SupplierCreateSchema(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    phone: Optional[str] = None

class ProductCreateSchema(BaseModel):
    sku: str = Field(..., min_length=3, max_length=50)
    name: str = Field(..., min_length=2, max_length=100)
    price: float = Field(..., gt=0, description="Price must be greater than zero")
    stock_quantity: int = Field(..., ge=0, description="Stock cannot be negative")
    supplier_id: int
    description: Optional[str] = None

    @field_validator("sku")
    @classmethod
    def validate_sku_format(cls, value: str) -> str:
        import re
        sku_clean = value.upper().strip()
        sku_regex = r"^[A-Z0-9_-]+$"
        if not re.match(sku_regex, sku_clean):
            raise ValueError("SKU can only contain uppercase alphanumeric characters, hyphens, and underscores")
        return sku_clean

class ProductUpdateSchema(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    price: Optional[float] = Field(None, gt=0)
    stock_quantity: Optional[int] = Field(None, ge=0)
    supplier_id: Optional[int] = None
    description: Optional[str] = None

class CustomerCreateSchema(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    phone: Optional[str] = None
    address: Optional[str] = None

class OrderItemSchema(BaseModel):
    product_id: int
    quantity: int = Field(..., gt=0, description="Quantity ordered must be greater than zero")

class OrderCreateSchema(BaseModel):
    customer_id: int
    items: List[OrderItemSchema]

class OrderStatusUpdateSchema(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def validate_status_value(cls, value: str) -> str:
        status_clean = value.upper().strip()
        if status_clean not in {"PENDING", "SHIPPED", "DELIVERED", "CANCELLED"}:
            raise ValueError("Status must be one of: PENDING, SHIPPED, DELIVERED, CANCELLED")
        return status_clean

# ==========================================
# API Endpoints
# ==========================================

# Dashboard
@app.get("/api/dashboard")
def read_dashboard_stats():
    with get_db_session() as db:
        try:
            return get_dashboard_analytics(db)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

# Products
@app.get("/api/products")
def read_products(
    search: str = Query("", description="Search by product name or SKU"),
    low_stock: Optional[bool] = Query(None, description="Filter for low stock items <= 5"),
    skip: int = 0,
    limit: int = 100
):
    with get_db_session() as db:
        try:
            threshold = 5 if low_stock else None
            products = get_products(db, skip=skip, limit=limit, search=search, low_stock_threshold=threshold)
            return [
                {
                    "id": p.id,
                    "sku": p.sku,
                    "name": p.name,
                    "price": p.price,
                    "stock_quantity": p.stock_quantity,
                    "supplier_id": p.supplier_id,
                    "supplier_name": p.supplier.name,
                    "description": p.description
                }
                for p in products
            ]
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/products", status_code=status.HTTP_201_CREATED)
def add_product(payload: ProductCreateSchema):
    with get_db_session() as db:
        # Check SKU uniqueness
        if get_product_by_sku(db, payload.sku):
            raise HTTPException(status_code=400, detail=f"Product with SKU '{payload.sku}' already exists.")
        
        # Check Supplier exists
        if not get_supplier(db, payload.supplier_id):
            raise HTTPException(status_code=400, detail=f"Supplier ID {payload.supplier_id} does not exist.")
        
        try:
            p = create_product(
                db, sku=payload.sku, name=payload.name, price=payload.price,
                stock_quantity=payload.stock_quantity, supplier_id=payload.supplier_id,
                description=payload.description
            )
            return {"message": "Product created successfully", "id": p.id, "sku": p.sku}
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/products/{product_id}")
def edit_product(product_id: int, payload: ProductUpdateSchema):
    with get_db_session() as db:
        if not get_product(db, product_id):
            raise HTTPException(status_code=404, detail="Product not found")
        
        if payload.supplier_id and not get_supplier(db, payload.supplier_id):
            raise HTTPException(status_code=400, detail="Supplier ID does not exist")
            
        try:
            # Filter non-None fields to update
            updates = {k: v for k, v in payload.model_dump().items() if v is not None}
            update_product(db, product_id, updates)
            return {"message": "Product updated successfully"}
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except InsufficientStockError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/products/{product_id}")
def remove_product(product_id: int):
    with get_db_session() as db:
        if not get_product(db, product_id):
            raise HTTPException(status_code=404, detail="Product not found")
        try:
            delete_product(db, product_id)
            return {"message": "Product deleted successfully"}
        except Exception as e:
            # Check for Foreign Key failure (restricting deletions of products on orders)
            raise HTTPException(
                status_code=400, 
                detail="Cannot delete product. It has associated order items or transactions. Keep it to preserve historical records."
            )

# Customers
@app.get("/api/customers")
def read_customers(skip: int = 0, limit: int = 100):
    with get_db_session() as db:
        customers = get_customers(db, skip=skip, limit=limit)
        return [
            {
                "id": c.id,
                "name": c.name,
                "email": c.email,
                "phone": c.phone,
                "address": c.address
            }
            for c in customers
        ]

@app.post("/api/customers", status_code=status.HTTP_201_CREATED)
def add_customer(payload: CustomerCreateSchema):
    with get_db_session() as db:
        if get_customer_by_email(db, payload.email):
            raise HTTPException(status_code=400, detail=f"Customer with email '{payload.email}' already exists.")
        try:
            c = create_customer(db, name=payload.name, email=payload.email, phone=payload.phone, address=payload.address)
            return {"message": "Customer created successfully", "id": c.id}
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

# Suppliers
@app.get("/api/suppliers")
def read_suppliers(skip: int = 0, limit: int = 100):
    with get_db_session() as db:
        suppliers = get_suppliers(db, skip=skip, limit=limit)
        return [
            {
                "id": s.id,
                "name": s.name,
                "email": s.email,
                "phone": s.phone
            }
            for s in suppliers
        ]

@app.post("/api/suppliers", status_code=status.HTTP_201_CREATED)
def add_supplier(payload: SupplierCreateSchema):
    with get_db_session() as db:
        if get_supplier_by_email(db, payload.email):
            raise HTTPException(status_code=400, detail=f"Supplier with email '{payload.email}' already exists.")
        try:
            s = create_supplier(db, name=payload.name, email=payload.email, phone=payload.phone)
            return {"message": "Supplier created successfully", "id": s.id}
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

# Orders
@app.get("/api/orders")
def read_orders(status: Optional[str] = None, skip: int = 0, limit: int = 100):
    with get_db_session() as db:
        orders = get_orders(db, skip=skip, limit=limit, status=status)
        return [
            {
                "id": o.id,
                "customer_name": o.customer.name,
                "customer_email": o.customer.email,
                "order_date": o.order_date.strftime("%Y-%m-%d %H:%M:%S"),
                "status": o.status,
                "total_amount": o.total_amount,
                "items": [
                    {
                        "product_name": item.product.name,
                        "sku": item.product.sku,
                        "quantity": item.quantity,
                        "unit_price": item.unit_price
                    }
                    for item in o.items
                ]
            }
            for o in orders
        ]

@app.post("/api/orders", status_code=status.HTTP_201_CREATED)
def place_order_api(payload: OrderCreateSchema):
    with get_db_session() as db:
        if not get_customer(db, payload.customer_id):
            raise HTTPException(status_code=400, detail="Customer not found")
        
        items_list = [{"product_id": x.product_id, "quantity": x.quantity} for x in payload.items]
        
        try:
            o = create_order(db, customer_id=payload.customer_id, items_list=items_list)
            return {"message": "Order created successfully", "id": o.id, "total": o.total_amount}
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except InsufficientStockError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/orders/{order_id}/status")
def change_order_status(order_id: int, payload: OrderStatusUpdateSchema):
    with get_db_session() as db:
        if not get_order(db, order_id):
            raise HTTPException(status_code=404, detail="Order not found")
        try:
            update_order_status(db, order_id, payload.status)
            return {"message": f"Order status updated to {payload.status}"}
        except InsufficientStockError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

# Transactions Audit Log
@app.get("/api/transactions")
def read_transactions(limit: int = 100):
    from src.models import StockTransaction
    with get_db_session() as db:
        txs = db.query(StockTransaction).order_by(StockTransaction.created_at.desc()).limit(limit).all()
        return [
            {
                "id": tx.id,
                "sku": tx.product.sku,
                "product_name": tx.product.name,
                "type": tx.transaction_type,
                "quantity": tx.quantity,
                "reason": tx.reason,
                "created_at": tx.created_at.strftime("%Y-%m-%d %H:%M:%S")
            }
            for tx in txs
        ]

# Mount static files UI at the root
STATIC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "static"))
os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")

if __name__ == "__main__":
    uvicorn.run("src.app:app", host="127.0.0.1", port=8000, reload=True)
