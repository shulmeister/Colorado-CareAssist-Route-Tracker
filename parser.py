import pdfplumber
import re
import io
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class PDFParser:
    """Parse MyWay route PDFs to extract visit information"""
    
    def __init__(self):
        # Known healthcare facilities in Colorado Springs area
        self.known_facilities = {
            "uchealth memorial hospital": "UCHealth Memorial Hospital Central",
            "uchealth memorial": "UCHealth Memorial Hospital Central",
            "memorial hospital": "UCHealth Memorial Hospital Central",
            "pikes peak hospice": "Pikes Peak Hospice",
            "independence center": "The Independence Center",
            "penrose hospital": "Penrose Hospital",
            "centura health": "Centura Health",
            "st francis medical center": "St. Francis Medical Center",
            "children's hospital colorado": "Children's Hospital Colorado",
            "peaks recovery center": "Peaks Recovery Center",
            "cedar springs hospital": "Cedar Springs Hospital",
            "parkview medical center": "Parkview Medical Center",
            "st mary corwin": "St. Mary-Corwin Medical Center",
            "healthsouth": "HealthSouth Rehabilitation Hospital",
            "kindred hospital": "Kindred Hospital",
            "rehabilitation hospital": "Rehabilitation Hospital",
            "veterans affairs": "VA Medical Center",
            "va hospital": "VA Medical Center",
            "mountain view medical": "Mountain View Medical Center",
            "peak vista": "Peak Vista Community Health Centers",
            "community health": "Community Health Centers",
            "primary care": "Primary Care Clinic",
            "urgent care": "Urgent Care Center",
            "emergency room": "Emergency Room",
            "er": "Emergency Room"
        }
        
        # Common address patterns
        self.address_patterns = [
            r'\d+\s+[A-Za-z\s]+(?:St|Street|Ave|Avenue|Blvd|Boulevard|Rd|Road|Dr|Drive|Way|Ln|Lane|Ct|Court|Pl|Place)',
            r'\d+\s+[A-Za-z\s]+(?:St|Street|Ave|Avenue|Blvd|Boulevard|Rd|Road|Dr|Drive|Way|Ln|Lane|Ct|Court|Pl|Place),\s*Colorado Springs',
            r'\d+\s+[A-Za-z\s]+(?:St|Street|Ave|Avenue|Blvd|Boulevard|Rd|Road|Dr|Drive|Way|Ln|Lane|Ct|Court|Pl|Place),\s*CO'
        ]
    
    def parse_pdf(self, pdf_content: bytes) -> List[Dict[str, Any]]:
        """Parse PDF content and extract visit information"""
        try:
            visits = []
            
            with pdfplumber.open(io.BytesIO(pdf_content)) as pdf:
                for page_num, page in enumerate(pdf.pages):
                    text = page.extract_text()
                    if text:
                        page_visits = self._extract_visits_from_text(text, page_num + 1)
                        visits.extend(page_visits)
            
            # Clean and validate visits
            cleaned_visits = self._clean_visits(visits)
            
            logger.info(f"Extracted {len(cleaned_visits)} visits from PDF")
            return cleaned_visits
            
        except Exception as e:
            logger.error(f"Error parsing PDF: {str(e)}")
            raise Exception(f"Failed to parse PDF: {str(e)}")
    
    def _extract_visits_from_text(self, text: str, page_num: int) -> List[Dict[str, Any]]:
        """Extract visit information from page text"""
        visits = []
        lines = text.split('\n')
        
        current_stop = None
        current_address = None
        current_notes = []
        
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
            
            # Look for stop numbers
            stop_match = re.search(r'^(\d+)[\.\)\-\s]', line)
            if stop_match:
                # Save previous visit if exists
                if current_stop is not None:
                    visit = self._create_visit(current_stop, current_address, current_notes, page_num)
                    if visit:
                        visits.append(visit)
                
                # Start new visit
                current_stop = int(stop_match.group(1))
                current_address = None
                current_notes = []
                
                # Extract address from the same line or next lines
                remaining_text = line[stop_match.end():].strip()
                address = self._extract_address(remaining_text)
                if address:
                    current_address = address
                else:
                    # Look in next few lines for address
                    for j in range(i+1, min(i+3, len(lines))):
                        address = self._extract_address(lines[j])
                        if address:
                            current_address = address
                            break
            
            # Look for addresses in non-stop lines
            elif current_stop is not None and not current_address:
                address = self._extract_address(line)
                if address:
                    current_address = address
            
            # Collect notes
            elif current_stop is not None:
                # Skip common non-note patterns
                if not re.match(r'^(Route|Stop|Time|Date|Driver|Vehicle)', line, re.IGNORECASE):
                    current_notes.append(line)
        
        # Don't forget the last visit
        if current_stop is not None:
            visit = self._create_visit(current_stop, current_address, current_notes, page_num)
            if visit:
                visits.append(visit)
        
        return visits
    
    def _extract_address(self, text: str) -> Optional[str]:
        """Extract address from text"""
        for pattern in self.address_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(0).strip()
        return None
    
    def _create_visit(self, stop_num: int, address: str, notes: List[str], page_num: int) -> Optional[Dict[str, Any]]:
        """Create a visit record"""
        if not address:
            logger.warning(f"Stop {stop_num} on page {page_num} has no address, skipping")
            return None
        
        # Infer business name
        business_name = self._infer_business_name(address, notes)
        
        # Extract city (default to Colorado Springs)
        city = "Colorado Springs"
        if "Denver" in address or "Denver" in " ".join(notes):
            city = "Denver"
        elif "Pueblo" in address or "Pueblo" in " ".join(notes):
            city = "Pueblo"
        
        # Clean up address
        clean_address = self._clean_address(address)
        
        # Combine notes
        combined_notes = " ".join(notes).strip()
        
        return {
            "stop": stop_num,
            "business_name": business_name,
            "location": clean_address,
            "city": city,
            "notes": combined_notes
        }
    
    def _infer_business_name(self, address: str, notes: List[str]) -> str:
        """Infer business name from address and notes"""
        text_to_search = f"{address} {' '.join(notes)}".lower()
        
        # Check against known facilities
        for keyword, facility_name in self.known_facilities.items():
            if keyword in text_to_search:
                return facility_name
        
        # Try to extract from notes
        for note in notes:
            note_lower = note.lower()
            for keyword, facility_name in self.known_facilities.items():
                if keyword in note_lower:
                    return facility_name
        
        # Enhanced business name extraction from address
        business_name = self._extract_business_name_from_address(address, notes)
        if business_name and business_name != "Healthcare Facility":
            return business_name
        
        # Default fallback
        return "Healthcare Facility"
    
    def _extract_business_name_from_address(self, address: str, notes: List[str]) -> str:
        """Extract business name from address using enhanced logic"""
        # Common patterns for healthcare facilities
        healthcare_patterns = [
            r'(\w+(?:\s+\w+)*)\s+(?:Hospital|Medical Center|Health Center|Healthcare Center)',
            r'(\w+(?:\s+\w+)*)\s+(?:Care Center|Rehabilitation Center|Rehab Center)',
            r'(\w+(?:\s+\w+)*)\s+(?:Assisted Living|Senior Living|Memory Care)',
            r'(\w+(?:\s+\w+)*)\s+(?:Hospice|Palliative Care)',
            r'(\w+(?:\s+\w+)*)\s+(?:Clinic|Medical Clinic|Health Clinic)',
            r'(\w+(?:\s+\w+)*)\s+(?:Emergency Room|ER|Emergency Department)',
            r'(\w+(?:\s+\w+)*)\s+(?:Recovery|Treatment Center)',
            r'(\w+(?:\s+\w+)*)\s+(?:Internal Medicine|Family Medicine)',
            r'(\w+(?:\s+\w+)*)\s+(?:Post Acute|Skilled Nursing)',
            r'(\w+(?:\s+\w+)*)\s+(?:Health Care|Healthcare)',
        ]
        
        # Try to match patterns in address
        for pattern in healthcare_patterns:
            match = re.search(pattern, address, re.IGNORECASE)
            if match:
                name_part = match.group(1).strip()
                if len(name_part) > 2 and not name_part.lower() in ['the', 'at', 'of', 'and']:
                    return name_part
        
        # Look for capitalized words that might be business names
        # Split address and look for meaningful capitalized sequences
        address_parts = address.split(',')[0].split()  # Take only street address part
        
        # Find sequences of capitalized words
        capitalized_words = []
        for part in address_parts:
            if part[0].isupper() and len(part) > 2 and not part.lower() in ['st', 'street', 'ave', 'avenue', 'blvd', 'boulevard', 'rd', 'road', 'dr', 'drive', 'ln', 'lane', 'ct', 'court', 'pl', 'place', 'way']:
                capitalized_words.append(part)
            elif capitalized_words:  # Stop if we hit a non-capitalized word after finding some
                break
        
        if capitalized_words:
            # Join capitalized words to form business name
            business_name = " ".join(capitalized_words)
            if len(business_name) > 3:
                return business_name
        
        # Try to extract from notes if available
        for note in notes:
            note_lower = note.lower()
            if any(term in note_lower for term in ['hospital', 'medical', 'health', 'clinic', 'center', 'care']):
                # Look for capitalized words in notes
                note_words = note.split()
                cap_words = [word for word in note_words if word[0].isupper() and len(word) > 2]
                if cap_words:
                    return " ".join(cap_words[:3])  # Take first 3 capitalized words
        
        return None
    
    def _clean_address(self, address: str) -> str:
        """Clean and normalize address"""
        # Remove extra whitespace
        address = re.sub(r'\s+', ' ', address.strip())
        
        # Standardize street abbreviations
        replacements = {
            r'\bSt\b': 'St',
            r'\bStreet\b': 'St',
            r'\bAve\b': 'Ave',
            r'\bAvenue\b': 'Ave',
            r'\bBlvd\b': 'Blvd',
            r'\bBoulevard\b': 'Blvd',
            r'\bRd\b': 'Rd',
            r'\bRoad\b': 'Rd',
            r'\bDr\b': 'Dr',
            r'\bDrive\b': 'Dr',
            r'\bLn\b': 'Ln',
            r'\bLane\b': 'Ln',
            r'\bCt\b': 'Ct',
            r'\bCourt\b': 'Ct',
            r'\bPl\b': 'Pl',
            r'\bPlace\b': 'Pl'
        }
        
        for pattern, replacement in replacements.items():
            address = re.sub(pattern, replacement, address, flags=re.IGNORECASE)
        
        return address
    
    def _clean_visits(self, visits: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Clean and validate visits"""
        cleaned = []
        seen_stops = set()
        
        for visit in visits:
            # Skip duplicates
            if visit["stop"] in seen_stops:
                continue
            
            # Skip incomplete visits
            if not visit["location"] or len(visit["location"]) < 10:
                continue
            
            # Skip obviously invalid stops
            if visit["stop"] < 1 or visit["stop"] > 100:
                continue
            
            seen_stops.add(visit["stop"])
            cleaned.append(visit)
        
        # Sort by stop number
        cleaned.sort(key=lambda x: x["stop"])
        
        return cleaned

