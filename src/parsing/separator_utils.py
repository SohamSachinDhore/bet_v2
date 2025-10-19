"""Unified separator handling utility for all parsers"""

import re
from typing import List, Dict, Tuple, Optional, Set
from enum import Enum


class SeparatorType(Enum):
    """Types of separators for different contexts"""
    NUMBER = "number"      # Between numbers: 128/129/120
    ASSIGNMENT = "assignment"  # Before values: =, ==
    MULTIPLICATION = "multiplication"  # For multiplication: x, *, ×


class UnifiedSeparatorHandler:
    """Centralized separator handling for all parser types"""

    # Universal separator configuration
    SEPARATOR_CONFIG = {
        'direct': {
            'primary': ['='],
            'secondary': [],
            'number_length': [1, 2, 3],  # Any single number length
            'min_numbers': 2,      # Number and value
            'max_numbers': 2,      # Only number=value format
            'format': 'NUMBER=VALUE',  # Direct assignment format
        },
        'pana': {
            'primary': ['/', '+', ',', '*', ' '],
            'secondary': ['★', '✱', '-', '|', ':'],
            'number_length': [3],  # 3-digit numbers
            'min_numbers': 2,      # At least 2 numbers
        },
        'time': {
            'primary': [' ', ',', '-'],
            'secondary': ['|', ':', '+', '/'],
            'number_length': [1, 2],  # Single and double digit numbers (0-99)
            'min_numbers': 1,      # Can be single number
        },
        'jodi': {
            'primary': ['-', ':', '|'],
            'secondary': [' ', ',', '+', '/'],
            'number_length': [2],  # 2-digit numbers
            'min_numbers': 2,      # At least 2 numbers
        },
        'multiplication': {
            'primary': ['x', '*', '×', 'X'],
            'secondary': ['⋅', '·'],
            'number_length': [2],  # 2-digit numbers
            'format': 'NUMBER[SEP]VALUE',  # Special format
        }
    }

    # All possible separators (for universal detection)
    ALL_SEPARATORS = ['=', '/', '+', ',', '*', ' ', '★', '✱', '-', '|', ':', 'x', '×', 'X', '⋅', '·']

    def __init__(self):
        """Initialize the separator handler"""
        # Create regex patterns for each separator type
        self.patterns = self._build_separator_patterns()

    def _build_separator_patterns(self) -> Dict[str, re.Pattern]:
        """Build regex patterns for separator detection"""
        patterns = {}

        # Escape special regex characters
        def escape_sep(sep):
            special_chars = ['+', '*', '|', '(', ')', '[', ']', '{', '}', '?', '.', '^', '$', '\\']
            return '\\' + sep if sep in special_chars else sep

        # Build pattern for each type
        for parser_type, config in self.SEPARATOR_CONFIG.items():
            all_seps = config['primary'] + config.get('secondary', [])
            escaped_seps = [escape_sep(sep) for sep in all_seps]

            if parser_type == 'multiplication':
                # Special pattern for multiplication - use alternation instead of character class
                seps_pattern = '|'.join(escaped_seps)
                pattern = f'(\\d{{2}})({seps_pattern})(\\d+)'
            else:
                # Standard number separation pattern - use alternation instead of character class
                seps_pattern = '|'.join(escaped_seps)
                pattern = f'\\d+({seps_pattern})'

            patterns[parser_type] = re.compile(pattern, re.IGNORECASE)

        return patterns

    def detect_separator_type(self, text: str) -> Tuple[str, List[str], float]:
        """
        Detect which parser type this text belongs to based on separators and number patterns

        Args:
            text: Input text to analyze

        Returns:
            Tuple of (parser_type, detected_separators, confidence_score)
        """
        scores = {}
        detected_separators = {}

        for parser_type, config in self.SEPARATOR_CONFIG.items():
            score, separators = self._score_parser_type(text, parser_type, config)
            scores[parser_type] = score
            detected_separators[parser_type] = separators

        # Get best match
        best_type = max(scores, key=scores.get)
        confidence = scores[best_type]

        return best_type, detected_separators[best_type], confidence

    def _score_parser_type(self, text: str, parser_type: str, config: Dict) -> Tuple[float, List[str]]:
        """Score how well text matches a parser type"""
        score = 0.0
        found_separators = []

        # Extract numbers from text
        numbers = re.findall(r'\d+', text)
        if not numbers:
            return 0.0, []

        # Special handling for assignment patterns with multiple numbers (12/13/14/15=300)
        multiple_numbers_assignment = r'^\s*\d+([^\d=]+\d+)+\s*=\s*\d+\s*$'
        is_multiple_assignment = re.match(multiple_numbers_assignment, text)

        if is_multiple_assignment:
            # For multiple number assignments, prioritize based on number lengths and separators
            if parser_type == 'pana':
                # Pana should have 3-digit numbers
                three_digit_count = sum(1 for num in numbers[:-1] if len(num) == 3)  # Exclude value
                if three_digit_count > 0:
                    score += 0.3 * (three_digit_count / (len(numbers) - 1))
            elif parser_type == 'time':
                # Time should have 1-digit numbers, but 2-digit can also be valid (like 12)
                one_digit_count = sum(1 for num in numbers[:-1] if len(num) == 1)  # Exclude value
                two_digit_count = sum(1 for num in numbers[:-1] if len(num) == 2)  # 2-digit numbers

                if one_digit_count > 0:
                    score += 0.4 * (one_digit_count / (len(numbers) - 1))
                # 2-digit numbers could be time columns (10, 11, 12 etc.) with modest boost
                elif two_digit_count > 0:
                    # Check if they look like time columns (10-19 range suggests time)
                    valid_time_nums = sum(1 for num in numbers[:-1] if len(num) == 2 and 10 <= int(num) <= 19)

                    # For small sequences with 2-digit numbers, boost time significantly
                    small_sequence_boost = 0.3 if len(numbers) <= 3 else 0.0

                    if valid_time_nums > 0:
                        score += (0.3 + small_sequence_boost) * (valid_time_nums / (len(numbers) - 1))
                    else:
                        # General 2-digit boost for time with small sequence preference
                        score += (0.2 + small_sequence_boost) * (two_digit_count / (len(numbers) - 1))
            elif parser_type == 'jodi':
                # Jodi should have 2-digit numbers with jodi separators
                two_digit_count = sum(1 for num in numbers[:-1] if len(num) == 2)  # Exclude value
                has_jodi_sep = any(sep in text for sep in ['-', ':', '|'])
                has_non_jodi_sep = any(sep in text for sep in ['/', '+', ',', '*'])

                if two_digit_count > 0 and has_jodi_sep and not has_non_jodi_sep:
                    # For small sequences (2-3 numbers), prefer time over jodi
                    if len(numbers) <= 3:  # Small sequences likely time, not jodi
                        score += 0.2 * (two_digit_count / (len(numbers) - 1))
                    else:  # Larger sequences likely jodi
                        score += 0.4 * (two_digit_count / (len(numbers) - 1))
                elif has_non_jodi_sep:
                    score -= 0.5  # Strong penalty for jodi with non-jodi separators

        # Special handling for simple direct assignment patterns (number=value)
        direct_assignment_pattern = r'^\s*\d{1,3}\s*=\s*\d+\s*$'
        is_direct_assignment = re.match(direct_assignment_pattern, text)

        if is_direct_assignment:
            # Direct assignments should generally not match multi-number patterns
            if parser_type in ['pana', 'jodi'] and len(numbers) == 2:
                # Penalize multi-number patterns for simple direct assignments
                score -= 0.5
            elif parser_type == 'time' and len(numbers) == 2:
                # Time patterns could be direct assignments
                pass  # Don't penalize
            elif parser_type == 'multiplication' and len(numbers) == 2:
                # Check if it looks like multiplication (no = between numbers)
                if 'x' not in text and '*' not in text and '×' not in text:
                    score -= 0.3  # Probably not multiplication

        # Check number length compatibility
        number_lengths = [len(num) for num in numbers]
        expected_lengths = config['number_length']

        length_match_score = 0
        for length in number_lengths:
            if length in expected_lengths:
                length_match_score += 1

        if length_match_score > 0:
            score += (length_match_score / len(numbers)) * 0.4  # 40% weight for number length

        # Check separator presence and priority
        all_seps = config['primary'] + config.get('secondary', [])
        separator_score = 0

        for i, sep in enumerate(all_seps):
            if sep in text:
                found_separators.append(sep)
                # Primary separators get higher score
                if i < len(config['primary']):
                    separator_score += 0.3  # Primary separator
                else:
                    separator_score += 0.1  # Secondary separator
                break  # Only count first found separator

        score += min(separator_score, 0.3)  # Max 30% for separator

        # Check minimum number requirement
        if len(numbers) >= config.get('min_numbers', 1):
            score += 0.2  # 20% for meeting minimum numbers

        # Special logic for specific types
        if parser_type == 'direct':
            # Direct assignments: exactly 2 numbers with = separator
            if len(numbers) == 2 and is_direct_assignment:
                score += 0.3  # Strong bonus for direct assignment pattern
            elif len(numbers) != 2:
                score -= 0.5  # Strong penalty for wrong number count
        elif parser_type == 'multiplication':
            # Must have exactly 2 numbers for multiplication
            if len(numbers) == 2:
                score += 0.1
        elif parser_type == 'pana':
            # Pana typically has multiple 3-digit numbers
            three_digit_count = sum(1 for num in numbers if len(num) == 3)
            if three_digit_count >= 2:
                score += 0.1
        elif parser_type == 'time':
            # Time typically has single digits 0-9
            single_digit_count = sum(1 for num in numbers if len(num) == 1 and int(num) <= 9)
            if single_digit_count > 0:
                score += 0.1
        elif parser_type == 'jodi':
            # Jodi typically has 2-digit numbers
            two_digit_count = sum(1 for num in numbers if len(num) == 2)
            if two_digit_count >= 2:
                score += 0.1

        return score, found_separators

    def extract_numbers_with_separators(self, text: str, parser_type: str) -> Tuple[List[int], List[str]]:
        """
        Extract numbers and separators for a specific parser type

        Args:
            text: Input text
            parser_type: Type of parser ('pana', 'time', 'jodi', 'multiplication')

        Returns:
            Tuple of (numbers_list, separators_used)
        """
        config = self.SEPARATOR_CONFIG.get(parser_type, {})
        all_seps = config.get('primary', []) + config.get('secondary', [])

        # Find all numbers
        numbers = [int(match) for match in re.findall(r'\d+', text)]

        # Find which separators are actually used
        separators_used = []
        for sep in all_seps:
            if sep in text:
                separators_used.append(sep)

        return numbers, separators_used

    def normalize_separators(self, text: str, target_separator: str = ' ') -> str:
        """
        Normalize all separators in text to a target separator

        Args:
            text: Input text with mixed separators
            target_separator: Desired separator (default: space)

        Returns:
            Text with normalized separators
        """
        normalized = text

        # Replace all known separators with target separator
        for sep in self.ALL_SEPARATORS:
            if sep != target_separator and sep in normalized:
                # Use word boundaries for single character separators to avoid conflicts
                if len(sep) == 1 and sep.isalnum():
                    pattern = f'\\b{re.escape(sep)}\\b'
                else:
                    pattern = re.escape(sep)
                normalized = re.sub(pattern, target_separator, normalized)

        # Clean up multiple consecutive separators
        normalized = re.sub(f'{re.escape(target_separator)}+', target_separator, normalized)

        return normalized.strip()

    def validate_separator_usage(self, text: str, parser_type: str) -> Tuple[bool, List[str]]:
        """
        Validate if separator usage is appropriate for parser type

        Args:
            text: Input text
            parser_type: Expected parser type

        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []

        config = self.SEPARATOR_CONFIG.get(parser_type)
        if not config:
            errors.append(f"Unknown parser type: {parser_type}")
            return False, errors

        # Extract numbers and check lengths
        numbers = re.findall(r'\d+', text)
        expected_lengths = config['number_length']

        for num in numbers:
            if len(num) not in expected_lengths:
                errors.append(f"Invalid number length for {parser_type}: {num} (expected {expected_lengths})")

        # Check minimum numbers
        min_numbers = config.get('min_numbers', 1)
        if len(numbers) < min_numbers:
            errors.append(f"Not enough numbers for {parser_type}: {len(numbers)} < {min_numbers}")

        # Check separator presence
        all_seps = config['primary'] + config.get('secondary', [])
        has_separator = any(sep in text for sep in all_seps)

        if len(numbers) > 1 and not has_separator:
            errors.append(f"Multiple numbers found but no valid separators for {parser_type}")

        return len(errors) == 0, errors

    def get_parser_examples(self, parser_type: str) -> List[str]:
        """Get example formats for a parser type"""
        examples = {
            'direct': [
                '1=100',
                '12=300',
                '119=125',
                '447=100',
                '5=25000'
            ],
            'pana': [
                '128/129/120 = 100',
                '128+129+120 = 100',
                '128,129,120 = 100',
                '128*129*120 = 100',
                '128 129 120 = 100'
            ],
            'time': [
                '1 = 100',
                '0 1 3 5 = 900',
                '1,2,3 = 300',
                '1-2-3 = 300',
                '1|2|3 = 300'
            ],
            'jodi': [
                '22-24-26 = 100',
                '22:24:26 = 100',
                '22|24|26 = 100',
                '22 24 26 = 100',
                '22,24,26 = 100'
            ],
            'multiplication': [
                '38x700',
                '38*700',
                '38×700',
                '38X700'
            ]
        }

        return examples.get(parser_type, [])

    def get_supported_separators(self, parser_type: str = None) -> Dict[str, List[str]]:
        """Get list of supported separators"""
        if parser_type:
            config = self.SEPARATOR_CONFIG.get(parser_type, {})
            return {
                'primary': config.get('primary', []),
                'secondary': config.get('secondary', [])
            }
        else:
            return {ptype: {
                'primary': config.get('primary', []),
                'secondary': config.get('secondary', [])
            } for ptype, config in self.SEPARATOR_CONFIG.items()}


# Convenience functions for easy integration
def detect_separator_type(text: str) -> Tuple[str, List[str], float]:
    """Detect separator type for given text"""
    handler = UnifiedSeparatorHandler()
    return handler.detect_separator_type(text)


def normalize_separators(text: str, target_separator: str = ' ') -> str:
    """Normalize separators in text"""
    handler = UnifiedSeparatorHandler()
    return handler.normalize_separators(text, target_separator)


def extract_numbers_universal(text: str, parser_type: str) -> Tuple[List[int], List[str]]:
    """Extract numbers with universal separator support"""
    handler = UnifiedSeparatorHandler()
    return handler.extract_numbers_with_separators(text, parser_type)