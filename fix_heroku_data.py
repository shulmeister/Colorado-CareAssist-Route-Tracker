#!/usr/bin/env python3
"""
One-time script to fix visit data on Heroku
"""

import os
import sys
import csv
import re
from datetime import datetime
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from models import Visit

def get_database_url():
    """Get database URL from environment"""
    return os.getenv('DATABASE_URL', 'sqlite:///sales_tracker.db')

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
        return None

def main():
    """Main function to replace visit data with enhanced business names"""
    print("🚀 Starting Heroku visit data replacement...")
    
    # Create database connection
    database_url = get_database_url()
    engine = create_engine(database_url)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    
    try:
        # Clear existing visits
        print("🗑️  Clearing existing visit data...")
        deleted_count = db.query(Visit).delete()
        db.commit()
        print(f"✅ Deleted {deleted_count} existing visits")
        
        # CSV data embedded in script
        csv_data = """Stop,Business Name,Location,City,Notes,Date,Facility Type,Follow-up Needed,Lead,Client
1,,1630 E Cheyenne Mountain Blvd,Colorado Springs,Cookie stop,2025-03-06 00:00:00,,,,
2,Colorado Springs Orthopaedic Group,1259 Lake Plaza Dr Unit 100,Colorado Springs,,2025-03-06 00:00:00,,,,
3,Summit Home Health Care,1160 Lake Plaza Dr Ste 255,Colorado Springs,,2025-03-06 00:00:00,,,,
4,Pikes Peak Hospice & Palliative Care,2550 Tenderfoot Hill St,Colorado Springs,,2025-03-06 00:00:00,,,,
5,Mountain View Post Acute,835 Tenderfoot Hill Rd,Colorado Springs,,2025-03-06 00:00:00,,,,
6,Professional Home Health Care,1140 S Eighth St,Colorado Springs,,2025-03-06 00:00:00,,,,
7,The Independence Center,729 S Tejon St,Colorado Springs,Super grateful and excited to read about / reach out for our services,2025-03-06 00:00:00,,,,
8,American Legion Post 5,15 E Platte Ave,Colorado Springs,No answer again.,2025-03-06 00:00:00,,,,
9,UCHealth Memorial Hospital Central,1400 E Boulder St,Colorado Springs,,2025-03-06 00:00:00,,,,
10,Life Care Center of Colorado Springs,2490 International Cir,Colorado Springs,Natasha at front desk was super helpful with connecting me with the case managers,2025-03-06 00:00:00,,,,
11,Advanced Health Care of Colorado Springs,55 S Parkside Dr,Colorado Springs,A bit busy again but was able to leave a good impression still,2025-03-06 00:00:00,,,,
12,Flagship Health,3210 N Academy Blvd Ste 1,Colorado Springs,Elka at the front desk was super interested...,2025-03-06 00:00:00,,,,
13,,1625 S Murray Blvd,Colorado Springs,Great opportunity to network more! 1200-1400 attendees he said,2025-03-06 00:00:00,,,,
14,Fountain Valley Senior Center,5725 Southmoor Dr,Fountain,"Not interested at all, quite rude...",2025-03-06 00:00:00,,,,
15,American Legion Post 38,6685 Southmoor Dr,Fountain,,2025-03-06 00:00:00,,,,
16,UCHealth Endocrinology Clinic - Grandview,5818 N Nevada Ave Ste 225,Colorado Springs,,2025-03-07 00:00:00,,,,
17,Maxim Healthcare Services,7150 Campus Dr Ste 160,Colorado Springs,Was in meeting again but definitely interested in connecting more,2025-03-07 00:00:00,,,,
18,,5225 N Academy Blvd #106,Colorado Springs,Passed on to supervisor. They don't let ya in the door,2025-03-07 00:00:00,,,,
19,Benefit Health Care,5426 N Academy Blvd Ste 200,Colorado Springs,Potential other client in same building,2025-03-07 00:00:00,,,,
20,,5373 N Union Blvd,Colorado Springs,"Closed in co springs, removing off route",2025-03-07 00:00:00,,,,
21,Gentiva Hospice,6270 Lehman Dr #150,Colorado Springs,Was able to meet patient manager and told her we would be in touch,2025-03-07 00:00:00,,,,
22,Better Healthcare,6208 Lehman Dr Unit 201,Colorado Springs,,2025-03-07 00:00:00,,,,
23,Bristol Hospice,7660 Goddard St #100,Colorado Springs,,2025-03-07 00:00:00,,,,
24,,1155 Kelly Johnson Blvd Ste 205,Colorado Springs,No longer at this location. Removing from route,2025-03-07 00:00:00,,,,
25,Corporate Pointe Medical Center,1975 Research Pkwy #300,Colorado Springs,,2025-03-07 00:00:00,,,,
26,Colorado Springs Orthopaedic Group,4110 Briargate Pkwy,Colorado Springs,Ortho group sent me to their surgery floor and said we'd have better luck connecting with someone who does more of that stuff,2025-03-07 00:00:00,,,,
27,UCHealth Memorial Hospital North,4050 Briargate Pkwy,Colorado Springs,,2025-03-07 00:00:00,,,,
28,The Center at Cordera,9208 Grand Cordera Pkwy,Colorado Springs,Got to meet admissions coordinator Brenna and she said she will pass it onto case managers. They may be interested in the respite care,2025-03-07 00:00:00,,,,
29,Penrose St. Francis Hospital,6001 E Woodmen Rd,Colorado Springs,Lead case manager Gail Abeyta,2025-03-07 00:00:00,,,,
30,Voyager Home Health Care,2233 Academy Pl Ste 105,Colorado Springs,,2025-03-18 00:00:00,,,,
31,CenterCare Home Health,1155 Kelly Johnson Blvd Ste 205,Colorado Springs,,2025-03-18 00:00:00,,,,
32,CenterCare Home Health,1155 Kelly Johnson Blvd Ste 205,Colorado Springs,Leslie is who spoke with Jason,2025-03-18 00:00:00,,,,
33,Gentiva Hospice,6270 Lehman Dr #150,Colorado Springs,,2025-03-18 00:00:00,,,,
34,Better Healthcare,6208 Lehman Dr Unit 201,Colorado Springs,,2025-03-18 00:00:00,,,,
35,,5426 N Academy Blvd #200,Colorado Springs,,2025-03-18 00:00:00,,,,
36,Peak Vista Community Health Centers,3225 Austin Bluffs Pkwy Ste 200,Colorado Springs,3204 in same building as mountain ridge now,2025-03-18 00:00:00,,,,
37,American Legion Post 209,3613 Jeannine Dr,Colorado Springs,,2025-03-18 00:00:00,,,,
38,Mountain Ridge Hospice,3204 N Academy Blvd Unit 110,Colorado Springs,,2025-03-18 00:00:00,,,,
39,,5850 Championship View,Colorado Springs,,2025-03-18 00:00:00,,,,
40,Penrose St. Francis Hospital,6001 E Woodmen Rd,Colorado Springs,Tracy is who we want to speak with here,2025-03-18 00:00:00,,,,
41,The Center at Cordera,9208 Grand Cordera Pkwy,Colorado Springs,,2025-03-18 00:00:00,,,,
42,Colorado Springs Orthopaedic Group,4110 Briargate Pkwy,Colorado Springs,,2025-03-18 00:00:00,,,,
43,UCHealth Memorial Hospital North,4050 Briargate Pkwy,Colorado Springs,,2025-03-18 00:00:00,,,,
44,Corporate Pointe Medical Center,1975 Research Pkwy #300,Colorado Springs,,2025-03-18 00:00:00,,,,
45,Bristol Hospice,7660 Goddard St #100,Colorado Springs,,2025-03-18 00:00:00,,,,
46,Maxim Healthcare Services,7150 Campus Dr Ste 160,Colorado Springs,,2025-03-18 00:00:00,,,,
47,,5623 Pulpit Peak View,Colorado Springs,,2025-03-18 00:00:00,,,,
48,FirstLight Home Care,910 Pinon Ranch View Ste 211,Colorado Springs,Recommended us to one of their clients last week.,2025-03-18 00:00:00,,,,
49,Optimal Home Care,1115 Elkton Dr,Colorado Springs,,2025-03-18 00:00:00,,,,
50,,4775 Centennial Blvd Unit 160,Colorado Springs,,2025-03-18 00:00:00,,,,
51,,3810 Bloomington St,Colorado Springs,,2025-03-18 00:00:00,,,,
52,,3830 Bloomington St,Colorado Springs,,2025-03-20 00:00:00,,,,
53,Flagship Health,3210 N Academy Blvd Ste 1,Colorado Springs,Multiple questions for Jason please email,2025-03-20 00:00:00,,,,
54,,3027 N Circle Dr,Colorado Springs,St. Francis primary and urgent care - common spirit,2025-03-20 00:00:00,,,,
55,Humana Neighborhood Center,1120 N Circle Dr Ste 7,Colorado Springs,Moved. Delete,2025-03-20 00:00:00,,,,
56,Life Care Center of Colorado Springs,2490 International Cir,Colorado Springs,Come back in the mornings before lunch and meetings,2025-03-20 00:00:00,,,,
57,Advanced Health Care of Colorado Springs,55 S Parkside Dr,Colorado Springs,Spoke with Ryan the administrative facilitator,2025-03-20 00:00:00,,,,
58,InnovAge Colorado PACE – Central,1414 N Hancock Ave,Colorado Springs,,2025-03-20 00:00:00,,,,
59,Envida,1514 N Hancock Ave,Colorado Springs,,2025-03-20 00:00:00,,,,
60,Silver Key Senior Services,207 N Nevada Ave,Colorado Springs,At the YMCA for now until building reconstruction is done,2025-03-20 00:00:00,,,,
61,UCHealth – Memorial Administrative Offices,2222 N Nevada Ave,Colorado Springs,Speak with Sheila; they're moving back after Labor Day,2025-03-20 00:00:00,,,,
62,Westside Cares,110 W Van Buren St,Colorado Springs,,2025-03-20 00:00:00,,,,
63,,,,,2025-03-20 00:00:00,,,,
64,,3490 Centennial Blvd,Colorado Springs,Come back mid morning on Mondays. Avoid Tues/Thurs 2-3pm,2025-03-20 00:00:00,,,,
65,PFC Floyd K Lindstrom VA Outpatient Clinic,3141 Centennial Blvd,Colorado Springs,,2025-03-20 00:00:00,,,,
66,Professional Home Health Care,1140 S Eighth St,Colorado Springs,,2025-03-20 00:00:00,,,,
67,The Independence Center,729 S Tejon St,Colorado Springs,Cameron and Tyler are the referral specialists,2025-03-20 00:00:00,,,,
68,UCHealth Memorial Hospital Central,1400 E Boulder St,Colorado Springs,Dr. Nimptsch-Kossek floats to other locations,2025-03-20 00:00:00,,,,
69,Pikes Peak Hospice & Palliative Care,2550 Tenderfoot Hill St,Colorado Springs,Daniel Smead is the director to talk to,2025-03-20 00:00:00,,,,
70,Mountain View Post Acute,835 Tenderfoot Hill Rd,Colorado Springs,Larissa is at front desk,2025-03-20 00:00:00,,,,
71,Summit Home Health Care,1160 Lake Plaza Dr Ste 255,Colorado Springs,,2025-03-20 00:00:00,,,,
72,Colorado Springs Orthopaedic Group,1259 Lake Plaza Dr Unit 100,Colorado Springs,,2025-03-20 00:00:00,,,,
73,Fountain Valley Senior Center,5725 Southmoor Dr,Fountain,,2025-03-20 00:00:00,,,,
74,American Legion Post 38,6685 Southmoor Dr,Fountain,,2025-03-20 00:00:00,,,,
75,,1605 S Murray Blvd,Colorado Springs,,2025-03-26 00:00:00,,,,
76,Life Care Center of Colorado Springs,2490 International Cir,Colorado Springs,,2025-03-26 00:00:00,,,,
77,Advanced Health Care of Colorado Springs,55 S Parkside Dr,Colorado Springs,,2025-03-26 00:00:00,,,,
78,UCHealth Memorial Hospital Central,1400 E Boulder St,Colorado Springs,,2025-03-26 00:00:00,,,,
79,Silver Key Senior Services,207 N Nevada Ave,Colorado Springs,,2025-03-26 00:00:00,,,,
80,InnovAge Colorado PACE – Central,1414 N Hancock Ave,Colorado Springs,,2025-03-26 00:00:00,,,,
81,,175 S Union Blvd,Colorado Springs,Still can't find Dr. Nimptsch Kossek,2025-03-26 00:00:00,,,,
82,Humana Neighborhood Center,1120 N Circle Dr Ste 7,Colorado Springs,Delete!,2025-03-26 00:00:00,,,,
83,Flagship Health,3210 N Academy Blvd Ste 1,Colorado Springs,,2025-03-26 00:00:00,,,,
84,,3027 N Circle Dr,Colorado Springs,Common spirit primary care,2025-03-26 00:00:00,,,,
85,UCHealth – Memorial Administrative Offices,2222 N Nevada Ave,Colorado Springs,Orthopedics 10th floor,2025-03-26 00:00:00,,,,
86,Westside Cares,110 W Van Buren St,Colorado Springs,,2025-03-26 00:00:00,,,,
87,,3490 Centennial Blvd,Colorado Springs,,2025-03-26 00:00:00,,,,
88,The Independence Center,729 S Tejon St,Colorado Springs,Closes at 4:30 Mon–Thu,2025-03-26 00:00:00,,,,
89,Pikes Peak Hospice & Palliative Care,2550 Tenderfoot Hill St,Colorado Springs,,2025-03-26 00:00:00,,,,
90,Mountain View Post Acute,835 Tenderfoot Hill Rd,Colorado Springs,,2025-03-26 00:00:00,,,,
91,Summit Home Health Care,1160 Lake Plaza Dr Ste 255,Colorado Springs,,2025-03-26 00:00:00,,,,
92,Colorado Springs Orthopaedic Group,1259 Lake Plaza Dr Unit 100,Colorado Springs,,2025-03-26 00:00:00,,,,
93,American Legion Post 38,6685 Southmoor Dr,Fountain,,2025-03-26 00:00:00,,,,
94,,2910 S Academy Blvd,Colorado Springs,,2025-03-27 00:00:00,,,,
95,Fountain Valley Senior Center,5725 Southmoor Dr,Fountain,,2025-03-27 00:00:00,,,,
96,PFC Floyd K Lindstrom VA Outpatient Clinic,3141 Centennial Blvd,Colorado Springs,,2025-03-27 00:00:00,,,,
97,Voyager Home Health Care,2233 Academy Pl Ste 105,Colorado Springs,,2025-03-27 00:00:00,,,,
98,Peak Vista Community Health Centers,3225 Austin Bluffs Pkwy Ste 200,Colorado Springs,3204 in same building as mountain ridge now,2025-03-27 00:00:00,,,,
99,American Legion Post 209,3613 Jeannine Dr,Colorado Springs,,2025-03-27 00:00:00,,,,
100,,5850 Championship View,Colorado Springs,,2025-03-27 00:00:00,,,,
101,Penrose St. Francis Hospital,6001 E Woodmen Rd,Colorado Springs,,2025-03-27 00:00:00,,,,
102,Flagship Health,3210 N Academy Blvd Ste 1,Colorado Springs,,2025-03-27 00:00:00,,,,
103,The Center at Cordera,9208 Grand Cordera Pkwy,Colorado Springs,,2025-03-27 00:00:00,,,,
104,Colorado Springs Orthopaedic Group,4110 Briargate Pkwy,Colorado Springs,,2025-03-27 00:00:00,,,,
105,UCHealth Memorial Hospital North,4050 Briargate Pkwy,Colorado Springs,,2025-03-27 00:00:00,,,,
106,Corporate Pointe Medical Center,1975 Research Pkwy #300,Colorado Springs,,2025-03-27 00:00:00,,,,
107,CenterCare Home Health,1155 Kelly Johnson Blvd Ste 205,Colorado Springs,Leslie is who spoke with Jason,2025-03-27 00:00:00,,,,
108,CenterCare Home Health,1155 Kelly Johnson Blvd Ste 205,Colorado Springs,,2025-03-27 00:00:00,,,,
109,Flagship Health,3210 N Academy Blvd Ste 1,Colorado Springs,,2025-03-31 00:00:00,,,,
110,,3027 N Circle Dr,Colorado Springs,,2025-03-31 00:00:00,,,,
111,Life Care Center of Colorado Springs,2490 International Cir,Colorado Springs,,2025-03-31 00:00:00,,,,
112,Advanced Health Care of Colorado Springs,55 S Parkside Dr,Colorado Springs,,2025-03-31 00:00:00,,,,
113,UCHealth Memorial Hospital Central,1400 E Boulder St,Colorado Springs,,2025-03-31 00:00:00,,,,
114,InnovAge Colorado PACE – Central,1414 N Hancock Ave,Colorado Springs,,2025-03-31 00:00:00,,,,
115,Silver Key Senior Services,207 N Nevada Ave,Colorado Springs,,2025-03-31 00:00:00,,,,
116,UCHealth – Memorial Administrative Offices,2222 N Nevada Ave,Colorado Springs,,2025-03-31 00:00:00,,,,
117,Westside Cares,110 W Van Buren St,Colorado Springs,,2025-03-31 00:00:00,,,,
118,,3490 Centennial Blvd,Colorado Springs,,2025-03-31 00:00:00,,,,
119,PFC Floyd K Lindstrom VA Outpatient Clinic,3141 Centennial Blvd,Colorado Springs,,2025-03-31 00:00:00,,,,
120,Professional Home Health Care,1140 S Eighth St,Colorado Springs,,2025-03-31 00:00:00,,,,
121,The Independence Center,729 S Tejon St,Colorado Springs,,2025-03-31 00:00:00,,,,
122,UCHealth Memorial Hospital Central,1400 E Boulder St,Colorado Springs,,2025-03-31 00:00:00,,,,
123,Pikes Peak Hospice & Palliative Care,2550 Tenderfoot Hill St,Colorado Springs,,2025-03-31 00:00:00,,,,
124,Mountain View Post Acute,835 Tenderfoot Hill Rd,Colorado Springs,,2025-03-31 00:00:00,,,,
125,Summit Home Health Care,1160 Lake Plaza Dr Ste 255,Colorado Springs,,2025-03-31 00:00:00,,,,
126,Colorado Springs Orthopaedic Group,1259 Lake Plaza Dr Unit 100,Colorado Springs,,2025-03-31 00:00:00,,,,
127,Fountain Valley Senior Center,5725 Southmoor Dr,Fountain,,2025-03-31 00:00:00,,,,
128,,1605 S Murray Blvd,Colorado Springs,,2025-03-31 00:00:00,,,,
129,American Legion Post 38,6685 Southmoor Dr,Fountain,,2025-03-31 00:00:00,,,,
130,,2715 Monica Dr W,Colorado Springs,,2025-03-31 00:00:00,,,,"""

        # Parse CSV data
        csv_reader = csv.reader(csv_data.split('\n'))
        header = next(csv_reader)  # Skip header
        
        imported_count = 0
        enhanced_count = 0
        
        for row_num, row in enumerate(csv_reader, 2):
            if not row or len(row) < 6:
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
                
            except Exception as e:
                print(f"  Warning: Skipping row {row_num}: {str(e)}")
                continue
        
        # Commit all changes
        db.commit()
        print(f"✅ Successfully imported {imported_count} visits!")
        print(f"🎯 Enhanced business names for {enhanced_count} visits")
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    main()
