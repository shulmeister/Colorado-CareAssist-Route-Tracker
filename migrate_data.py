import gspread
from google.oauth2.service_account import Credentials
import json
import os
import logging
from datetime import datetime
from sqlalchemy.orm import sessionmaker
from database import db_manager
from models import Visit, TimeEntry, Contact
import re

logger = logging.getLogger(__name__)

class GoogleSheetsMigrator:
    """Migrate data from Google Sheets to database"""
    
    def __init__(self):
        self.sheet_id = os.getenv("SHEET_ID", "1rKBP_5eLgvIVprVEzOYRnyL9J3FMf9H-6SLjIvIYFgg")
        self.client = None
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize Google Sheets client"""
        try:
            service_account_key = os.getenv("GOOGLE_SERVICE_ACCOUNT_KEY")
            
            if not service_account_key:
                raise Exception("GOOGLE_SERVICE_ACCOUNT_KEY environment variable not set")
            
            credentials_info = json.loads(service_account_key)
            
            scope = [
                "https://spreadsheets.google.com/feeds",
                "https://www.googleapis.com/auth/drive"
            ]
            
            credentials = Credentials.from_service_account_info(
                credentials_info, 
                scopes=scope
            )
            
            self.client = gspread.authorize(credentials)
            logger.info(f"Successfully connected to Google Sheet: {self.sheet_id}")
            
        except Exception as e:
            logger.error(f"Failed to initialize Google Sheets client: {str(e)}")
            raise Exception(f"Google Sheets initialization failed: {str(e)}")
    
    def migrate_all_data(self):
        """Migrate all data from Google Sheets to database"""
        try:
            # Get database session
            SessionLocal = sessionmaker(bind=db_manager.engine)
            db = SessionLocal()
            
            # Migrate visits
            visits_migrated = self.migrate_visits(db)
            
            # Migrate time entries
            time_entries_migrated = self.migrate_time_entries(db)
            
            # Commit all changes
            db.commit()
            db.close()
            
            logger.info(f"Migration complete: {visits_migrated} visits, {time_entries_migrated} time entries")
            
            return {
                "success": True,
                "visits_migrated": visits_migrated,
                "time_entries_migrated": time_entries_migrated
            }
            
        except Exception as e:
            logger.error(f"Migration failed: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def migrate_visits(self, db):
        """Migrate visits from Google Sheets"""
        try:
            spreadsheet = self.client.open_by_key(self.sheet_id)
            
            # Try to find the visits worksheet
            worksheets = spreadsheet.worksheets()
            visits_worksheet = None
            
            for ws in worksheets:
                if ws.title.lower() in ['visits', 'tracker', 'visit tracker']:
                    visits_worksheet = ws
                    break
            
            if not visits_worksheet:
                logger.warning("No visits worksheet found")
                return 0
            
            # Get all data
            all_values = visits_worksheet.get_all_values()
            
            if len(all_values) <= 1:  # Only header or empty
                logger.info("No visit data to migrate")
                return 0
            
            # Skip header row
            data_rows = all_values[1:]
            
            migrated_count = 0
            
            for row in data_rows:
                if not row or len(row) < 3:  # Skip empty rows
                    continue
                
                try:
                    # Parse the row data
                    # Assuming format: Date, Stop, Business Name, Address, City, Notes
                    visit_date = None
                    stop_number = None
                    business_name = ""
                    address = ""
                    city = ""
                    notes = ""
                    
                    if len(row) >= 1 and row[0]:
                        try:
                            # Try to parse date
                            visit_date = datetime.strptime(row[0], '%Y-%m-%d')
                        except:
                            try:
                                visit_date = datetime.strptime(row[0], '%m/%d/%Y')
                            except:
                                visit_date = datetime.now()
                    
                    if len(row) >= 2 and row[1]:
                        try:
                            stop_number = int(row[1])
                        except:
                            stop_number = 1
                    
                    if len(row) >= 3:
                        business_name = row[2] or "Unknown Facility"
                    
                    if len(row) >= 4:
                        address = (row[3] or "")[:500]  # Truncate to 500 chars
                    
                    if len(row) >= 5:
                        city = (row[4] or "")[:500]  # Truncate to 500 chars
                    
                    if len(row) >= 6:
                        notes = (row[5] or "")[:1000]  # Truncate to 1000 chars
                    
                    # Create visit record
                    visit = Visit(
                        stop_number=stop_number or 1,
                        business_name=business_name,
                        address=address,
                        city=city,
                        notes=notes,
                        visit_date=visit_date or datetime.now()
                    )
                    
                    db.add(visit)
                    migrated_count += 1
                    
                except Exception as e:
                    logger.warning(f"Failed to migrate visit row: {row}, error: {str(e)}")
                    continue
            
            logger.info(f"Migrated {migrated_count} visits")
            return migrated_count
            
        except Exception as e:
            logger.error(f"Error migrating visits: {str(e)}")
            return 0
    
    def migrate_time_entries(self, db):
        """Migrate time entries from Daily Summary worksheet"""
        try:
            spreadsheet = self.client.open_by_key(self.sheet_id)
            
            # Try to find the Daily Summary worksheet
            worksheets = spreadsheet.worksheets()
            daily_summary_worksheet = None
            
            for ws in worksheets:
                if ws.title.lower() in ['daily summary', 'daily', 'summary', 'hours']:
                    daily_summary_worksheet = ws
                    break
            
            if not daily_summary_worksheet:
                logger.warning("No Daily Summary worksheet found")
                return 0
            
            # Get all data
            all_values = daily_summary_worksheet.get_all_values()
            
            if len(all_values) <= 1:  # Only header or empty
                logger.info("No time entry data to migrate")
                return 0
            
            # Skip header row
            data_rows = all_values[1:]
            
            migrated_count = 0
            
            for row in data_rows:
                if not row or len(row) < 2:  # Skip empty rows
                    continue
                
                try:
                    # Parse the row data
                    # Assuming format: Date, Hours Worked, ...
                    date_str = row[0]
                    hours_str = row[1]
                    
                    if not date_str or not hours_str:
                        continue
                    
                    # Parse date
                    try:
                        entry_date = datetime.strptime(date_str, '%Y-%m-%d')
                    except:
                        try:
                            entry_date = datetime.strptime(date_str, '%m/%d/%Y')
                        except:
                            continue
                    
                    # Parse hours
                    try:
                        hours_worked = float(hours_str)
                    except:
                        continue
                    
                    # Create time entry record
                    time_entry = TimeEntry(
                        date=entry_date,
                        hours_worked=hours_worked
                    )
                    
                    db.add(time_entry)
                    migrated_count += 1
                    
                except Exception as e:
                    logger.warning(f"Failed to migrate time entry row: {row}, error: {str(e)}")
                    continue
            
            logger.info(f"Migrated {migrated_count} time entries")
            return migrated_count
            
        except Exception as e:
            logger.error(f"Error migrating time entries: {str(e)}")
            return 0

def run_migration():
    """Run the migration process"""
    migrator = GoogleSheetsMigrator()
    result = migrator.migrate_all_data()
    
    if result["success"]:
        print(f"✅ Migration successful!")
        print(f"   📊 Visits migrated: {result['visits_migrated']}")
        print(f"   ⏰ Time entries migrated: {result['time_entries_migrated']}")
    else:
        print(f"❌ Migration failed: {result['error']}")

if __name__ == "__main__":
    run_migration()
