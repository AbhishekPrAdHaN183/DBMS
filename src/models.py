import re
from datetime import datetime
from sqlalchemy import String, Integer, Float, ForeignKey, CheckConstraint, DateTime, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates
from src.database import Base

class Supplier(Base):
    __tablename__ = "suppliers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    phone: Mapped[str] = mapped_column(String(20), nullable=True)

    # Relationships
    products: Mapped[list["Product"]] = relationship(
        "Product", back_populates="supplier", cascade="all, delete-orphan"
    )

    @validates("email")
    def validate_email(self, key, address):
        if not address or "@" not in address:
            raise ValueError(f"Invalid email address provided for Supplier: {address}")
        email_regex = r"^[\w\.-]+@[\w\.-]+\.\w+$"
        if not re.match(email_regex, address):
            raise ValueError(f"Invalid email address pattern: {address}")
        return address

class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("price > 0", name="check_positive_price"),
        CheckConstraint("stock_quantity >= 0", name="check_non_negative_stock"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sku: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=True)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    stock_quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    supplier_id: Mapped[int] = mapped_column(Integer, ForeignKey("suppliers.id", ondelete="RESTRICT"), nullable=False)

    # Relationships
    supplier: Mapped["Supplier"] = relationship("Supplier", back_populates="products")
    transactions: Mapped[list["StockTransaction"]] = relationship(
        "StockTransaction", back_populates="product", cascade="all, delete-orphan"
    )
    order_items: Mapped[list["OrderItem"]] = relationship("OrderItem", back_populates="product")

    @validates("price")
    def validate_price(self, key, value):
        if value <= 0:
            raise ValueError("Product price must be greater than zero.")
        return value

    @validates("stock_quantity")
    def validate_stock(self, key, value):
        if value < 0:
            raise ValueError("Stock quantity cannot be negative.")
        return value

    @validates("sku")
    def validate_sku(self, key, value):
        if not value or len(value) < 3:
            raise ValueError("SKU code must be at least 3 characters long.")
        sku_regex = r"^[A-Z0-9_-]+$"
        if not re.match(sku_regex, value):
            raise ValueError("SKU can only contain uppercase letters, numbers, hyphens, and underscores.")
        return value

class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    phone: Mapped[str] = mapped_column(String(20), nullable=True)
    address: Mapped[str] = mapped_column(String(255), nullable=True)

    # Relationships
    orders: Mapped[list["Order"]] = relationship("Order", back_populates="customer")

    @validates("email")
    def validate_email(self, key, address):
        if not address or "@" not in address:
            raise ValueError(f"Invalid email address provided for Customer: {address}")
        email_regex = r"^[\w\.-]+@[\w\.-]+\.\w+$"
        if not re.match(email_regex, address):
            raise ValueError(f"Invalid email address pattern: {address}")
        return address

class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        CheckConstraint("total_amount >= 0", name="check_non_negative_total"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(Integer, ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False)
    order_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="PENDING", nullable=False)  # PENDING, SHIPPED, DELIVERED, CANCELLED
    total_amount: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # Relationships
    customer: Mapped["Customer"] = relationship("Customer", back_populates="orders")
    items: Mapped[list["OrderItem"]] = relationship(
        "OrderItem", back_populates="order", cascade="all, delete-orphan"
    )

    @validates("status")
    def validate_status(self, key, value):
        valid_statuses = {"PENDING", "SHIPPED", "DELIVERED", "CANCELLED"}
        if value not in valid_statuses:
            raise ValueError(f"Invalid order status: {value}. Must be one of {valid_statuses}")
        return value

class OrderItem(Base):
    __tablename__ = "order_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="check_positive_quantity"),
        CheckConstraint("unit_price >= 0", name="check_non_negative_unit_price"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("products.id", ondelete="RESTRICT"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[float] = mapped_column(Float, nullable=False)

    # Relationships
    order: Mapped["Order"] = relationship("Order", back_populates="items")
    product: Mapped["Product"] = relationship("Product", back_populates="order_items")

    @validates("quantity")
    def validate_quantity(self, key, value):
        if value <= 0:
            raise ValueError("Order item quantity must be greater than zero.")
        return value

    @validates("unit_price")
    def validate_unit_price(self, key, value):
        if value < 0:
            raise ValueError("Unit price cannot be negative.")
        return value

class StockTransaction(Base):
    __tablename__ = "stock_transactions"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="check_positive_trans_quantity"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    transaction_type: Mapped[str] = mapped_column(String(10), nullable=False)  # IN, OUT
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String(50), nullable=False)  # Restock, Sale, Adjustment, Return
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    product: Mapped["Product"] = relationship("Product", back_populates="transactions")

    @validates("transaction_type")
    def validate_type(self, key, value):
        if value not in {"IN", "OUT"}:
            raise ValueError(f"Invalid transaction type: {value}. Must be 'IN' or 'OUT'.")
        return value

    @validates("quantity")
    def validate_quantity(self, key, value):
        if value <= 0:
            raise ValueError("Stock transaction quantity must be greater than zero.")
        return value
