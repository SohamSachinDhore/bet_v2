"""
Parser Adapter - Bridges UnifiedParser with existing CalculationEngine
Converts simplified parser output to ParsedInputResult format
"""

from typing import Dict, List
from .unified_parser import UnifiedParser, ParsedEntry, TypeTableEntry, FamilyPanaEntry as UnifiedFamilyPanaEntry
from ..database.models import (
    ParsedInputResult, PanaEntry, TimeEntry, JodiEntry,
    DirectNumberEntry, TypeEntry, MultiEntry, FamilyPanaEntry
)


class ParserAdapter:
    """
    Adapter to connect new UnifiedParser with existing business logic.
    Converts UnifiedParser output to ParsedInputResult format.
    """

    def __init__(self):
        self.parser = UnifiedParser()

    def parse(self, text: str) -> ParsedInputResult:
        """
        Parse input text and return ParsedInputResult compatible with CalculationEngine.

        Args:
            text: Multi-line input text

        Returns:
            ParsedInputResult with categorized entries

        Raises:
            ValueError: If parsing fails
        """
        # Parse using unified parser
        result = self.parser.parse(text)

        if not result['success']:
            error_msg = "; ".join(result['errors'])
            raise ValueError(f"Parse failed: {error_msg}")

        # Convert to ParsedInputResult format
        parsed_result = ParsedInputResult()

        # Convert time entries (1 digit → TimeEntry with columns list)
        for entry in result['time_entries']:
            time_entry = TimeEntry(
                columns=[entry.number],  # Single column as list
                value=entry.value
            )
            parsed_result.time_entries.append(time_entry)

        # Convert jodi entries (2 digits → JodiEntry with jodi_numbers list)
        for entry in result['jodi_entries']:
            jodi_entry = JodiEntry(
                jodi_numbers=[entry.number],  # Single jodi number as list
                value=entry.value
            )
            parsed_result.jodi_entries.append(jodi_entry)

        # Convert pana entries (3 digits → PanaEntry)
        for entry in result['pana_entries']:
            pana_entry = PanaEntry(
                number=entry.number,
                value=entry.value
            )
            parsed_result.pana_entries.append(pana_entry)

        # Convert type table entries (SP/DP/CP → TypeEntry)
        for entry in result['type_entries']:
            type_entry = TypeEntry(
                table_type=entry.table_type,
                column=entry.column,
                value=entry.value,
                numbers=[]  # Numbers will be expanded by CalculationEngine
            )
            parsed_result.type_entries.append(type_entry)

        # Convert family pana entries (678family → FamilyPanaEntry)
        for entry in result['family_pana_entries']:
            family_entry = FamilyPanaEntry(
                reference_number=entry.reference_number,
                value=entry.value
            )
            parsed_result.family_pana_entries.append(family_entry)

        return parsed_result

    def parse_with_validation(self, text: str) -> tuple[ParsedInputResult, List[str]]:
        """
        Parse with validation warnings.

        Args:
            text: Input text

        Returns:
            Tuple of (ParsedInputResult, warnings_list)
        """
        warnings = []

        # Parse using unified parser
        result = self.parser.parse(text)

        # Collect warnings from errors (non-fatal issues)
        if result['errors']:
            warnings.extend(result['errors'])

        # Create ParsedInputResult
        try:
            parsed_result = self.parse(text)
        except ValueError as e:
            # Return empty result with error as warning
            warnings.append(str(e))
            return ParsedInputResult(), warnings

        return parsed_result, warnings


# For backward compatibility - acts like MixedInputParser
class MixedInputParser:
    """
    Drop-in replacement for old MixedInputParser.
    Uses UnifiedParser under the hood.
    """

    def __init__(self):
        self.adapter = ParserAdapter()

    def parse(self, text: str) -> ParsedInputResult:
        """
        Parse input text (backward compatible interface).

        Args:
            text: Multi-line input text

        Returns:
            ParsedInputResult
        """
        return self.adapter.parse(text)


# TypeTableLoader - Loads SP/DP/CP tables from database
class TypeTableLoader:
    """
    Loads type tables (SP/DP/CP) from database for CalculationEngine.
    """

    def __init__(self, db_manager=None):
        self.db_manager = db_manager

    def load_all_tables(self):
        """
        Load all type tables from database.

        Returns:
            Tuple of (sp_table, dp_table, cp_table)
            Each table is a Dict[int, Set[int]] mapping column → set of pana numbers
        """
        if not self.db_manager:
            return {}, {}, {}

        sp_table = self._load_table('sp')
        dp_table = self._load_table('dp')
        cp_table = self._load_table('cp')

        return sp_table, dp_table, cp_table

    def _load_table(self, table_type: str):
        """
        Load a single type table from database.

        Args:
            table_type: 'sp', 'dp', or 'cp'

        Returns:
            Dict[int, Set[int]] mapping column → set of pana numbers
        """
        if not self.db_manager:
            return {}

        table_name = f"type_table_{table_type}"

        try:
            # Query all numbers grouped by column
            rows = self.db_manager.execute_query(
                f"SELECT column_number, number FROM {table_name} ORDER BY column_number, row_number"
            )

            # Build column → set of numbers mapping
            table = {}
            for row in rows:
                column = row[0]
                number = row[1]

                if column not in table:
                    table[column] = set()

                table[column].add(number)

            return table

        except Exception as e:
            print(f"⚠️ Warning: Failed to load {table_name}: {e}")
            return {}

    def load_table(self, table_type: str):
        """Load single table by type (for backward compatibility)"""
        return self._load_table(table_type.lower())

    def load_family_pana_table(self):
        """
        Load family pana table.

        Returns:
            Dict[int, List[int]] - {reference_number: [pana_numbers]}
        """
        try:
            # Import the actual family pana table data
            from ..data.family_pana_table import FAMILY_LOOKUP
            return FAMILY_LOOKUP
        except ImportError:
            print("⚠️ Warning: Failed to import family_pana_table module")
            # Fallback to empty dict
            return {}
