from fastapi import FastAPI, File, UploadFile, HTTPException, Request, Depends
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import os
import json
from typing import List, Dict, Any
import logging
from parser import PDFParser
from google_sheets import GoogleSheetsManager
from database import get_db, db_manager
from models import Visit, TimeEntry, Contact
from analytics import AnalyticsEngine
from migrate_data import GoogleSheetsMigrator

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Colorado CareAssist Sales Dashboard", version="2.0.0")

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

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """Serve the main dashboard page"""
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """Upload and parse PDF file (MyWay route or Time tracking)"""
    try:
        # Validate file type
        if not file.filename.lower().endswith('.pdf'):
            raise HTTPException(status_code=400, detail="Only PDF files are allowed")
        
        # Read file content
        content = await file.read()
        
        # Parse PDF
        logger.info(f"Parsing PDF: {file.filename}")
        result = pdf_parser.parse_pdf(content)
        
        if not result.get("success", False):
            error_msg = result.get("error", "Failed to parse PDF")
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
        
    except Exception as e:
        logger.error(f"Error processing file: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")

@app.post("/append-to-sheet")
async def append_to_sheet(request: Request, db: Session = Depends(get_db)):
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
                    stop_number=visit_data.get("stop"),
                    business_name=visit_data.get("business_name"),
                    address=visit_data.get("location"),
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
@app.get("/api/dashboard/summary")
async def get_dashboard_summary(db: Session = Depends(get_db)):
    """Get dashboard summary statistics"""
    try:
        analytics = AnalyticsEngine(db)
        summary = analytics.get_dashboard_summary()
        return JSONResponse(summary)
    except Exception as e:
        logger.error(f"Error getting dashboard summary: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/dashboard/visits-by-month")
async def get_visits_by_month(months: int = 12, db: Session = Depends(get_db)):
    """Get visits grouped by month"""
    try:
        analytics = AnalyticsEngine(db)
        data = analytics.get_visits_by_month(months)
        return JSONResponse(data)
    except Exception as e:
        logger.error(f"Error getting visits by month: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/dashboard/hours-by-month")
async def get_hours_by_month(months: int = 12, db: Session = Depends(get_db)):
    """Get hours worked grouped by month"""
    try:
        analytics = AnalyticsEngine(db)
        data = analytics.get_hours_by_month(months)
        return JSONResponse(data)
    except Exception as e:
        logger.error(f"Error getting hours by month: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/dashboard/top-facilities")
async def get_top_facilities(limit: int = 10, db: Session = Depends(get_db)):
    """Get most visited facilities"""
    try:
        analytics = AnalyticsEngine(db)
        data = analytics.get_top_facilities(limit)
        return JSONResponse(data)
    except Exception as e:
        logger.error(f"Error getting top facilities: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/dashboard/recent-activity")
async def get_recent_activity(limit: int = 20, db: Session = Depends(get_db)):
    """Get recent activity across all data types"""
    try:
        analytics = AnalyticsEngine(db)
        data = analytics.get_recent_activity(limit)
        return JSONResponse(data)
    except Exception as e:
        logger.error(f"Error getting recent activity: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/dashboard/weekly-summary")
async def get_weekly_summary(db: Session = Depends(get_db)):
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
async def scan_business_card(file: UploadFile = File(...)):
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
async def save_contact(request: Request, db: Session = Depends(get_db)):
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
async def migrate_data():
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
