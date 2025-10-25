import pytesseract
from PIL import Image
import io
import re
import os
import tempfile
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class BusinessCardScanner:
    """Extract ONLY essential contact information: first name, last name, and email"""
    
    def __init__(self):
        # Focus ONLY on email pattern - this is the most reliable
        self.email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    
    def scan_image(self, image_content: bytes) -> Dict[str, Any]:
        """Extract contact information from business card image"""
        try:
            # Debug: Log the content info
            logger.info(f"Image content length: {len(image_content)} bytes")
            logger.info(f"First 20 bytes: {image_content[:20]}")
            
            # Open image with explicit format handling
            image_buffer = io.BytesIO(image_content)
            
            # Try to open the image
            try:
                image = Image.open(image_buffer)
                logger.info(f"Successfully opened image: {image.format}, mode: {image.mode}, size: {image.size}")
            except Exception as e:
                logger.error(f"Failed to open image with PIL: {str(e)}")
                # For HEIC files, register opener and try temp file approach
                try:
                    logger.info("Attempting HEIC via temporary file")
                    # Register HEIF opener
                    try:
                        from pillow_heif import register_heif_opener
                        register_heif_opener()
                        logger.info("Registered HEIF opener for HEIC files")
                    except ImportError as ie:
                        logger.error(f"Failed to import pillow_heif: {ie}")
                        raise ie
                    
                    image_buffer.seek(0)
                    
                    # Write bytes to temporary file
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.heic') as temp_file:
                        temp_file.write(image_buffer.getvalue())
                        temp_file_path = temp_file.name
                    
                    try:
                        # Now PIL can open it with registered opener
                        image = Image.open(temp_file_path)
                        logger.info(f"Successfully opened HEIC via temp file: {image.mode}, size: {image.size}")
                    finally:
                        # Clean up temp file
                        os.unlink(temp_file_path)
                        
                except Exception as heif_error:
                    logger.error(f"Failed to open HEIC via temp file: {str(heif_error)}")
                    # Try pyheif as fallback
                    try:
                        logger.info("Attempting pyheif as fallback")
                        import pyheif
                        image_buffer.seek(0)
                        heif_file = pyheif.read_heif(image_buffer.getvalue())
                        # Convert to PIL Image
                        image = Image.frombytes(
                            heif_file.mode,
                            heif_file.size,
                            heif_file.data,
                            "raw",
                            heif_file.stride,
                            heif_file.orientation
                        )
                        logger.info(f"Successfully opened HEIC via pyheif: {image.mode}, size: {image.size}")
                    except Exception as pyheif_error:
                        logger.error(f"Failed to open HEIC via pyheif: {str(pyheif_error)}")
                        raise e
            
            # Convert to RGB if necessary (handles HEIC, RGBA, etc.)
            if image.mode not in ['RGB', 'L']:
                logger.info(f"Converting image from {image.mode} to RGB")
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
                "error": f"Failed to process image: {str(e)}",
                "contact": None
            }
    
    def _parse_contact_info(self, text: str) -> Dict[str, Any]:
        """Parse ONLY essential contact information: first name, last name, and email"""
        contact = {
            "first_name": None,
            "last_name": None,
            "email": None,
            "name": None,  # For backward compatibility
            "company": None,  # Will be derived from email domain
            "title": None,
            "phone": None,
            "website": None,
            "address": None,
            "notes": text.strip()
        }
        
        # STEP 1: Extract email (most reliable)
        email_match = re.search(self.email_pattern, text)
        if email_match:
            contact['email'] = email_match.group().lower().strip()
            
            # Extract company from email domain
            email_parts = contact['email'].split('@')
            if len(email_parts) == 2:
                domain = email_parts[1].split('.')[0]  # Get domain without .com, .org, etc.
                # Clean up common domain patterns
                domain = domain.replace('-', ' ').replace('_', ' ')
                contact['company'] = domain.title()
        
        # STEP 2: Extract name using multiple strategies
        name = self._extract_name(text)
        if name:
            contact['name'] = name
            # Try to split into first and last name
            name_parts = name.split()
            if len(name_parts) >= 2:
                contact['first_name'] = name_parts[0].strip()
                contact['last_name'] = ' '.join(name_parts[1:]).strip()
            else:
                contact['first_name'] = name.strip()
        
        return contact
    
    def _extract_name(self, text: str) -> Optional[str]:
        """Extract the most likely name from OCR text"""
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        
        if not lines:
            return None
        
        # Strategy 1: First line that looks like a name (not email, not all caps, not too long)
        for line in lines[:3]:  # Check first 3 lines
            if self._looks_like_name(line):
                return line
        
        # Strategy 2: Look for capitalized words that aren't email addresses
        words = text.split()
        name_candidates = []
        
        for word in words:
            # Skip if it's an email, phone number, or common business words
            if (re.search(self.email_pattern, word) or 
                re.search(r'\d', word) or 
                word.lower() in ['inc', 'llc', 'corp', 'company', 'hospital', 'medical', 'health', 'center', 'clinic', 'the', 'and', 'of', 'for']):
                continue
            
            # If it's capitalized and looks like a name
            if word[0].isupper() and len(word) > 1 and word.isalpha():
                name_candidates.append(word)
        
        # If we found 2-3 name-like words, combine them
        if 2 <= len(name_candidates) <= 3:
            return ' '.join(name_candidates)
        
        return None
    
    def _looks_like_name(self, text: str) -> bool:
        """Check if text looks like a person's name"""
        # Skip if it's an email
        if re.search(self.email_pattern, text):
            return False
        
        # Skip if it contains numbers (likely phone or address)
        if re.search(r'\d', text):
            return False
        
        # Skip if it's too long (likely company name or address)
        if len(text) > 30:
            return False
        
        # Skip if it's all caps (likely company name)
        if text.isupper():
            return False
        
        # Skip common business words
        business_words = ['inc', 'llc', 'corp', 'company', 'hospital', 'medical', 'health', 'center', 'clinic', 'manager', 'director', 'coordinator']
        if any(word in text.lower() for word in business_words):
            return False
        
        # Must have at least 2 words and start with capital letter
        words = text.split()
        if len(words) < 2:
            return False
        
        # All words should start with capital letters
        if not all(word[0].isupper() for word in words if word):
            return False
        
        return True
    
    def validate_contact(self, contact: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and clean ONLY essential contact information"""
        validated = contact.copy()
        
        # Clean email (most important)
        if validated.get('email'):
            validated['email'] = validated['email'].lower().strip()
        
        # Clean names
        if validated.get('first_name'):
            validated['first_name'] = validated['first_name'].strip().title()
        
        if validated.get('last_name'):
            validated['last_name'] = validated['last_name'].strip().title()
        
        if validated.get('name'):
            validated['name'] = validated['name'].strip().title()
        
        # Clean company (derived from email domain)
        if validated.get('company'):
            validated['company'] = validated['company'].strip()
        
        # Set empty fields to None for cleaner Mailchimp export
        for field in ['title', 'phone', 'website', 'address']:
            if not validated.get(field):
                validated[field] = None
        
        return validated
