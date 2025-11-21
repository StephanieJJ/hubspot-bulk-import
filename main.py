"""
HubSpot CRM Bulk Import - Main Script
Orchestrates the complete import process with validation, mapping, and error handling

PROCESS FLOW:
1. Load CSV files
2. Validate data quality
3. Smart mapping & enrichment
4. Import to HubSpot (Companies → Contacts → Tickets)
5. Create associations
6. Generate detailed reports

USAGE:
    python main.py

AUTHOR: Khadi97 (WBSE - We Bring Support & Expertise)
"""

import pandas as pd
import time
import logging
from datetime import datetime
from pathlib import Path
import sys

# Add src to path
sys.path.append('src')

from validator import DataValidator
from smart_mapper import SmartMapper
from hubspot_client import HubSpotClient, ImportResult
import config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('output/import.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class CRMBulkImporter:
    """Main orchestrator for CRM bulk import"""
    
    def __init__(self):
        """Initialize importer with all components"""
        logger.info("=" * 70)
        logger.info("🚀 HubSpot CRM Bulk Import System")
        logger.info("   by Khadi97 - WBSE (We Bring Support & Expertise)")
        logger.info("=" * 70)
        
        self.validator = DataValidator()
        self.hubspot_client = HubSpotClient()
        
        # Storage for loaded data
        self.companies_df = None
        self.contacts_df = None
        self.tickets_df = None
        self.enriched_tickets_df = None
        
        # Storage for import results
        self.results = {
            'companies': None,
            'contacts': None,
            'tickets': None,
            'associations': {}
        }
        
        # Timing
        self.start_time = None
        self.end_time = None
    
    def load_data(self) -> bool:
        """
        Load all CSV files
        
        Returns:
            bool: True if all files loaded successfully
        """
        logger.info("\n📂 STEP 1: Loading CSV files...")
        logger.info("-" * 70)
        
        try:
            # Load companies
            companies_path = config.INPUT_FILES['companies']
            self.companies_df = pd.read_csv(companies_path)
            logger.info(f"✅ Companies: {len(self.companies_df)} records from {companies_path}")
            
            # Load contacts
            contacts_path = config.INPUT_FILES['contacts']
            self.contacts_df = pd.read_csv(contacts_path)
            logger.info(f"✅ Contacts: {len(self.contacts_df)} records from {contacts_path}")
            
            # Load tickets
            tickets_path = config.INPUT_FILES['tickets']
            self.tickets_df = pd.read_csv(tickets_path)
            logger.info(f"✅ Tickets: {len(self.tickets_df)} records from {tickets_path}")
            
            logger.info(f"\n📊 Total records to process: {len(self.companies_df) + len(self.contacts_df) + len(self.tickets_df)}")
            
            return True
            
        except FileNotFoundError as e:
            logger.error(f"❌ File not found: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ Error loading files: {e}")
            return False
    
    def validate_data(self) -> bool:
        """
        Validate all data before import
        
        Returns:
            bool: True if all validations pass
        """
        logger.info("\n🔍 STEP 2: Validating data quality...")
        logger.info("-" * 70)
        
        all_valid = True
        
        # Validate companies
        companies_valid, companies_errors = self.validator.validate_companies(self.companies_df)
        if not companies_valid:
            logger.error(f"❌ Companies validation failed: {len(companies_errors)} errors")
            all_valid = False
        
        # Validate contacts
        contacts_valid, contacts_errors = self.validator.validate_contacts(self.contacts_df)
        if not contacts_valid:
            logger.error(f"❌ Contacts validation failed: {len(contacts_errors)} errors")
            all_valid = False
        
        # Validate tickets
        tickets_valid, tickets_errors = self.validator.validate_tickets(self.tickets_df)
        if not tickets_valid:
            logger.error(f"❌ Tickets validation failed: {len(tickets_errors)} errors")
            all_valid = False
        
        if all_valid:
            logger.info("✅ All validations passed successfully!")
        else:
            logger.warning("⚠️  Some validations failed. Review errors above.")
            logger.info("   You can continue with valid records or fix errors and retry.")
        
        return all_valid
    
    def enrich_and_map(self):
        """
        Smart mapping and enrichment of data
        """
        logger.info("\n🧠 STEP 3: Smart mapping & enrichment...")
        logger.info("-" * 70)
        
        # Initialize mapper with reference data
        mapper = SmartMapper(self.contacts_df, self.companies_df)
        
        # Enrich tickets with extracted contact info
        self.enriched_tickets_df = mapper.enrich_tickets(self.tickets_df)
        
        # Get associations
        self.associations = mapper.get_ticket_associations(self.enriched_tickets_df)
        
        logger.info("✅ Mapping and enrichment complete")
    
    def import_to_hubspot(self) -> bool:
        """
        Import all data to HubSpot in correct order
        
        Returns:
            bool: True if import successful
        """
        logger.info("\n🚀 STEP 4: Importing to HubSpot...")
        logger.info("-" * 70)
        
        # Test connection first
        if not self.hubspot_client.test_connection():
            logger.error("❌ Cannot connect to HubSpot API. Check your API key.")
            return False
        
        # Map data to HubSpot format
        mapper = SmartMapper()
        
        # 1. Import Companies
        logger.info("\n1️⃣  Importing Companies...")
        companies_data = mapper.map_dataframe_to_hubspot(
            self.companies_df, 
            config.PROPERTY_MAPPINGS['companies']
        )
        self.results['companies'] = self.hubspot_client.batch_create_companies(companies_data)
        
        # 2. Import Contacts
        logger.info("\n2️⃣  Importing Contacts...")
        contacts_data = mapper.map_dataframe_to_hubspot(
            self.contacts_df,
            config.PROPERTY_MAPPINGS['contacts']
        )
        self.results['contacts'] = self.hubspot_client.batch_create_contacts(contacts_data)
        
        # 3. Import Tickets
        logger.info("\n3️⃣  Importing Tickets...")
        tickets_data = mapper.map_dataframe_to_hubspot(
            self.enriched_tickets_df,
            config.PROPERTY_MAPPINGS['tickets']
        )
        self.results['tickets'] = self.hubspot_client.batch_create_tickets(tickets_data)
        
        return True
    
    def create_associations(self):
        """Create associations between objects"""
        logger.info("\n🔗 STEP 5: Creating associations...")
        logger.info("-" * 70)
        
        # Contact → Company associations
        if 'company' in self.contacts_df.columns:
            logger.info("Creating Contact → Company associations...")
            contact_company_assocs = []
            
            for idx, row in self.contacts_df.iterrows():
                if pd.notna(row.get('company')):
                    company_id = SmartMapper(None, self.companies_df).find_company_by_name(row['company'])
                    if company_id:
                        contact_company_assocs.append({
                            'from_id': row['id'],
                            'to_id': company_id
                        })
            
            if contact_company_assocs:
                self.results['associations']['contact_to_company'] = \
                    self.hubspot_client.create_associations(
                        'contacts', 'companies', contact_company_assocs
                    )
        
        # Ticket → Contact associations
        if self.associations.get('ticket_to_contact'):
            logger.info("Creating Ticket → Contact associations...")
            ticket_contact_assocs = []
            for assoc in self.associations['ticket_to_contact']:
                ticket_contact_assocs.append({
                    'from_id': assoc['ticket_id'],
                    'to_id': assoc['contact_id']
                })
            
            self.results['associations']['ticket_to_contact'] = \
                self.hubspot_client.create_associations(
                    'tickets', 'contacts', ticket_contact_assocs
                )
        
        # Ticket → Company associations
        if self.associations.get('ticket_to_company'):
            logger.info("Creating Ticket → Company associations...")
            ticket_company_assocs = []
            for assoc in self.associations['ticket_to_company']:
                ticket_company_assocs.append({
                    'from_id': assoc['ticket_id'],
                    'to_id': assoc['company_id']
                })
            
            self.results['associations']['ticket_to_company'] = \
                self.hubspot_client.create_associations(
                    'tickets', 'companies', ticket_company_assocs
                )
        
        logger.info("✅ Associations created successfully")
    
    def generate_report(self):
        """Generate comprehensive import report"""
        logger.info("\n📊 STEP 6: Generating report...")
        logger.info("-" * 70)
        
        duration = (self.end_time - self.start_time)
        
        report = []
        report.append("=" * 80)
        report.append("📋 HUBSPOT CRM BULK IMPORT - FINAL REPORT")
        report.append("=" * 80)
        report.append(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"Duration: {duration:.2f} seconds")
        report.append("")
        
        # Import summary
        report.append("📊 IMPORT SUMMARY")
        report.append("-" * 80)
        
        for obj_type, result in self.results.items():
            if obj_type == 'associations':
                continue
            if result:
                report.append(f"\n{obj_type.upper()}:")
                report.append(f"  ✅ Success: {result.success_count}")
                report.append(f"  ❌ Errors: {result.error_count}")
                report.append(f"  ⏱️  Duration: {result.duration_seconds:.2f}s")
        
        # Associations summary
        if self.results['associations']:
            report.append("\n🔗 ASSOCIATIONS:")
            for assoc_type, result in self.results['associations'].items():
                if result:
                    report.append(f"  {assoc_type}: {result.success_count} created")
        
        # Statistics
        total_success = sum(r.success_count for r in self.results.values() 
                          if r and isinstance(r, ImportResult))
        total_errors = sum(r.error_count for r in self.results.values() 
                         if r and isinstance(r, ImportResult))
        
        report.append("")
        report.append("🎯 OVERALL STATISTICS")
        report.append("-" * 80)
        report.append(f"Total records processed: {total_success + total_errors}")
        report.append(f"Total success: {total_success}")
        report.append(f"Total errors: {total_errors}")
        report.append(f"Success rate: {(total_success / (total_success + total_errors) * 100):.1f}%")
        
        report.append("")
        report.append("=" * 80)
        report.append("✅ Import process completed!")
        report.append("=" * 80)
        
        report_text = "\n".join(report)
        
        # Print to console
        print("\n" + report_text)
        
        # Save to file
        report_file = f"output/reports/import_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        with open(report_file, 'w') as f:
            f.write(report_text)
        
        logger.info(f"📄 Report saved to: {report_file}")
    
    def run(self):
        """Execute complete import process"""
        self.start_time = time.time()
        
        try:
            # Step 1: Load data
            if not self.load_data():
                logger.error("❌ Failed to load data. Aborting.")
                return False
            
            # Step 2: Validate
            if not self.validate_data():
                response = input("\n⚠️  Validation errors found. Continue anyway? (y/n): ")
                if response.lower() != 'y':
                    logger.info("Import cancelled by user.")
                    return False
            
            # Step 3: Enrich & Map
            self.enrich_and_map()
            
            # Step 4: Import to HubSpot
            if not self.import_to_hubspot():
                logger.error("❌ Import to HubSpot failed. Aborting.")
                return False
            
            # Step 5: Create associations
            self.create_associations()
            
            self.end_time = time.time()
            
            # Step 6: Generate report
            self.generate_report()
            
            logger.info("\n✨ Import process completed successfully!")
            return True
            
        except KeyboardInterrupt:
            logger.warning("\n⚠️  Import interrupted by user")
            return False
        except Exception as e:
            logger.error(f"\n❌ Unexpected error: {e}", exc_info=True)
            return False


def main():
    """Main entry point"""
    importer = CRMBulkImporter()
    success = importer.run()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
