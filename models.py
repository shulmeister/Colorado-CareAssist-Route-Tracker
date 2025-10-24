from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

Base = declarative_base()

class Visit(Base):
    """Visit records from MyWay route PDFs"""
    __tablename__ = "visits"
    
    id = Column(Integer, primary_key=True, index=True)
    stop_number = Column(Integer, nullable=False)
    business_name = Column(String(255), nullable=False)
    address = Column(Text, nullable=True)
    city = Column(String(500), nullable=True)
    notes = Column(Text, nullable=True)
    visit_date = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            "id": self.id,
            "stop_number": self.stop_number,
            "business_name": self.business_name,
            "address": self.address,
            "city": self.city,
            "notes": self.notes,
            "visit_date": self.visit_date.isoformat() if self.visit_date else None,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }

class TimeEntry(Base):
    """Time tracking entries from time tracking PDFs"""
    __tablename__ = "time_entries"
    
    id = Column(Integer, primary_key=True, index=True)
    date = Column(DateTime, nullable=False)
    hours_worked = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            "id": self.id,
            "date": self.date.isoformat() if self.date else None,
            "hours_worked": self.hours_worked,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }

class Contact(Base):
    """Business contacts from scanned business cards"""
    __tablename__ = "contacts"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=True)
    company = Column(String(255), nullable=True)
    title = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)
    email = Column(String(255), nullable=True)
    address = Column(Text, nullable=True)
    website = Column(String(255), nullable=True)
    notes = Column(Text, nullable=True)
    scanned_date = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "company": self.company,
            "title": self.title,
            "phone": self.phone,
            "email": self.email,
            "address": self.address,
            "website": self.website,
            "notes": self.notes,
            "scanned_date": self.scanned_date.isoformat() if self.scanned_date else None,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }

class FinancialEntry(Base):
    """Financial tracking entries from daily summary data"""
    __tablename__ = "financial_entries"
    
    id = Column(Integer, primary_key=True, index=True)
    date = Column(DateTime, nullable=False)
    hours_worked = Column(Float, nullable=False)
    labor_cost = Column(Float, nullable=False)  # Hour Total ($) - $20/hour
    miles_driven = Column(Float, nullable=True)
    mileage_cost = Column(Float, nullable=True)  # Mileage Cost ($) - $0.70/mile
    materials_cost = Column(Float, nullable=True)  # Gas/Treats/Materials ($) - cookies, gas, etc
    total_daily_cost = Column(Float, nullable=False)  # Total Daily Cost ($)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            "id": self.id,
            "date": self.date.isoformat() if self.date else None,
            "hours_worked": self.hours_worked,
            "labor_cost": self.labor_cost,
            "miles_driven": self.miles_driven,
            "mileage_cost": self.mileage_cost,
            "materials_cost": self.materials_cost,
            "total_daily_cost": self.total_daily_cost,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }

class SalesBonus(Base):
    """Sales bonuses from closed sales"""
    __tablename__ = "sales_bonuses"
    
    id = Column(Integer, primary_key=True, index=True)
    client_name = Column(String(255), nullable=False)
    bonus_amount = Column(Float, nullable=False)  # $250 or $350
    commission_paid = Column(Boolean, default=False)
    start_date = Column(DateTime, nullable=True)
    wellsky_status = Column(String(100), nullable=True)
    status = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            "id": self.id,
            "client_name": self.client_name,
            "bonus_amount": self.bonus_amount,
            "commission_paid": self.commission_paid,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "wellsky_status": self.wellsky_status,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }

class ActivityNote(Base):
    """Activity notes for tracking daily activities and observations"""
    __tablename__ = "activity_notes"
    
    id = Column(Integer, primary_key=True, index=True)
    date = Column(DateTime, nullable=False)
    notes = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            "id": self.id,
            "date": self.date.isoformat() if self.date else None,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }

class AnalyticsCache(Base):
    """Cached analytics data for performance"""
    __tablename__ = "analytics_cache"
    
    id = Column(Integer, primary_key=True, index=True)
    metric_name = Column(String(100), nullable=False, index=True)
    metric_value = Column(Float, nullable=False)
    period = Column(String(50), nullable=False)  # daily, weekly, monthly, yearly
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            "id": self.id,
            "metric_name": self.metric_name,
            "metric_value": self.metric_value,
            "period": self.period,
            "period_start": self.period_start.isoformat() if self.period_start else None,
            "period_end": self.period_end.isoformat() if self.period_end else None,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
