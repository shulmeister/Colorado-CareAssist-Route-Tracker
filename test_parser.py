#!/usr/bin/env python3

from parser import PDFParser

def test_parser():
    parser = PDFParser()
    
    # Test with Monaco data
    test_data = {
        "address": "4900 S Monaco St",
        "notes": ["ETA 11:19 AM 12m 4.46 mi."]
    }
    
    # Test street name extraction
    street_name = parser._extract_street_name(test_data["address"])
    print(f"Extracted street name: {street_name}")
    
    result = parser._infer_business_name(test_data["address"], test_data["notes"])
    print(f"Address: {test_data['address']}")
    print(f"Notes: {test_data['notes']}")
    print(f"Inferred name: {result}")
    
    # Test with Arkansas data
    test_data2 = {
        "address": "3105 W Arkansas Ave", 
        "notes": ["ETA 12:15 PM 24m 11.05 mi."]
    }
    
    result2 = parser._infer_business_name(test_data2["address"], test_data2["notes"])
    print(f"\nAddress: {test_data2['address']}")
    print(f"Notes: {test_data2['notes']}")
    print(f"Inferred name: {result2}")

if __name__ == "__main__":
    test_parser()
