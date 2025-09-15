"""Multiplication input parser for Type 4 patterns (38x700, 83x700) with universal separator support"""

import re
from typing import List, Optional, Dict, Any
from ..database.models import MultiEntry, ValidationResult
from ..utils.error_handler import ParseError, ValidationError
from ..utils.logger import get_logger
from .separator_utils import UnifiedSeparatorHandler

class MultiplicationParser:
    """Multiplication input parser for digit-based multiplication with universal separator support"""

    def __init__(self, multiplication_validator: Optional['MultiplicationValidator'] = None):
        self.validator = multiplication_validator
        self.logger = get_logger(__name__)
        self.separator_handler = UnifiedSeparatorHandler()

        # Get supported multiplication symbols from unified handler
        separator_config = self.separator_handler.get_supported_separators('multiplication')
        all_mult_symbols = separator_config['primary'] + separator_config['secondary']
        escaped_symbols = [re.escape(sym) for sym in all_mult_symbols]

        # Enhanced regex pattern for multiplication format with universal symbols
        self.pattern = re.compile(f'(\\d{{2}})[{"".join(escaped_symbols)}](\\d+)', re.IGNORECASE)
    
    def parse(self, input_text: str) -> List[MultiEntry]:
        """
        Main parsing entry point for multiplication format
        
        Supported formats:
        - Standard: "38x700"
        - Multiple: "38x700 83x500"
        - Multi-line: Multiple lines with different multiplications
        
        Args:
            input_text: Raw input text to parse
            
        Returns:
            List of validated MultiEntry objects
            
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
            
            self.logger.info(f"Successfully parsed {len(entries)} multiplication entries")
            return entries
            
        except Exception as e:
            self.logger.error(f"Multiplication parsing failed: {e}")
            raise ParseError(f"Failed to parse multiplication input: {str(e)}")
    
    def preprocess_input(self, input_text: str) -> List[str]:
        """Clean and normalize input text"""
        if not input_text:
            raise ParseError("Input text cannot be empty")
        
        lines = input_text.strip().split('\n')
        cleaned_lines = []
        
        for line in lines:
            # Remove extra whitespace
            line = ' '.join(line.split())
            
            # Convert any multiplication symbols to 'x'
            line = self.normalize_multiplication_symbols(line)
            
            if line:
                cleaned_lines.append(line)
        
        if not cleaned_lines:
            raise ParseError("No valid lines found after preprocessing")
        
        return cleaned_lines
    
    def normalize_multiplication_symbols(self, line: str) -> str:
        """Convert various multiplication symbols to 'x'"""
        # Replace *, ×, X with x
        line = re.sub(r'[*×X]', 'x', line)
        return line
    
    def parse_line(self, line: str) -> List[MultiEntry]:
        """Parse line for multiplication patterns: 38x700"""
        matches = self.pattern.findall(line)
        
        if not matches:
            raise ParseError(f"No valid multiplication format found in line: {line}")
        
        entries = []
        for match in matches:
            number_text = match[0]
            value_text = match[1]
            
            # Extract number and value
            number = int(number_text)
            value = int(value_text)
            
            if value <= 0:
                raise ParseError(f"Invalid value: {value}")
            
            # Extract tens and units digits
            tens_digit = number // 10
            units_digit = number % 10
            
            # Validate number range (00-99)
            if not (0 <= number <= 99):
                raise ValidationError(f"Invalid number: {number}. Must be between 00 and 99")
            
            try:
                entry = MultiEntry(
                    number=number,
                    tens_digit=tens_digit,
                    units_digit=units_digit,
                    value=value
                )
                entries.append(entry)
            except ValueError as e:
                raise ValidationError(f"Invalid multiplication entry {number}x{value}: {e}")
        
        return entries
    
    def get_supported_formats(self) -> List[str]:
        """Get list of supported input formats"""
        return [
            "38x700",          # Number 38, value 700
            "83x500",          # Number 83, value 500
            "05x100",          # Number 05, value 100
            "00x50",           # Number 00, value 50
            "99x1000",         # Number 99, value 1000
            "38x700 83x500",   # Multiple on same line
            "38x700\n83x500",  # Multi-line format
            "12*600",          # Alternative multiplication symbol
            "45×800",          # Unicode multiplication symbol
            "67X400"           # Capital X multiplication symbol
        ]
    
    def get_multiplication_info(self) -> Dict[str, Any]:
        """Get information about multiplication parsing"""
        return {
            'number_range': '00-99',
            'value_range': 'positive integers',
            'tens_digit_range': '0-9',
            'units_digit_range': '0-9',
            'supported_symbols': ['x', '*', '×', 'X'],
            'description': 'Two-digit number multiplication with automatic digit extraction',
            'examples': {
                'basic': '38x700 (number 38, tens=3, units=8, value=700)',
                'leading_zero': '05x100 (number 05, tens=0, units=5, value=100)',
                'multiple': '38x700 83x500 (two multiplications on same line)'
            }
        }


class MultiplicationValidator:
    """Validates multiplication entries"""
    
    def __init__(self, max_value: int = 1000000, allowed_numbers: Optional[List[int]] = None):
        """
        Initialize validator with constraints
        
        Args:
            max_value: Maximum value allowed per entry
            allowed_numbers: List of allowed numbers (None = allow all 00-99)
        """
        self.max_value = max_value
        self.allowed_numbers = set(allowed_numbers) if allowed_numbers else None
        self.logger = get_logger(__name__)
    
    def validate_entries(self, entries: List[MultiEntry]) -> List[MultiEntry]:
        """Validate all entries"""
        validated_entries = []
        
        for entry in entries:
            if self.is_valid_multiplication_entry(entry):
                validated_entries.append(entry)
            else:
                # Create detailed error message
                errors = self.get_validation_errors(entry)
                raise ValidationError(f"Invalid multiplication entry: {', '.join(errors)}")
        
        self.logger.info(f"Validated {len(validated_entries)} multiplication entries")
        return validated_entries
    
    def is_valid_multiplication_entry(self, entry: MultiEntry) -> bool:
        """Check if multiplication entry is valid"""
        # Check value range
        if entry.value > self.max_value:
            return False
        
        # Check if number is in allowed list (if specified)
        if self.allowed_numbers and entry.number not in self.allowed_numbers:
            return False
        
        # Verify digit extraction is correct
        expected_tens = entry.number // 10
        expected_units = entry.number % 10
        
        if entry.tens_digit != expected_tens or entry.units_digit != expected_units:
            return False
        
        return True
    
    def get_validation_errors(self, entry: MultiEntry) -> List[str]:
        """Get detailed validation errors for entry"""
        errors = []
        
        # Check value range
        if entry.value > self.max_value:
            errors.append(f"Value too large: {entry.value} > {self.max_value}")
        
        # Check if number is allowed
        if self.allowed_numbers and entry.number not in self.allowed_numbers:
            errors.append(f"Number not allowed: {entry.number}")
        
        # Verify digit extraction
        expected_tens = entry.number // 10
        expected_units = entry.number % 10
        
        if entry.tens_digit != expected_tens:
            errors.append(f"Invalid tens digit: {entry.tens_digit} != {expected_tens}")
        
        if entry.units_digit != expected_units:
            errors.append(f"Invalid units digit: {entry.units_digit} != {expected_units}")
        
        return errors
    
    def get_validation_stats(self) -> Dict[str, Any]:
        """Get validation statistics and configuration"""
        return {
            'max_value': self.max_value,
            'allowed_numbers_count': len(self.allowed_numbers) if self.allowed_numbers else 100,
            'number_range': '00-99',
            'total_possible_numbers': 100,
            'restricted_numbers': self.allowed_numbers is not None
        }


class MultiplicationCalculator:
    """Calculator for multiplication business logic"""
    
    def __init__(self):
        self.logger = get_logger(__name__)
    
    def calculate_digit_distributions(self, entries: List[MultiEntry]) -> Dict[str, Dict[int, int]]:
        """
        Calculate value distribution by digit positions
        
        Args:
            entries: List of MultiEntry objects
            
        Returns:
            Dictionary with 'tens' and 'units' mappings to digit -> total_value
        """
        tens_totals = {}
        units_totals = {}
        
        for entry in entries:
            # Add to tens digit total
            if entry.tens_digit not in tens_totals:
                tens_totals[entry.tens_digit] = 0
            tens_totals[entry.tens_digit] += entry.value
            
            # Add to units digit total
            if entry.units_digit not in units_totals:
                units_totals[entry.units_digit] = 0
            units_totals[entry.units_digit] += entry.value
        
        self.logger.info(f"Calculated digit distributions for {len(entries)} entries")
        return {
            'tens': tens_totals,
            'units': units_totals
        }
    
    def calculate_number_frequencies(self, entries: List[MultiEntry]) -> Dict[int, Dict[str, Any]]:
        """Calculate frequency and value statistics for each number"""
        number_stats = {}
        
        for entry in entries:
            if entry.number not in number_stats:
                number_stats[entry.number] = {
                    'frequency': 0,
                    'total_value': 0,
                    'values': []
                }
            
            number_stats[entry.number]['frequency'] += 1
            number_stats[entry.number]['total_value'] += entry.value
            number_stats[entry.number]['values'].append(entry.value)
        
        # Calculate averages
        for number, stats in number_stats.items():
            stats['average_value'] = stats['total_value'] // stats['frequency']
            stats['min_value'] = min(stats['values'])
            stats['max_value'] = max(stats['values'])
        
        return number_stats
    
    def calculate_total_value(self, entries: List[MultiEntry]) -> int:
        """Calculate total value from all entries"""
        return sum(entry.value for entry in entries)
    
    def get_multiplication_statistics(self, entries: List[MultiEntry]) -> Dict[str, Any]:
        """Get comprehensive statistics about multiplication entries"""
        if not entries:
            return {
                'total_entries': 0,
                'total_value': 0,
                'unique_numbers': 0,
                'most_frequent_numbers': [],
                'highest_value_numbers': [],
                'average_value_per_entry': 0
            }
        
        # Calculate basic stats
        total_value = sum(entry.value for entry in entries)
        number_frequencies = {}
        number_values = {}
        
        for entry in entries:
            # Count frequencies
            number_frequencies[entry.number] = number_frequencies.get(entry.number, 0) + 1
            
            # Track max values
            if entry.number not in number_values or entry.value > number_values[entry.number]:
                number_values[entry.number] = entry.value
        
        # Sort by frequency and value
        sorted_by_frequency = sorted(number_frequencies.items(), key=lambda x: x[1], reverse=True)
        sorted_by_value = sorted(number_values.items(), key=lambda x: x[1], reverse=True)
        
        return {
            'total_entries': len(entries),
            'total_value': total_value,
            'unique_numbers': len(number_frequencies),
            'most_frequent_numbers': sorted_by_frequency[:5],
            'highest_value_numbers': sorted_by_value[:5],
            'average_value_per_entry': total_value // len(entries),
            'number_frequency_distribution': number_frequencies,
            'digit_statistics': self.calculate_digit_distributions(entries)
        }