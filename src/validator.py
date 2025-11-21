"""
Data Validator Module
Validates CSV data before import to prevent API errors

FEATURES:
- Email validation (RFC 5322 compliant)
- Phone number validation (international format)
- Required field checking
- Data type validation
- Duplicate detection
- Error reporting with line numbers

USAGE:
    validator = DataValidator()
    is_valid, errors = validator.validate_contacts(df)
"""

import re
import pandas as pd
from email_validator import validate_email, EmailNotValidError
import phonenumbers
from typing import Tuple, List, Dict
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DataValidator:
    """Validates data before HubSpot import"""
    
    def __init__(self):
        """Initialize validator with regex patterns"""
        self.errors = []
        
        # Email pattern (basic check before full validation)
        self.email_pattern = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    
    def validate_email_field(self, email: str, row_index: int) -> bool:
        """
        Validate email address
        
        Args:
            email: Email address to validate
            row_index: Row number in CSV for error reporting
            
        Returns:
            bool: True if valid, False otherwise
        """
        if pd.isna(email) or not email or str(email).strip() == '':
            return False
        
        email = str(email).strip().lower()
        
        # Basic regex validation (when DNS not available)
        if not self.email_pattern.match(email):
            self.errors.append({
                'row': row_index,
                'field': 'email',
                'value': email,
                'error': 'Invalid email format'
            })
            return False
        
        try:
            # Full RFC 5322 validation (skip DNS check in demo mode)
            valid = validate_email(email, check_deliverability=False)
            return True
        except EmailNotValidError as e:
            self.errors.append({
                'row': row_index,
                'field': 'email',
                'value': email,
                'error': str(e)
            })
            return False
        except Exception:
            # Fallback to regex if DNS fails
            return True
    
    def validate_phone_field(self, phone: str, row_index: int, default_region: str = 'US') -> bool:
        """
        Validate phone number (international format)
        
        Args:
            phone: Phone number to validate
            row_index: Row number for error reporting
            default_region: Default country code if not specified
            
        Returns:
            bool: True if valid, False otherwise
        """
        if pd.isna(phone) or not phone or str(phone).strip() == '':
            return True  # Phone is optional
        
        phone = str(phone).strip()
        
        try:
            parsed = phonenumbers.parse(phone, default_region)
            is_valid = phonenumbers.is_valid_number(parsed)
            
            if not is_valid:
                self.errors.append({
                    'row': row_index,
                    'field': 'phone',
                    'value': phone,
                    'error': 'Invalid phone number format'
                })
            
            return is_valid
        except phonenumbers.NumberParseException as e:
            # If parsing fails, it might still work in HubSpot, so just warn
            logger.warning(f"Row {row_index}: Could not parse phone '{phone}': {e}")
            return True  # Don't block import for phone issues
    
    def check_required_fields(self, df: pd.DataFrame, required_fields: List[str], 
                            object_type: str) -> List[Dict]:
        """
        Check if required fields are present and not empty
        
        Args:
            df: DataFrame to check
            required_fields: List of required field names
            object_type: Type of object (for error messages)
            
        Returns:
            List of errors found
        """
        missing_errors = []
        
        for field in required_fields:
            if field not in df.columns:
                missing_errors.append({
                    'row': 'ALL',
                    'field': field,
                    'value': None,
                    'error': f'Required column "{field}" missing from CSV'
                })
            else:
                # Check for empty values in required fields
                empty_rows = df[df[field].isna() | (df[field] == '')].index.tolist()
                for row_idx in empty_rows:
                    missing_errors.append({
                        'row': row_idx + 2,  # +2 because index starts at 0 and CSV has header
                        'field': field,
                        'value': None,
                        'error': f'Required field "{field}" is empty'
                    })
        
        return missing_errors
    
    def check_duplicates(self, df: pd.DataFrame, key_field: str, 
                        object_type: str) -> List[Dict]:
        """
        Check for duplicate values in key field (like email)
        
        Args:
            df: DataFrame to check
            key_field: Field to check for duplicates (e.g., 'email')
            object_type: Type of object for error messages
            
        Returns:
            List of duplicate errors
        """
        if key_field not in df.columns:
            return []
        
        duplicate_errors = []
        duplicates = df[df.duplicated(subset=[key_field], keep=False)]
        
        if not duplicates.empty:
            for value in duplicates[key_field].unique():
                rows = df[df[key_field] == value].index.tolist()
                duplicate_errors.append({
                    'row': [r + 2 for r in rows],  # +2 for CSV row numbers
                    'field': key_field,
                    'value': value,
                    'error': f'Duplicate {key_field} found in rows: {[r + 2 for r in rows]}'
                })
        
        return duplicate_errors
    
    def validate_contacts(self, df: pd.DataFrame) -> Tuple[bool, List[Dict]]:
        """
        Validate contacts DataFrame
        
        Args:
            df: Contacts DataFrame
            
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        logger.info("🔍 Validating contacts data...")
        self.errors = []
        
        # Check required fields
        required_errors = self.check_required_fields(df, ['email'], 'contacts')
        self.errors.extend(required_errors)
        
        # Validate emails
        if 'email' in df.columns:
            for idx, email in df['email'].items():
                self.validate_email_field(email, idx + 2)
        
        # Validate phones
        if 'phone' in df.columns:
            for idx, phone in df['phone'].items():
                self.validate_phone_field(phone, idx + 2)
        
        # Check for duplicate emails
        duplicate_errors = self.check_duplicates(df, 'email', 'contacts')
        self.errors.extend(duplicate_errors)
        
        is_valid = len(self.errors) == 0
        
        if is_valid:
            logger.info(f"✅ Contacts validation passed ({len(df)} records)")
        else:
            logger.error(f"❌ Contacts validation failed ({len(self.errors)} errors)")
        
        return is_valid, self.errors.copy()
    
    def validate_companies(self, df: pd.DataFrame) -> Tuple[bool, List[Dict]]:
        """
        Validate companies DataFrame
        
        Args:
            df: Companies DataFrame
            
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        logger.info("🔍 Validating companies data...")
        self.errors = []
        
        # Check required fields
        required_errors = self.check_required_fields(df, ['name'], 'companies')
        self.errors.extend(required_errors)
        
        # Check for duplicate company names
        duplicate_errors = self.check_duplicates(df, 'name', 'companies')
        self.errors.extend(duplicate_errors)
        
        is_valid = len(self.errors) == 0
        
        if is_valid:
            logger.info(f"✅ Companies validation passed ({len(df)} records)")
        else:
            logger.error(f"❌ Companies validation failed ({len(self.errors)} errors)")
        
        return is_valid, self.errors.copy()
    
    def validate_tickets(self, df: pd.DataFrame) -> Tuple[bool, List[Dict]]:
        """
        Validate tickets DataFrame
        
        Args:
            df: Tickets DataFrame
            
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        logger.info("🔍 Validating tickets data...")
        self.errors = []
        
        # Check required fields
        required_errors = self.check_required_fields(df, ['subject'], 'tickets')
        self.errors.extend(required_errors)
        
        is_valid = len(self.errors) == 0
        
        if is_valid:
            logger.info(f"✅ Tickets validation passed ({len(df)} records)")
        else:
            logger.error(f"❌ Tickets validation failed ({len(self.errors)} errors)")
        
        return is_valid, self.errors.copy()
    
    def get_validation_summary(self) -> str:
        """
        Generate a human-readable validation summary
        
        Returns:
            Formatted string with validation results
        """
        if not self.errors:
            return "✅ All validations passed successfully!"
        
        summary = f"❌ Found {len(self.errors)} validation errors:\n\n"
        
        # Group errors by type
        error_types = {}
        for error in self.errors:
            error_type = error.get('field', 'unknown')
            if error_type not in error_types:
                error_types[error_type] = []
            error_types[error_type].append(error)
        
        for error_type, errors in error_types.items():
            summary += f"  {error_type.upper()}: {len(errors)} errors\n"
            for err in errors[:5]:  # Show first 5 of each type
                summary += f"    - Row {err['row']}: {err['error']}\n"
            if len(errors) > 5:
                summary += f"    ... and {len(errors) - 5} more\n"
        
        return summary
