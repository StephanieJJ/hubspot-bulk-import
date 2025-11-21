"""
CRM Import Engine
=================

Orchestrates the complete import process:
1. Data validation and mapping
2. Import companies → contacts → tickets (proper order)
3. Create associations between objects
4. Generate comprehensive reports

Author: Khadi97 - WBSE
"""

import logging
import pandas as pd
from typing import Dict, List, Tuple
from pathlib import Path
from datetime import datetime
import json

from data_validator import DataValidator, SmartMapper, TicketAssociationExtractor
from hubspot_client import HubSpotClient, ImportResult

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ImportEngine:
    """
    Main engine that coordinates the entire CRM import process.
    
    Process Flow:
    1. Load and validate CSV data
    2. Map columns to HubSpot properties
    3. Import in order: Companies → Contacts → Tickets
    4. Create associations (tickets ↔ contacts ↔ companies)
    5. Generate detailed report
    """
    
    def __init__(self, hubspot_client: HubSpotClient, config: Dict):
        """
        Initialize import engine.
        
        Args:
            hubspot_client: Configured HubSpot API client
            config: Configuration dictionary with settings
        """
        self.client = hubspot_client
        self.config = config
        
        # Initialize validators and mappers
        self.validator = DataValidator(
            config['EMAIL_REGEX'],
            config['PHONE_REGEX']
        )
        
        # Store imported object IDs for associations
        self.imported_companies = {}  # name -> hubspot_id
        self.imported_contacts = {}   # email -> hubspot_id
        self.imported_tickets = {}    # ticket_id -> hubspot_id
        
        # Store import results
        self.results = {
            'companies': None,
            'contacts': None,
            'tickets': None
        }
        
        self.start_time = None
        self.end_time = None
        
        logger.info("✓ ImportEngine initialized")
    
    def load_and_validate_data(self) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """
        Load all CSV files and perform validation.
        
        Returns:
            (companies_df, contacts_df, tickets_df)
        """
        logger.info("\n" + "="*60)
        logger.info("STEP 1: LOADING & VALIDATING DATA")
        logger.info("="*60)
        
        # Load CSV files
        companies_df = self.validator.load_csv(self.config['CSV_FILES']['companies'])
        contacts_df = self.validator.load_csv(self.config['CSV_FILES']['contacts'])
        tickets_df = self.validator.load_csv(self.config['CSV_FILES']['tickets'])
        
        # Validate data quality
        logger.info("\nData Quality Assessment:")
        for name, df in [('Companies', companies_df), 
                        ('Contacts', contacts_df), 
                        ('Tickets', tickets_df)]:
            quality = self.validator.calculate_data_quality(df)
            logger.info(f"  {name}: {quality['completeness']}% complete "
                       f"({quality['row_count']} rows, {quality['column_count']} columns)")
        
        # Validate required fields
        logger.info("\nValidating required fields...")
        for obj_type, df in [('companies', companies_df), 
                            ('contacts', contacts_df), 
                            ('tickets', tickets_df)]:
            required = self.config['REQUIRED_FIELDS'][obj_type]
            is_valid, missing = self.validator.validate_required_fields(df, required)
            
            if not is_valid:
                raise ValueError(f"Missing required fields in {obj_type}: {missing}")
            else:
                logger.info(f"  ✓ {obj_type.capitalize()}: All required fields present")
        
        logger.info("\n✓ Data validation completed successfully")
        return companies_df, contacts_df, tickets_df
    
    def import_companies(self, companies_df: pd.DataFrame) -> ImportResult:
        """
        Import companies to HubSpot.
        
        Args:
            companies_df: DataFrame with company data
            
        Returns:
            ImportResult with operation details
        """
        logger.info("\n" + "="*60)
        logger.info("STEP 2: IMPORTING COMPANIES")
        logger.info("="*60)
        
        # Setup mapper
        mapper = SmartMapper(self.config['COMPANY_PROPERTY_MAPPING'])
        column_mapping = mapper.map_columns(companies_df)
        
        # Prepare properties for each company
        properties_list = []
        for idx, row in companies_df.iterrows():
            props = mapper.prepare_properties(row, column_mapping)
            if props:  # Only add if has valid properties
                properties_list.append(props)
        
        logger.info(f"Prepared {len(properties_list)} companies for import")
        
        # Import via batch API
        result = self.client.batch_create_objects(
            'companies',
            properties_list,
            batch_size=self.config['BATCH_SIZE_COMPANIES']
        )
        
        # Store company name -> ID mapping for associations
        for idx, company_id in enumerate(result.created_ids):
            company_name = properties_list[idx].get('name')
            if company_name:
                self.imported_companies[company_name] = company_id
        
        logger.info(f"✓ Stored {len(self.imported_companies)} company mappings for associations")
        
        self.results['companies'] = result
        return result
    
    def import_contacts(self, contacts_df: pd.DataFrame) -> ImportResult:
        """
        Import contacts to HubSpot with company associations.
        
        Args:
            contacts_df: DataFrame with contact data
            
        Returns:
            ImportResult with operation details
        """
        logger.info("\n" + "="*60)
        logger.info("STEP 3: IMPORTING CONTACTS")
        logger.info("="*60)
        
        # Setup mapper
        mapper = SmartMapper(self.config['CONTACT_PROPERTY_MAPPING'])
        column_mapping = mapper.map_columns(contacts_df)
        
        # Prepare properties and track company associations
        properties_list = []
        contact_company_map = []  # Track which contact goes to which company
        
        for idx, row in contacts_df.iterrows():
            props = mapper.prepare_properties(row, column_mapping)
            
            if props and 'email' in props:  # Email is required
                properties_list.append(props)
                
                # Store company name for later association
                company_name = row.get('company')
                contact_company_map.append({
                    'email': props['email'],
                    'company_name': company_name
                })
        
        logger.info(f"Prepared {len(properties_list)} contacts for import")
        
        # Import via batch API
        result = self.client.batch_create_objects(
            'contacts',
            properties_list,
            batch_size=self.config['BATCH_SIZE_CONTACTS']
        )
        
        # Store email -> ID mapping
        for idx, contact_id in enumerate(result.created_ids):
            email = properties_list[idx].get('email')
            if email:
                self.imported_contacts[email] = contact_id
        
        logger.info(f"✓ Stored {len(self.imported_contacts)} contact mappings for associations")
        
        # Create contact → company associations
        logger.info("\nCreating contact → company associations...")
        associations_created = 0
        associations_failed = 0
        
        for idx, contact_id in enumerate(result.created_ids):
            contact_info = contact_company_map[idx]
            company_name = contact_info.get('company_name')
            
            if company_name and company_name in self.imported_companies:
                company_id = self.imported_companies[company_name]
                
                if self.client.create_association('contacts', contact_id, 
                                                 'companies', company_id):
                    associations_created += 1
                else:
                    associations_failed += 1
        
        logger.info(f"  ✓ Created {associations_created} contact→company associations")
        if associations_failed > 0:
            logger.warning(f"  ⚠ Failed {associations_failed} associations")
        
        self.results['contacts'] = result
        return result
    
    def import_tickets(self, tickets_df: pd.DataFrame, 
                      contacts_df: pd.DataFrame) -> ImportResult:
        """
        Import tickets to HubSpot with contact associations.
        
        Args:
            tickets_df: DataFrame with ticket data
            contacts_df: DataFrame with contact data (for email lookup)
            
        Returns:
            ImportResult with operation details
        """
        logger.info("\n" + "="*60)
        logger.info("STEP 4: IMPORTING TICKETS")
        logger.info("="*60)
        
        # Extract contact info from ticket content
        extractor = TicketAssociationExtractor(self.validator)
        tickets_df = extractor.enrich_tickets_with_associations(tickets_df, contacts_df)
        
        # Setup mapper
        mapper = SmartMapper(self.config['TICKET_PROPERTY_MAPPING'])
        column_mapping = mapper.map_columns(tickets_df)
        
        # Prepare properties and track contact associations
        properties_list = []
        ticket_contact_map = []
        
        for idx, row in tickets_df.iterrows():
            props = mapper.prepare_properties(row, column_mapping)
            
            if props and 'subject' in props:  # Subject is required
                properties_list.append(props)
                
                # Store extracted email for association
                extracted_email = row.get('contact_email_extracted')
                ticket_contact_map.append({
                    'ticket_subject': props.get('subject'),
                    'contact_email': extracted_email
                })
        
        logger.info(f"Prepared {len(properties_list)} tickets for import")
        
        # Import via batch API
        result = self.client.batch_create_objects(
            'tickets',
            properties_list,
            batch_size=self.config['BATCH_SIZE_TICKETS']
        )
        
        # Create ticket → contact associations
        logger.info("\nCreating ticket → contact associations...")
        associations_created = 0
        associations_failed = 0
        associations_skipped = 0
        
        for idx, ticket_id in enumerate(result.created_ids):
            ticket_info = ticket_contact_map[idx]
            contact_email = ticket_info.get('contact_email')
            
            if not contact_email:
                associations_skipped += 1
                continue
            
            # Find contact ID
            if contact_email in self.imported_contacts:
                contact_id = self.imported_contacts[contact_email]
                
                if self.client.create_association('tickets', ticket_id, 
                                                 'contacts', contact_id):
                    associations_created += 1
                else:
                    associations_failed += 1
            else:
                # Try to find in HubSpot
                contact_id = self.client.find_contact_by_email(contact_email)
                if contact_id:
                    if self.client.create_association('tickets', ticket_id, 
                                                     'contacts', contact_id):
                        associations_created += 1
                    else:
                        associations_failed += 1
                else:
                    associations_skipped += 1
        
        logger.info(f"  ✓ Created {associations_created} ticket→contact associations")
        if associations_skipped > 0:
            logger.info(f"  ⊘ Skipped {associations_skipped} (no contact found)")
        if associations_failed > 0:
            logger.warning(f"  ⚠ Failed {associations_failed} associations")
        
        self.results['tickets'] = result
        return result
    
    def execute_full_import(self) -> Dict:
        """
        Execute the complete import process.
        
        Returns:
            Summary dictionary with all results
        """
        self.start_time = datetime.now()
        
        logger.info("\n" + "="*60)
        logger.info("🚀 STARTING CRM BULK IMPORT PROCESS")
        logger.info("="*60)
        logger.info(f"Start time: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        try:
            # Step 1: Load and validate
            companies_df, contacts_df, tickets_df = self.load_and_validate_data()
            
            # Step 2: Test API connection
            logger.info("\nTesting HubSpot API connection...")
            if not self.client.test_connection():
                raise ConnectionError("Failed to connect to HubSpot API")
            
            # Step 3: Import in correct order
            self.import_companies(companies_df)
            self.import_contacts(contacts_df)
            self.import_tickets(tickets_df, contacts_df)
            
            self.end_time = datetime.now()
            duration = (self.end_time - self.start_time).total_seconds()
            
            # Generate summary
            summary = self._generate_summary(duration)
            
            logger.info("\n" + "="*60)
            logger.info("✓ IMPORT PROCESS COMPLETED SUCCESSFULLY")
            logger.info("="*60)
            logger.info(f"Duration: {duration:.2f} seconds")
            
            return summary
            
        except Exception as e:
            logger.error(f"\n✗ Import process failed: {str(e)}")
            raise
    
    def _generate_summary(self, duration: float) -> Dict:
        """Generate comprehensive import summary."""
        summary = {
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat(),
            'duration_seconds': duration,
            'objects': {}
        }
        
        # Add results for each object type
        for obj_type, result in self.results.items():
            if result:
                summary['objects'][obj_type] = result.get_summary()
        
        # Calculate totals
        total_success = sum(s['successful'] for s in summary['objects'].values())
        total_failed = sum(s['failed'] for s in summary['objects'].values())
        total_processed = total_success + total_failed
        
        summary['totals'] = {
            'total_processed': total_processed,
            'total_successful': total_success,
            'total_failed': total_failed,
            'overall_success_rate': round((total_success / total_processed * 100) 
                                        if total_processed > 0 else 0, 2)
        }
        
        return summary


# ==========================================
# USAGE EXAMPLE
# ==========================================
if __name__ == "__main__":
    """
    Demonstrate import engine functionality
    """
    import sys
    sys.path.append(str(Path(__file__).parent.parent))
    from config import *
    from hubspot_client import DemoHubSpotClient
    
    print("\n" + "="*60)
    print("CRM IMPORT ENGINE - Demo")
    print("="*60 + "\n")
    
    # Use demo client for testing
    demo_client = DemoHubSpotClient(success_rate=0.95)
    
    # Prepare config dict
    config = {
        'EMAIL_REGEX': EMAIL_REGEX,
        'PHONE_REGEX': PHONE_REGEX,
        'CSV_FILES': CSV_FILES,
        'REQUIRED_FIELDS': REQUIRED_FIELDS,
        'COMPANY_PROPERTY_MAPPING': COMPANY_PROPERTY_MAPPING,
        'CONTACT_PROPERTY_MAPPING': CONTACT_PROPERTY_MAPPING,
        'TICKET_PROPERTY_MAPPING': TICKET_PROPERTY_MAPPING,
        'BATCH_SIZE_COMPANIES': BATCH_SIZE_COMPANIES,
        'BATCH_SIZE_CONTACTS': BATCH_SIZE_CONTACTS,
        'BATCH_SIZE_TICKETS': BATCH_SIZE_TICKETS
    }
    
    # Initialize and run engine
    engine = ImportEngine(demo_client, config)
    
    try:
        summary = engine.execute_full_import()
        
        print("\n" + "="*60)
        print("IMPORT SUMMARY")
        print("="*60)
        print(json.dumps(summary, indent=2))
        
    except Exception as e:
        print(f"\n✗ Demo failed: {str(e)}")
        import traceback
        traceback.print_exc()
