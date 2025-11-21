"""
Configuration file for HubSpot CRM Bulk Import
Stores API credentials, endpoint URLs, and project settings
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ============================================
# HUBSPOT API CONFIGURATION
# ============================================
HUBSPOT_API_KEY = os.getenv('HUBSPOT_API_KEY', 'YOUR_API_KEY_HERE')
HUBSPOT_BASE_URL = "https://api.hubapi.com"

# API Endpoints
ENDPOINTS = {
    'companies': '/crm/v3/objects/companies',
    'contacts': '/crm/v3/objects/contacts',
    'tickets': '/crm/v3/objects/tickets',
    'associations': '/crm/v4/associations/{fromObjectType}/{toObjectType}/batch/create',
    'batch': '/batch/create'
}

# ============================================
# IMPORT SETTINGS
# ============================================

# Batch sizes (HubSpot limits: 100 per batch)
BATCH_SIZE = 100

# Retry settings
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds

# Rate limiting (to avoid 429 errors)
REQUESTS_PER_SECOND = 10
DELAY_BETWEEN_BATCHES = 0.1  # 100ms

# ============================================
# DATA VALIDATION RULES
# ============================================

# Required fields per object type
REQUIRED_FIELDS = {
    'companies': ['name'],
    'contacts': ['email'],
    'tickets': ['subject']
}

# Field type validation
FIELD_TYPES = {
    'email': 'email',
    'phone': 'phone',
    'createdate': 'datetime',
    'lastmodifieddate': 'datetime',
    'closed_date': 'datetime',
    'numberofemployees': 'number',
    'annualrevenue': 'number'
}

# ============================================
# MAPPING CONFIGURATION
# ============================================

# Standard HubSpot property mappings
PROPERTY_MAPPINGS = {
    'companies': {
        'name': 'name',
        'domain': 'domain',
        'industry': 'industry',
        'city': 'city',
        'state': 'state',
        'country': 'country',
        'phone': 'phone',
        'numberofemployees': 'numberofemployees',
        'annualrevenue': 'annualrevenue',
        'lifecyclestage': 'lifecyclestage',
        'hs_lead_status': 'hs_lead_status'
    },
    'contacts': {
        'firstname': 'firstname',
        'lastname': 'lastname',
        'email': 'email',
        'phone': 'phone',
        'company': 'company',
        'jobtitle': 'jobtitle',
        'lifecyclestage': 'lifecyclestage',
        'hs_lead_status': 'hs_lead_status'
    },
    'tickets': {
        'subject': 'subject',
        'content': 'content',
        'hs_ticket_priority': 'hs_ticket_priority',
        'hs_pipeline_stage': 'hs_pipeline_stage',
        'hs_ticket_category': 'hs_ticket_category',
        'source_type': 'source_type',
        'createdate': 'createdate',
        'closed_date': 'closed_date'
    }
}

# ============================================
# ASSOCIATION TYPES (HubSpot IDs)
# ============================================

ASSOCIATION_TYPES = {
    'contact_to_company': 1,  # Contact to Company (Primary)
    'ticket_to_contact': 16,  # Ticket to Contact
    'ticket_to_company': 26   # Ticket to Company
}

# ============================================
# OUTPUT SETTINGS
# ============================================

OUTPUT_DIR = 'output/reports'
LOG_LEVEL = 'INFO'

# Report settings
GENERATE_HTML_REPORT = True
GENERATE_CSV_REPORT = True
GENERATE_DASHBOARD = True

# ============================================
# FILE PATHS
# ============================================

DATA_DIR = 'data'
INPUT_FILES = {
    'companies': f'{DATA_DIR}/companies.csv',
    'contacts': f'{DATA_DIR}/contacts.csv',
    'tickets': f'{DATA_DIR}/tickets.csv'
}
