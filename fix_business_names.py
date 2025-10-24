#!/usr/bin/env python3

from database import get_db
from models import Visit
import re

def fix_business_names():
    """Update existing visits with better business names"""
    db = next(get_db())
    
    # Get all visits with generic "Healthcare Facility" names
    visits = db.query(Visit).filter(Visit.business_name.like("Healthcare Facility%")).all()
    
    print(f"Found {len(visits)} visits to update")
    
    updated_count = 0
    for visit in visits:
        # Extract street name from address
        street_name = extract_street_name(visit.address)
        if street_name:
            # Create better business name
            if street_name.lower() in ['monaco', 'arkansas', 'morrison', 'lowell', 'downing', 'harrison', 'first', 'mississippi']:
                new_name = f"{street_name} Healthcare Center"
            else:
                new_name = f"{street_name} Healthcare Facility"
            
            visit.business_name = new_name
            updated_count += 1
    
    db.commit()
    print(f"Updated {updated_count} business names")

def extract_street_name(address: str) -> str:
    """Extract street name from address"""
    if not address:
        return None
    
    # Common street name patterns
    street_patterns = [
        r'(\w+)\s+(?:St|Street|Ave|Avenue|Blvd|Boulevard|Rd|Road|Dr|Drive|Ln|Lane|Way|Ct|Court|Pl|Place)',
        r'(\w+)\s+(?:North|South|East|West|N|S|E|W)\s+(?:St|Street|Ave|Avenue|Blvd|Boulevard)',
    ]

    for pattern in street_patterns:
        match = re.search(pattern, address, re.IGNORECASE)
        if match:
            street_name = match.group(1).strip()
            # Filter out common non-street words
            if street_name.lower() not in ['the', 'at', 'of', 'and', 'on', 'in', 'to', 'for']:
                return street_name.title()

    # For addresses like "4900 S Monaco St", try to extract from the beginning
    words = address.split()
    for word in words:
        if word[0].isupper() and len(word) > 2 and word.lower() not in ['the', 'at', 'of', 'and', 'on', 'in', 'to', 'for', 'colorado', 'springs', 'denver']:
            return word.title()

    return None

if __name__ == "__main__":
    fix_business_names()
