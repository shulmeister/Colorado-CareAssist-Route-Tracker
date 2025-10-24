#!/usr/bin/env python3

from database import get_db
from models import Visit, SalesBonus

def debug_data():
    db = next(get_db())
    
    # Check recent visits
    recent_visits = db.query(Visit).order_by(Visit.created_at.desc()).limit(10).all()
    print("Recent visits:")
    for v in recent_visits:
        business_name = v.business_name or "[EMPTY]"
        print(f"{business_name} - {v.address} - {v.created_at}")
    
    # Check visits with empty business names
    empty_business = db.query(Visit).filter(Visit.business_name == None).count()
    print(f"\nVisits with empty business names: {empty_business}")
    
    # Check sales bonuses
    sales = db.query(SalesBonus).all()
    print(f"\nTotal sales bonuses: {len(sales)}")
    for s in sales[:3]:
        print(f"Sale: {s.client_name} - ${s.bonus_amount}")

if __name__ == "__main__":
    debug_data()
