import pytesseract
from PIL import Image
import io
import re
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class BusinessCardScanner:
    """Extract contact information from business card images"""
    
    def __init__(self):
        # Common patterns for extracting contact info
        self.patterns = {
            'email': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            'phone': r'(\+?1[-.\s]?)?\(?([0-9]{3})\)?[-.\s]?([0-9]{3})[-.\s]?([0-9]{4})',
            'website': r'(?:www\.)?[a-zA-Z0-9-]+\.[a-zA-Z]{2,}(?:/[^\s]*)?',
            'address': r'\d+\s+[A-Za-z0-9\s,.-]+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Drive|Dr|Lane|Ln|Court|Ct|Place|Pl)',
        }
    
    def scan_image(self, image_content: bytes) -> Dict[str, Any]:
        """Extract contact information from business card image"""
        try:
            # Open image
            image = Image.open(io.BytesIO(image_content))
            
            # Convert to RGB if necessary
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Extract text using OCR
            text = pytesseract.image_to_string(image)
            
            # Parse contact information
            contact_info = self._parse_contact_info(text)
            
            logger.info(f"Successfully scanned business card: {contact_info.get('name', 'Unknown')}")
            
            return {
                "success": True,
                "contact": contact_info,
                "raw_text": text
            }
            
        except Exception as e:
            logger.error(f"Error scanning business card: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "contact": None
            }
    
    def _parse_contact_info(self, text: str) -> Dict[str, Any]:
        """Parse contact information from OCR text"""
        contact = {
            "name": None,
            "company": None,
            "title": None,
            "phone": None,
            "email": None,
            "website": None,
            "address": None,
            "notes": text.strip()
        }
        
        # Extract email
        email_match = re.search(self.patterns['email'], text)
        if email_match:
            contact['email'] = email_match.group()
        
        # Extract phone
        phone_match = re.search(self.patterns['phone'], text)
        if phone_match:
            contact['phone'] = phone_match.group()
        
        # Extract website
        website_match = re.search(self.patterns['website'], text)
        if website_match:
            contact['website'] = website_match.group()
        
        # Extract address
        address_match = re.search(self.patterns['address'], text)
        if address_match:
            contact['address'] = address_match.group()
        
        # Try to extract name and company from text lines
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        
        if lines:
            # First line is often the name
            contact['name'] = lines[0]
            
            # Look for company indicators
            for line in lines[1:]:
                if any(keyword in line.lower() for keyword in ['inc', 'llc', 'corp', 'company', 'hospital', 'medical', 'health', 'center', 'clinic']):
                    contact['company'] = line
                    break
            
            # Look for title indicators
            for line in lines:
                if any(keyword in line.lower() for keyword in ['manager', 'director', 'coordinator', 'specialist', 'nurse', 'doctor', 'md', 'rn']):
                    contact['title'] = line
                    break
        
        return contact
    
    def validate_contact(self, contact: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and clean contact information"""
        validated = contact.copy()
        
        # Clean phone number
        if validated.get('phone'):
            # Remove all non-digit characters except +
            phone = re.sub(r'[^\d+]', '', validated['phone'])
            if len(phone) == 10:
                validated['phone'] = f"({phone[:3]}) {phone[3:6]}-{phone[6:]}"
            elif len(phone) == 11 and phone.startswith('1'):
                validated['phone'] = f"({phone[1:4]}) {phone[4:7]}-{phone[7:]}"
        
        # Clean email
        if validated.get('email'):
            validated['email'] = validated['email'].lower().strip()
        
        # Clean website
        if validated.get('website'):
            website = validated['website'].lower().strip()
            if not website.startswith('http'):
                website = f"https://{website}"
            validated['website'] = website
        
        # Clean name and company
        if validated.get('name'):
            validated['name'] = validated['name'].strip().title()
        
        if validated.get('company'):
            validated['company'] = validated['company'].strip()
        
        return validated
