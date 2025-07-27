"""Pattern detection engine for intelligent input classification"""

import re
from enum import Enum
from typing import List, Tuple, Optional
from ..utils.logger import get_logger

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
    """Intelligent pattern recognition for input classification"""
    
    # Regex patterns with priority ordering (highest specificity first)
    PATTERNS = {
        PatternType.TYPE_TABLE: r'(\d+)(SP|DP|CP)\s*=\s*\d+',
        PatternType.TIME_MULTIPLY: r'(\d{2})x(\d+)',
        PatternType.JODI_TABLE: r'(\d{2}-\d{2}-.*=\d+)|(\d{2}-\d{2}-\d{2})',  # Jodi numbers with hyphens, ending in =value or just hyphen pattern
        PatternType.DIRECT_NUMBER: r'^\s*(\d{1,2})\s*=\s*\d+\s*$',  # 1-2 digit direct numbers only
        PatternType.PANA_TABLE: r'(\d{3}[\/\+\s\,\*]+.*=.*\d+)|(\d{3}\s*=\s*\d+)|(.*,\s*=.*Rs)|(^\d{3},\d{3},)|(^\s*=.*Rs)|(.*,\s*$)|(\d{3}[\/\+\,\*]+(\d{3}[\/\+\,\*]+)*\d{3}[\/\+\,\*]*$)|(^\s*=\s*\d+\s*$)',
        PatternType.TIME_DIRECT: r'^([\d\s]+)\s*={1,2}\s*\d+$',
    }
    
    def __init__(self):
        self.logger = get_logger(__name__)
    
    def detect_pattern_type(self, line: str) -> PatternType:
        
        """
        Detect pattern type with priority ordering and special logic
        
        Priority:
        1. TYPE_TABLE (highest specificity: 1SP=100)
        2. TIME_MULTIPLY (specific format: 38x700)
        3. DIRECT_NUMBER vs PANA_TABLE (special logic)
        4. TIME_DIRECT (simple format: 1 2 3=100)
        
        Args:
            line: Input line to analyze
            
        Returns:
            PatternType enum value
        """
        line = line.strip()
        
        if not line:
            return PatternType.UNKNOWN
        
        # First check TYPE_TABLE, TIME_MULTIPLY, and JODI_TABLE (highest priority)
        for pattern_type in [PatternType.TYPE_TABLE, PatternType.TIME_MULTIPLY, PatternType.JODI_TABLE]:
            regex = self.PATTERNS[pattern_type]
            if re.search(regex, line, re.IGNORECASE):
                self.logger.debug(f"Detected pattern {pattern_type.value} for line: {line}")
                return pattern_type
        
        # Special logic for TIME_DIRECT vs DIRECT_NUMBER vs PANA_TABLE
        if re.match(r'^\s*(\d{1,3})\s*=\s*\d+\s*$', line):
            # If it's a single number = value format, check context
            if re.match(r'^\s*([0-9])\s*=\s*\d+\s*$', line):
                # Single digits (0-9) are TIME_DIRECT entries
                return PatternType.TIME_DIRECT
            elif re.match(r'^\s*(\d{2})\s*=\s*\d+\s*$', line):
                # 2-digit numbers could be time or direct - need more context
                # For now, treat as DIRECT_NUMBER (pana table)
                return PatternType.DIRECT_NUMBER
            elif re.match(r'^\s*(\d{3})\s*=\s*\d+\s*$', line):
                # 3-digit numbers are DIRECT_NUMBER (pana table)
                return PatternType.DIRECT_NUMBER
        
        # Check remaining patterns
        for pattern_type in [PatternType.PANA_TABLE, PatternType.TIME_DIRECT]:
            regex = self.PATTERNS[pattern_type]
            if re.search(regex, line, re.IGNORECASE):
                self.logger.debug(f"Detected pattern {pattern_type.value} for line: {line}")
                return pattern_type
        
        self.logger.warning(f"No pattern matched for line: {line}")
        return PatternType.UNKNOWN
    
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
        """Get example strings for each pattern type"""
        return {
            PatternType.PANA_TABLE: [
                "128/129/120 = 100",
                "128+129+120 = 100", 
                "128 129 120 = 100",
                "128,129,120 = 100"
            ],
            PatternType.TYPE_TABLE: [
                "1SP=100",
                "5DP=200", 
                "15CP=300"
            ],
            PatternType.TIME_DIRECT: [
                "1=100",
                "0 1 3 5 = 900",
                "2 4 6 8 = 1200"
            ],
            PatternType.TIME_MULTIPLY: [
                "38x700",
                "83x700",
                "05x100"
            ]
        }