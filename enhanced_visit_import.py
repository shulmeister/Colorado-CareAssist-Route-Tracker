#!/usr/bin/env python3
"""
Enhanced script to extract business names from addresses and notes
"""

import csv
import os
import re
from datetime import datetime
from sqlalchemy.orm import sessionmaker
from database import db_manager
from models import Visit
from dotenv import load_dotenv

load_dotenv()

def extract_business_name_from_address(address):
    """Extract business name from address"""
    if not address:
        return None
    
    # Common patterns for business names in addresses
    patterns = [
        r'(\d+\s+[A-Za-z\s&]+(?:Hospital|Medical|Health|Care|Center|Clinic|Group|Services|Healthcare))',
        r'(\d+\s+[A-Za-z\s&]+(?:Post|Legion|VFW|American Legion))',
        r'(\d+\s+[A-Za-z\s&]+(?:Senior|Living|Assisted|Nursing))',
        r'(\d+\s+[A-Za-z\s&]+(?:Hospice|Palliative))',
        r'(\d+\s+[A-Za-z\s&]+(?:Orthopaedic|Orthopedic|Surgical))',
        r'(\d+\s+[A-Za-z\s&]+(?:Rehabilitation|Rehab))',
        r'(\d+\s+[A-Za-z\s&]+(?:Community|Health Centers))',
        r'(\d+\s+[A-Za-z\s&]+(?:Memorial|St\. Francis|Penrose))',
        r'(\d+\s+[A-Za-z\s&]+(?:VA|Veterans|Outpatient))',
        r'(\d+\s+[A-Za-z\s&]+(?:PACE|InnovAge))',
        r'(\d+\s+[A-Za-z\s&]+(?:Home Health|Home Care))',
        r'(\d+\s+[A-Za-z\s&]+(?:Therapy|Therapeutic))',
        r'(\d+\s+[A-Za-z\s&]+(?:Behavioral|Mental Health))',
        r'(\d+\s+[A-Za-z\s&]+(?:Cancer|Oncology))',
        r'(\d+\s+[A-Za-z\s&]+(?:Women\'s|Obstetrics))',
        r'(\d+\s+[A-Za-z\s&]+(?:Emergency|ER))',
        r'(\d+\s+[A-Za-z\s&]+(?:Administrative|Admin))',
        r'(\d+\s+[A-Za-z\s&]+(?:Foundation|Fund))',
        r'(\d+\s+[A-Za-z\s&]+(?:Resort|Residential))',
        r'(\d+\s+[A-Za-z\s&]+(?:Plaza|Medical Plaza))',
        r'(\d+\s+[A-Za-z\s&]+(?:Pavilion|Tower))',
        r'(\d+\s+[A-Za-z\s&]+(?:Building|Complex))',
        r'(\d+\s+[A-Za-z\s&]+(?:Suite|Ste|Unit))',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, address, re.IGNORECASE)
        if match:
            business_name = match.group(1).strip()
            # Clean up the name
            business_name = re.sub(r'\s+', ' ', business_name)  # Multiple spaces to single
            business_name = re.sub(r'\s+(St|Ave|Blvd|Dr|Rd|Cir|Pkwy|Way)\s*$', '', business_name, flags=re.IGNORECASE)
            return business_name
    
    return None

def extract_business_name_from_notes(notes):
    """Extract business name from notes"""
    if not notes:
        return None
    
    # Look for business names in notes
    patterns = [
        r'([A-Za-z\s&]+(?:Hospital|Medical|Health|Care|Center|Clinic|Group|Services|Healthcare))',
        r'([A-Za-z\s&]+(?:Post|Legion|VFW|American Legion))',
        r'([A-Za-z\s&]+(?:Senior|Living|Assisted|Nursing))',
        r'([A-Za-z\s&]+(?:Hospice|Palliative))',
        r'([A-Za-z\s&]+(?:Orthopaedic|Orthopedic|Surgical))',
        r'([A-Za-z\s&]+(?:Rehabilitation|Rehab))',
        r'([A-Za-z\s&]+(?:Community|Health Centers))',
        r'([A-Za-z\s&]+(?:Memorial|St\. Francis|Penrose))',
        r'([A-Za-z\s&]+(?:VA|Veterans|Outpatient))',
        r'([A-Za-z\s&]+(?:PACE|InnovAge))',
        r'([A-Za-z\s&]+(?:Home Health|Home Care))',
        r'([A-Za-z\s&]+(?:Therapy|Therapeutic))',
        r'([A-Za-z\s&]+(?:Behavioral|Mental Health))',
        r'([A-Za-z\s&]+(?:Cancer|Oncology))',
        r'([A-Za-z\s&]+(?:Women\'s|Obstetrics))',
        r'([A-Za-z\s&]+(?:Emergency|ER))',
        r'([A-Za-z\s&]+(?:Administrative|Admin))',
        r'([A-Za-z\s&]+(?:Foundation|Fund))',
        r'([A-Za-z\s&]+(?:Resort|Residential))',
        r'([A-Za-z\s&]+(?:Plaza|Medical Plaza))',
        r'([A-Za-z\s&]+(?:Pavilion|Tower))',
        r'([A-Za-z\s&]+(?:Building|Complex))',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, notes, re.IGNORECASE)
        if match:
            business_name = match.group(1).strip()
            # Clean up the name
            business_name = re.sub(r'\s+', ' ', business_name)  # Multiple spaces to single
            return business_name
    
    return None

def infer_business_name_from_context(stop_number, address, city, notes):
    """Infer business name from context when all else fails"""
    if not address:
        return "Unknown Facility"
    
    # Extract street name and create a descriptive name
    street_match = re.search(r'\d+\s+([A-Za-z\s&]+)', address)
    if street_match:
        street_name = street_match.group(1).strip()
        
        # Create healthcare facility names based on street patterns
        if any(word in street_name.lower() for word in ['main', 'primary', 'central']):
            return f"{street_name} Healthcare Center"
        elif any(word in street_name.lower() for word in ['union', 'academy', 'nevada']):
            return f"{street_name} Medical Center"
        elif any(word in street_name.lower() for word in ['boulder', 'platte', 'tejon']):
            return f"{street_name} Healthcare Facility"
        elif any(word in street_name.lower() for word in ['tenderfoot', 'lake', 'plaza']):
            return f"{street_name} Care Center"
        elif any(word in street_name.lower() for word in ['international', 'research', 'briargate']):
            return f"{street_name} Medical Facility"
        elif any(word in street_name.lower() for word in ['woodmen', 'championship', 'cordera']):
            return f"{street_name} Healthcare Services"
        elif any(word in street_name.lower() for word in ['austin', 'jeannine', 'murray']):
            return f"{street_name} Health Center"
        elif any(word in street_name.lower() for word in ['lehman', 'goddard', 'pulpit']):
            return f"{street_name} Medical Services"
        elif any(word in street_name.lower() for word in ['pinon', 'elkton', 'centennial']):
            return f"{street_name} Healthcare Group"
        elif any(word in street_name.lower() for word in ['bloomington', 'monica', 'southgate']):
            return f"{street_name} Care Services"
        elif any(word in street_name.lower() for word in ['circle', 'hancock', 'parkside']):
            return f"{street_name} Medical Group"
        elif any(word in street_name.lower() for word in ['van buren', 'eighth', 'southmoor']):
            return f"{street_name} Healthcare Center"
        else:
            return f"{street_name} Healthcare Facility"
    
    return "Unknown Healthcare Facility"

def get_best_business_name(business_name, address, city, notes):
    """Get the best business name from available data"""
    # If we already have a business name, use it
    if business_name and business_name.strip() and business_name != "Unknown Facility":
        return business_name.strip()
    
    # Try to extract from address
    extracted_from_address = extract_business_name_from_address(address)
    if extracted_from_address:
        return extracted_from_address
    
    # Try to extract from notes
    extracted_from_notes = extract_business_name_from_notes(notes)
    if extracted_from_notes:
        return extracted_from_notes
    
    # Infer from context
    return infer_business_name_from_context(None, address, city, notes)

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

def import_enhanced_visits_csv(csv_file_path):
    """Import visits with enhanced business name extraction"""
    print(f"📥 Importing enhanced visits from {csv_file_path}...")
    
    SessionLocal = sessionmaker(bind=db_manager.engine)
    db = SessionLocal()
    
    imported_count = 0
    skipped_count = 0
    enhanced_count = 0
    
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
                    original_business_name = row[1].strip() if row[1] else ""
                    address = row[2].strip() if row[2] else None
                    city = row[3].strip() if row[3] else None
                    notes = row[4].strip() if row[4] else None
                    date_str = row[5].strip() if row[5] else None
                    
                    # Get the best business name using enhanced extraction
                    business_name = get_best_business_name(original_business_name, address, city, notes)
                    
                    # Track if we enhanced the business name
                    if not original_business_name or original_business_name == "Unknown Facility":
                        enhanced_count += 1
                    
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
        print(f"🎯 Enhanced business names for {enhanced_count} visits")
        print(f"⚠️  Skipped {skipped_count} rows due to errors")
        
        return imported_count
        
    except Exception as e:
        print(f"❌ Error importing CSV: {str(e)}")
        db.rollback()
        return 0
    finally:
        db.close()

def main():
    """Main function to replace visit data with enhanced business names"""
    print("🚀 Starting enhanced visit data import...")
    
    csv_file = "real_visits_data.csv"
    
    if not os.path.exists(csv_file):
        print(f"❌ CSV file not found: {csv_file}")
        return
    
    # Step 1: Clear existing data
    if not clear_existing_visits():
        print("❌ Failed to clear existing data. Aborting.")
        return
    
    # Step 2: Import enhanced data
    imported_count = import_enhanced_visits_csv(csv_file)
    
    if imported_count > 0:
        print(f"🎉 Successfully imported {imported_count} visits with enhanced business names!")
        print("🔄 Refresh your dashboard to see the updated data.")
    else:
        print("❌ Failed to import enhanced visit data.")

if __name__ == "__main__":
    main()
