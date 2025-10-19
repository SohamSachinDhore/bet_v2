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
        # Simple pattern that matches numbers with any of the jodi separators
        # Multi-line pattern (traditional jodi format)
        self.jodi_pattern = re.compile(r'^([0-9\-:\|\s\n,+/]+)\s*=\s*(\d+)$', re.MULTILINE | re.DOTALL)

        # Single-line pattern for mixed entries (22-23-24=100)
        self.single_line_pattern = re.compile(r'^([0-9\-:\|\s,+/]+)\s*=\s*(\d+)$')
        
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

            # Try single-line pattern first (for mixed entries)
            single_match = self.single_line_pattern.match(input_text.strip())
            if single_match:
                return self._parse_single_line(single_match)

            # Try multi-line pattern (traditional jodi format)
            multi_match = self.jodi_pattern.match(input_text)
            if multi_match:
                return self._parse_multi_line(multi_match)

            # Try parsing as individual lines for mixed format
            return self._parse_individual_lines(input_text)

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

                # Filter to valid jodi numbers (0-99, including single digits as 00-09)
                for num in numbers:
                    if 0 <= num <= 99:  # Valid jodi range (00-99)
                        jodi_numbers.append(num)

            except Exception as e:
                self.logger.warning(f"Separator handler failed for jodi line '{line}': {e}")

                # Fallback to manual parsing with all jodi separators
                # Try different separators in order of preference
                separators_to_try = ['-', ':', '|', ' ', ',', '+', '/']
                parts = [line]  # Default to whole line

                for sep in separators_to_try:
                    if sep in line:
                        parts = line.split(sep)
                        break

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

    def _parse_single_line(self, match) -> List[JodiEntry]:
        """Parse single-line jodi format: 12/13/14/15=300"""
        numbers_text = match.group(1).strip()
        value_text = match.group(2).strip()

        # Extract jodi numbers
        jodi_numbers = self.extract_jodi_numbers(numbers_text)
        value = self.extract_value(value_text)

        if not jodi_numbers:
            raise ParseError("No valid jodi numbers found")

        if value <= 0:
            raise ParseError(f"Invalid value: {value}")

        # Create JodiEntry
        try:
            entry = JodiEntry(jodi_numbers=jodi_numbers, value=value)
            entries = [entry]
        except ValueError as e:
            raise ValidationError(f"Invalid jodi entry: {e}")

        # Validate if validator is provided
        if self.validator:
            validated_entries = self.validator.validate_entries(entries)
            self.logger.info(f"Successfully parsed and validated {len(validated_entries)} single-line jodi entries")
            return validated_entries
        else:
            self.logger.info(f"Successfully parsed {len(entries)} single-line jodi entries")
            return entries

    def _parse_multi_line(self, match) -> List[JodiEntry]:
        """Parse multi-line jodi format (traditional)"""
        numbers_text = match.group(1).strip()
        value_text = match.group(2).strip()

        # Extract jodi numbers from all lines
        jodi_numbers = self.extract_jodi_numbers(numbers_text)
        value = self.extract_value(value_text)

        if not jodi_numbers:
            raise ParseError("No valid jodi numbers found")

        if value <= 0:
            raise ParseError(f"Invalid value: {value}")

        # Create JodiEntry
        try:
            entry = JodiEntry(jodi_numbers=jodi_numbers, value=value)
            entries = [entry]
        except ValueError as e:
            raise ValidationError(f"Invalid jodi entry: {e}")

        # Validate if validator is provided
        if self.validator:
            validated_entries = self.validator.validate_entries(entries)
            self.logger.info(f"Successfully parsed and validated {len(validated_entries)} multi-line jodi entries")
            return validated_entries
        else:
            self.logger.info(f"Successfully parsed {len(entries)} multi-line jodi entries")
            return entries

    def _parse_individual_lines(self, input_text: str) -> List[JodiEntry]:
        """Parse individual lines that might be jodi format"""
        lines = [line.strip() for line in input_text.strip().split('\n') if line.strip()]
        all_entries = []

        for line in lines:
            # Try to parse each line as single jodi format
            single_match = self.single_line_pattern.match(line)
            if single_match:
                try:
                    line_entries = self._parse_single_line(single_match)
                    all_entries.extend(line_entries)
                except Exception as e:
                    self.logger.warning(f"Failed to parse jodi line '{line}': {e}")

        if not all_entries:
            raise ParseError("No valid jodi entries found in individual lines")

        self.logger.info(f"Successfully parsed {len(all_entries)} individual jodi entries")
        return all_entries
    
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