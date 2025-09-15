"""Jodi table input parser for jodi number patterns with universal separator support"""

import re
from typing import List, Optional
from ..database.models import JodiEntry
from ..utils.error_handler import ParseError, ValidationError
from ..utils.logger import get_logger
from .separator_utils import UnifiedSeparatorHandler

class JodiTableParser:
    """Jodi table input parser for multi-line jodi number assignments with universal separator support"""

    def __init__(self, jodi_validator: Optional['JodiValidator'] = None):
        self.validator = jodi_validator
        self.logger = get_logger(__name__)
        self.separator_handler = UnifiedSeparatorHandler()

        # Get supported separators from unified handler
        separator_config = self.separator_handler.get_supported_separators('jodi')
        all_jodi_seps = separator_config['primary'] + separator_config['secondary']
        escaped_seps = [re.escape(sep) for sep in all_jodi_seps]

        # Enhanced pattern for jodi format with universal separators
        separator_pattern = f'[{"".join(escaped_seps)}]'
        self.jodi_pattern = re.compile(f'^([0-9{separator_pattern}\\s\\n]+)\\s*=\\s*(\\d+)$', re.MULTILINE | re.DOTALL)
        
    def parse(self, input_text: str) -> List[JodiEntry]:
        """
        Main parsing entry point for jodi table format
        
        Supported formats:
        - Multi-line with shared value:
          22-24-26-28-20
          42-44-46-48-40
          66-68-60-62-64
          88-80-82-84-86
          00-02-04-06-08=500
        
        Args:
            input_text: Raw input text to parse
            
        Returns:
            List of validated JodiEntry objects
            
        Raises:
            ParseError: If parsing fails
            ValidationError: If validation fails
        """
        try:
            # Preprocess input
            input_text = self.preprocess_input(input_text)
            
            # Match the jodi pattern
            match = self.jodi_pattern.match(input_text)
            if not match:
                raise ParseError(f"Invalid jodi format. Expected format: jodi numbers on separate lines ending with =value")
            
            numbers_text = match.group(1).strip()
            value_text = match.group(2).strip()
            
            # Extract jodi numbers from all lines
            jodi_numbers = self.extract_jodi_numbers(numbers_text)
            value = self.extract_value(value_text)
            
            if not jodi_numbers:
                raise ParseError("No valid jodi numbers found")
            
            if value <= 0:
                raise ParseError(f"Invalid value: {value}")
            
            # Create single JodiEntry with all numbers
            try:
                entry = JodiEntry(jodi_numbers=jodi_numbers, value=value)
                entries = [entry]
            except ValueError as e:
                raise ValidationError(f"Invalid jodi entry: {e}")
            
            # Validate if validator is provided
            if self.validator:
                validated_entries = self.validator.validate_entries(entries)
                self.logger.info(f"Successfully parsed and validated {len(validated_entries)} jodi entries")
                return validated_entries
            else:
                self.logger.info(f"Successfully parsed {len(entries)} jodi entries")
                return entries
            
        except Exception as e:
            self.logger.error(f"Jodi table parsing failed: {e}")
            raise ParseError(f"Failed to parse jodi table input: {str(e)}")
    
    def preprocess_input(self, input_text: str) -> str:
        """Clean and normalize input text"""
        if not input_text:
            raise ParseError("Input text cannot be empty")
        
        # Remove extra whitespace but preserve line breaks
        lines = input_text.strip().split('\n')
        cleaned_lines = []
        
        for line in lines:
            line = line.strip()
            if line:
                cleaned_lines.append(line)
        
        if not cleaned_lines:
            raise ParseError("No valid lines found after preprocessing")
        
        return '\n'.join(cleaned_lines)
    
    def extract_jodi_numbers(self, numbers_text: str) -> List[int]:
        """Extract jodi numbers from multi-line text with universal separator support"""
        jodi_numbers = []

        # Split by lines and process each line
        lines = numbers_text.split('\n')

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Use separator handler for universal separator support
            try:
                numbers, separators_used = self.separator_handler.extract_numbers_with_separators(line, 'jodi')

                # Filter to valid 2-digit jodi numbers
                for num in numbers:
                    if 10 <= num <= 99:  # Valid 2-digit jodi range
                        jodi_numbers.append(num)

            except Exception as e:
                self.logger.warning(f"Separator handler failed for jodi line '{line}': {e}")

                # Fallback to manual parsing with dash separator
                parts = line.split('-')

                for part in parts:
                    part = part.strip()
                    if part.isdigit():
                        jodi_num = int(part)

                        # Validate jodi number range (00-99)
                        if 0 <= jodi_num <= 99:
                            jodi_numbers.append(jodi_num)
                        else:
                            raise ParseError(f"Invalid jodi number: {jodi_num}. Must be between 00 and 99")
        
        # Remove duplicates while preserving order
        seen = set()
        unique_numbers = []
        for num in jodi_numbers:
            if num not in seen:
                seen.add(num)
                unique_numbers.append(num)
        
        return unique_numbers
    
    def extract_value(self, value_text: str) -> int:
        """Extract numeric value from text"""
        if not value_text:
            raise ParseError("Value text cannot be empty")
        
        if not value_text.isdigit():
            raise ParseError(f"Invalid numeric value: {value_text}")
        
        value = int(value_text)
        if value <= 0:
            raise ParseError(f"Value must be positive: {value}")
        
        return value
    
    def get_supported_formats(self) -> List[str]:
        """Get list of supported input formats"""
        return [
            "22-24-26-28-20\\n42-44-46-48-40\\n66-68-60-62-64\\n88-80-82-84-86\\n00-02-04-06-08=500",
            "Multi-line jodi numbers with shared value at the end"
        ]
    
    def get_jodi_info(self) -> dict:
        """Get information about jodi table structure"""
        return {
            'jodi_range': '00-99',
            'format': 'Multi-line jodi numbers separated by hyphens, ending with =value',
            'example': '22-24-26-28-20\\n42-44-46-48-40=500',
            'description': 'Each jodi number gets the full value (not split)',
            'total_calculation': 'total_numbers × value'
        }


class JodiValidator:
    """Validates jodi table entries"""
    
    def __init__(self, max_jodi_numbers_per_entry: int = 100, max_value_per_entry: int = 100000):
        """
        Initialize validator with constraints
        
        Args:
            max_jodi_numbers_per_entry: Maximum number of jodi numbers per entry
            max_value_per_entry: Maximum value allowed per entry
        """
        self.max_jodi_numbers_per_entry = max_jodi_numbers_per_entry
        self.max_value_per_entry = max_value_per_entry
        self.logger = get_logger(__name__)
    
    def validate_entries(self, entries: List[JodiEntry]) -> List[JodiEntry]:
        """Validate all entries"""
        validated_entries = []
        
        for entry in entries:
            if self.is_valid_jodi_entry(entry):
                validated_entries.append(entry)
            else:
                # Create detailed error message
                errors = self.get_validation_errors(entry)
                raise ValidationError(f"Invalid jodi entry: {errors}")
        
        self.logger.info(f"Validated {len(validated_entries)} jodi entries")
        return validated_entries
    
    def is_valid_jodi_entry(self, entry: JodiEntry) -> bool:
        """Check if jodi entry is valid"""
        # Check jodi numbers count
        if len(entry.jodi_numbers) > self.max_jodi_numbers_per_entry:
            return False
        
        # Check value range
        if entry.value > self.max_value_per_entry:
            return False
        
        # Check for valid jodi numbers (00-99)
        for jodi_num in entry.jodi_numbers:
            if not (0 <= jodi_num <= 99):
                return False
        
        # Check for duplicate jodi numbers (should not happen after parsing, but safe check)
        if len(entry.jodi_numbers) != len(set(entry.jodi_numbers)):
            return False
        
        return True
    
    def get_validation_errors(self, entry: JodiEntry) -> List[str]:
        """Get detailed validation errors for entry"""
        errors = []
        
        # Check jodi numbers count
        if len(entry.jodi_numbers) > self.max_jodi_numbers_per_entry:
            errors.append(f"Too many jodi numbers: {len(entry.jodi_numbers)} > {self.max_jodi_numbers_per_entry}")
        
        # Check value range
        if entry.value > self.max_value_per_entry:
            errors.append(f"Value too large: {entry.value} > {self.max_value_per_entry}")
        
        # Check for invalid jodi numbers
        invalid_numbers = [num for num in entry.jodi_numbers if not (0 <= num <= 99)]
        if invalid_numbers:
            errors.append(f"Invalid jodi numbers: {invalid_numbers}")
        
        # Check for duplicate jodi numbers
        if len(entry.jodi_numbers) != len(set(entry.jodi_numbers)):
            duplicates = [num for num in entry.jodi_numbers if entry.jodi_numbers.count(num) > 1]
            errors.append(f"Duplicate jodi numbers: {set(duplicates)}")
        
        return errors
    
    def get_validation_stats(self) -> dict:
        """Get validation statistics and configuration"""
        return {
            'max_jodi_numbers_per_entry': self.max_jodi_numbers_per_entry,
            'max_value_per_entry': self.max_value_per_entry,
            'valid_jodi_range': '00-99',
            'total_possible_jodi_numbers': 100
        }