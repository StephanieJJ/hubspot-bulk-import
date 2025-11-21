"""
Smart Mapper Module
Extracts contact information from ticket content and creates intelligent mappings

FEATURES:
- Email extraction from text (regex-based)
- Phone extraction from text (international format)
- Automatic field mapping to HubSpot properties
- Association detection (ticket → contact via email)
- Company name extraction and matching

USAGE:
    mapper = SmartMapper(contacts_df, companies_df)
    mapped_tickets = mapper.enrich_tickets(tickets_df)
    associations = mapper.get_ticket_associations()
"""

import re
import pandas as pd
from typing import Dict, List, Tuple, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SmartMapper:
    """Intelligent mapping and extraction for CRM data"""
    
    def __init__(self, contacts_df: pd.DataFrame = None, companies_df: pd.DataFrame = None):
        """
        Initialize SmartMapper with reference data
        
        Args:
            contacts_df: DataFrame of contacts (for email matching)
            companies_df: DataFrame of companies (for name matching)
        """
        self.contacts_df = contacts_df
        self.companies_df = companies_df
        
        # Email regex (comprehensive pattern)
        self.email_pattern = re.compile(
            r'\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b',
            re.IGNORECASE
        )
        
        # Phone regex (international format with + or 00)
        self.phone_pattern = re.compile(
            r'(?:\+|00)\d{1,4}[\s.-]?\d{1,14}(?:[\s.-]?\d{1,13})?'
        )
        
        # Build lookup dictionaries for fast matching
        self.email_to_contact_id = {}
        self.company_name_to_id = {}
        
        if contacts_df is not None:
            self._build_contact_lookup()
        
        if companies_df is not None:
            self._build_company_lookup()
    
    def _build_contact_lookup(self):
        """Build email → contact_id lookup dictionary"""
        if 'email' in self.contacts_df.columns and 'id' in self.contacts_df.columns:
            for idx, row in self.contacts_df.iterrows():
                email = str(row['email']).strip().lower()
                contact_id = row['id']
                self.email_to_contact_id[email] = contact_id
            
            logger.info(f"📇 Built contact lookup: {len(self.email_to_contact_id)} emails indexed")
    
    def _build_company_lookup(self):
        """Build company_name → company_id lookup dictionary"""
        if 'name' in self.companies_df.columns and 'id' in self.companies_df.columns:
            for idx, row in self.companies_df.iterrows():
                name = str(row['name']).strip().lower()
                company_id = row['id']
                self.company_name_to_id[name] = company_id
            
            logger.info(f"🏢 Built company lookup: {len(self.company_name_to_id)} companies indexed")
    
    def extract_emails(self, text: str) -> List[str]:
        """
        Extract all email addresses from text
        
        Args:
            text: Text to search for emails
            
        Returns:
            List of email addresses found
        """
        if pd.isna(text) or not text:
            return []
        
        emails = self.email_pattern.findall(str(text))
        # Clean and deduplicate
        emails = [email.strip().lower() for email in emails]
        return list(set(emails))  # Remove duplicates
    
    def extract_phones(self, text: str) -> List[str]:
        """
        Extract all phone numbers from text
        
        Args:
            text: Text to search for phone numbers
            
        Returns:
            List of phone numbers found
        """
        if pd.isna(text) or not text:
            return []
        
        phones = self.phone_pattern.findall(str(text))
        # Clean
        phones = [phone.strip() for phone in phones]
        return list(set(phones))
    
    def extract_contact_info(self, text: str) -> Dict[str, any]:
        """
        Extract all contact information from text
        
        Args:
            text: Text containing contact info (ticket content, etc.)
            
        Returns:
            Dictionary with extracted info: {'emails': [...], 'phones': [...]}
        """
        return {
            'emails': self.extract_emails(text),
            'phones': self.extract_phones(text)
        }
    
    def find_contact_by_email(self, email: str) -> Optional[str]:
        """
        Find contact ID by email address
        
        Args:
            email: Email address to search
            
        Returns:
            Contact ID if found, None otherwise
        """
        email = str(email).strip().lower()
        return self.email_to_contact_id.get(email)
    
    def find_company_by_name(self, company_name: str) -> Optional[str]:
        """
        Find company ID by company name
        
        Args:
            company_name: Company name to search
            
        Returns:
            Company ID if found, None otherwise
        """
        name = str(company_name).strip().lower()
        return self.company_name_to_id.get(name)
    
    def enrich_tickets(self, tickets_df: pd.DataFrame) -> pd.DataFrame:
        """
        Enrich tickets with extracted contact information and associations
        
        Args:
            tickets_df: DataFrame of tickets
            
        Returns:
            Enriched DataFrame with new columns: 
            - extracted_emails
            - extracted_phones
            - associated_contact_id
            - associated_company_id
        """
        logger.info("🔄 Enriching tickets with contact information...")
        
        enriched_df = tickets_df.copy()
        
        # Initialize new columns
        enriched_df['extracted_emails'] = None
        enriched_df['extracted_phones'] = None
        enriched_df['associated_contact_id'] = None
        enriched_df['associated_company_id'] = None
        
        for idx, row in enriched_df.iterrows():
            # Extract from subject and content
            search_text = f"{row.get('subject', '')} {row.get('content', '')}"
            
            # Extract contact info
            contact_info = self.extract_contact_info(search_text)
            enriched_df.at[idx, 'extracted_emails'] = contact_info['emails']
            enriched_df.at[idx, 'extracted_phones'] = contact_info['phones']
            
            # Try to find associated contact (use first email found)
            if contact_info['emails']:
                first_email = contact_info['emails'][0]
                contact_id = self.find_contact_by_email(first_email)
                
                if contact_id:
                    enriched_df.at[idx, 'associated_contact_id'] = contact_id
                    
                    # If we found contact, try to get their company
                    if self.contacts_df is not None:
                        contact_row = self.contacts_df[self.contacts_df['id'] == contact_id]
                        if not contact_row.empty and 'company' in contact_row.columns:
                            company_name = contact_row.iloc[0]['company']
                            company_id = self.find_company_by_name(company_name)
                            if company_id:
                                enriched_df.at[idx, 'associated_company_id'] = company_id
        
        # Count associations found
        contacts_found = enriched_df['associated_contact_id'].notna().sum()
        companies_found = enriched_df['associated_company_id'].notna().sum()
        
        logger.info(f"✅ Enrichment complete:")
        logger.info(f"   - {contacts_found}/{len(enriched_df)} tickets associated with contacts")
        logger.info(f"   - {companies_found}/{len(enriched_df)} tickets associated with companies")
        
        return enriched_df
    
    def get_ticket_associations(self, enriched_tickets_df: pd.DataFrame) -> Dict[str, List[Tuple]]:
        """
        Generate association lists for HubSpot API
        
        Args:
            enriched_tickets_df: DataFrame with associated_contact_id and associated_company_id
            
        Returns:
            Dictionary with association lists:
            {
                'ticket_to_contact': [(ticket_id, contact_id), ...],
                'ticket_to_company': [(ticket_id, company_id), ...]
            }
        """
        associations = {
            'ticket_to_contact': [],
            'ticket_to_company': []
        }
        
        for idx, row in enriched_tickets_df.iterrows():
            ticket_id = row.get('id')
            
            if not ticket_id:
                continue
            
            # Ticket → Contact association
            if pd.notna(row.get('associated_contact_id')):
                associations['ticket_to_contact'].append({
                    'ticket_id': str(ticket_id),
                    'contact_id': str(row['associated_contact_id'])
                })
            
            # Ticket → Company association
            if pd.notna(row.get('associated_company_id')):
                associations['ticket_to_company'].append({
                    'ticket_id': str(ticket_id),
                    'company_id': str(row['associated_company_id'])
                })
        
        logger.info(f"📊 Associations prepared:")
        logger.info(f"   - {len(associations['ticket_to_contact'])} ticket→contact")
        logger.info(f"   - {len(associations['ticket_to_company'])} ticket→company")
        
        return associations
    
    def map_dataframe_to_hubspot(self, df: pd.DataFrame, 
                                 property_mapping: Dict[str, str]) -> List[Dict]:
        """
        Map DataFrame columns to HubSpot properties
        
        Args:
            df: DataFrame to map
            property_mapping: Dictionary mapping CSV columns to HubSpot properties
            
        Returns:
            List of dictionaries ready for HubSpot API
        """
        mapped_data = []
        
        for idx, row in df.iterrows():
            properties = {}
            
            for csv_col, hubspot_prop in property_mapping.items():
                if csv_col in df.columns:
                    value = row[csv_col]
                    
                    # Skip empty values
                    if pd.isna(value) or value == '':
                        continue
                    
                    # Convert to string for HubSpot
                    properties[hubspot_prop] = str(value)
            
            if properties:  # Only add if we have at least one property
                mapped_data.append({'properties': properties})
        
        return mapped_data
    
    def get_mapping_report(self, df: pd.DataFrame, 
                          property_mapping: Dict[str, str]) -> str:
        """
        Generate a mapping report showing what will be imported
        
        Args:
            df: DataFrame to analyze
            property_mapping: Property mapping dictionary
            
        Returns:
            Formatted report string
        """
        report = "📋 MAPPING REPORT\n"
        report += "=" * 50 + "\n\n"
        
        report += f"Total records: {len(df)}\n\n"
        
        report += "Column Mappings:\n"
        for csv_col, hubspot_prop in property_mapping.items():
            if csv_col in df.columns:
                non_empty = df[csv_col].notna().sum()
                report += f"  ✓ {csv_col:20} → {hubspot_prop:20} ({non_empty} values)\n"
            else:
                report += f"  ✗ {csv_col:20} → {hubspot_prop:20} (MISSING)\n"
        
        return report
