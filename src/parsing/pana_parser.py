"""Improved Pana table input parser for Type 1 patterns (128/129/120 = 100) with universal separator support"""

import re
from typing import List, Set, Optional
from ..database.models import PanaEntry, ValidationResult
from ..utils.error_handler import ParseError, ValidationError
from ..utils.logger import get_logger
from .separator_utils import UnifiedSeparatorHandler

class PanaTableParser:
    """Improved Pana table input parser with universal separator support"""

    def __init__(self, pana_validator: Optional['PanaValidator'] = None):
        self.validator = pana_validator
        self.separator_handler = UnifiedSeparatorHandler()
        self.logger = get_logger(__name__)

        # Get supported separators from unified handler
        separator_config = self.separator_handler.get_supported_separators('pana')
        self.separators = separator_config['primary'] + separator_config['secondary']
        
        # Improved patterns for complex PANA formats
        self.pana_patterns = [
            r'^\d{3}[+\/\*\,\s]+(\d{3}[+\/\*\,\s]+)*\d{3}[+\/\*\,\s]*$',  # Number combinations
            r'^\s*=\s*(RS?\.{0,3}\s*[\,\.\s]*)*\d+\s*$',                    # Result assignments
            r'^\d{3}\s*=\s*\d+$',                                          # Direct PANA assignments
            r'^\d{3}[+\/\*\,\s]+.*$',                                      # PANA number lines
        ]
        
    def parse(self, input_text: str) -> List[PanaEntry]:
        """
        Main parsing entry point for pana table format with improved handling
        
        Supported formats:
        - Single line: "128/129/120 = 100"
        - Multi-line: Multiple lines with shared or individual values
        - Complex formats: "138+347+230+349+269+" with "=RS,, 400"
        - Mixed separators: /, +, space, comma, *
        
        Args:
            input_text: Raw input text to parse
            
        Returns:
            List of validated PanaEntry objects
            
        Raises:
            ParseError: If parsing fails
            ValidationError: If validation fails
        """
        try:
            lines = self.preprocess_input(input_text)
            entries = []
            
            for line_group in self.group_multiline_entries_robust(lines):
                parsed_group = self.parse_line_group(line_group)
                if self.validator:
                    validated_group = self.validator.validate_entries(parsed_group)
                    entries.extend(validated_group)
                else:
                    entries.extend(parsed_group)
            
            if not entries:
                raise ParseError("No valid pana entries found")
            
            self.logger.info(f"Successfully parsed {len(entries)} pana entries")
            return entries
            
        except Exception as e:
            error_msg = f"Failed to parse pana input: {str(e)}"
            self.logger.error(error_msg)
            raise ParseError(error_msg)
    
    def preprocess_input(self, input_text: str) -> List[str]:
        """Clean and prepare input for parsing"""
        lines = input_text.strip().split('\n')
        processed_lines = []
        
        for line in lines:
            line = line.strip()
            if line:  # Keep non-empty lines
                processed_lines.append(line)
            else:
                # Keep empty lines for grouping logic
                processed_lines.append('')
        
        return processed_lines
    
    def group_multiline_entries_robust(self, lines: List[str]) -> List[List[str]]:
        """
        Enhanced grouping for multi-line PANA entries
        
        Handles complex patterns like:
        138+347+230+349+269+
        =RS,, 400
        
        369+378+270+578+590+
        128+380+129+670+580+
        =150
        """
        groups = []
        current_group = []
        
        for line in lines:
            line = line.strip()
            
            if not line:
                # Empty line - potential group separator
                if current_group:
                    # If we have accumulated lines, this might be end of group
                    # Check if current group has a value, if not keep accumulating
                    has_value = any('=' in l for l in current_group)
                    if has_value:
                        groups.append(current_group)
                        current_group = []
                continue
                
            if line.startswith('='):
                # Result line - completes current group
                if current_group:
                    current_group.append(line)
                    groups.append(current_group)
                    current_group = []
                else:
                    # Standalone result line - treat as single entry
                    groups.append([line])
            else:
                # Number line or regular line
                if self.is_pana_number_line(line):
                    current_group.append(line)
                elif '=' in line:
                    # Line with embedded value
                    current_group.append(line)
                    groups.append(current_group)
                    current_group = []
                else:
                    # Other line types
                    current_group.append(line)
        
        # Handle any remaining group
        if current_group:
            groups.append(current_group)
            
        return [group for group in groups if group]  # Remove empty groups
    
    def is_pana_number_line(self, line: str) -> bool:
        """Check if line contains PANA numbers"""
        # Look for 3-digit numbers with separators
        pattern = r'\d{3}[+\/\*\,\s]*'
        matches = re.findall(pattern, line)
        
        # Check if we have multiple 3-digit numbers
        numbers = re.findall(r'\d{3}', line)
        return len(numbers) >= 1 and not line.startswith('=')
    
    def parse_line_group(self, line_group: List[str]) -> List[PanaEntry]:
        """Parse a group of related lines"""
        if len(line_group) == 1:
            return self.parse_single_line(line_group[0])
        else:
            return self.parse_multiline_group(line_group)
    
    def parse_single_line(self, line: str) -> List[PanaEntry]:
        """Parse single line format: 128/129/120 = 100"""
        if '=' not in line:
            raise ParseError(f"Invalid format, missing '=' in line: {line}")
            
        parts = line.split('=')
        if len(parts) != 2:
            raise ParseError(f"Invalid format, multiple '=' in line: {line}")
        
        numbers_part = parts[0].strip()
        value_part = parts[1].strip()
        
        # Extract numbers and value
        numbers = self.extract_numbers(numbers_part)
        value = self.extract_value_robust(value_part)
        
        if not numbers:
            raise ParseError(f"No valid numbers found in: {numbers_part}")
        
        # Create entries
        entries = []
        for number in numbers:
            entry = PanaEntry(number=number, value=value)
            entries.append(entry)
        
        return entries
    
    def parse_multiline_group(self, line_group: List[str]) -> List[PanaEntry]:
        """Parse multi-line group with enhanced logic"""
        all_numbers = []
        value = None
        
        for line in line_group:
            if line.startswith('='):
                # Value line
                value = self.extract_value_robust(line)
            elif '=' in line:
                # Split line with numbers and value
                parts = line.split('=')
                numbers = self.extract_numbers(parts[0].strip())
                value = self.extract_value_robust(parts[1].strip())
                all_numbers.extend(numbers)
            else:
                # Numbers only line
                numbers = self.extract_numbers(line)
                all_numbers.extend(numbers)
        
        if not all_numbers:
            raise ParseError("No valid numbers found in number lines")
        
        if value is None:
            raise ParseError("No value found in group")
        
        # Create entries
        entries = []
        for number in all_numbers:
            entry = PanaEntry(number=number, value=value)
            entries.append(entry)
        
        return entries
    
    def extract_numbers(self, numbers_text: str) -> List[int]:
        """Extract 3-digit pana numbers from text using universal separator support"""
        if not numbers_text:
            return []

        # Use separator handler for intelligent extraction
        try:
            numbers, separators_used = self.separator_handler.extract_numbers_with_separators(numbers_text, 'pana')

            # Filter to valid 3-digit pana numbers
            valid_numbers = []
            for num in numbers:
                if 100 <= num <= 999:  # Valid 3-digit number range
                    valid_numbers.append(num)

            if valid_numbers:
                return valid_numbers

        except Exception as e:
            self.logger.warning(f"Separator handler failed for pana parsing: {e}")

        # Fallback to regex extraction
        numbers = re.findall(r'\d{3}', numbers_text)

        # Convert to integers and validate
        valid_numbers = []
        for num_str in numbers:
            try:
                num = int(num_str)
                if 100 <= num <= 999:  # Valid 3-digit number range
                    valid_numbers.append(num)
            except ValueError:
                continue

        return valid_numbers
    
    def extract_value_robust(self, value_text: str) -> int:
        """
        Enhanced value extraction handling complex formats like:
        - 'RS,, 400'
        - '= RS,60' 
        - '=150'
        - 'RS. 100'
        """
        if not value_text:
            raise ParseError("Value text cannot be empty")
        
        # Remove various currency indicators and formatting
        cleaned = value_text.strip()
        
        # Remove common currency patterns (case insensitive)
        currency_patterns = [
            r'RS\.{0,3}\s*[\,\.\s]*',   # RS..., RS. ., RS, etc.
            r'R\s*[\,\.\s]*',           # R with optional spacing/punctuation
            r'₹\s*',                     # Rupee symbol
            r'=\s*',                     # Equals sign at start
        ]
        
        for pattern in currency_patterns:
            cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)
        
        # Remove extra commas, dots, spaces but preserve the number
        cleaned = re.sub(r'[\,\.\s]+', ' ', cleaned).strip()
        
        # Extract all numbers and take the first valid one
        numbers = re.findall(r'\d+', cleaned)
        if not numbers:
            raise ParseError(f"No numeric value found in: '{value_text}'")
        
        value = int(numbers[0])
        if value <= 0:
            raise ParseError(f"Value must be positive: {value}")
        
        return value

    def get_supported_formats(self) -> List[str]:
        """Get list of supported input formats"""
        return [
            "128/129/120 = 100",                    # Standard format
            "138+347+230+349+269+",                # Number combinations
            "=RS,, 400",                           # Complex value format
            "= RS,60",                             # Spaced value format
            "128★129★120 = 100",                   # Unicode separators
            "128\n129\n120\n= 100",              # Multiline format
            "138+347+230+349+269+\n=RS,, 400",   # Complex multiline
        ]


class PanaValidator:
    """Validates pana table entries against reference table"""
    
    def __init__(self, pana_reference_table: Set[int]):
        self.valid_numbers = pana_reference_table
        self.logger = get_logger(__name__)
        
    def validate_entries(self, entries: List[PanaEntry]) -> List[PanaEntry]:
        """Validate all entries against pana table"""
        if not self.valid_numbers:
            self.logger.warning("No pana reference numbers available, skipping validation")
            return entries
            
        valid_entries = []
        for entry in entries:
            if entry.number in self.valid_numbers:
                valid_entries.append(entry)
            else:
                self.logger.warning(f"Invalid pana number: {entry.number}")
                
        if not valid_entries and entries:
            raise ValidationError("No valid pana numbers found")
            
        return valid_entries
