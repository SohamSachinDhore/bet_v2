"""
Simplified Unified Parser for Rickey Mama V2
Handles three types based on number length:
- 1 digit (0-9) → time table
- 2 digits (10-99) → jodi
- 3 digits (100-999) → pana
"""

import re
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass


@dataclass
class ParsedEntry:
    """Single parsed entry with number, value, and type"""
    number: int
    value: int
    entry_type: str  # 'time', 'jodi', 'pana'

    def __repr__(self):
        return f"{self.entry_type.upper()}({self.number}={self.value})"


@dataclass
class TypeTableEntry:
    """Type table entry (SP/DP/CP)"""
    column: int
    table_type: str  # 'SP', 'DP', 'CP'
    value: int

    def __repr__(self):
        return f"{self.table_type}(col={self.column}, value={self.value})"


@dataclass
class FamilyPanaEntry:
    """Family pana entry (expands to multiple pana numbers)"""
    reference_number: int  # Pana number to lookup (e.g., 678)
    value: int

    def __repr__(self):
        return f"FAMILY({self.reference_number}={self.value})"


class UnifiedParser:
    """
    Simplified parser that classifies entries by number length.

    Supported formats:
    - 1*2*3*4=5000 (time table with asterisks)
    - 5/6/8/9=5000 (time table with slashes)
    - 12-13-14-15-16=500 (jodi with dashes)
    - 50/52/58/56/59=500 (jodi with slashes)
    - 123-234-567-589-123=500 (pana with dashes)
    - 456/489/789/458/159=500 (pana with slashes)
    - 1sp=200 (special notation - future support)

    Handles:
    - Multiple separators: *, /, -, ,, |, :, +, spaces
    - Newlines
    - Double ==
    - Currency symbols (RS, ₹)
    - Comma-formatted values (5,000)
    """

    def __init__(self):
        # All supported separators combined
        self.separators_pattern = r'[*/\-,\s|:+]+'

    def _preprocess_multiline_values(self, text: str) -> str:
        """
        Preprocess text to combine lines that are part of the same logical entry.

        Handles cases like:
        - 5DP\n=100 → 5DP=100
        - 5DP\n100 → 5DP=100
        - 1/2/3\n=5000 → 1/2/3=5000
        - 1/2/3\n5000 → 1/2/3=5000
        - 1+\n2+3=500 → 1+2+3=500
        - 1*\n2=200 → 1*2=200
        - Also handles empty lines between numbers and values

        Args:
            text: Raw input text

        Returns:
            Preprocessed text with combined lines
        """
        lines = text.split('\n')
        combined_lines = []
        i = 0

        while i < len(lines):
            current_line_raw = lines[i]
            current_line = current_line_raw.strip()

            # Skip empty lines
            if not current_line:
                combined_lines.append(current_line)
                i += 1
                continue

            # Check if current line has = (complete entry)
            if '=' in current_line:
                # Line is complete, just add it
                combined_lines.append(current_line)
                i += 1
                continue

            # Current line doesn't have =, need to combine with following lines
            # Keep combining until we find = or a pure value
            combined = current_line

            # Check if original line had trailing space (used as separator)
            had_trailing_space = current_line_raw != current_line_raw.rstrip() and current_line_raw.rstrip() == current_line

            next_idx = i + 1
            empty_lines_before_value = 0

            last_potential_value = None
            last_potential_value_idx = None

            while next_idx < len(lines):
                next_line_raw = lines[next_idx]
                next_line = next_line_raw.strip()

                # Skip empty lines but track them
                if not next_line:
                    empty_lines_before_value += 1
                    next_idx += 1
                    continue

                # Check if next line completes the entry
                if next_line.startswith('='):
                    # Found value with =: "numbers" + "=value"
                    combined += next_line
                    combined_lines.append(combined)
                    # Add back empty lines we skipped
                    for _ in range(empty_lines_before_value):
                        combined_lines.append('')
                    i = next_idx + 1
                    break
                elif self._is_pure_value(next_line):
                    # Found pure value: "numbers" + "value"
                    combined += '=' + next_line
                    combined_lines.append(combined)
                    # Add back empty lines we skipped
                    for _ in range(empty_lines_before_value):
                        combined_lines.append('')
                    i = next_idx + 1
                    break
                else:
                    # Next line is more numbers/separators, combine them
                    # But keep track of it as potential value if it's a plain number
                    if self._could_be_value(next_line):
                        last_potential_value = next_line
                        last_potential_value_idx = next_idx

                    # Add space if previous line had trailing space (space separator)
                    if had_trailing_space:
                        combined += ' '
                        had_trailing_space = False  # Reset after using

                    combined += next_line

                    # Check if this line has trailing space for next iteration
                    had_trailing_space = next_line_raw != next_line_raw.rstrip() and next_line_raw.rstrip() == next_line

                    empty_lines_before_value = 0  # Reset since we found content
                    next_idx += 1
            else:
                # Reached end of input
                # If the last thing we combined could be a value, treat it as such
                if last_potential_value and last_potential_value_idx:
                    # Remove the last potential value from combined and treat it as value
                    combined = combined[:-(len(last_potential_value))]
                    combined += '=' + last_potential_value

                combined_lines.append(combined)
                i = next_idx

        return '\n'.join(combined_lines)

    def _is_pure_value(self, text: str) -> bool:
        """
        Check if text looks like a pure value (not part of number sequence).

        Examples that return True:
        - "5000" (larger number likely a value)
        - "RS 100" (has currency)
        - "₹5000" (has currency)
        - "5,000" (has comma formatting in middle)

        Examples that return False:
        - "1" (single digit, likely part of sequence)
        - "12" (small number, could be part of sequence)
        - "2," (trailing comma, part of sequence)
        - "1/2/3" (contains separators)
        - "5DP" (contains letters)
        - "123" (could be a pana number in sequence)

        Args:
            text: Text to check

        Returns:
            True if text looks like a standalone value
        """
        # Check for currency symbols (strong indicator of value)
        has_currency = 'RS' in text.upper() or '₹' in text

        if has_currency:
            return True

        # Check for trailing comma (indicates part of sequence, not a value)
        if text.rstrip().endswith(','):
            return False

        # Check for comma formatting (e.g., "5,000")
        # Comma should be internal to the number, not at the edges
        has_comma_formatting = ',' in text and not text.startswith(',') and not text.endswith(',')

        if has_comma_formatting:
            # Verify it's actually number formatting, not separator usage
            # Remove commas and check if remaining text is digits
            cleaned_for_comma_check = text.replace(',', '').strip()
            if cleaned_for_comma_check.isdigit() and len(cleaned_for_comma_check) >= 4:
                return True

        # Remove currency and commas for further checking
        cleaned = text.upper().replace('RS', '').replace('₹', '').replace(',', '').strip()
        cleaned_no_spaces = cleaned.replace(' ', '')

        # Must be all digits
        if not cleaned_no_spaces.isdigit():
            return False

        # Empty is not a value
        if len(cleaned_no_spaces) == 0:
            return False

        # Small numbers (1-3 digits) without currency are ambiguous
        # Treat them as part of sequence, not values
        # Only 4+ digit numbers are clearly values
        if len(cleaned_no_spaces) <= 3:
            return False

        return True

    def _could_be_value(self, text: str) -> bool:
        """
        Check if text could potentially be a value at end of sequence.
        More permissive than _is_pure_value() - allows smaller numbers.

        This is used to identify potential values when we reach end of input
        without finding an explicit '=' sign. For example, in "12-13-14 500",
        "500" could be the value even though it's a small number.

        Examples that return True:
        - "500" (could be value at end)
        - "100" (could be value at end)
        - "5000" (definitely a value)
        - "5,000" (formatted with commas)

        Examples that return False:
        - "1/2/3" (contains separators, part of sequence)
        - "2," (ends with separator, part of sequence)
        - "5DP" (contains letters, not a plain number)
        - "" (empty string)

        Args:
            text: Text to check

        Returns:
            True if text could be a value at end of sequence
        """
        # Check for number separators (excluding commas which can be in values)
        # If text contains these, it's part of a sequence, not a standalone value
        separators = ['/', '-', '*', '+', ':', '|']
        for sep in separators:
            if sep in text:
                return False

        # If text ends with a comma, it's part of a sequence (e.g., "2,")
        if text.rstrip().endswith(','):
            return False

        # Remove currency and commas for validation
        cleaned = text.upper().replace('RS', '').replace('₹', '').replace(',', '').strip()
        cleaned_no_spaces = cleaned.replace(' ', '')

        # Must be all digits
        if not cleaned_no_spaces.isdigit():
            return False

        # Empty is not a value
        if len(cleaned_no_spaces) == 0:
            return False

        # Any plain number could be a value if at end of sequence
        # This is more permissive than _is_pure_value()
        return True

    def parse(self, text: str) -> Dict:
        """
        Parse input text and return categorized entries.

        Args:
            text: Multi-line input text

        Returns:
            Dictionary with:
            - success: bool
            - entries: List[ParsedEntry] (all entries)
            - time_entries: List[ParsedEntry] (1-digit)
            - jodi_entries: List[ParsedEntry] (2-digit)
            - pana_entries: List[ParsedEntry] (3-digit)
            - type_entries: List[TypeTableEntry] (SP/DP/CP)
            - errors: List[str] (error messages)
        """
        results = {
            'success': True,
            'entries': [],
            'errors': [],
            'time_entries': [],
            'jodi_entries': [],
            'pana_entries': [],
            'type_entries': [],
            'family_pana_entries': []
        }

        if not text or not text.strip():
            results['success'] = False
            results['errors'].append("Empty input")
            return results

        # Preprocess: combine lines where value is on next line
        text = self._preprocess_multiline_values(text)

        # Split by newlines
        lines = text.strip().split('\n')

        for line_num, line in enumerate(lines, 1):
            line = line.strip()

            # Skip empty lines
            if not line:
                continue

            try:
                # Parse single line
                line_results = self._parse_line(line)

                # Handle both regular entries and type table entries
                if isinstance(line_results, list):
                    # Regular entries (ParsedEntry objects)
                    for entry in line_results:
                        if isinstance(entry, TypeTableEntry):
                            results['type_entries'].append(entry)
                        elif isinstance(entry, FamilyPanaEntry):
                            results['family_pana_entries'].append(entry)
                        else:
                            results['entries'].append(entry)

                            # Categorize by type
                            if entry.entry_type == 'time':
                                results['time_entries'].append(entry)
                            elif entry.entry_type == 'jodi':
                                results['jodi_entries'].append(entry)
                            elif entry.entry_type == 'pana':
                                results['pana_entries'].append(entry)

            except Exception as e:
                error_msg = f"Line {line_num} error: {str(e)} [Input: {line[:50]}]"
                results['errors'].append(error_msg)
                results['success'] = False

        # Final success check
        if not results['entries'] and not results['type_entries'] and not results['family_pana_entries'] and not results['errors']:
            results['success'] = False
            results['errors'].append("No valid entries found")

        return results

    def _parse_line(self, line: str) -> List:
        """
        Parse a single line and return list of entries.

        Formats:
        - NUMBERS=VALUE (e.g., 1/2/3=5000)
        - TYPE_TABLE=VALUE (e.g., 1SP=200, 5DP=100, 15CP=300)

        Args:
            line: Single line of input

        Returns:
            List of ParsedEntry or TypeTableEntry objects

        Raises:
            ValueError: If line format is invalid
        """
        # Handle double == (replace with single =)
        line = line.replace('==', '=')

        # Check if line has = sign
        if '=' not in line:
            raise ValueError(f"Missing value assignment (=)")

        # Split by = to get numbers and value
        parts = line.split('=', 1)  # Only split on first =

        numbers_part = parts[0].strip()
        value_part = parts[1].strip()

        # Validate both parts exist
        if not numbers_part:
            raise ValueError("No numbers before =")
        if not value_part:
            raise ValueError("No value after =")

        # Extract value
        value = self._extract_value(value_part)

        # Check if this is a family pana entry (678family=200)
        family_entry = self._parse_family_pana_entry(numbers_part, value)
        if family_entry:
            return [family_entry]

        # Check if this is a type table entry (SP/DP/CP)
        type_entries = self._parse_type_table_entries(numbers_part, value)
        if type_entries:
            return type_entries

        # Otherwise, extract regular numbers
        number_strings = self._extract_numbers(numbers_part)

        if not number_strings:
            raise ValueError(f"No valid numbers found")

        # Create entries based on number string length
        entries = []
        for num_str in number_strings:
            entry_type, num_value = self._classify_by_length(num_str)
            entries.append(ParsedEntry(
                number=num_value,  # Store as integer
                value=value,
                entry_type=entry_type
            ))

        return entries

    def _parse_family_pana_entry(self, text: str, value: int) -> Optional[FamilyPanaEntry]:
        """
        Parse family pana entry (678family=200).

        Format: NUMBER+family
        Examples:
        - 678family (reference pana number 678 in family table)
        - 123FAMILY (case insensitive)

        Args:
            text: Text containing family pana specification
            value: Value to assign to all pana numbers in that family

        Returns:
            FamilyPanaEntry object, or None if not family format
        """
        # Pattern to match: 3-digit NUMBER + "family" (case insensitive)
        family_pattern = r'^(\d{3})(family|FAMILY|Family)$'

        match = re.match(family_pattern, text.strip())

        if not match:
            return None

        reference_number = int(match.group(1))

        # Validate it's a valid 3-digit pana number
        if not (100 <= reference_number <= 999):
            raise ValueError(f"Family pana reference must be 100-999, got: {reference_number}")

        return FamilyPanaEntry(
            reference_number=reference_number,
            value=value
        )

    def _parse_type_table_entries(self, text: str, value: int) -> Optional[List[TypeTableEntry]]:
        """
        Parse type table entries (SP/DP/DPT/CP format).

        Format: COLUMN+TYPE or multiple separated
        Examples:
        - 1SP (column 1, SP table)
        - 5DP (column 5, DP table - excludes triplets)
        - 5DPT (column 5, DP table - includes triplets)
        - 15CP (column 15, CP table)
        - 1SP/2SP/3SP (multiple columns, same type)
        - 1SP/5DP/15CP (multiple columns, different types)

        Args:
            text: Text containing type table specifications
            value: Value to assign

        Returns:
            List of TypeTableEntry objects, or None if not type table format
        """
        # Pattern to match: NUMBER + TYPE (SP/DP/DPT/CP)
        # Supports: 1SP, 2DP, 5DPT, 15CP, etc.
        # DPT must be matched before DP to avoid false match
        type_pattern = r'(\d+)(DPT|SP|DP|CP|dpt|sp|dp|cp)'

        matches = re.findall(type_pattern, text, re.IGNORECASE)

        if not matches:
            return None

        entries = []
        for column_str, table_type in matches:
            column = int(column_str)
            table_type = table_type.upper()  # Normalize to uppercase

            # Validate column ranges
            if table_type == 'SP' and not (1 <= column <= 10):
                raise ValueError(f"SP column must be 1-10, got: {column}")
            elif table_type in ['DP', 'DPT'] and not (1 <= column <= 10):
                raise ValueError(f"{table_type} column must be 1-10, got: {column}")
            elif table_type == 'CP' and not ((11 <= column <= 99) or column == 0):
                raise ValueError(f"CP column must be 0 or 11-99, got: {column}")

            entries.append(TypeTableEntry(
                column=column,
                table_type=table_type,
                value=value
            ))

        return entries if entries else None

    def _extract_numbers(self, text: str) -> List[str]:
        """
        Extract all numbers from text using separator patterns.
        Returns numbers as strings to preserve leading zeros (e.g., "05" for jodi).

        Supports: 1*2*3, 1/2/3, 1-2-3, 1,2,3, 1|2|3, etc.

        Args:
            text: Text containing numbers and separators

        Returns:
            List of extracted number strings (preserves leading zeros)
        """
        # Split by all supported separators
        parts = re.split(self.separators_pattern, text)

        numbers = []
        for part in parts:
            part = part.strip()
            if not part:
                continue

            # Extract number string (handles special notation like 1sp, 2dp)
            # Keep as string to preserve leading zeros
            match = re.match(r'(\d+)', part)
            if match:
                num_str = match.group(1)
                numbers.append(num_str)

        return numbers

    def _extract_value(self, text: str) -> int:
        """
        Extract numeric value from text.

        Handles:
        - Plain numbers: 5000
        - Currency: RS 5000, ₹5000
        - Comma-formatted: 5,000
        - With text: RS,, 400

        Args:
            text: Text containing value

        Returns:
            Extracted integer value

        Raises:
            ValueError: If no numeric value found
        """
        # Remove common currency symbols and text
        cleaned = text.upper()
        cleaned = cleaned.replace('RS', '')
        cleaned = cleaned.replace('₹', '')
        cleaned = cleaned.replace(',', '')
        cleaned = cleaned.strip()

        # Extract first continuous number
        match = re.search(r'\d+', cleaned)
        if match:
            value = int(match.group(0))
            if value < 0:
                raise ValueError(f"Negative value not allowed: {value}")
            return value

        raise ValueError(f"No numeric value found in: {text}")

    def _classify_by_length(self, num_str: str) -> tuple[str, int]:
        """
        Classify entry type based on number string length (preserves leading zeros).

        Rules:
        - 1 digit string: time table (e.g., "5" → time)
        - 2 digit string: jodi (e.g., "05", "12" → jodi)
        - 3 digit string: pana (e.g., "100", "005" → pana)

        Args:
            num_str: Number as string (preserves leading zeros)

        Returns:
            Tuple of (entry_type, numeric_value)
            - entry_type: 'time', 'jodi', or 'pana'
            - numeric_value: Integer value of the number

        Raises:
            ValueError: If number string length is invalid
        """
        length = len(num_str)
        num_value = int(num_str)

        if length == 1:
            # Single digit: time table (0-9)
            if not (0 <= num_value <= 9):
                raise ValueError(f"Invalid time number: {num_str} (must be 0-9)")
            return 'time', num_value
        elif length == 2:
            # Two digits: jodi (00-99)
            if not (0 <= num_value <= 99):
                raise ValueError(f"Invalid jodi number: {num_str} (must be 00-99)")
            return 'jodi', num_value
        elif length == 3:
            # Three digits: pana (000-999)
            if not (0 <= num_value <= 999):
                raise ValueError(f"Invalid pana number: {num_str} (must be 000-999)")
            return 'pana', num_value
        else:
            raise ValueError(
                f"Invalid number length: {num_str} (must be 1, 2, or 3 digits)"
            )

    def parse_with_type_hint(self, text: str, expected_type: Optional[str] = None) -> Dict:
        """
        Parse with optional type hint for validation.

        Args:
            text: Input text
            expected_type: Expected entry type ('time', 'jodi', 'pana')

        Returns:
            Parse results with type validation
        """
        results = self.parse(text)

        if expected_type and results['success']:
            # Validate all entries match expected type
            for entry in results['entries']:
                if entry.entry_type != expected_type:
                    results['errors'].append(
                        f"Type mismatch: expected {expected_type}, got {entry.entry_type} "
                        f"for number {entry.number}"
                    )
                    results['success'] = False

        return results


# Example usage and testing
if __name__ == '__main__':
    parser = UnifiedParser()

    # Test cases
    test_inputs = [
        "1*2*3*4=5000",           # time table with *
        "5/6/8/9=5000",           # time table with /
        "12-13-14-15-16=500",     # jodi with -
        "50/52/58/56/59=500",     # jodi with /
        "123-234-567-589=500",    # pana with -
        "456/489/789/458/159=500", # pana with /
        "1SP=200",                 # SP type table
        "5DP=100",                 # DP type table (excludes triplets)
        "5DPT=100",                # DPT type table (includes triplets)
        "15CP=300",                # CP type table
        "1SP/2SP/3SP=150",        # Multiple SP columns
        "1==200",                  # double ==
        "5,6,7=RS 1000",          # comma separator with RS
        "100/200/300=5,000",      # comma in value
    ]

    print("Unified Parser Test Results:")
    print("=" * 60)

    for test_input in test_inputs:
        print(f"\nInput: {test_input}")
        result = parser.parse(test_input)

        if result['success']:
            total = len(result['entries']) + len(result['type_entries'])
            print(f"  ✓ Success: {total} total entries")

            if result['entries']:
                print(f"    Regular entries ({len(result['entries'])}):")
                for entry in result['entries'][:5]:  # Show first 5
                    print(f"      - {entry}")

            if result['type_entries']:
                print(f"    Type table entries ({len(result['type_entries'])}):")
                for entry in result['type_entries']:
                    print(f"      - {entry}")
        else:
            print(f"  ✗ Failed")
            for error in result['errors']:
                print(f"    - {error}")
