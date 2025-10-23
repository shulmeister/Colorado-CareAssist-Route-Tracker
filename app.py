from fastapi import FastAPI, File, UploadFile, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import os
import json
from typing import List, Dict, Any
import logging
from parser import PDFParser
from google_sheets import GoogleSheetsManager
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Colorado CareAssist Route Tracker", version="1.0.0")

# Mount static files and templates
templates = Jinja2Templates(directory="templates")

# Initialize components
pdf_parser = PDFParser()

# Initialize Google Sheets manager with error handling
try:
    sheets_manager = GoogleSheetsManager()
    logger.info("Google Sheets manager initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize Google Sheets manager: {str(e)}")
    sheets_manager = None

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """Serve the main upload page"""
    return templates.TemplateResponse("index.html", {"request": request})

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
async def append_to_sheet(request: Request):
    """Append visits to Google Sheet or update Daily Summary"""
    try:
        if not sheets_manager:
            raise HTTPException(status_code=500, detail="Google Sheets not configured. Please check environment variables.")
        
        data = await request.json()
        data_type = data.get("type", "myway_route")
        
        if data_type == "time_tracking":
            # Handle time tracking data
            date = data.get("date")
            total_hours = data.get("total_hours")
            
            if not date or total_hours is None:
                raise HTTPException(status_code=400, detail="Date and total_hours are required for time tracking")
            
            # Update Daily Summary
            result = sheets_manager.update_daily_summary(date, total_hours)
            
            logger.info(f"Successfully updated Daily Summary for {date} with {total_hours} hours")
            
            return JSONResponse({
                "success": True,
                "message": f"Successfully updated Daily Summary for {date} with {total_hours} hours",
                "date": date,
                "hours": total_hours
            })
        
        else:
            # Handle MyWay route data
            visits = data.get("visits", [])
            
            if not visits:
                raise HTTPException(status_code=400, detail="No visits provided")
            
            # Append to Google Sheet
            result = sheets_manager.append_visits(visits)
            
            logger.info(f"Successfully appended {len(visits)} visits to Google Sheet")
            
            return JSONResponse({
                "success": True,
                "message": f"Successfully added {len(visits)} visits to the tracker",
                "appended_count": len(visits)
            })
        
    except Exception as e:
        logger.error(f"Error updating sheet: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error updating sheet: {str(e)}")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "Colorado CareAssist Route Tracker"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
