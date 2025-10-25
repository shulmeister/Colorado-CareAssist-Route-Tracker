from fastapi import FastAPI, File, UploadFile, HTTPException, Request, Depends, status
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from sqlalchemy.orm import Session
import os
import json
from typing import List, Dict, Any, Optional
import logging
from parser import PDFParser
from google_sheets import GoogleSheetsManager
from database import get_db, db_manager
from models import Visit, TimeEntry, Contact, ActivityNote, FinancialEntry, SalesBonus
from analytics import AnalyticsEngine
from migrate_data import GoogleSheetsMigrator
from business_card_scanner import BusinessCardScanner
from mailchimp_service import MailchimpService
from auth import oauth_manager, get_current_user, get_current_user_optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Helper functions for business name extraction
import re
from datetime import datetime

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

app = FastAPI(title="Colorado CareAssist Sales Dashboard", version="2.0.0")

# Add security middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "https://tracker.coloradocareassist.com"],  # Production domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add trusted host middleware
app.add_middleware(
    TrustedHostMiddleware, 
    allowed_hosts=["localhost", "127.0.0.1", "*.herokuapp.com", "tracker.coloradocareassist.com"]  # Production domain
)

# Mount static files and templates
templates = Jinja2Templates(directory="templates")

# Initialize components
pdf_parser = PDFParser()
business_card_scanner = BusinessCardScanner()

# Initialize Google Sheets manager with error handling (for migration)
try:
    sheets_manager = GoogleSheetsManager()
    logger.info("Google Sheets manager initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize Google Sheets manager: {str(e)}")
    sheets_manager = None

# Authentication endpoints
@app.get("/auth/login")
async def login():
    """Redirect to Google OAuth login"""
    try:
        auth_url = oauth_manager.get_authorization_url()
        return RedirectResponse(url=auth_url)
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        raise HTTPException(status_code=500, detail="Authentication service unavailable")

@app.get("/auth/callback")
async def auth_callback(request: Request, code: str = None, error: str = None):
    """Handle Google OAuth callback"""
    if error:
        logger.error(f"OAuth error: {error}")
        raise HTTPException(status_code=400, detail=f"Authentication failed: {error}")
    
    if not code:
        raise HTTPException(status_code=400, detail="Authorization code not provided")
    
    try:
        result = await oauth_manager.handle_callback(code, "")
        
        # Create response with session cookie
        response = RedirectResponse(url="/", status_code=302)
        response.set_cookie(
            key="session_token",
            value=result["session_token"],
            max_age=3600 * 24,  # 24 hours
            httponly=True,
            secure=True,  # HTTPS required in production
            samesite="lax"
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Callback error: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Authentication failed: {str(e)}")

@app.post("/auth/logout")
async def logout(request: Request):
    """Logout user"""
    session_token = request.cookies.get("session_token")
    if session_token:
        oauth_manager.logout(session_token)
    
    response = JSONResponse({"success": True, "message": "Logged out successfully"})
    response.delete_cookie("session_token")
    return response

@app.get("/auth/me")
async def get_current_user_info(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Get current user information"""
    return {
        "success": True,
        "user": {
            "email": current_user.get("email"),
            "name": current_user.get("name"),
            "picture": current_user.get("picture"),
            "domain": current_user.get("domain")
        }
    }

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request, current_user: Optional[Dict[str, Any]] = Depends(get_current_user_optional)):
    """Serve the main dashboard page"""
    if not current_user:
        # Redirect to login if not authenticated
        return RedirectResponse(url="/auth/login")
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "user": current_user
    })

@app.post("/upload")
async def upload_file(file: UploadFile = File(...), current_user: Dict[str, Any] = Depends(get_current_user)):
    """Upload and parse PDF file (MyWay route or Time tracking) or scan business card image"""
    try:
        # Validate file type
        file_extension = file.filename.lower().split('.')[-1] if '.' in file.filename else ''
        allowed_extensions = ['pdf', 'jpg', 'jpeg', 'png', 'heic', 'heif']
        
        if file_extension not in allowed_extensions:
            raise HTTPException(status_code=400, detail=f"Only {', '.join(allowed_extensions)} files are allowed")
        
        # Read file content
        content = await file.read()
        
        if file_extension == 'pdf':
            # Parse PDF (MyWay route or Time tracking)
            logger.info(f"Parsing PDF: {file.filename}")
            result = pdf_parser.parse_pdf(content)
            
            if not result.get("success", False):
                error_msg = result.get("error", "Failed to parse PDF")
                logger.error(f"PDF parsing failed: {error_msg}")
                raise HTTPException(status_code=400, detail=error_msg)
        
            # Return appropriate response based on PDF type
            if result["type"] == "time_tracking":
                logger.info(f"Successfully parsed time tracking data: {result['date']} - {result['total_hours']} hours")
                return JSONResponse({
                    "success": True,
                    "filename": file.filename,
                    "type": "time_tracking",
                    "date": result["date"],
                    "total_hours": result["total_hours"]
                })
            else:
                visits = result["visits"]
                if not visits:
                    raise HTTPException(status_code=400, detail="No visits found in PDF")
                
                logger.info(f"Successfully parsed {len(visits)} visits")
                return JSONResponse({
                    "success": True,
                    "filename": file.filename,
                    "type": "myway_route",
                    "visits": visits,
                    "count": len(visits)
                })
        else:
            # Handle business card image (including HEIC)
            logger.info(f"Processing business card image: {file.filename}")
            logger.info(f"File content length: {len(content)} bytes")
            logger.info(f"File extension: {file_extension}")
            try:
                result = business_card_scanner.scan_image(content)
                
                if not result.get("success", False):
                    error_msg = result.get("error", "Failed to scan business card")
                    logger.error(f"Business card scanning failed: {error_msg}")
                    raise HTTPException(status_code=400, detail=error_msg)
                
                # Validate contact information
                contact = business_card_scanner.validate_contact(result["contact"])
                
                # Export to Mailchimp if configured
                mailchimp_result = None
                mailchimp_service = MailchimpService()
                if mailchimp_service.enabled and contact.get('email'):
                    mailchimp_result = mailchimp_service.add_contact(contact)
                    logger.info(f"Mailchimp export result: {mailchimp_result}")
                
                logger.info(f"Successfully scanned business card: {contact.get('name', 'Unknown')}")
                return JSONResponse({
                    "success": True,
                    "filename": file.filename,
                    "type": "business_card",
                    "contact": contact,
                    "extracted_text": result.get("raw_text", ""),
                    "mailchimp_export": mailchimp_result
                })
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Error processing business card image: {str(e)}")
                raise HTTPException(status_code=500, detail=f"Error processing image: {str(e)}")
        
    except Exception as e:
        logger.error(f"Error processing file: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")

@app.post("/append-to-sheet")
async def append_to_sheet(request: Request, db: Session = Depends(get_db), current_user: Dict[str, Any] = Depends(get_current_user)):
    """Append visits to database and optionally sync to Google Sheet"""
    try:
        data = await request.json()
        data_type = data.get("type", "myway_route")
        
        if data_type == "time_tracking":
            # Handle time tracking data
            date = data.get("date")
            total_hours = data.get("total_hours")
            
            if not date or total_hours is None:
                raise HTTPException(status_code=400, detail="Date and total_hours are required for time tracking")
            
            # Save to database
            from datetime import datetime
            time_entry = TimeEntry(
                date=datetime.fromisoformat(date.replace('Z', '+00:00')) if 'T' in date else datetime.strptime(date, '%Y-%m-%d'),
                hours_worked=total_hours
            )
            
            db.add(time_entry)
            db.commit()
            db.refresh(time_entry)
            
            # Also sync to Google Sheets if available
            if sheets_manager:
                try:
                    sheets_manager.update_daily_summary(date, total_hours)
                    logger.info("Synced time entry to Google Sheets")
                except Exception as e:
                    logger.warning(f"Failed to sync to Google Sheets: {str(e)}")
            
            logger.info(f"Successfully saved time entry: {date} - {total_hours} hours")
            
            return JSONResponse({
                "success": True,
                "message": f"Successfully saved {total_hours} hours for {date}",
                "date": date,
                "hours": total_hours
            })
        
        else:
            # Handle MyWay route data
            visits = data.get("visits", [])
            
            if not visits:
                raise HTTPException(status_code=400, detail="No visits provided")
            
            # Save visits to database
            saved_visits = []
            for visit_data in visits:
                visit = Visit(
                    stop_number=visit_data.get("stop_number"),
                    business_name=visit_data.get("business_name"),
                    address=visit_data.get("address"),
                    city=visit_data.get("city"),
                    notes=visit_data.get("notes")
                )
                db.add(visit)
                saved_visits.append(visit)
            
            db.commit()
            
            # Refresh all visits to get IDs
            for visit in saved_visits:
                db.refresh(visit)
            
            # Also sync to Google Sheets if available
            if sheets_manager:
                try:
                    sheets_manager.append_visits(visits)
                    logger.info("Synced visits to Google Sheets")
                except Exception as e:
                    logger.warning(f"Failed to sync to Google Sheets: {str(e)}")
            
            logger.info(f"Successfully saved {len(visits)} visits to database")
            
            return JSONResponse({
                "success": True,
                "message": f"Successfully saved {len(visits)} visits to database",
                "appended_count": len(visits)
            })
        
    except Exception as e:
        logger.error(f"Error saving data: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error saving data: {str(e)}")

# Dashboard API endpoints
@app.get("/api/mailchimp/test")
async def test_mailchimp_connection(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Test Mailchimp API connection"""
    try:
        mailchimp_service = MailchimpService()
        result = mailchimp_service.test_connection()
        return JSONResponse(result)
    except Exception as e:
        logger.error(f"Error testing Mailchimp connection: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error testing Mailchimp: {str(e)}")

@app.post("/api/mailchimp/export")
async def export_contact_to_mailchimp(contact_data: Dict[str, Any], current_user: Dict[str, Any] = Depends(get_current_user)):
    """Export a contact to Mailchimp"""
    try:
        mailchimp_service = MailchimpService()
        result = mailchimp_service.add_contact(contact_data)
        return JSONResponse(result)
    except Exception as e:
        logger.error(f"Error exporting contact to Mailchimp: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error exporting to Mailchimp: {str(e)}")

@app.get("/api/dashboard/summary")
async def get_dashboard_summary(db: Session = Depends(get_db), current_user: Dict[str, Any] = Depends(get_current_user)):
    """Get dashboard summary statistics"""
    try:
        analytics = AnalyticsEngine(db)
        summary = analytics.get_dashboard_summary()
        return JSONResponse(summary)
    except Exception as e:
        logger.error(f"Error getting dashboard summary: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/dashboard/visits-by-month")
async def get_visits_by_month(months: int = 12, db: Session = Depends(get_db), current_user: Dict[str, Any] = Depends(get_current_user)):
    """Get visits grouped by month"""
    try:
        analytics = AnalyticsEngine(db)
        data = analytics.get_visits_by_month(months)
        return JSONResponse(data)
    except Exception as e:
        logger.error(f"Error getting visits by month: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/dashboard/hours-by-month")
async def get_hours_by_month(months: int = 12, db: Session = Depends(get_db), current_user: Dict[str, Any] = Depends(get_current_user)):
    """Get hours worked grouped by month"""
    try:
        analytics = AnalyticsEngine(db)
        data = analytics.get_hours_by_month(months)
        return JSONResponse(data)
    except Exception as e:
        logger.error(f"Error getting hours by month: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/dashboard/top-facilities")
async def get_top_facilities(limit: int = 10, db: Session = Depends(get_db), current_user: Dict[str, Any] = Depends(get_current_user)):
    """Get most visited facilities"""
    try:
        analytics = AnalyticsEngine(db)
        data = analytics.get_top_facilities(limit)
        return JSONResponse(data)
    except Exception as e:
        logger.error(f"Error getting top facilities: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/dashboard/costs-by-month")
async def get_costs_by_month(months: int = 12, db: Session = Depends(get_db), current_user: Dict[str, Any] = Depends(get_current_user)):
    """Get costs grouped by month"""
    try:
        analytics = AnalyticsEngine(db)
        data = analytics.get_costs_by_month(months)
        return JSONResponse(data)
    except Exception as e:
        logger.error(f"Error getting costs by month: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/dashboard/recent-activity")
async def get_recent_activity(limit: int = 20, db: Session = Depends(get_db), current_user: Dict[str, Any] = Depends(get_current_user)):
    """Get recent activity across all data types"""
    try:
        analytics = AnalyticsEngine(db)
        data = analytics.get_recent_activity(limit)
        return JSONResponse(data)
    except Exception as e:
        logger.error(f"Error getting recent activity: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/visits")
async def get_visits(db: Session = Depends(get_db), current_user: Dict[str, Any] = Depends(get_current_user)):
    """Get all visits"""
    try:
        visits = db.query(Visit).order_by(Visit.visit_date.desc()).all()
        return JSONResponse([visit.to_dict() for visit in visits])
    except Exception as e:
        logger.error(f"Error getting visits: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/sales-bonuses")
async def get_sales_bonuses(db: Session = Depends(get_db), current_user: Dict[str, Any] = Depends(get_current_user)):
    """Get all sales bonuses"""
    try:
        sales = db.query(SalesBonus).order_by(SalesBonus.start_date.desc()).all()
        return JSONResponse([sale.to_dict() for sale in sales])
    except Exception as e:
        logger.error(f"Error getting sales bonuses: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/contacts")
async def get_contacts(db: Session = Depends(get_db), current_user: Dict[str, Any] = Depends(get_current_user)):
    """Get all saved contacts"""
    try:
        contacts = db.query(Contact).order_by(Contact.created_at.desc()).all()
        return JSONResponse([contact.to_dict() for contact in contacts])
    except Exception as e:
        logger.error(f"Error fetching contacts: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/dashboard/weekly-summary")
async def get_weekly_summary(db: Session = Depends(get_db), current_user: Dict[str, Any] = Depends(get_current_user)):
    """Get this week's summary"""
    try:
        analytics = AnalyticsEngine(db)
        data = analytics.get_weekly_summary()
        return JSONResponse(data)
    except Exception as e:
        logger.error(f"Error getting weekly summary: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Business card scanning endpoint
@app.post("/api/scan-business-card")
async def scan_business_card(file: UploadFile = File(...), current_user: Dict[str, Any] = Depends(get_current_user)):
    """Scan business card image and extract contact information"""
    try:
        # Validate file type
        if not file.content_type.startswith('image/'):
            raise HTTPException(status_code=400, detail="Only image files are allowed")
        
        # Read file content
        content = await file.read()
        
        # Scan business card
        result = business_card_scanner.scan_image(content)
        
        if not result.get("success", False):
            error_msg = result.get("error", "Failed to scan business card")
            raise HTTPException(status_code=400, detail=error_msg)
        
        # Validate contact information
        contact = business_card_scanner.validate_contact(result["contact"])
        
        logger.info(f"Successfully scanned business card: {contact.get('name', 'Unknown')}")
        
        return JSONResponse({
            "success": True,
            "filename": file.filename,
            "contact": contact
        })
        
    except Exception as e:
        logger.error(f"Error scanning business card: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error scanning business card: {str(e)}")

@app.post("/api/save-contact")
async def save_contact(request: Request, db: Session = Depends(get_db), current_user: Dict[str, Any] = Depends(get_current_user)):
    """Save contact to database"""
    try:
        data = await request.json()
        
        # Create new contact
        contact = Contact(
            name=data.get("name"),
            company=data.get("company"),
            title=data.get("title"),
            phone=data.get("phone"),
            email=data.get("email"),
            website=data.get("website"),
            address=data.get("address"),
            notes=data.get("notes")
        )
        
        db.add(contact)
        db.commit()
        db.refresh(contact)
        
        logger.info(f"Successfully saved contact: {contact.name or contact.company}")
        
        return JSONResponse({
            "success": True,
            "message": "Contact saved successfully",
            "contact": contact.to_dict()
        })
        
    except Exception as e:
        logger.error(f"Error saving contact: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error saving contact: {str(e)}")

@app.post("/api/fix-visit-data")
async def fix_visit_data():
    """Fix visit data with enhanced business names - no auth required for one-time fix"""
    try:
        logger.info("Starting visit data fix...")
        
        # Clear existing visits
        db = next(get_db())
        try:
            deleted_count = db.query(Visit).delete()
            db.commit()
            logger.info(f"Deleted {deleted_count} existing visits")
            
            # Import real visit data with enhanced business names
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
            import csv
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
                    logger.warning(f"Skipping row {row_num}: {str(e)}")
                    continue
            
            # Commit all changes
            db.commit()
            logger.info(f"Successfully imported {imported_count} visits with {enhanced_count} enhanced business names")
            
            return JSONResponse({
                "success": True,
                "message": f"Successfully imported {imported_count} visits with {enhanced_count} enhanced business names",
                "imported_count": imported_count,
                "enhanced_count": enhanced_count
            })
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error fixing visit data: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/migrate-data")
async def migrate_data(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Migrate data from Google Sheets to database and fix visit data"""
    try:
        # First fix the visit data
        logger.info("Starting visit data fix...")
        
        # Clear existing visits
        db = next(get_db())
        try:
            deleted_count = db.query(Visit).delete()
            db.commit()
            logger.info(f"Deleted {deleted_count} existing visits")
            
            # Import real visit data with enhanced business names
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
            import csv
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
                    logger.warning(f"Skipping row {row_num}: {str(e)}")
                    continue
            
            # Commit all changes
            db.commit()
            logger.info(f"Successfully imported {imported_count} visits with {enhanced_count} enhanced business names")
            
        finally:
            db.close()
        
        # Then run the normal migration
        migrator = GoogleSheetsMigrator()
        result = migrator.migrate_all_data()
        
        if result["success"]:
            return JSONResponse({
                "success": True,
                "message": "Data migration and visit data fix completed successfully",
                "details": {
                    "visits_imported": imported_count,
                    "business_names_enhanced": enhanced_count,
                    "migration_details": result["details"]
                }
            })
        else:
            return JSONResponse({
                "success": False,
                "error": result["error"]
            })
            
    except Exception as e:
        logger.error(f"Error migrating data: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/dashboard/financial-summary")
async def get_financial_summary(db: Session = Depends(get_db), current_user: Dict[str, Any] = Depends(get_current_user)):
    """Get comprehensive financial summary"""
    try:
        analytics = AnalyticsEngine(db)
        summary = analytics.get_financial_summary()
        return JSONResponse(summary)
    except Exception as e:
        logger.error(f"Error getting financial summary: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting financial summary: {str(e)}")

@app.get("/api/dashboard/revenue-by-month")
async def get_revenue_by_month(db: Session = Depends(get_db), current_user: Dict[str, Any] = Depends(get_current_user)):
    """Get revenue by month"""
    try:
        analytics = AnalyticsEngine(db)
        data = analytics.get_revenue_by_month()
        return JSONResponse(data)
    except Exception as e:
        logger.error(f"Error getting revenue by month: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting revenue by month: {str(e)}")

# Activity Notes API Endpoints
@app.get("/api/activity-notes")
async def get_activity_notes(db: Session = Depends(get_db), current_user: Dict[str, Any] = Depends(get_current_user)):
    """Get all activity notes"""
    try:
        notes = db.query(ActivityNote).order_by(ActivityNote.date.desc()).all()
        return JSONResponse({
            "success": True,
            "notes": [note.to_dict() for note in notes]
        })
    except Exception as e:
        logger.error(f"Error fetching activity notes: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error fetching activity notes: {str(e)}")

@app.post("/api/activity-notes")
async def create_activity_note(request: Request, db: Session = Depends(get_db), current_user: Dict[str, Any] = Depends(get_current_user)):
    """Create a new activity note"""
    try:
        data = await request.json()
        date_str = data.get("date")
        notes_text = data.get("notes")
        
        if not date_str or not notes_text:
            raise HTTPException(status_code=400, detail="Date and notes are required")
        
        # Parse date
        from datetime import datetime
        note_date = datetime.fromisoformat(date_str.replace('Z', '+00:00')) if 'T' in date_str else datetime.strptime(date_str, '%Y-%m-%d')
        
        activity_note = ActivityNote(
            date=note_date,
            notes=notes_text
        )
        
        db.add(activity_note)
        db.commit()
        db.refresh(activity_note)
        
        logger.info(f"Successfully created activity note for {note_date}")
        
        return JSONResponse({
            "success": True,
            "message": "Activity note created successfully",
            "note": activity_note.to_dict()
        })
        
    except Exception as e:
        logger.error(f"Error creating activity note: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error creating activity note: {str(e)}")

@app.put("/api/activity-notes/{note_id}")
async def update_activity_note(note_id: int, request: Request, db: Session = Depends(get_db), current_user: Dict[str, Any] = Depends(get_current_user)):
    """Update an existing activity note"""
    try:
        data = await request.json()
        notes_text = data.get("notes")
        
        if not notes_text:
            raise HTTPException(status_code=400, detail="Notes are required")
        
        activity_note = db.query(ActivityNote).filter(ActivityNote.id == note_id).first()
        if not activity_note:
            raise HTTPException(status_code=404, detail="Activity note not found")
        
        activity_note.notes = notes_text
        db.commit()
        db.refresh(activity_note)
        
        logger.info(f"Successfully updated activity note {note_id}")
        
        return JSONResponse({
            "success": True,
            "message": "Activity note updated successfully",
            "note": activity_note.to_dict()
        })
        
    except Exception as e:
        logger.error(f"Error updating activity note: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error updating activity note: {str(e)}")

@app.delete("/api/activity-notes/{note_id}")
async def delete_activity_note(note_id: int, db: Session = Depends(get_db), current_user: Dict[str, Any] = Depends(get_current_user)):
    """Delete an activity note"""
    try:
        activity_note = db.query(ActivityNote).filter(ActivityNote.id == note_id).first()
        if not activity_note:
            raise HTTPException(status_code=404, detail="Activity note not found")
        
        db.delete(activity_note)
        db.commit()
        
        logger.info(f"Successfully deleted activity note {note_id}")
        
        return JSONResponse({
            "success": True,
            "message": "Activity note deleted successfully"
        })
        
    except Exception as e:
        logger.error(f"Error deleting activity note: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error deleting activity note: {str(e)}")

@app.get("/favicon.ico")
async def favicon():
    """Serve favicon"""
    return FileResponse("static/favicon.ico")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "Colorado CareAssist Sales Dashboard"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
