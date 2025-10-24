from sqlalchemy.orm import Session
from sqlalchemy import func, desc, and_
from models import Visit, TimeEntry, Contact, AnalyticsCache
from datetime import datetime, timedelta
from typing import Dict, List, Any
import logging

logger = logging.getLogger(__name__)

class AnalyticsEngine:
    """Generate analytics and KPIs for the sales dashboard"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_dashboard_summary(self) -> Dict[str, Any]:
        """Get overall dashboard summary"""
        try:
            # Total visits
            total_visits = self.db.query(Visit).count()
            
            # Visits this month
            current_month_start = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            visits_this_month = self.db.query(Visit).filter(
                Visit.created_at >= current_month_start
            ).count()
            
            # Total hours worked
            total_hours = self.db.query(func.sum(TimeEntry.hours_worked)).scalar() or 0
            
            # Hours this month
            hours_this_month = self.db.query(func.sum(TimeEntry.hours_worked)).filter(
                TimeEntry.date >= current_month_start
            ).scalar() or 0
            
            # Total contacts
            total_contacts = self.db.query(Contact).count()
            
            # Unique facilities visited
            unique_facilities = self.db.query(func.count(func.distinct(Visit.business_name))).scalar()
            
            return {
                "total_visits": total_visits,
                "visits_this_month": visits_this_month,
                "total_hours": round(total_hours, 2),
                "hours_this_month": round(hours_this_month, 2),
                "total_contacts": total_contacts,
                "unique_facilities": unique_facilities,
                "last_updated": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting dashboard summary: {str(e)}")
            return {}
    
    def get_visits_by_month(self, months: int = 12) -> List[Dict[str, Any]]:
        """Get visits grouped by month"""
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=months * 30)
            
            results = self.db.query(
                func.date_trunc('month', Visit.created_at).label('month'),
                func.count(Visit.id).label('count')
            ).filter(
                Visit.created_at >= start_date
            ).group_by(
                func.date_trunc('month', Visit.created_at)
            ).order_by('month').all()
            
            return [
                {
                    "month": result.month.strftime("%Y-%m"),
                    "count": result.count
                }
                for result in results
            ]
            
        except Exception as e:
            logger.error(f"Error getting visits by month: {str(e)}")
            return []
    
    def get_hours_by_month(self, months: int = 12) -> List[Dict[str, Any]]:
        """Get hours worked grouped by month"""
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=months * 30)
            
            results = self.db.query(
                func.date_trunc('month', TimeEntry.date).label('month'),
                func.sum(TimeEntry.hours_worked).label('total_hours')
            ).filter(
                TimeEntry.date >= start_date
            ).group_by(
                func.date_trunc('month', TimeEntry.date)
            ).order_by('month').all()
            
            return [
                {
                    "month": result.month.strftime("%Y-%m"),
                    "hours": round(result.total_hours, 2)
                }
                for result in results
            ]
            
        except Exception as e:
            logger.error(f"Error getting hours by month: {str(e)}")
            return []
    
    def get_top_facilities(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get most visited facilities"""
        try:
            results = self.db.query(
                Visit.business_name,
                func.count(Visit.id).label('visit_count')
            ).group_by(
                Visit.business_name
            ).order_by(
                desc('visit_count')
            ).limit(limit).all()
            
            return [
                {
                    "facility": result.business_name,
                    "visits": result.visit_count
                }
                for result in results
            ]
            
        except Exception as e:
            logger.error(f"Error getting top facilities: {str(e)}")
            return []
    
    def get_recent_activity(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent activity across all data types"""
        try:
            activities = []
            
            # Recent visits
            recent_visits = self.db.query(Visit).order_by(
                desc(Visit.created_at)
            ).limit(limit).all()
            
            for visit in recent_visits:
                activities.append({
                    "type": "visit",
                    "description": f"Visit to {visit.business_name}",
                    "date": visit.created_at.isoformat(),
                    "details": {
                        "stop": visit.stop_number,
                        "address": visit.address,
                        "city": visit.city
                    }
                })
            
            # Recent time entries
            recent_time = self.db.query(TimeEntry).order_by(
                desc(TimeEntry.created_at)
            ).limit(limit).all()
            
            for entry in recent_time:
                activities.append({
                    "type": "time_entry",
                    "description": f"Logged {entry.hours_worked} hours",
                    "date": entry.created_at.isoformat(),
                    "details": {
                        "date": entry.date.isoformat(),
                        "hours": entry.hours_worked
                    }
                })
            
            # Recent contacts
            recent_contacts = self.db.query(Contact).order_by(
                desc(Contact.created_at)
            ).limit(limit).all()
            
            for contact in recent_contacts:
                activities.append({
                    "type": "contact",
                    "description": f"Added contact: {contact.name or contact.company}",
                    "date": contact.created_at.isoformat(),
                    "details": {
                        "name": contact.name,
                        "company": contact.company,
                        "phone": contact.phone,
                        "email": contact.email
                    }
                })
            
            # Sort by date and return top N
            activities.sort(key=lambda x: x['date'], reverse=True)
            return activities[:limit]
            
        except Exception as e:
            logger.error(f"Error getting recent activity: {str(e)}")
            return []
    
    def get_weekly_summary(self) -> Dict[str, Any]:
        """Get this week's summary"""
        try:
            # Start of this week (Monday)
            today = datetime.now()
            start_of_week = today - timedelta(days=today.weekday())
            start_of_week = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)
            
            # Visits this week
            visits_this_week = self.db.query(Visit).filter(
                Visit.created_at >= start_of_week
            ).count()
            
            # Hours this week
            hours_this_week = self.db.query(func.sum(TimeEntry.hours_worked)).filter(
                TimeEntry.date >= start_of_week
            ).scalar() or 0
            
            # New contacts this week
            contacts_this_week = self.db.query(Contact).filter(
                Contact.created_at >= start_of_week
            ).count()
            
            return {
                "visits_this_week": visits_this_week,
                "hours_this_week": round(hours_this_week, 2),
                "contacts_this_week": contacts_this_week,
                "week_start": start_of_week.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting weekly summary: {str(e)}")
            return {}
