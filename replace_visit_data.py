#!/usr/bin/env python3
"""
Script to replace placeholder visit data with real CSV data
"""

import csv
import os
from datetime import datetime
from sqlalchemy.orm import sessionmaker
from database import db_manager
from models import Visit
from dotenv import load_dotenv

load_dotenv()

def clear_existing_visits():
    """Clear all existing visit data from database"""
    print("🗑️  Clearing existing visit data...")
    
    SessionLocal = sessionmaker(bind=db_manager.engine)
    db = SessionLocal()
    
    try:
        # Delete all existing visits
        deleted_count = db.query(Visit).delete()
        db.commit()
        print(f"✅ Deleted {deleted_count} existing visits")
        return True
    except Exception as e:
        print(f"❌ Error clearing visits: {str(e)}")
        db.rollback()
        return False
    finally:
        db.close()

def parse_date(date_str):
    """Parse date string from CSV"""
    if not date_str or date_str.strip() == '' or date_str == '—':
        return None
    
    try:
        # Handle different date formats
        if ' ' in date_str:
            # Format: "2025-03-06 00:00:00"
            date_part = date_str.split()[0]
            return datetime.strptime(date_part, '%Y-%m-%d')
        else:
            # Format: "2025-03-06"
            return datetime.strptime(date_str, '%Y-%m-%d')
    except ValueError:
        print(f"Warning: Could not parse date: {date_str}")
        return None

def import_real_visits_csv(csv_file_path):
    """Import real visits from CSV"""
    print(f"📥 Importing real visits from {csv_file_path}...")
    
    SessionLocal = sessionmaker(bind=db_manager.engine)
    db = SessionLocal()
    
    imported_count = 0
    skipped_count = 0
    
    try:
        with open(csv_file_path, 'r', encoding='utf-8') as file:
            csv_reader = csv.reader(file)
            header = next(csv_reader)  # Skip header
            
            for row_num, row in enumerate(csv_reader, 2):
                if not row or len(row) < 6:
                    skipped_count += 1
                    continue
                
                try:
                    # Parse row data
                    stop_number = int(row[0]) if row[0] and row[0].isdigit() else None
                    business_name = row[1].strip() if row[1] else "Unknown Facility"
                    address = row[2].strip() if row[2] else None
                    city = row[3].strip() if row[3] else None
                    notes = row[4].strip() if row[4] else None
                    date_str = row[5].strip() if row[5] else None
                    
                    # Parse date
                    visit_date = parse_date(date_str)
                    if not visit_date:
                        # Use current date if no valid date
                        visit_date = datetime.now()
                    
                    # Create visit record
                    visit = Visit(
                        stop_number=stop_number,
                        business_name=business_name,
                        address=address,
                        city=city,
                        notes=notes,
                        visit_date=visit_date
                    )
                    
                    db.add(visit)
                    imported_count += 1
                    
                    if imported_count % 50 == 0:
                        print(f"  Processed {imported_count} visits...")
                        
                except Exception as e:
                    print(f"  Warning: Skipping row {row_num}: {str(e)}")
                    skipped_count += 1
                    continue
        
        # Commit all changes
        db.commit()
        print(f"✅ Successfully imported {imported_count} visits!")
        print(f"⚠️  Skipped {skipped_count} rows due to errors")
        
        return imported_count
        
    except Exception as e:
        print(f"❌ Error importing CSV: {str(e)}")
        db.rollback()
        return 0
    finally:
        db.close()

def main():
    """Main function to replace visit data"""
    print("🚀 Starting visit data replacement...")
    
    csv_file = "real_visits_data.csv"
    
    if not os.path.exists(csv_file):
        print(f"❌ CSV file not found: {csv_file}")
        return
    
    # Step 1: Clear existing data
    if not clear_existing_visits():
        print("❌ Failed to clear existing data. Aborting.")
        return
    
    # Step 2: Import real data
    imported_count = import_real_visits_csv(csv_file)
    
    if imported_count > 0:
        print(f"🎉 Successfully replaced visit data with {imported_count} real visits!")
        print("🔄 Refresh your dashboard to see the updated data.")
    else:
        print("❌ Failed to import real visit data.")

if __name__ == "__main__":
    main()
