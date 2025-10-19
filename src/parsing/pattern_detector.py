"""Pattern detection engine for intelligent input classification"""

import re
from enum import Enum
from typing import List, Tuple, Optional
from ..utils.logger import get_logger
from .separator_utils import UnifiedSeparatorHandler

class PatternType(Enum):
    """Input pattern type enumeration"""
    PANA_TABLE = "pana_table"
    TYPE_TABLE = "type_table"
    TIME_DIRECT = "time_direct"
    TIME_MULTIPLY = "time_multiply"
    JODI_TABLE = "jodi_table"
    DIRECT_NUMBER = "direct_number"
    MIXED = "mixed"
    UNKNOWN = "unknown"

class PatternDetector:
    """Intelligent pattern recognition for input classification with universal separator support"""

    # Enhanced regex patterns with universal separator support
    PATTERNS = {
        PatternType.TYPE_TABLE: r'(\d+)(SP|DP|CP)\s*=\s*\d+',
        PatternType.TIME_MULTIPLY: r'(\d{2})[x\*×X⋅·](\d+)',  # Enhanced multiplication symbols
        PatternType.JODI_TABLE: r'(\d{2}(-|:|,|\||\s|\/|\+)\d{2}(-|:|,|\||\s|\/|\+|\d)*=\d+)|(\d{2}(-|:|,|\||\s|\/|\+)\d{2}(-|:|,|\||\s|\/|\+|\d)*$)',  # Universal separators
        PatternType.DIRECT_NUMBER: r'^\s*(\d{1,3})\s*=\s*(Rs\.{0,3}\s*\.?\s*)?(\d+)\s*$',  # Enhanced with currency
        PatternType.PANA_TABLE: r'(\d{3}(\/|\+|\s|,|\*|★|✱|-|\||:)+.*=.*\d+)|(\d{3}\s*=\s*\d+)|(.*,\s*=.*Rs)|(^\d{3}(\/|\+|\s|,|\*|★|✱|-|\||:)+\d{3})|(^\s*=.*Rs)|(.*(\/)|(.*\+)|(.*\s)|(.*,)|(.*\*)|(.*★)|(.*✱)|(.*-)|(.*\|)|(.*:)\s*$)|(\d{3}(\/|\+|,|\*|★|✱|-|\||:|\s)+(\d{3}(\/|\+|,|\*|★|✱|-|\||:|\s)+)*\d{3}(\/|\+|,|\*|★|✱|-|\||:|\s)*$)|(^\s*=\s*\d+\s*$)',
        PatternType.TIME_DIRECT: r'^((\d|\s|,|-|\||\:|\/|\+|\*|★|✱)+)\s*={1,2}\s*(Rs\.{0,3}\s*\.?\s*)?(\d+)$',  # Universal separators
    }

    def __init__(self):
        self.logger = get_logger(__name__)
        self.separator_handler = UnifiedSeparatorHandler()
    
    def detect_pattern_type(self, line: str) -> PatternType:
        """
        Detect pattern type with universal separator support and intelligent classification

        Priority:
        1. TYPE_TABLE (highest specificity: 1SP=100)
        2. TIME_MULTIPLY (specific format: 38x700)
        3. Universal separator analysis using separator handler
        4. Fallback to number length and context analysis

        Args:
            line: Input line to analyze

        Returns:
            PatternType enum value
        """
        line = line.strip()

        if not line:
            return PatternType.UNKNOWN

        # First check TYPE_TABLE (highest priority - has unique SP/DP/CP identifiers)
        if re.search(self.PATTERNS[PatternType.TYPE_TABLE], line, re.IGNORECASE):
            self.logger.debug(f"Detected TYPE_TABLE pattern for line: {line}")
            return PatternType.TYPE_TABLE

        # Use separator handler for intelligent detection
        try:
            detected_type, separators, confidence = self.separator_handler.detect_separator_type(line)

            # Map separator handler results to PatternType
            type_mapping = {
                'direct': PatternType.DIRECT_NUMBER,
                'pana': PatternType.PANA_TABLE,
                'time': PatternType.TIME_DIRECT,
                'jodi': PatternType.JODI_TABLE,
                'multiplication': PatternType.TIME_MULTIPLY
            }

            if detected_type in type_mapping and confidence > 0.6:
                pattern_type = type_mapping[detected_type]
                self.logger.debug(f"Separator handler detected {pattern_type.value} for line: {line} (confidence: {confidence:.2f})")
                return pattern_type

        except Exception as e:
            self.logger.warning(f"Separator handler failed for line: {line}, error: {e}")

        # Fallback to enhanced number-based classification
        return self._fallback_number_classification(line)

    def _fallback_number_classification(self, line: str) -> PatternType:
        """Enhanced fallback classification using number analysis and universal separators"""

        # Extract all numbers from the line
        numbers = re.findall(r'\d+', line)
        if not numbers:
            return PatternType.UNKNOWN

        # Check for assignment pattern (has =)
        has_assignment = '=' in line

        if has_assignment:
            # Simple number=value patterns
            simple_number_pattern = r'^\s*(\d{1,4})\s*=\s*(Rs\.{0,3}\s*\.?\s*)?(\d+)\s*$'
            match = re.match(simple_number_pattern, line)

            if match:
                number = int(match.group(1))
                value = int(match.group(3))

                # Enhanced classification based on number length and value
                if len(str(number)) == 1:  # Single digit (0-9)
                    # Check for multi-column pattern with separators
                    if self._has_universal_separators(line):
                        return PatternType.TIME_DIRECT
                    # Large values suggest direct assignment, small values suggest time
                    elif value >= 10000:
                        return PatternType.DIRECT_NUMBER
                    else:
                        return PatternType.TIME_DIRECT

                elif len(str(number)) == 2:  # Two digits (10-99)
                    # Could be time, direct, or jodi
                    if self._has_universal_separators(line):
                        return PatternType.TIME_DIRECT
                    else:
                        return PatternType.DIRECT_NUMBER

                elif len(str(number)) == 3:  # Three digits (100-999)
                    # Likely direct number or pana
                    if len(numbers) == 1:
                        return PatternType.DIRECT_NUMBER
                    else:
                        return PatternType.PANA_TABLE

            # Multi-column patterns with assignment
            multi_column_pattern = r'^\s*((\d|\s|,|-|\||\:|\/|\+|\*|★|✱)+)\s*={1,2}\s*(Rs\.{0,3}\s*\.?\s*)?(\d+)\s*$'
            if re.match(multi_column_pattern, line):
                numbers_part = re.match(multi_column_pattern, line).group(1).strip()

                # Analyze the numbers part
                extracted_numbers = re.findall(r'\d+', numbers_part)
                if len(extracted_numbers) > 1:
                    # Multiple numbers - check their lengths
                    number_lengths = [len(num) for num in extracted_numbers]

                    if all(length == 1 for length in number_lengths):
                        return PatternType.TIME_DIRECT
                    elif all(length == 2 for length in number_lengths):
                        return PatternType.JODI_TABLE
                    elif all(length == 3 for length in number_lengths):
                        return PatternType.PANA_TABLE
                    else:
                        # Mixed lengths - use majority rule
                        if number_lengths.count(1) >= len(number_lengths) / 2:
                            return PatternType.TIME_DIRECT
                        elif number_lengths.count(3) >= len(number_lengths) / 2:
                            return PatternType.PANA_TABLE
                        else:
                            return PatternType.TIME_DIRECT

        else:
            # No assignment - could be number sequence or jodi
            if len(numbers) >= 2:
                number_lengths = [len(num) for num in numbers]

                if all(length == 2 for length in number_lengths):
                    return PatternType.JODI_TABLE
                elif all(length == 3 for length in number_lengths):
                    return PatternType.PANA_TABLE

        # Final regex fallback
        for pattern_type in [PatternType.JODI_TABLE, PatternType.PANA_TABLE, PatternType.TIME_DIRECT]:
            regex = self.PATTERNS[pattern_type]
            if re.search(regex, line, re.IGNORECASE):
                self.logger.debug(f"Regex fallback detected {pattern_type.value} for line: {line}")
                return pattern_type

        self.logger.warning(f"No pattern matched for line: {line}")
        return PatternType.UNKNOWN

    def _has_universal_separators(self, line: str) -> bool:
        """Check if line contains any universal separators"""
        separators = [',', '-', '|', ':', '/', '+', '*', '★', '✱']
        return any(sep in line for sep in separators)
    
    def analyze_input(self, input_text: str) -> Tuple[PatternType, List[PatternType], dict]:
        """
        Analyze entire input and return overall type and line types
        
        Args:
            input_text: Complete input text to analyze
            
        Returns:
            Tuple of (overall_pattern_type, list_of_line_patterns, analysis_stats)
        """
        lines = [line.strip() for line in input_text.strip().split('\n') if line.strip()]
        line_types = []
        pattern_counts = {}
        
        # Special check for JODI table pattern first (multi-line analysis)
        if self._is_jodi_table_format(input_text):
            return PatternType.JODI_TABLE, [PatternType.JODI_TABLE] * len(lines), {
                'total_lines': len(lines),
                'pattern_counts': {PatternType.JODI_TABLE: len(lines)},
                'unknown_lines': 0,
                'confidence': 1.0
            }
        
        # Analyze each line
        for line in lines:
            line_type = self.detect_pattern_type(line)
            line_types.append(line_type)
            
            # Count pattern occurrences
            pattern_counts[line_type] = pattern_counts.get(line_type, 0) + 1
        
        # Determine overall pattern type
        overall_type = self._determine_overall_type(pattern_counts, line_types)
        
        # Create analysis statistics
        stats = {
            'total_lines': len(lines),
            'pattern_counts': pattern_counts,
            'unknown_lines': pattern_counts.get(PatternType.UNKNOWN, 0),
            'confidence': self._calculate_confidence(pattern_counts, len(lines))
        }
        
        self.logger.info(f"Input analysis: {overall_type.value}, {len(lines)} lines, "
                        f"confidence: {stats['confidence']:.2f}")
        
        return overall_type, line_types, stats
    
    def _is_jodi_table_format(self, input_text: str) -> bool:
        """Check if input matches JODI table multi-line format"""
        lines = [line.strip() for line in input_text.strip().split('\n') if line.strip()]

        if len(lines) < 2:
            return False

        # Check for classic JODI pattern: multiple lines of hyphen-separated numbers ending with =value
        jodi_number_lines = 0
        value_line_found = False
        mixed_pattern_detected = False

        for line in lines:
            # Check if line contains hyphen-separated 2-digit numbers
            if re.match(r'^\d{2}(-\d{2})+$', line):
                jodi_number_lines += 1
            # Check if line starts with = (value line)
            elif re.match(r'^=\s*\d+$', line):
                value_line_found = True
            # Check if line ends with =value
            elif re.match(r'.*=\s*\d+$', line):
                # Extract numbers before the = sign to validate pattern
                numbers_part = line.split('=')[0].strip()
                numbers = re.findall(r'\d+', numbers_part)

                # Check if all numbers are 2-digit and uses jodi separators
                all_two_digit = all(len(num) == 2 for num in numbers)
                has_jodi_separators = any(sep in numbers_part for sep in ['-', ':', '|'])
                has_non_jodi_separators = any(sep in numbers_part for sep in ['/', '+', ',', '*'])

                # Check for 3-digit numbers (pana pattern)
                has_three_digit = any(len(num) == 3 for num in numbers)

                if all_two_digit and has_jodi_separators and not has_non_jodi_separators:
                    jodi_number_lines += 1
                    value_line_found = True
                elif has_three_digit or has_non_jodi_separators:
                    # This looks like a mixed pattern (pana, time, etc.)
                    mixed_pattern_detected = True

        # Don't classify as jodi table if mixed patterns detected
        if mixed_pattern_detected:
            return False

        # Must have at least 1 jodi number line and 1 value indicator
        return jodi_number_lines >= 1 and (value_line_found or lines[-1].startswith('='))
    
    def _determine_overall_type(self, pattern_counts: dict, line_types: List[PatternType]) -> PatternType:
        """Determine overall pattern type from line analysis"""
        
        # Remove unknown patterns from consideration
        valid_patterns = {k: v for k, v in pattern_counts.items() 
                         if k != PatternType.UNKNOWN}
        
        if not valid_patterns:
            return PatternType.UNKNOWN
        
        # If only one pattern type, return it
        if len(valid_patterns) == 1:
            return list(valid_patterns.keys())[0]
        
        # If multiple patterns, classify as MIXED
        if len(valid_patterns) > 1:
            return PatternType.MIXED
        
        # Fallback
        return PatternType.UNKNOWN
    
    def _calculate_confidence(self, pattern_counts: dict, total_lines: int) -> float:
        """Calculate confidence score for pattern detection"""
        if total_lines == 0:
            return 0.0
        
        unknown_count = pattern_counts.get(PatternType.UNKNOWN, 0)
        known_count = total_lines - unknown_count
        
        return known_count / total_lines
    
    def validate_pattern_structure(self, line: str, expected_pattern: PatternType) -> bool:
        """Validate that a line matches expected pattern structure"""
        detected_pattern = self.detect_pattern_type(line)
        return detected_pattern == expected_pattern
    
    def extract_pattern_components(self, line: str, pattern_type: PatternType) -> Optional[dict]:
        """Extract components from a line based on its pattern type"""
        
        if pattern_type == PatternType.TYPE_TABLE:
            return self._extract_type_table_components(line)
        elif pattern_type == PatternType.TIME_MULTIPLY:
            return self._extract_multiplication_components(line)
        elif pattern_type == PatternType.PANA_TABLE:
            return self._extract_pana_components(line)
        elif pattern_type == PatternType.TIME_DIRECT:
            return self._extract_time_direct_components(line)
        
        return None
    
    def _extract_type_table_components(self, line: str) -> Optional[dict]:
        """Extract components from type table format (1SP=100)"""
        match = re.search(self.PATTERNS[PatternType.TYPE_TABLE], line, re.IGNORECASE)
        if match:
            return {
                'column': int(match.group(1)),
                'table_type': match.group(2).upper(),
                'value': int(re.search(r'=\s*(\d+)', line).group(1))
            }
        return None
    
    def _extract_multiplication_components(self, line: str) -> Optional[dict]:
        """Extract components from multiplication format (38x700)"""
        match = re.search(self.PATTERNS[PatternType.TIME_MULTIPLY], line)
        if match:
            number = match.group(1)
            value = int(match.group(2))
            return {
                'number': int(number),
                'tens_digit': int(number[0]),
                'units_digit': int(number[1]),
                'value': value
            }
        return None
    
    def _extract_pana_components(self, line: str) -> Optional[dict]:
        """Extract components from pana table format (128/129=100)"""
        parts = line.split('=')
        if len(parts) != 2:
            return None
        
        numbers_part = parts[0].strip()
        value_part = parts[1].strip()
        
        # Extract numbers using different separators
        numbers = []
        separators = ['/', '+', ',', '*']
        
        for sep in separators:
            if sep in numbers_part:
                numbers = [int(n.strip()) for n in numbers_part.split(sep) 
                          if n.strip().isdigit()]
                break
        else:
            # Space-separated fallback
            numbers = [int(n) for n in numbers_part.split() if n.isdigit()]
        
        # Extract value
        value_match = re.search(r'\d+', value_part)
        value = int(value_match.group()) if value_match else 0
        
        return {
            'numbers': numbers,
            'value': value,
            'separator': sep if sep in numbers_part else ' '
        }
    
    def _extract_time_direct_components(self, line: str) -> Optional[dict]:
        """Extract components from time direct format (1 2 3=100)"""
        parts = line.split('=')
        if len(parts) != 2:
            return None
        
        columns_part = parts[0].strip()
        value_part = parts[1].strip()
        
        # Extract column numbers
        columns = [int(n) for n in columns_part.split() if n.isdigit() and 0 <= int(n) <= 9]
        
        # Extract value
        value_match = re.search(r'\d+', value_part)
        value = int(value_match.group()) if value_match else 0
        
        return {
            'columns': columns,
            'value': value
        }
    
    def get_pattern_examples(self) -> dict:
        """Get example strings for each pattern type with universal separator support"""
        return {
            PatternType.PANA_TABLE: [
                "128/129/120 = 100",    # Forward slash
                "128+129+120 = 100",    # Plus sign
                "128,129,120 = 100",    # Comma
                "128*129*120 = 100",    # Asterisk
                "128-129-120 = 100",    # Dash
                "128|129|120 = 100",    # Pipe
                "128:129:120 = 100",    # Colon
                "128 129 120 = 100",    # Space
                "128★129★120 = 100",    # Star symbols
            ],
            PatternType.TYPE_TABLE: [
                "1SP=100",
                "5DP=200",
                "15CP=300"
            ],
            PatternType.TIME_DIRECT: [
                "0 1 3 5 = 900",       # Space separated
                "0,1,3,5 = 900",       # Comma separated
                "0-1-3-5 = 900",       # Dash separated
                "0|1|3|5 = 900",       # Pipe separated
                "0:1:3:5 = 900",       # Colon separated
                "2 4 6 8 = 1200"       # Multiple digits
            ],
            PatternType.TIME_MULTIPLY: [
                "38x700",              # x
                "38*700",              # asterisk
                "38×700",              # multiplication symbol
                "38X700",              # capital X
                "05×100"               # with leading zero
            ],
            PatternType.JODI_TABLE: [
                "22-24-26 = 100",      # Dash separated
                "22:24:26 = 100",      # Colon separated
                "22|24|26 = 100",      # Pipe separated
                "22,24,26 = 100",      # Comma separated
                "22 24 26 = 100",      # Space separated
                "22/24/26 = 100",      # Forward slash
                "22+24+26 = 100"       # Plus sign
            ],
            PatternType.DIRECT_NUMBER: [
                "1=100",               # Single digit
                "12=300",              # Two digits
                "119=125",             # Three digits
                "447=100",             # Three digits
                "5=25000"              # Single digit with large value
            ]
        }

    def get_supported_separators_info(self) -> dict:
        """Get information about supported separators for each pattern type"""
        return self.separator_handler.get_supported_separators()