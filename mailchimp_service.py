import requests
import logging
from typing import Dict, Any, Optional
import os

logger = logging.getLogger(__name__)

class MailchimpService:
    """Service for integrating with Mailchimp API"""
    
    def __init__(self):
        self.api_key = os.getenv('MAILCHIMP_API_KEY')
        self.server_prefix = os.getenv('MAILCHIMP_SERVER_PREFIX')  # e.g., 'us1', 'us2', etc.
        self.list_id = os.getenv('MAILCHIMP_LIST_ID')
        
        if not all([self.api_key, self.server_prefix, self.list_id]):
            logger.warning("Mailchimp credentials not configured. Export functionality will be disabled.")
            self.enabled = False
        else:
            self.enabled = True
            self.base_url = f"https://{self.server_prefix}.api.mailchimp.com/3.0"
    
    def add_contact(self, contact_info: Dict[str, Any]) -> Dict[str, Any]:
        """Add a contact to Mailchimp list"""
        if not self.enabled:
            return {
                "success": False,
                "error": "Mailchimp not configured"
            }
        
        try:
            # Prepare contact data for Mailchimp
            email = contact_info.get('email', '').strip()
            if not email:
                return {
                    "success": False,
                    "error": "Email address is required for Mailchimp export"
                }
            
            # Mailchimp contact data structure - only include fields with valid data
            merge_fields = {}
            
            # Add fields only if they have valid data
            if contact_info.get('first_name'):
                merge_fields['FNAME'] = contact_info['first_name']
            if contact_info.get('last_name'):
                merge_fields['LNAME'] = contact_info['last_name']
            if contact_info.get('company'):
                merge_fields['COMPANY'] = contact_info['company']
            
            # Only add phone if it's a valid format
            phone = contact_info.get('phone') or ''
            phone = phone.strip() if phone else ''
            if phone and len(phone) >= 10:
                merge_fields['PHONE'] = phone
            
            # Only add address if it's substantial
            address = contact_info.get('address') or ''
            address = address.strip() if address else ''
            if address and len(address) > 10:
                merge_fields['ADDRESS'] = address
            
            # Only add website if it looks like a URL
            website = contact_info.get('website') or ''
            website = website.strip() if website else ''
            if website and ('.' in website and len(website) > 5):
                merge_fields['WEBSITE'] = website
            
            data = {
                "email_address": email,
                "status": "subscribed",
                "merge_fields": merge_fields
            }
            
            # Add tags if available
            if contact_info.get('tags'):
                data['tags'] = contact_info['tags']
            
            # Make API request
            url = f"{self.base_url}/lists/{self.list_id}/members"
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            }
            
            response = requests.post(url, json=data, headers=headers)
            
            if response.status_code in [200, 201]:
                logger.info(f"Successfully added contact to Mailchimp: {email}")
                return {
                    "success": True,
                    "message": f"Contact {email} added to Mailchimp successfully",
                    "mailchimp_id": response.json().get('id')
                }
            elif response.status_code == 400:
                error_data = response.json()
                logger.error(f"Mailchimp 400 error details: {error_data}")
                
                if error_data.get('title') == 'Member Exists':
                    return {
                        "success": True,
                        "message": f"Contact {email} already exists in Mailchimp",
                        "mailchimp_id": error_data.get('detail', '')
                    }
                else:
                    # Get more specific error details
                    error_detail = error_data.get('detail', 'Unknown error')
                    errors = error_data.get('errors', [])
                    if errors:
                        error_detail += f" Errors: {errors}"
                    
                    return {
                        "success": False,
                        "error": f"Mailchimp error: {error_detail}"
                    }
            else:
                return {
                    "success": False,
                    "error": f"Mailchimp API error: {response.status_code} - {response.text}"
                }
                
        except Exception as e:
            logger.error(f"Error adding contact to Mailchimp: {str(e)}")
            return {
                "success": False,
                "error": f"Failed to add contact to Mailchimp: {str(e)}"
            }
    
    def test_connection(self) -> Dict[str, Any]:
        """Test Mailchimp API connection"""
        if not self.enabled:
            return {
                "success": False,
                "error": "Mailchimp not configured"
            }
        
        try:
            url = f"{self.base_url}/lists/{self.list_id}"
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            }
            
            response = requests.get(url, headers=headers)
            
            if response.status_code == 200:
                list_info = response.json()
                return {
                    "success": True,
                    "message": f"Connected to Mailchimp list: {list_info.get('name', 'Unknown')}",
                    "list_name": list_info.get('name'),
                    "member_count": list_info.get('stats', {}).get('member_count', 0)
                }
            else:
                return {
                    "success": False,
                    "error": f"Mailchimp API error: {response.status_code} - {response.text}"
                }
                
        except Exception as e:
            logger.error(f"Error testing Mailchimp connection: {str(e)}")
            return {
                "success": False,
                "error": f"Failed to connect to Mailchimp: {str(e)}"
            }
