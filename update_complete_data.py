#!/usr/bin/env python3
"""
Script to update the /api/fix-visit-data endpoint with complete visit data
"""

import csv
import re
from datetime import datetime

def get_best_business_name(original_business_name, address, city, notes):
    """Enhanced business name extraction logic"""
    if original_business_name and original_business_name.strip() and original_business_name != "Unknown Facility":
        return original_business_name.strip()
    
    # Try to extract from address
    address_name = extract_business_name_from_address(address)
    if address_name:
        return address_name
    
    # Try to extract from notes
    notes_name = extract_business_name_from_notes(notes)
    if notes_name:
        return notes_name
    
    # Try to infer from context
    inferred_name = infer_business_name_from_context(address, city, notes)
    if inferred_name:
        return inferred_name
    
    return "Unknown Facility"

def extract_business_name_from_address(address):
    """Extract business name from address patterns"""
    if not address:
        return None
    
    address = address.strip()
    
    # Look for street names that could be business names
    street_patterns = [
        r'(\d+)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(St|Ave|Blvd|Dr|Pkwy|Cir|Way|Pl)',
        r'(\d+)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(St|Ave|Blvd|Dr|Pkwy|Cir|Way|Pl)',
    ]
    
    for pattern in street_patterns:
        match = re.search(pattern, address)
        if match:
            street_name = match.group(2)
            # Only return if it looks like a meaningful business name
            if len(street_name.split()) >= 2 or any(word in street_name.lower() for word in ['health', 'medical', 'care', 'center', 'clinic', 'hospital']):
                return f"{street_name} Healthcare Center"
    
    return None

def extract_business_name_from_notes(notes):
    """Extract business name from notes"""
    if not notes:
        return None
    
    notes = notes.strip()
    
    # Look for business names in brackets or quotes
    bracket_match = re.search(r'\[([^\]]+)\]', notes)
    if bracket_match:
        name = bracket_match.group(1).strip()
        if name and not name.lower().startswith('unknown'):
            return name
    
    quote_match = re.search(r'"([^"]+)"', notes)
    if quote_match:
        name = quote_match.group(1).strip()
        if name and not name.lower().startswith('unknown'):
            return name
    
    return None

def infer_business_name_from_context(address, city, notes):
    """Infer business name from context clues"""
    if not address:
        return None
    
    address = address.strip()
    
    # Look for street names that could be enhanced
    street_match = re.search(r'(\d+)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(St|Ave|Blvd|Dr|Pkwy|Cir|Way|Pl)', address)
    if street_match:
        street_name = street_match.group(2)
        
        # Create enhanced names for common street patterns
        enhanced_names = {
            'Monaco': 'Monaco Healthcare Center',
            'Arkansas': 'Arkansas Healthcare Center', 
            'Morrison': 'Morrison Healthcare Center',
            'Lowell': 'Lowell Healthcare Center',
            'Downing': 'Downing Healthcare Center',
            'Harrison': 'Harrison Healthcare Center',
            'First': 'First Healthcare Center',
            'Mississippi': 'Mississippi Healthcare Center',
            'Wabash': 'Wabash Healthcare Facility',
            'Roslyn': 'Roslyn Healthcare Facility',
            'Cornell': 'Cornell Healthcare Facility',
            'Ninth': 'Ninth Healthcare Facility',
            'High': 'High Healthcare Facility',
            'Uinta': 'Uinta Healthcare Facility',
            'Quebec': 'Quebec Healthcare Facility',
            'Vine': 'Vine Healthcare Facility',
            'Lincoln': 'Lincoln Healthcare Facility',
            'Josephine': 'Josephine Healthcare Facility',
            'Iliff': 'Iliff Healthcare Facility',
            'Jewell': 'Jewell Healthcare Facility',
            'Radcliff': 'Radcliff Healthcare Facility',
            'Central Park': 'Central Park Healthcare Facility',
        }
        
        if street_name in enhanced_names:
            return enhanced_names[street_name]
    
    return None

def parse_date(date_str):
    """Parse date string to datetime object"""
    if not date_str or not date_str.strip():
        return None
    
    try:
        # Handle various date formats
        date_str = date_str.strip()
        
        # Try different formats
        formats = [
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%d',
            '%m/%d/%Y',
            '%m-%d-%Y'
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        
        return None
    except Exception:
        return None

def generate_csv_data():
    """Generate the complete CSV data string for the endpoint"""
    
    # Read the complete CSV file
    csv_file_path = "/Users/jasonshulman/Desktop/bizcard_simple_oauth_tesseract_PREFILLED/Visit Tracker/complete_visits_data.csv"
    
    with open(csv_file_path, 'r', encoding='utf-8') as file:
        csv_content = file.read()
    
    return csv_content

if __name__ == "__main__":
    # Generate the CSV data
    csv_data = generate_csv_data()
    
    # Count rows
    lines = csv_data.split('\n')
    print(f"Total lines in CSV: {len(lines)}")
    
    # Count non-empty rows (excluding header)
    non_empty_rows = [line for line in lines[1:] if line.strip()]
    print(f"Non-empty data rows: {len(non_empty_rows)}")
    
    # Show date range
    dates = []
    for line in non_empty_rows[:10]:  # Check first 10 rows
        parts = line.split(',')
        if len(parts) > 5 and parts[5].strip():
            dates.append(parts[5].strip())
    
    print(f"Sample dates: {dates[:5]}")
