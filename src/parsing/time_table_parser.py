"""Time table input parser for Type 3 patterns (1=100, 0 1 3 5 = 900) with universal separator support"""

import re
from typing import List, Optional, Dict, Any
from ..database.models import TimeEntry, ValidationResult
from ..utils.error_handler import ParseError, ValidationError
from ..utils.logger import get_logger
from .separator_utils import UnifiedSeparatorHandler

class TimeTableParser:
    """Time table input parser for direct column assignments with universal separator support"""

    def __init__(self, time_validator: Optional['TimeTableValidator'] = None):
        self.validator = time_validator
        self.logger = get_logger(__name__)
        self.separator_handler = UnifiedSeparatorHandler()

        # Enhanced regex pattern for time table format with universal separators
        self.pattern = re.compile(r'^([0-9\s\,\-\|\:\/\+\*★✱]+)\s*={1,2}\s*(Rs\.{0,3}\s*\.?\s*)?(\d+)$', re.IGNORECASE)
    
    def parse(self, input_text: str) -> List[TimeEntry]:
        """
        Main parsing entry point for time table format
        
        Supported formats:
        - Single column: "1=100"
        - Multiple columns: "0 1 3 5 = 900"
        - Multi-line: Multiple lines with different column assignments
        
        Args:
            input_text: Raw input text to parse
            
        Returns:
            List of validated TimeEntry objects
            
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
            
            self.logger.info(f"Successfully parsed {len(entries)} time table entries")
            return entries
            
        except Exception as e:
            self.logger.error(f"Time table parsing failed: {e}")
            raise ParseError(f"Failed to parse time table input: {str(e)}")
    
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
        # Pattern to match currency after = or == including Rs..., Rs. ., etc.
        patterns = [
            r'(={1,2}\s*)(Rs\.{0,3}\s*\.?\s*)(\d+)',  # Rs..., Rs. ., Rs., Rs
            r'(={1,2}\s*)(R\s*)(\d+)',                # R 
        ]
        
        for pattern in patterns:
            line = re.sub(pattern, r'\1\3', line)
        return line
    
    def parse_line(self, line: str) -> List[TimeEntry]:
        """Parse single line format with universal separator support: 0,1,3,5 = 900"""
        match = self.pattern.match(line)

        if not match:
            raise ParseError(f"Invalid time table format in line: {line}")

        columns_text = match.group(1).strip()

        # Use separator handler to extract numbers with universal separator support
        try:
            numbers, separators_used = self.separator_handler.extract_numbers_with_separators(columns_text, 'time')
            columns = [num for num in numbers if 0 <= num <= 9]  # Filter to valid time columns

            if not columns:
                # Fallback to manual parsing if separator handler doesn't work
                columns = self._extract_columns_fallback(columns_text)

        except Exception as e:
            self.logger.warning(f"Separator handler failed for time parsing: {e}")
            columns = self._extract_columns_fallback(columns_text)

        currency_text = match.group(2) if match.group(2) else ""
        value_text = match.group(3).strip()

        # Extract value
        value = self.extract_value(value_text)

        if not columns:
            raise ParseError(f"No valid columns found in: {columns_text}")
        
        if value <= 0:
            raise ParseError(f"Invalid value: {value}")
        
        # Validate all columns are in range 0-9
        for col in columns:
            if not (0 <= col <= 9):
                raise ValidationError(f"Invalid column number: {col}. Must be between 0 and 9")
        
        try:
            entry = TimeEntry(columns=columns, value=value)
            return [entry]
        except ValueError as e:
            raise ValidationError(f"Invalid time entry {columns}={value}: {e}")

    def _extract_columns_fallback(self, columns_text: str) -> List[int]:
        """Fallback method for extracting columns with universal separators"""
        # Normalize separators to spaces first
        normalized = self.separator_handler.normalize_separators(columns_text, ' ')

        # Extract column numbers
        columns = []
        for num_str in normalized.split():
            try:
                num = int(num_str)
                if 0 <= num <= 9:  # Valid time column range
                    columns.append(num)
            except ValueError:
                continue

        return columns

    def extract_columns(self, columns_text: str) -> List[int]:
        """Extract column numbers from text, handling both individual digits and numbers"""
        if not columns_text:
            return []
        
        # Handle leading/trailing spaces and normalize
        columns_text = columns_text.strip()
        
        # Split by spaces and extract digits/numbers
        parts = columns_text.split()
        columns = []
        
        for part in parts:
            part = part.strip()
            if part.isdigit():
                # Check if it's a single digit (0-9) for column or multi-digit number
                if len(part) == 1:
                    col = int(part)
                    if 0 <= col <= 9:
                        columns.append(col)
                    else:
                        raise ValidationError(f"Invalid column number: {col}. Must be between 0 and 9")
                else:
                    # Multi-digit number - treat each digit as separate column
                    for digit_char in part:
                        if digit_char.isdigit():
                            col = int(digit_char)
                            if 0 <= col <= 9:
                                columns.append(col)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_columns = []
        for col in columns:
            if col not in seen:
                seen.add(col)
                unique_columns.append(col)
        
        return unique_columns
    
    def extract_value(self, value_text: str) -> int:
        """Extract numeric value from text"""
        if not value_text:
            raise ParseError("Value text cannot be empty")
        
        # Extract first number found
        if not value_text.isdigit():
            raise ParseError(f"Invalid numeric value: {value_text}")
        
        value = int(value_text)
        if value <= 0:
            raise ParseError(f"Value must be positive: {value}")
        
        return value
    
    def get_supported_formats(self) -> List[str]:
        """Get list of supported input formats"""
        return [
            "1=100",           # Single column 1, value 100
            "0=50",            # Single column 0, value 50
            "0 1 3 5 = 900",   # Multiple columns, value 900
            "2 4 6 8 = 1200",  # Multiple columns, value 1200
            "9=75",            # Single column 9, value 75
            "1=100\n5=200",    # Multi-line format
            "0 1 2 = 300\n7 8 9 = 400"  # Multi-line with multiple columns
        ]
    
    def get_column_info(self) -> Dict[str, Any]:
        """Get information about time table columns"""
        return {
            'total_columns': 10,
            'column_range': '0-9',
            'description': 'Direct column assignment for digits 0-9',
            'examples': {
                'single_column': '1=100 (assigns 100 to column 1)',
                'multiple_columns': '0 1 3 5 = 900 (assigns 900 to columns 0,1,3,5)',
                'all_columns': '0 1 2 3 4 5 6 7 8 9 = 5000 (assigns 5000 to all columns)'
            }
        }


class TimeTableValidator:
    """Validates time table entries"""
    
    def __init__(self, max_columns_per_entry: int = 10, max_value_per_entry: int = 100000):
        """
        Initialize validator with constraints
        
        Args:
            max_columns_per_entry: Maximum number of columns per entry
            max_value_per_entry: Maximum value allowed per entry
        """
        self.max_columns_per_entry = max_columns_per_entry
        self.max_value_per_entry = max_value_per_entry
        self.logger = get_logger(__name__)
    
    def validate_entries(self, entries: List[TimeEntry]) -> List[TimeEntry]:
        """Validate all entries"""
        validated_entries = []
        
        for entry in entries:
            if self.is_valid_time_entry(entry):
                validated_entries.append(entry)
            else:
                # Create detailed error message
                errors = self.get_validation_errors(entry)
                raise ValidationError(f"Invalid time entry: {errors}")
        
        self.logger.info(f"Validated {len(validated_entries)} time entries")
        return validated_entries
    
    def is_valid_time_entry(self, entry: TimeEntry) -> bool:
        """Check if time entry is valid"""
        # Check column count
        if len(entry.columns) > self.max_columns_per_entry:
            return False
        
        # Check value range
        if entry.value > self.max_value_per_entry:
            return False
        
        # Check for valid column numbers (0-9)
        for col in entry.columns:
            if not (0 <= col <= 9):
                return False
        
        # Check for duplicate columns (should not happen after parsing, but safe check)
        if len(entry.columns) != len(set(entry.columns)):
            return False
        
        return True
    
    def get_validation_errors(self, entry: TimeEntry) -> List[str]:
        """Get detailed validation errors for entry"""
        errors = []
        
        # Check column count
        if len(entry.columns) > self.max_columns_per_entry:
            errors.append(f"Too many columns: {len(entry.columns)} > {self.max_columns_per_entry}")
        
        # Check value range
        if entry.value > self.max_value_per_entry:
            errors.append(f"Value too large: {entry.value} > {self.max_value_per_entry}")
        
        # Check for invalid column numbers
        invalid_columns = [col for col in entry.columns if not (0 <= col <= 9)]
        if invalid_columns:
            errors.append(f"Invalid column numbers: {invalid_columns}")
        
        # Check for duplicate columns
        if len(entry.columns) != len(set(entry.columns)):
            duplicates = [col for col in entry.columns if entry.columns.count(col) > 1]
            errors.append(f"Duplicate columns: {set(duplicates)}")
        
        return errors
    
    def get_validation_stats(self) -> Dict[str, Any]:
        """Get validation statistics and configuration"""
        return {
            'max_columns_per_entry': self.max_columns_per_entry,
            'max_value_per_entry': self.max_value_per_entry,
            'valid_column_range': '0-9',
            'total_possible_columns': 10
        }


class TimeTableCalculator:
    """Calculator for time table business logic"""
    
    def __init__(self):
        self.logger = get_logger(__name__)
    
    def calculate_column_distributions(self, entries: List[TimeEntry]) -> Dict[int, int]:
        """
        Calculate value distribution across columns
        
        Args:
            entries: List of TimeEntry objects
            
        Returns:
            Dictionary mapping column -> total_value
        """
        column_totals = {}
        
        for entry in entries:
            # Distribute value equally across all specified columns
            value_per_column = entry.value // len(entry.columns)
            remainder = entry.value % len(entry.columns)
            
            for i, column in enumerate(entry.columns):
                if column not in column_totals:
                    column_totals[column] = 0
                
                # Add base value
                column_totals[column] += value_per_column
                
                # Distribute remainder to first columns
                if i < remainder:
                    column_totals[column] += 1
        
        self.logger.info(f"Calculated distributions for {len(column_totals)} columns")
        return column_totals
    
    def calculate_total_value(self, entries: List[TimeEntry]) -> int:
        """Calculate total value from all entries"""
        return sum(entry.value for entry in entries)
    
    def get_column_statistics(self, entries: List[TimeEntry]) -> Dict[str, Any]:
        """Get statistical information about column usage"""
        if not entries:
            return {
                'total_entries': 0,
                'total_value': 0,
                'unique_columns_used': 0,
                'most_used_columns': [],
                'average_value_per_entry': 0
            }
        
        column_usage = {}
        total_value = 0
        
        for entry in entries:
            total_value += entry.value
            for column in entry.columns:
                column_usage[column] = column_usage.get(column, 0) + 1
        
        # Sort columns by usage frequency
        sorted_columns = sorted(column_usage.items(), key=lambda x: x[1], reverse=True)
        
        return {
            'total_entries': len(entries),
            'total_value': total_value,
            'unique_columns_used': len(column_usage),
            'most_used_columns': sorted_columns[:5],  # Top 5 most used
            'average_value_per_entry': total_value // len(entries) if entries else 0,
            'column_usage_distribution': column_usage
        }