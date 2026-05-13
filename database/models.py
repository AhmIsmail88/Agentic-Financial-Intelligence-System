from datetime import datetime
from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import DeclarativeBase, relationship

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"
    
    telegram_id = Column(BigInteger, primary_key=True)
    username = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    expenses = relationship("Expense", back_populates="user")

class Category(Base):
    __tablename__ = "categories"
    
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    
    expenses = relationship("Expense", back_populates="category")

class Expense(Base):
    __tablename__ = "expenses"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, ForeignKey("users.telegram_id"), nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False)
    item = Column(Text, nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    currency = Column(String, default="EGP")
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="expenses")
    category = relationship("Category", back_populates="expenses")
