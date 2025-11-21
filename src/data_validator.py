"""
Data Validator & Smart Mapper
==============================

This module handles:
1. CSV data loading and validation
2. Smart column mapping (automatic detection)
3. Email/phone extraction from text fields
4. Data quality checks and recommendations

Author: Khadi97 - WBSE
"""

import re
import pandas as pd
from typing import Dict, List, Tuple, Optional
from pathlib import Path
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DataValidator:
    """
    Validates and prepares data for HubSpot import.
    
    Key Features:
    - Automatic email/phone extraction
    - Data type validation
    - Missing data detection
    - Quality score calculation
    """
    
    def __init__(self, email_regex: str, phone_regex: str):
        """
        Initialize validator with regex patterns.
        
        Args:
            email_regex: Regular expression for email validation
            phone_regex: Regular expression for phone validation
        """
        self.email_pattern = re.compile(email_regex)
        self.phone_pattern = re.compile(phone_regex)
        logger.info("✓ DataValidator initialized")
    
    def extract_email(self, text: str) -> Optional[str]:
        """
        Extract email address from text content.
        
        Args:
            text: Text to search for email
            
        Returns:
            First email found or None
            
        Example:
            >>> validator.extract_email("Contact: john@example.com for info")
            'john@example.com'
        """
        if not isinstance(text, str):
            return None
        
        matches = self.email_pattern.findall(text)
        return matches[0] if matches else None
    
    def extract_phone(self, text: str) -> Optional[str]:
        """
        Extract phone number from text content.
        
        Args:
            text: Text to search for phone
            
        Returns:
            First phone found or None
            
        Example:
            >>> validator.extract_phone("Call +33112345678 for support")
            '+33112345678'
        """
        if not isinstance(text, str):
            return None
        
        # Look for patterns like +33112345678 or Tél: +33112345678
        phone_search = re.search(r'\+?\d{10,15}', text)
        return phone_search.group(0) if phone_search else None
    
    def validate_email(self, email: str) -> bool:
        """Validate email format."""
        if not email or not isinstance(email, str):
            return False
        return bool(self.email_pattern.match(email))
    
    def validate_phone(self, phone: str) -> bool:
        """Validate phone format."""
        if not phone or not isinstance(phone, str):
            return False
        return bool(self.phone_pattern.match(phone))
    
    def load_csv(self, file_path: Path) -> pd.DataFrame:
        """
        Load CSV file with error handling.
        
        Args:
            file_path: Path to CSV file
            
        Returns:
            Pandas DataFrame
            
        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If file is empty or invalid
        """
        if not file_path.exists():
            raise FileNotFoundError(f"CSV file not found: {file_path}")
        
        try:
            df = pd.read_csv(file_path)
            logger.info(f"✓ Loaded {len(df)} rows from {file_path.name}")
            return df
        except Exception as e:
            logger.error(f"✗ Failed to load {file_path.name}: {str(e)}")
            raise ValueError(f"Invalid CSV file: {str(e)}")
    
    def validate_required_fields(self, df: pd.DataFrame, 
                                 required_fields: List[str]) -> Tuple[bool, List[str]]:
        """
        Check if all required fields are present.
        
        Args:
            df: DataFrame to validate
            required_fields: List of required column names
            
        Returns:
            (is_valid, missing_fields)
        """
        missing = [field for field in required_fields if field not in df.columns]
        
        if missing:
            logger.warning(f"⚠ Missing required fields: {', '.join(missing)}")
            return False, missing
        
        return True, []
    
    def calculate_data_quality(self, df: pd.DataFrame) -> Dict[str, any]:
        """
        Calculate data quality metrics.
        
        Returns:
            Dictionary with quality metrics:
            - completeness: % of non-null values
            - row_count: Total rows
            - column_count: Total columns
            - empty_rows: Rows with all null values
        """
        total_cells = df.shape[0] * df.shape[1]
        non_null_cells = df.count().sum()
        
        quality_score = {
            "completeness": round((non_null_cells / total_cells) * 100, 2),
            "row_count": len(df),
            "column_count": len(df.columns),
            "empty_rows": df.isnull().all(axis=1).sum(),
            "columns_with_nulls": df.isnull().any().sum()
        }
        
        logger.info(f"  Data quality: {quality_score['completeness']}% complete")
        return quality_score


class SmartMapper:
    """
    Intelligent column mapping between CSV and HubSpot properties.
    
    Features:
    - Automatic column detection
    - Fuzzy matching for similar names
    - Custom property suggestions
    """
    
    def __init__(self, property_mapping: Dict[str, str]):
        """
        Initialize mapper with predefined mappings.
        
        Args:
            property_mapping: Dict of CSV column -> HubSpot property
        """
        self.mapping = property_mapping
        logger.info(f"✓ SmartMapper initialized with {len(property_mapping)} mappings")
    
    def map_columns(self, df: pd.DataFrame) -> Dict[str, str]:
        """
        Map DataFrame columns to HubSpot properties.
        
        Args:
            df: DataFrame with CSV data
            
        Returns:
            Dictionary of actual_column -> hubspot_property
        """
        mapped = {}
        unmapped = []
        
        for csv_col in df.columns:
            # Skip ID columns (HubSpot generates these)
            if csv_col.lower() in ['id', 'hs_object_id']:
                continue
            
            # Check if column is in our mapping
            if csv_col in self.mapping:
                mapped[csv_col] = self.mapping[csv_col]
            else:
                unmapped.append(csv_col)
        
        if mapped:
            logger.info(f"  ✓ Mapped {len(mapped)} columns")
        if unmapped:
            logger.warning(f"  ⚠ Unmapped columns: {', '.join(unmapped)}")
        
        return mapped
    
    def prepare_properties(self, row: pd.Series, 
                          column_mapping: Dict[str, str]) -> Dict[str, any]:
        """
        Convert a DataFrame row to HubSpot properties format.
        
        Args:
            row: Single row from DataFrame
            column_mapping: Column to property mapping
            
        Returns:
            Dict formatted for HubSpot API
        """
        properties = {}
        
        for csv_col, hs_prop in column_mapping.items():
            value = row.get(csv_col)
            
            # Skip null/empty values
            if pd.isna(value) or value == '':
                continue
            
            # Convert to string (HubSpot expects strings)
            properties[hs_prop] = str(value)
        
        return properties


class TicketAssociationExtractor:
    """
    Specialized class for extracting contact information from ticket content.
    
    This handles the unique challenge where tickets contain embedded
    contact details (email, phone) that need to be extracted for associations.
    """
    
    def __init__(self, validator: DataValidator):
        """
        Initialize with a DataValidator instance.
        
        Args:
            validator: DataValidator for email/phone extraction
        """
        self.validator = validator
        logger.info("✓ TicketAssociationExtractor initialized")
    
    def extract_contact_info(self, ticket_content: str) -> Dict[str, str]:
        """
        Extract email and phone from ticket content.
        
        Args:
            ticket_content: Text content of ticket
            
        Returns:
            Dict with 'email' and 'phone' keys (values may be None)
            
        Example:
            Content: "Contact: john@company.com - Tel: +33123456789"
            Returns: {'email': 'john@company.com', 'phone': '+33123456789'}
        """
        if not ticket_content or not isinstance(ticket_content, str):
            return {'email': None, 'phone': None}
        
        return {
            'email': self.validator.extract_email(ticket_content),
            'phone': self.validator.extract_phone(ticket_content)
        }
    
    def enrich_tickets_with_associations(self, 
                                        tickets_df: pd.DataFrame,
                                        contacts_df: pd.DataFrame) -> pd.DataFrame:
        """
        Add contact_email and contact_phone columns to tickets DataFrame
        by extracting from ticket content.
        
        Args:
            tickets_df: DataFrame with tickets
            contacts_df: DataFrame with contacts (for validation)
            
        Returns:
            Enhanced tickets DataFrame with association columns
        """
        logger.info("Extracting contact associations from ticket content...")
        
        # Create new columns
        tickets_df['contact_email_extracted'] = None
        tickets_df['contact_phone_extracted'] = None
        
        extraction_stats = {'email_found': 0, 'phone_found': 0, 'both_found': 0}
        
        for idx, row in tickets_df.iterrows():
            content = row.get('content', '')
            contact_info = self.extract_contact_info(content)
            
            if contact_info['email']:
                tickets_df.at[idx, 'contact_email_extracted'] = contact_info['email']
                extraction_stats['email_found'] += 1
            
            if contact_info['phone']:
                tickets_df.at[idx, 'contact_phone_extracted'] = contact_info['phone']
                extraction_stats['phone_found'] += 1
            
            if contact_info['email'] and contact_info['phone']:
                extraction_stats['both_found'] += 1
        
        logger.info(f"  ✓ Extracted {extraction_stats['email_found']} emails")
        logger.info(f"  ✓ Extracted {extraction_stats['phone_found']} phones")
        logger.info(f"  ✓ Both found in {extraction_stats['both_found']} tickets")
        
        return tickets_df


# ==========================================
# USAGE EXAMPLE
# ==========================================
if __name__ == "__main__":
    """
    Demonstrate validator and mapper functionality
    """
    from config import EMAIL_REGEX, PHONE_REGEX, CSV_FILES, CONTACT_PROPERTY_MAPPING
    
    print("\n" + "="*60)
    print("DATA VALIDATOR & SMART MAPPER - Demo")
    print("="*60 + "\n")
    
    # Initialize components
    validator = DataValidator(EMAIL_REGEX, PHONE_REGEX)
    mapper = SmartMapper(CONTACT_PROPERTY_MAPPING)
    
    # Test email extraction
    test_text = "Contact: sarah.connor@skynet.com - Tel: +33123456789"
    print(f"Test text: {test_text}")
    print(f"  → Email: {validator.extract_email(test_text)}")
    print(f"  → Phone: {validator.extract_phone(test_text)}")
    
    # Load and validate contacts
    print(f"\nLoading contacts from {CSV_FILES['contacts']}...")
    contacts_df = validator.load_csv(CSV_FILES['contacts'])
    
    # Check data quality
    quality = validator.calculate_data_quality(contacts_df)
    print(f"\nData Quality Report:")
    for metric, value in quality.items():
        print(f"  {metric}: {value}")
    
    # Map columns
    print(f"\nMapping columns...")
    column_map = mapper.map_columns(contacts_df)
    print(f"Mapped columns: {len(column_map)}")
    for csv_col, hs_prop in list(column_map.items())[:5]:
        print(f"  {csv_col} → {hs_prop}")
    
    print("\n✓ Validation & Mapping demo completed successfully!")
