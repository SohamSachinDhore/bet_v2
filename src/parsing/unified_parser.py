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
        Preprocess text to combine lines where value is on next line.

        Handles cases like:
        - 5DP\n=100 → 5DP=100
        - 5DP\n100 → 5DP=100
        - 1/2/3\n=5000 → 1/2/3=5000
        - 1/2/3\n5000 → 1/2/3=5000
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
            current_line = lines[i].strip()

            # Skip empty lines
            if not current_line:
                combined_lines.append(current_line)
                i += 1
                continue

            # Check if current line has =
            if '=' in current_line:
                # Line is complete, just add it
                combined_lines.append(current_line)
                i += 1
                continue

            # Current line doesn't have =, find next non-empty line
            next_idx = i + 1
            next_line = None
            empty_lines_count = 0

            # Skip empty lines to find next non-empty line
            while next_idx < len(lines):
                potential_next = lines[next_idx].strip()
                if potential_next:
                    next_line = potential_next
                    break
                empty_lines_count += 1
                next_idx += 1

            # Check if next non-empty line starts with = or is just a number
            if next_line:
                if next_line.startswith('='):
                    # Combine: "5DP" + "=100" → "5DP=100"
                    combined_lines.append(current_line + next_line)
                    # Add empty lines we skipped
                    for _ in range(empty_lines_count):
                        combined_lines.append('')
                    i = next_idx + 1
                    continue
                elif self._is_pure_value(next_line):
                    # Combine: "5DP" + "100" → "5DP=100"
                    combined_lines.append(current_line + '=' + next_line)
                    # Add empty lines we skipped
                    for _ in range(empty_lines_count):
                        combined_lines.append('')
                    i = next_idx + 1
                    continue

            # If we reach here, current line stands alone (might be error)
            combined_lines.append(current_line)
            i += 1

        return '\n'.join(combined_lines)

    def _is_pure_value(self, text: str) -> bool:
        """
        Check if text looks like a pure value (just number, possibly with currency).

        Examples that return True:
        - "100"
        - "5000"
        - "RS 100"
        - "₹5000"
        - "5,000"

        Examples that return False:
        - "1/2/3" (contains separators)
        - "5DP" (contains letters)
        - "123-456" (multiple numbers)

        Args:
            text: Text to check

        Returns:
            True if text looks like a pure value
        """
        # Remove common currency symbols and commas
        cleaned = text.upper().replace('RS', '').replace('₹', '').replace(',', '').strip()

        # Check if remaining text is just digits (possibly with spaces)
        cleaned_no_spaces = cleaned.replace(' ', '')

        # Should be all digits and not empty
        return cleaned_no_spaces.isdigit() and len(cleaned_no_spaces) > 0

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
            'type_entries': []
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
        if not results['entries'] and not results['type_entries'] and not results['errors']:
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

        # Check if this is a type table entry (SP/DP/CP)
        type_entries = self._parse_type_table_entries(numbers_part, value)
        if type_entries:
            return type_entries

        # Otherwise, extract regular numbers
        numbers = self._extract_numbers(numbers_part)

        if not numbers:
            raise ValueError(f"No valid numbers found")

        # Create entries based on number length
        entries = []
        for number in numbers:
            entry_type = self._classify_by_length(number)
            entries.append(ParsedEntry(
                number=number,
                value=value,
                entry_type=entry_type
            ))

        return entries

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

    def _extract_numbers(self, text: str) -> List[int]:
        """
        Extract all numbers from text using separator patterns.

        Supports: 1*2*3, 1/2/3, 1-2-3, 1,2,3, 1|2|3, etc.

        Args:
            text: Text containing numbers and separators

        Returns:
            List of extracted numbers
        """
        # Split by all supported separators
        parts = re.split(self.separators_pattern, text)

        numbers = []
        for part in parts:
            part = part.strip()
            if not part:
                continue

            # Extract number (handles special notation like 1sp, 2dp)
            # For now, just extract the leading digits
            match = re.match(r'(\d+)', part)
            if match:
                num = int(match.group(1))
                numbers.append(num)

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

    def _classify_by_length(self, number: int) -> str:
        """
        Classify entry type based on number length/range.

        Rules:
        - 0-9: time table (single digit)
        - 10-99: jodi (two digits)
        - 100-999: pana (three digits)

        Args:
            number: Number to classify

        Returns:
            Entry type: 'time', 'jodi', or 'pana'

        Raises:
            ValueError: If number is out of valid range
        """
        if 0 <= number <= 9:
            return 'time'
        elif 10 <= number <= 99:
            return 'jodi'
        elif 100 <= number <= 999:
            return 'pana'
        else:
            raise ValueError(
                f"Number {number} out of valid range (0-9: time, 10-99: jodi, 100-999: pana)"
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
