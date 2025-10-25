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

@app.post("/api/migrate-data")
async def migrate_data(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Migrate data from Google Sheets to database"""
    try:
        migrator = GoogleSheetsMigrator()
        result = migrator.migrate_all_data()
        
        if result["success"]:
            logger.info(f"Migration successful: {result['visits_migrated']} visits, {result['time_entries_migrated']} time entries")
            return JSONResponse({
                "success": True,
                "message": f"Successfully migrated {result['visits_migrated']} visits and {result['time_entries_migrated']} time entries",
                "visits_migrated": result["visits_migrated"],
                "time_entries_migrated": result["time_entries_migrated"]
            })
        else:
            logger.error(f"Migration failed: {result['error']}")
            raise HTTPException(status_code=500, detail=f"Migration failed: {result['error']}")
            
    except Exception as e:
        logger.error(f"Error during migration: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Migration error: {str(e)}")

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
