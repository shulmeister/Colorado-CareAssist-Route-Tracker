#!/usr/bin/env python3
"""
Script to generate the complete CSV data string for the /api/fix-visit-data endpoint
"""

def generate_complete_csv_data():
    """Generate the complete CSV data string"""
    
    # Read the complete CSV file
    csv_file_path = "/Users/jasonshulman/Desktop/bizcard_simple_oauth_tesseract_PREFILLED/Visit Tracker/complete_visits_data.csv"
    
    with open(csv_file_path, 'r', encoding='utf-8') as file:
        csv_content = file.read()
    
    # Escape quotes and format for Python string
    csv_content = csv_content.replace('"', '\\"')
    csv_content = csv_content.replace('\n', '\\n')
    
    return csv_content

if __name__ == "__main__":
    csv_data = generate_complete_csv_data()
    
    # Write to a file that can be used to update the endpoint
    with open("complete_csv_data.txt", "w") as f:
        f.write(csv_data)
    
    print("Complete CSV data written to complete_csv_data.txt")
    print(f"Data length: {len(csv_data)} characters")
