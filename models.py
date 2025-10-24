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
