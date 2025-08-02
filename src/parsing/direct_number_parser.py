"""Direct number assignment parser for individual number=value patterns (124=400, 669=60)"""

import re
from typing import List, Optional, Dict, Any
from ..database.models import DirectNumberEntry, ValidationResult
from ..utils.error_handler import ParseError, ValidationError
from ..utils.logger import get_logger

class DirectNumberParser:
    """Direct number assignment parser for individual entries"""
    
    def __init__(self, direct_validator: Optional['DirectNumberValidator'] = None):
        self.validator = direct_validator
        self.logger = get_logger(__name__)
        
        # Regex pattern for direct number format (supports currency)
        self.pattern = re.compile(r'^\s*(\d{1,3})\s*=\s*(Rs\.{0,3}\s*\.?\s*)?(\d+)\s*$', re.IGNORECASE)
    
    def parse(self, input_text: str) -> List[DirectNumberEntry]:
        """
        Main parsing entry point for direct number format
        
        Supported formats:
        - Direct assignment: "124=400"
        - With spaces: " 4=24000"
        - Multi-line: Multiple lines with different assignments
        
        Args:
            input_text: Raw input text to parse
            
        Returns:
            List of validated DirectNumberEntry objects
            
        Raises:
            ParseError: If parsing fails
            ValidationError: If validation fails
        """
        try:
            lines = self.preprocess_input(input_text)
            entries = []
            
            for line in lines:
                line_entries = self.parse_line(line)
                
                if self.validator:
                    validated_entries = self.validator.validate_entries(line_entries)
                    entries.extend(validated_entries)
                else:
                    entries.extend(line_entries)
            
            self.logger.info(f"Successfully parsed {len(entries)} direct number entries")
            return entries
            
        except Exception as e:
            self.logger.error(f"Direct number parsing failed: {e}")
            raise ParseError(f"Failed to parse direct number input: {str(e)}")
    
    def preprocess_input(self, input_text: str) -> List[str]:
        """Clean and normalize input text"""
        if not input_text:
            raise ParseError("Input text cannot be empty")
        
        lines = input_text.strip().split('\n')
        cleaned_lines = []
        
        for line in lines:
            # Remove extra whitespace
            line = ' '.join(line.split())
            
            # Remove currency indicators (Rs, R, Rs., Rs..)
            line = self.remove_currency_indicators(line)
            
            if line:
                cleaned_lines.append(line)
        
        if not cleaned_lines:
            raise ParseError("No valid lines found after preprocessing")
        
        return cleaned_lines
    
    def remove_currency_indicators(self, line: str) -> str:
        """Remove Rs, R, Rs., Rs.. patterns including complex variations"""
        # Pattern to match currency after = including Rs..., Rs. ., etc.
        patterns = [
            r'(=\s*)(Rs\.{0,3}\s*\.?\s*)(\d+)',  # Rs..., Rs. ., Rs., Rs
            r'(=\s*)(R\s*)(\d+)',                # R 
        ]
        
        for pattern in patterns:
            line = re.sub(pattern, r'\1\3', line)
        return line
    
    def parse_line(self, line: str) -> List[DirectNumberEntry]:
        """Parse single line format: 124=400"""
        match = self.pattern.match(line)
        
        if not match:
            raise ParseError(f"Invalid direct number format in line: {line}")
        
        number_text = match.group(1).strip()
        currency_text = match.group(2) if match.group(2) else ""
        value_text = match.group(3).strip()
        
        # Extract number and value
        number = int(number_text)
        value = int(value_text)
        
        if value <= 0:
            raise ParseError(f"Invalid value: {value}")
        
        # Validate number range (1-999, allowing single digits like 4)
        if not (1 <= number <= 999):
            raise ValidationError(f"Invalid number: {number}. Must be between 1 and 999")
        
        try:
            entry = DirectNumberEntry(number=number, value=value)
            return [entry]
        except ValueError as e:
            raise ValidationError(f"Invalid direct number entry {number}={value}: {e}")
    
    def get_supported_formats(self) -> List[str]:
        """Get list of supported input formats"""
        return [
            "124=400",         # Number 124, value 400
            "147=250",         # Number 147, value 250
            "4=24000",         # Single digit 4, value 24000
            "148=600",         # Number 148, value 600
            "669=60",          # Number 669, value 60
            " 124=400",        # With leading space
            "124=400\n147=250", # Multi-line format
        ]
    
    def get_direct_number_info(self) -> Dict[str, Any]:
        """Get information about direct number parsing"""
        return {
            'number_range': '1-999',
            'value_range': 'positive integers',
            'description': 'Direct number to value assignment',
            'examples': {
                'single_digit': '4=24000 (assigns 24000 to number 4)',
                'three_digit': '124=400 (assigns 400 to number 124)',
                'multi_line': '124=400\\n147=250 (multiple assignments)'
            }
        }


class DirectNumberValidator:
    """Validates direct number entries"""
    
    def __init__(self, max_value: int = 1000000, allowed_numbers: Optional[List[int]] = None):
        """
        Initialize validator with constraints
        
        Args:
            max_value: Maximum value allowed per entry
            allowed_numbers: List of allowed numbers (None = allow all 1-999)
        """
        self.max_value = max_value
        self.allowed_numbers = set(allowed_numbers) if allowed_numbers else None
        self.logger = get_logger(__name__)
    
    def validate_entries(self, entries: List[DirectNumberEntry]) -> List[DirectNumberEntry]:
        """Validate all entries"""
        validated_entries = []
        
        for entry in entries:
            if self.is_valid_direct_number_entry(entry):
                validated_entries.append(entry)
            else:
                # Create detailed error message
                errors = self.get_validation_errors(entry)
                raise ValidationError(f"Invalid direct number entry: {', '.join(errors)}")
        
        self.logger.info(f"Validated {len(validated_entries)} direct number entries")
        return validated_entries
    
    def is_valid_direct_number_entry(self, entry: DirectNumberEntry) -> bool:
        """Check if direct number entry is valid"""
        # Check value range
        if entry.value > self.max_value:
            return False
        
        # Check if number is in allowed list (if specified)
        if self.allowed_numbers and entry.number not in self.allowed_numbers:
            return False
        
        # Check number range
        if not (1 <= entry.number <= 999):
            return False
        
        return True
    
    def get_validation_errors(self, entry: DirectNumberEntry) -> List[str]:
        """Get detailed validation errors for entry"""
        errors = []
        
        # Check value range
        if entry.value > self.max_value:
            errors.append(f"Value too large: {entry.value} > {self.max_value}")
        
        # Check if number is allowed
        if self.allowed_numbers and entry.number not in self.allowed_numbers:
            errors.append(f"Number not allowed: {entry.number}")
        
        # Check number range
        if not (1 <= entry.number <= 999):
            errors.append(f"Number out of range: {entry.number} (must be 1-999)")
        
        return errors
    
    def get_validation_stats(self) -> Dict[str, Any]:
        """Get validation statistics and configuration"""
        return {
            'max_value': self.max_value,
            'allowed_numbers_count': len(self.allowed_numbers) if self.allowed_numbers else 999,
            'number_range': '1-999',
            'total_possible_numbers': 999,
            'restricted_numbers': self.allowed_numbers is not None
        }


class DirectNumberCalculator:
    """Calculator for direct number business logic"""
    
    def __init__(self):
        self.logger = get_logger(__name__)
    
    def calculate_total_value(self, entries: List[DirectNumberEntry]) -> int:
        """Calculate total value from all entries"""
        return sum(entry.value for entry in entries)
    
    def get_number_statistics(self, entries: List[DirectNumberEntry]) -> Dict[str, Any]:
        """Get comprehensive statistics about direct number entries"""
        if not entries:
            return {
                'total_entries': 0,
                'total_value': 0,
                'unique_numbers': 0,
                'highest_value_numbers': [],
                'average_value_per_entry': 0,
                'number_distribution': {}
            }
        
        # Calculate basic stats
        total_value = sum(entry.value for entry in entries)
        number_values = {}
        
        for entry in entries:
            # Track values for each number (in case of duplicates, keep max)
            if entry.number not in number_values or entry.value > number_values[entry.number]:
                number_values[entry.number] = entry.value
        
        # Sort by value
        sorted_by_value = sorted(number_values.items(), key=lambda x: x[1], reverse=True)
        
        return {
            'total_entries': len(entries),
            'total_value': total_value,
            'unique_numbers': len(number_values),
            'highest_value_numbers': sorted_by_value[:10],
            'average_value_per_entry': total_value // len(entries),
            'number_distribution': number_values,
            'single_digit_count': len([n for n in number_values.keys() if 1 <= n <= 9]),
            'two_digit_count': len([n for n in number_values.keys() if 10 <= n <= 99]),
            'three_digit_count': len([n for n in number_values.keys() if 100 <= n <= 999])
        }