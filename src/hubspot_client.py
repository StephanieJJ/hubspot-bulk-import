"""
HubSpot API Client
Handles all API interactions with retry logic and error handling

FEATURES:
- Batch create operations (up to 100 records per batch)
- Automatic retry with exponential backoff
- Rate limiting protection
- Association management
- Detailed error tracking

USAGE:
    client = HubSpotClient(api_key)
    result = client.batch_create_companies(companies_data)
"""

import requests
import time
import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class ImportResult:
    """Container for import operation results"""
    success_count: int
    error_count: int
    created_ids: List[str]
    errors: List[Dict]
    duration_seconds: float


class HubSpotClient:
    """Client for HubSpot CRM API operations"""
    
    def __init__(self, api_key: str = None):
        """
        Initialize HubSpot client
        
        Args:
            api_key: HubSpot API key (or use from config)
        """
        self.api_key = api_key or config.HUBSPOT_API_KEY
        self.base_url = config.HUBSPOT_BASE_URL
        self.batch_size = config.BATCH_SIZE
        self.max_retries = config.MAX_RETRIES
        self.retry_delay = config.RETRY_DELAY
        
        # Validate API key
        if not self.api_key or self.api_key == 'YOUR_API_KEY_HERE':
            logger.warning("⚠️  No valid API key configured. Using DEMO mode.")
            self.demo_mode = True
        else:
            self.demo_mode = False
            logger.info("✅ HubSpot client initialized with API key")
    
    def _get_headers(self) -> Dict[str, str]:
        """Get HTTP headers for API requests"""
        return {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
    
    def _make_request(self, method: str, endpoint: str, data: Dict = None,
                     retry_count: int = 0) -> Tuple[bool, Optional[Dict], Optional[str]]:
        """
        Make HTTP request with retry logic
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint
            data: Request body data
            retry_count: Current retry attempt
            
        Returns:
            Tuple of (success, response_data, error_message)
        """
        if self.demo_mode:
            logger.info(f"🔧 DEMO MODE: Would {method} to {endpoint}")
            # Simulate successful response
            return True, {'results': [], 'status': 'DEMO'}, None
        
        url = f"{self.base_url}{endpoint}"
        
        try:
            if method == 'POST':
                response = requests.post(url, headers=self._get_headers(), json=data)
            elif method == 'GET':
                response = requests.get(url, headers=self._get_headers())
            else:
                return False, None, f"Unsupported method: {method}"
            
            # Handle rate limiting (429)
            if response.status_code == 429:
                if retry_count < self.max_retries:
                    wait_time = self.retry_delay * (2 ** retry_count)  # Exponential backoff
                    logger.warning(f"⏳ Rate limited. Waiting {wait_time}s before retry...")
                    time.sleep(wait_time)
                    return self._make_request(method, endpoint, data, retry_count + 1)
                else:
                    return False, None, "Max retries exceeded (rate limit)"
            
            # Handle other errors
            if response.status_code >= 400:
                error_msg = f"HTTP {response.status_code}: {response.text}"
                logger.error(f"❌ API Error: {error_msg}")
                
                # Retry on server errors (5xx)
                if response.status_code >= 500 and retry_count < self.max_retries:
                    wait_time = self.retry_delay * (2 ** retry_count)
                    logger.warning(f"🔄 Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                    return self._make_request(method, endpoint, data, retry_count + 1)
                
                return False, None, error_msg
            
            # Success
            return True, response.json(), None
            
        except requests.exceptions.RequestException as e:
            error_msg = f"Request exception: {str(e)}"
            logger.error(f"❌ {error_msg}")
            
            # Retry on connection errors
            if retry_count < self.max_retries:
                wait_time = self.retry_delay * (2 ** retry_count)
                logger.warning(f"🔄 Retrying in {wait_time}s...")
                time.sleep(wait_time)
                return self._make_request(method, endpoint, data, retry_count + 1)
            
            return False, None, error_msg
    
    def batch_create(self, object_type: str, records: List[Dict]) -> ImportResult:
        """
        Create multiple records in batches
        
        Args:
            object_type: HubSpot object type (companies, contacts, tickets)
            records: List of records with 'properties' dict
            
        Returns:
            ImportResult with success/error counts and details
        """
        logger.info(f"🚀 Starting batch create for {len(records)} {object_type}...")
        
        start_time = time.time()
        created_ids = []
        errors = []
        
        # Split into batches
        for i in range(0, len(records), self.batch_size):
            batch = records[i:i + self.batch_size]
            batch_num = (i // self.batch_size) + 1
            total_batches = (len(records) + self.batch_size - 1) // self.batch_size
            
            logger.info(f"📦 Processing batch {batch_num}/{total_batches} ({len(batch)} records)...")
            
            # Prepare batch data
            batch_data = {'inputs': batch}
            
            # Make API request
            endpoint = f"{config.ENDPOINTS[object_type]}/batch/create"
            success, response_data, error_msg = self._make_request('POST', endpoint, batch_data)
            
            if success and response_data:
                # Extract created IDs
                if 'results' in response_data:
                    for result in response_data['results']:
                        if 'id' in result:
                            created_ids.append(result['id'])
                
                logger.info(f"   ✅ Batch {batch_num} completed successfully")
            else:
                # Log errors
                error_info = {
                    'batch': batch_num,
                    'records': len(batch),
                    'error': error_msg
                }
                errors.append(error_info)
                logger.error(f"   ❌ Batch {batch_num} failed: {error_msg}")
            
            # Rate limiting delay between batches
            if i + self.batch_size < len(records):
                time.sleep(config.DELAY_BETWEEN_BATCHES)
        
        duration = time.time() - start_time
        
        result = ImportResult(
            success_count=len(created_ids),
            error_count=len(records) - len(created_ids),
            created_ids=created_ids,
            errors=errors,
            duration_seconds=duration
        )
        
        logger.info(f"✨ Import complete: {result.success_count} success, "
                   f"{result.error_count} errors in {duration:.2f}s")
        
        return result
    
    def batch_create_companies(self, companies_data: List[Dict]) -> ImportResult:
        """Create companies in batches"""
        return self.batch_create('companies', companies_data)
    
    def batch_create_contacts(self, contacts_data: List[Dict]) -> ImportResult:
        """Create contacts in batches"""
        return self.batch_create('contacts', contacts_data)
    
    def batch_create_tickets(self, tickets_data: List[Dict]) -> ImportResult:
        """Create tickets in batches"""
        return self.batch_create('tickets', tickets_data)
    
    def create_associations(self, from_object_type: str, to_object_type: str,
                          associations: List[Dict]) -> ImportResult:
        """
        Create associations between objects
        
        Args:
            from_object_type: Source object type (e.g., 'contacts')
            to_object_type: Target object type (e.g., 'companies')
            associations: List of dicts with 'from_id' and 'to_id'
            
        Returns:
            ImportResult with association results
        """
        logger.info(f"🔗 Creating {len(associations)} {from_object_type}→{to_object_type} associations...")
        
        if not associations:
            logger.info("   No associations to create")
            return ImportResult(0, 0, [], [], 0)
        
        start_time = time.time()
        success_count = 0
        errors = []
        
        # Get association type ID
        assoc_key = f"{from_object_type}_to_{to_object_type}"
        association_type_id = config.ASSOCIATION_TYPES.get(assoc_key)
        
        if not association_type_id:
            error_msg = f"Unknown association type: {assoc_key}"
            logger.error(f"❌ {error_msg}")
            return ImportResult(0, len(associations), [], [{'error': error_msg}], 0)
        
        # Process in batches
        for i in range(0, len(associations), self.batch_size):
            batch = associations[i:i + self.batch_size]
            batch_num = (i // self.batch_size) + 1
            
            # Format for HubSpot API
            inputs = []
            for assoc in batch:
                inputs.append({
                    'from': {'id': str(assoc.get('from_id') or assoc.get('contact_id') or assoc.get('ticket_id'))},
                    'to': {'id': str(assoc.get('to_id') or assoc.get('company_id'))},
                    'type': association_type_id
                })
            
            batch_data = {'inputs': inputs}
            
            # Make request
            endpoint = f"/crm/v3/associations/{from_object_type}/{to_object_type}/batch/create"
            success, response_data, error_msg = self._make_request('POST', endpoint, batch_data)
            
            if success:
                success_count += len(batch)
                logger.info(f"   ✅ Association batch {batch_num} completed")
            else:
                errors.append({
                    'batch': batch_num,
                    'count': len(batch),
                    'error': error_msg
                })
                logger.error(f"   ❌ Association batch {batch_num} failed: {error_msg}")
            
            time.sleep(config.DELAY_BETWEEN_BATCHES)
        
        duration = time.time() - start_time
        
        return ImportResult(
            success_count=success_count,
            error_count=len(associations) - success_count,
            created_ids=[],
            errors=errors,
            duration_seconds=duration
        )
    
    def test_connection(self) -> bool:
        """
        Test API connection
        
        Returns:
            bool: True if connection successful
        """
        logger.info("🔌 Testing HubSpot API connection...")
        
        if self.demo_mode:
            logger.info("✅ DEMO MODE active (no real API calls)")
            return True
        
        # Simple GET request to verify credentials
        success, data, error = self._make_request('GET', '/crm/v3/objects/contacts?limit=1')
        
        if success:
            logger.info("✅ API connection successful")
            return True
        else:
            logger.error(f"❌ API connection failed: {error}")
            return False
