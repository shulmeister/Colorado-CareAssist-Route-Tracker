import gspread
from google.oauth2.service_account import Credentials
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
import json
import os
import logging
from typing import List, Dict, Any
import pickle

logger = logging.getLogger(__name__)

class GoogleSheetsManager:
    """Manage Google Sheets integration for visit tracking"""
    
    def __init__(self):
        self.sheet_id = os.getenv("SHEET_ID", "1rKBP_5eLgvIVprVEzOYRnyL9J3FMf9H-6SLjIvIYFgg")
        self.worksheet_name = "Visits"
        self.client = None
        self.worksheet = None
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize Google Sheets client"""
        try:
            # Get service account credentials from environment
            service_account_key = os.getenv("GOOGLE_SERVICE_ACCOUNT_KEY")
            
            if not service_account_key:
                raise Exception("GOOGLE_SERVICE_ACCOUNT_KEY environment variable not set")
            
            # Parse JSON credentials
            try:
                credentials_info = json.loads(service_account_key)
            except json.JSONDecodeError:
                raise Exception("Invalid JSON in GOOGLE_SERVICE_ACCOUNT_KEY")
            
            # Set up credentials
            scope = [
                "https://spreadsheets.google.com/feeds",
                "https://www.googleapis.com/auth/drive"
            ]
            
            credentials = Credentials.from_service_account_info(
                credentials_info, 
                scopes=scope
            )
            
            # Initialize client
            self.client = gspread.authorize(credentials)
            
            # Open the spreadsheet
            spreadsheet = self.client.open_by_key(self.sheet_id)
            self.worksheet = spreadsheet.worksheet(self.worksheet_name)
            
            logger.info(f"Successfully connected to Google Sheet: {self.sheet_id}")
            
        except Exception as e:
            logger.error(f"Failed to initialize Google Sheets client: {str(e)}")
            raise Exception(f"Google Sheets initialization failed: {str(e)}")
    
    def append_visits(self, visits: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Append visits to the Google Sheet"""
        try:
            if not self.worksheet:
                raise Exception("Google Sheets not initialized")
            
            if not visits:
                raise Exception("No visits to append")
            
            # Prepare data for insertion
            rows_to_add = []
            
            for visit in visits:
                row = [
                    visit.get("stop", ""),
                    visit.get("business_name", ""),
                    visit.get("location", ""),
                    visit.get("city", ""),
                    visit.get("notes", "")
                ]
                rows_to_add.append(row)
            
            # Append to worksheet
            self.worksheet.append_rows(rows_to_add)
            
            logger.info(f"Successfully appended {len(visits)} visits to Google Sheet")
            
            return {
                "success": True,
                "appended_count": len(visits),
                "message": f"Added {len(visits)} visits to the tracker"
            }
            
        except Exception as e:
            logger.error(f"Error appending visits to sheet: {str(e)}")
            raise Exception(f"Failed to append visits: {str(e)}")
    
    def get_recent_visits(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent visits from the sheet"""
        try:
            if not self.worksheet:
                raise Exception("Google Sheets not initialized")
            
            # Get all records
            records = self.worksheet.get_all_records()
            
            # Return most recent (assuming they're added in order)
            recent = records[-limit:] if len(records) > limit else records
            
            return recent
            
        except Exception as e:
            logger.error(f"Error getting recent visits: {str(e)}")
            raise Exception(f"Failed to get recent visits: {str(e)}")
    
    def get_visit_count(self) -> int:
        """Get total number of visits in the sheet"""
        try:
            if not self.worksheet:
                raise Exception("Google Sheets not initialized")
            
            # Get all records and count non-empty rows
            records = self.worksheet.get_all_records()
            return len(records)
            
        except Exception as e:
            logger.error(f"Error getting visit count: {str(e)}")
            return 0
    
    def test_connection(self) -> bool:
        """Test the Google Sheets connection"""
        try:
            if not self.worksheet:
                return False
            
            # Try to read the first row
            self.worksheet.row_values(1)
            return True
            
        except Exception as e:
            logger.error(f"Google Sheets connection test failed: {str(e)}")
            return False
