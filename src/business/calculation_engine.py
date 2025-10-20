"""Calculation Engine for RickyMama business logic and calculations"""

from typing import Dict, List, Any, Optional, Set, Tuple
from datetime import date
from dataclasses import dataclass, field
from ..database.models import (
    ParsedInputResult, PanaEntry, TypeTableEntry, 
    TimeEntry, MultiEntry, UniversalLogEntry, EntryType
)
from ..utils.logger import get_logger
from ..utils.error_handler import CalculationError

@dataclass
class CalculationContext:
    """Context for calculation operations"""
    customer_id: int
    customer_name: str
    entry_date: date
    bazar: str
    source_data: ParsedInputResult
    
@dataclass
class CalculationResult:
    """Calculation result with type breakdown - matches specification"""
    pana_total: int = 0
    type_total: int = 0
    time_total: int = 0
    multi_total: int = 0
    direct_total: int = 0
    jodi_total: int = 0
    grand_total: int = 0
    calculation_details: Dict[str, Any] = field(default_factory=dict)

@dataclass
class BusinessCalculation:
    """Business calculation result with detailed breakdown"""
    grand_total: int
    bazar_total: int
    pana_total: int = 0
    type_total: int = 0
    time_total: int = 0
    multi_total: int = 0
    direct_total: int = 0
    jodi_total: int = 0
    breakdown: Dict[str, Any] = field(default_factory=dict)
    universal_entries: List[UniversalLogEntry] = field(default_factory=list)


class CalculationEngine:
    """Core calculation engine for all business logic"""

    def __init__(self, sp_table: Dict[int, Set[int]] = None,
                 dp_table: Dict[int, Set[int]] = None,
                 cp_table: Dict[int, Set[int]] = None):
        """
        Initialize calculation engine with type table references

        Args:
            sp_table: SP table mapping {column: {valid_numbers}}
            dp_table: DP table mapping {column: {valid_numbers}}
            cp_table: CP table mapping {column: {valid_numbers}}
        """
        self.sp_table = sp_table or {}
        self.dp_table = dp_table or {}
        self.cp_table = cp_table or {}
        self.logger = get_logger(__name__)

    @staticmethod
    def _is_triplet(number: int) -> bool:
        """
        Check if a 3-digit pana number is a triplet (all digits same).

        Triplets: 111, 222, 333, 444, 555, 666, 777, 888, 999, 000

        Args:
            number: 3-digit pana number

        Returns:
            True if all three digits are the same
        """
        # Convert to 3-digit string with leading zeros
        num_str = str(number).zfill(3)

        # Check if all digits are the same
        return num_str[0] == num_str[1] == num_str[2]
    
    def calculate_total(self, parsed_entries: ParsedInputResult) -> CalculationResult:
        """
        Master total calculation for mixed input types - matches specification interface
        Returns: CalculationResult with breakdown by type
        """
        result = CalculationResult()
        
        # Calculate each type separately
        result.pana_total = self.calculate_pana_total(parsed_entries.pana_entries or [])
        result.type_total = self.calculate_type_total(parsed_entries.type_entries or [])
        result.time_total = self.calculate_time_total(parsed_entries.time_entries or [])
        result.multi_total = self.calculate_multi_total(parsed_entries.multi_entries or [])
        result.direct_total = self.calculate_direct_total(getattr(parsed_entries, 'direct_entries', []) or [])
        result.jodi_total = self.calculate_jodi_total(getattr(parsed_entries, 'jodi_entries', []) or [])
        
        # Calculate grand total
        result.grand_total = (
            result.pana_total + 
            result.type_total + 
            result.time_total + 
            result.multi_total + 
            result.direct_total + 
            result.jodi_total
        )
        
        return result
    
    def calculate(self, context: CalculationContext) -> BusinessCalculation:
        """
        Main calculation entry point
        
        Processes all parsed entries and generates comprehensive business calculations
        
        Args:
            context: Calculation context with customer, date, bazar info
            
        Returns:
            BusinessCalculation with complete results and universal log entries
            
        Raises:
            CalculationError: If calculation fails
        """
        try:
            result = context.source_data
            calculation = BusinessCalculation(grand_total=0, bazar_total=0)
            
            # Process each entry type
            if result.pana_entries:
                pana_calc = self._calculate_pana_entries(context, result.pana_entries)
                calculation.pana_total = pana_calc['total']
                calculation.breakdown['pana'] = pana_calc
                calculation.universal_entries.extend(pana_calc['universal_entries'])
            
            if result.type_entries:
                type_calc = self._calculate_type_entries(context, result.type_entries)
                calculation.type_total = type_calc['total']
                calculation.breakdown['type'] = type_calc
                calculation.universal_entries.extend(type_calc['universal_entries'])
            
            if result.time_entries:
                time_calc = self._calculate_time_entries(context, result.time_entries)
                calculation.time_total = time_calc['total']
                calculation.breakdown['time'] = time_calc
                calculation.universal_entries.extend(time_calc['universal_entries'])
            
            if result.multi_entries:
                multi_calc = self._calculate_multi_entries(context, result.multi_entries)
                calculation.multi_total = multi_calc['total']
                calculation.breakdown['multi'] = multi_calc
                calculation.universal_entries.extend(multi_calc['universal_entries'])
            
            # Add support for direct entries
            if hasattr(result, 'direct_entries') and result.direct_entries:
                direct_calc = self._calculate_direct_entries(context, result.direct_entries)
                calculation.direct_total = direct_calc['total']
                calculation.breakdown['direct'] = direct_calc
                calculation.universal_entries.extend(direct_calc['universal_entries'])
            else:
                calculation.direct_total = 0
            
            # Add support for jodi entries
            if hasattr(result, 'jodi_entries') and result.jodi_entries:
                jodi_calc = self._calculate_jodi_entries(context, result.jodi_entries)
                calculation.jodi_total = jodi_calc['total']
                calculation.breakdown['jodi'] = jodi_calc
                calculation.universal_entries.extend(jodi_calc['universal_entries'])
            else:
                calculation.jodi_total = 0
            
            # Calculate totals
            calculation.bazar_total = (calculation.pana_total + calculation.type_total + 
                                    calculation.time_total + calculation.multi_total + 
                                    calculation.direct_total + calculation.jodi_total)
            calculation.grand_total = calculation.bazar_total
            
            # Add summary to breakdown
            calculation.breakdown['summary'] = {
                'total_entries': len(calculation.universal_entries),
                'grand_total': calculation.grand_total,
                'bazar_total': calculation.bazar_total,
                'entry_type_totals': {
                    'pana': calculation.pana_total,
                    'type': calculation.type_total,
                    'time': calculation.time_total,
                    'multi': calculation.multi_total,
                    'direct': calculation.direct_total,
                    'jodi': calculation.jodi_total
                }
            }
            
            self.logger.info(f"Calculation complete: {calculation.grand_total} total, "
                           f"{len(calculation.universal_entries)} entries")
            
            return calculation
            
        except Exception as e:
            self.logger.error(f"Calculation failed: {e}")
            raise CalculationError(f"Failed to calculate business logic: {str(e)}")
    
    def _calculate_pana_entries(self, context: CalculationContext, 
                               entries: List[PanaEntry]) -> Dict[str, Any]:
        """Calculate pana table entries"""
        total = 0
        universal_entries = []
        entry_details = []
        
        for entry in entries:
            # Direct value assignment for pana entries
            total += entry.value
            
            # Create universal log entry
            universal_entry = UniversalLogEntry(
                customer_id=context.customer_id,
                customer_name=context.customer_name,
                entry_date=context.entry_date,
                bazar=context.bazar,
                number=entry.number,
                value=entry.value,
                entry_type=EntryType.PANA,
                source_line=f"{entry.number}={entry.value}"
            )
            universal_entries.append(universal_entry)
            
            entry_details.append({
                'number': entry.number,
                'value': entry.value,
                'type': 'direct_pana'
            })
        
        return {
            'total': total,
            'entry_count': len(entries),
            'universal_entries': universal_entries,
            'details': entry_details,
            'calculation_method': 'direct_value_assignment'
        }
    
    def _calculate_type_entries(self, context: CalculationContext, 
                               entries: List[TypeTableEntry]) -> Dict[str, Any]:
        """Calculate type table entries by expanding numbers from tables"""
        total = 0
        universal_entries = []
        entry_details = []
        
        for entry in entries:
            # Get numbers from appropriate table
            if entry.table_type == 'SP':
                numbers = self.sp_table.get(entry.column, set())
            elif entry.table_type in ['DP', 'DPT']:
                numbers = self.dp_table.get(entry.column, set())

                # DP excludes triplets, DPT includes them
                if entry.table_type == 'DP':
                    # Filter out triplets (111, 222, 333, etc.)
                    numbers = {num for num in numbers if not self._is_triplet(num)}
                    self.logger.debug(f"DP column {entry.column}: Excluded triplets, {len(numbers)} numbers remain")
                # DPT keeps all numbers including triplets (no filtering needed)

            elif entry.table_type == 'CP':
                numbers = self.cp_table.get(entry.column, set())
            else:
                numbers = set()

            if not numbers:
                self.logger.warning(f"No numbers found for {entry.table_type} column {entry.column}")
                continue
            
            # Create universal entries for each number in the table
            entry_total = 0
            for number in numbers:
                total += entry.value
                entry_total += entry.value
                
                universal_entry = UniversalLogEntry(
                    customer_id=context.customer_id,
                    customer_name=context.customer_name,
                    entry_date=context.entry_date,
                    bazar=context.bazar,
                    number=number,
                    value=entry.value,
                    entry_type=EntryType.TYPE,
                    source_line=f"{entry.column}{entry.table_type}={entry.value}"
                )
                universal_entries.append(universal_entry)
            
            entry_details.append({
                'column': entry.column,
                'table_type': entry.table_type,
                'value_per_number': entry.value,
                'numbers_count': len(numbers),
                'total_value': entry_total,
                'numbers': sorted(list(numbers))
            })
        
        return {
            'total': total,
            'entry_count': len(entries),
            'universal_entries': universal_entries,
            'details': entry_details,
            'calculation_method': 'table_expansion'
        }
    
    def _calculate_time_entries(self, context: CalculationContext, 
                               entries: List[TimeEntry]) -> Dict[str, Any]:
        """Calculate time table entries by multiplying value by number of columns"""
        total = 0
        universal_entries = []
        entry_details = []
        
        for entry in entries:
            # Multiply value by number of columns for total calculation
            entry_total = entry.value * len(entry.columns)
            total += entry_total  # Add to running total
            
            # Each column gets the FULL value (not split across columns)
            # For 6 8 9 0==3300, each column (6,8,9,0) gets full 3300
            column_distributions = {}
            
            for column in entry.columns:
                # Each column gets the full value
                column_value = entry.value
                column_distributions[column] = column_value
                
                # Create universal entry for this column
                universal_entry = UniversalLogEntry(
                    customer_id=context.customer_id,
                    customer_name=context.customer_name,
                    entry_date=context.entry_date,
                    bazar=context.bazar,
                    number=column,  # Column number (0-9)
                    value=column_value,
                    entry_type=EntryType.TIME_DIRECT,
                    source_line=f"{' '.join(map(str, entry.columns))}={entry.value}"
                )
                universal_entries.append(universal_entry)
            
            entry_details.append({
                'columns': entry.columns,
                'input_value': entry.value,
                'multiplier': len(entry.columns),
                'total_value': entry_total,  # value × number_of_columns
                'value_per_column': entry.value,  # Full value per column
                'column_distributions': column_distributions,
                'calculation': f"{entry.value} × {len(entry.columns)} = {entry_total} (each column gets full {entry.value})"
            })
        
        return {
            'total': total,
            'entry_count': len(entries),
            'universal_entries': universal_entries,
            'details': entry_details,
            'calculation_method': 'column_distribution'
        }
    
    def _calculate_multi_entries(self, context: CalculationContext, 
                                entries: List[MultiEntry]) -> Dict[str, Any]:
        """Calculate multiplication entries by applying values to digit positions and jodi table"""
        total = 0
        universal_entries = []
        entry_details = []
        
        for entry in entries:
            # Each entry contributes its multiplication value (not doubled)
            total += entry.value  # Fixed: single value contribution per specification
            
            # Create universal entries for tens digit
            tens_universal = UniversalLogEntry(
                customer_id=context.customer_id,
                customer_name=context.customer_name,
                entry_date=context.entry_date,
                bazar=context.bazar,
                number=entry.tens_digit,
                value=entry.value,
                entry_type=EntryType.TIME_MULTI,
                source_line=f"{entry.number:02d}x{entry.value}"
            )
            universal_entries.append(tens_universal)
            
            # Create universal entries for units digit
            units_universal = UniversalLogEntry(
                customer_id=context.customer_id,
                customer_name=context.customer_name,
                entry_date=context.entry_date,
                bazar=context.bazar,
                number=entry.units_digit,
                value=entry.value,
                entry_type=EntryType.TIME_MULTI,
                source_line=f"{entry.number:02d}x{entry.value}"
            )
            universal_entries.append(units_universal)
            
            # Create universal entry for JODI table using the full 2-digit number
            jodi_universal = UniversalLogEntry(
                customer_id=context.customer_id,
                customer_name=context.customer_name,
                entry_date=context.entry_date,
                bazar=context.bazar,
                number=entry.number,  # Full 2-digit number (38, 83, 96, etc.)
                value=entry.value,
                entry_type=EntryType.JODI,
                source_line=f"{entry.number:02d}x{entry.value}"
            )
            universal_entries.append(jodi_universal)
            
            entry_details.append({
                'number': entry.number,
                'tens_digit': entry.tens_digit,
                'units_digit': entry.units_digit,
                'value_per_digit': entry.value,
                'total_value': entry.value,  # Fixed: single value per specification
                'application': 'both_digits_and_jodi'
            })
        
        return {
            'total': total,
            'entry_count': len(entries),
            'universal_entries': universal_entries,
            'details': entry_details,
            'calculation_method': 'digit_multiplication'
        }
    
    def _calculate_direct_entries(self, context: CalculationContext, entries) -> Dict[str, Any]:
        """Calculate direct number entries (simple value assignment)"""
        total = 0
        universal_entries = []
        entry_details = []
        
        for entry in entries:
            # Direct entries contribute their exact value
            total += entry.value
            
            # Create universal entry for direct number
            universal_entry = UniversalLogEntry(
                customer_id=context.customer_id,
                customer_name=context.customer_name,
                entry_date=context.entry_date,
                bazar=context.bazar,
                number=entry.number,
                value=entry.value,
                entry_type=EntryType.DIRECT,
                source_line=f"{entry.number}={entry.value}"
            )
            universal_entries.append(universal_entry)
            
            entry_details.append({
                'number': entry.number,
                'value': entry.value,
                'type': 'direct_assignment'
            })
        
        return {
            'total': total,
            'entry_count': len(entries),
            'universal_entries': universal_entries,
            'details': entry_details,
            'calculation_method': 'direct_assignment'
        }
    
    def _calculate_jodi_entries(self, context: CalculationContext, entries) -> Dict[str, Any]:
        """Calculate jodi entries - each jodi number gets the full value and populate time table based on digit frequencies"""
        total = 0
        universal_entries = []
        entry_details = []
        
        for entry in entries:
            # Each jodi number gets the full value
            # Total calculation: number_of_jodi_numbers × value
            entry_total = len(entry.jodi_numbers) * entry.value
            total += entry_total
            
            # Create universal entry for each jodi number (for jodi table)
            for jodi_number in entry.jodi_numbers:
                jodi_universal_entry = UniversalLogEntry(
                    customer_id=context.customer_id,
                    customer_name=context.customer_name,
                    entry_date=context.entry_date,
                    bazar=context.bazar,
                    number=jodi_number,  # Jodi number (00-99)
                    value=entry.value,   # Full value for each jodi number
                    entry_type=EntryType.JODI,
                    source_line=f"{'-'.join(map(str, entry.jodi_numbers))}={entry.value}"
                )
                universal_entries.append(jodi_universal_entry)
            
            # Calculate digit frequency for time table population
            digit_frequency = {}
            for jodi_number in entry.jodi_numbers:
                # Extract units digit (column number for time table)
                units_digit = jodi_number % 10
                if units_digit not in digit_frequency:
                    digit_frequency[units_digit] = 0
                digit_frequency[units_digit] += 1
            
            # Create TIME_MULTI universal entries based on digit frequency
            for digit, frequency in digit_frequency.items():
                time_value = entry.value * frequency  # value × frequency
                time_universal_entry = UniversalLogEntry(
                    customer_id=context.customer_id,
                    customer_name=context.customer_name,
                    entry_date=context.entry_date,
                    bazar=context.bazar,
                    number=digit,  # Column number (0-9)
                    value=time_value,  # value × frequency
                    entry_type=EntryType.TIME_MULTI,
                    source_line=f"{'-'.join(map(str, entry.jodi_numbers))}={entry.value} (digit_{digit}×{frequency})"
                )
                universal_entries.append(time_universal_entry)
            
            entry_details.append({
                'jodi_numbers': entry.jodi_numbers,
                'input_value': entry.value,
                'count': len(entry.jodi_numbers),
                'total_value': entry_total,
                'value_per_jodi': entry.value,  # Full value per jodi number
                'digit_frequency': digit_frequency,  # Added digit frequency info
                'calculation': f"{entry.value} × {len(entry.jodi_numbers)} = {entry_total} (each jodi gets full {entry.value})"
            })
        
        return {
            'total': total,
            'entry_count': len(entries),
            'universal_entries': universal_entries,
            'details': entry_details,
            'calculation_method': 'jodi_assignment'
        }
    
    def calculate_pana_total(self, entries: List[PanaEntry]) -> int:
        """Calculate pana total following specification rules"""
        if not entries:
            return 0
        
        # Group entries by value (for mixed value scenarios)
        value_groups = {}
        for entry in entries:
            value = entry.value
            if value not in value_groups:
                value_groups[value] = []
            value_groups[value].append(entry)
        
        total = 0
        for value, group_entries in value_groups.items():
            # Each group: count × value
            count = len(group_entries)
            group_total = count * value
            total += group_total
        
        return total
    
    def calculate_type_total(self, entries: List[TypeTableEntry]) -> int:
        """Calculate type table total by expanding numbers from tables"""
        total = 0
        
        # Default table sizes when actual tables are not loaded
        default_table_sizes = {
            'SP': {1: 10, 2: 10, 3: 10, 4: 10, 5: 10, 6: 10, 7: 10, 8: 10, 9: 10, 10: 10},
            'DP': {1: 10, 2: 10, 3: 10, 4: 10, 5: 10, 6: 10, 7: 10, 8: 10, 9: 10, 10: 10},
            'CP': {0: 10, 11: 9, 12: 9, 13: 9, 14: 9, 15: 9, 16: 9, 17: 9, 18: 9, 19: 9,
                   20: 9, 21: 9, 22: 9, 23: 9, 24: 9, 25: 9, 26: 9, 27: 9, 28: 9, 29: 9,
                   30: 9, 31: 9, 32: 9, 33: 9, 34: 9, 35: 9, 36: 9, 37: 9, 38: 9, 39: 9,
                   40: 9, 41: 9, 42: 9, 43: 9, 44: 9, 45: 9, 46: 9, 47: 9, 48: 9, 49: 9,
                   50: 9, 51: 9, 52: 9, 53: 9, 54: 9, 55: 9, 56: 9, 57: 9, 58: 9, 59: 9,
                   60: 9, 61: 9, 62: 9, 63: 9, 64: 9, 65: 9, 66: 9, 67: 9, 68: 9, 69: 9,
                   70: 9, 71: 9, 72: 9, 73: 9, 74: 9, 75: 9, 76: 9, 77: 9, 78: 9, 79: 9,
                   80: 9, 81: 9, 82: 9, 83: 9, 84: 9, 85: 9, 86: 9, 87: 9, 88: 9, 89: 9,
                   90: 9, 91: 9, 92: 9, 93: 9, 94: 9, 95: 9, 96: 9, 97: 9, 98: 9, 99: 9}
        }
        
        for entry in entries:
            # Get numbers from appropriate table
            if entry.table_type == 'SP':
                numbers = self.sp_table.get(entry.column, set())
            elif entry.table_type in ['DP', 'DPT']:
                numbers = self.dp_table.get(entry.column, set())

                # DP excludes triplets, DPT includes them
                if entry.table_type == 'DP':
                    # Filter out triplets (111, 222, 333, etc.)
                    numbers = {num for num in numbers if not self._is_triplet(num)}
                # DPT keeps all numbers including triplets (no filtering needed)

            elif entry.table_type == 'CP':
                numbers = self.cp_table.get(entry.column, set())
            else:
                numbers = set()

            # If no actual table data, use default sizes for calculation
            if not numbers and not self.sp_table and not self.dp_table and not self.cp_table:
                # Use default table sizes when tables are not loaded
                default_sizes = default_table_sizes.get(entry.table_type, {})
                number_count = default_sizes.get(entry.column, 10)  # Default to 10 numbers per column
                entry_total = number_count * entry.value
                total += entry_total
                self.logger.debug(f"Using default calculation for {entry.table_type} column {entry.column}: {number_count} numbers × {entry.value} = {entry_total}")
            else:
                # Use actual table data
                number_count = len(numbers)
                entry_total = number_count * entry.value
                total += entry_total
                if number_count == 0:
                    self.logger.warning(f"No numbers found for {entry.table_type} column {entry.column}")
        
        return total
    
    def calculate_time_total(self, entries: List[TimeEntry]) -> int:
        """Calculate time table total by multiplying value by number of columns
        
        Updated Rule: value × number_of_columns
        Examples:
        - 1=100 → 100 × 1 = 100
        - 0 1 3 5 = 900 → 900 × 4 = 3,600
        """
        total = 0
        for entry in entries:
            # Multiply value by the number of columns
            total += entry.value * len(entry.columns)
        return total
    
    def calculate_multi_total(self, entries: List[MultiEntry]) -> int:
        """Calculate multiplication total per specification"""
        return sum(entry.value for entry in entries)
    
    def calculate_direct_total(self, entries: List) -> int:
        """Calculate direct number total (simple sum of values)"""
        return sum(entry.value for entry in entries)
    
    def calculate_jodi_total(self, entries: List) -> int:
        """Calculate jodi total - each jodi number gets the full value"""
        total = 0
        for entry in entries:
            # Each jodi number gets the full value
            # Total calculation: number_of_jodi_numbers × value
            entry_total = len(entry.jodi_numbers) * entry.value
            total += entry_total
        return total
    
    def validate_pana_number(self, number: int) -> bool:
        """Validate if number exists in pana table"""
        # This would validate against actual pana table
        return 100 <= number <= 999
    
    def get_calculation_summary(self, calculation: BusinessCalculation) -> Dict[str, Any]:
        """Get summary statistics for calculation result"""
        return {
            'totals': {
                'grand_total': calculation.grand_total,
                'bazar_total': calculation.bazar_total,
                'pana_total': calculation.pana_total,
                'type_total': calculation.type_total,
                'time_total': calculation.time_total,
                'multi_total': calculation.multi_total,
                'direct_total': calculation.direct_total
            },
            'entry_counts': {
                'total_universal_entries': len(calculation.universal_entries),
                'pana_entries': len([e for e in calculation.universal_entries if e.entry_type == EntryType.PANA]),
                'type_entries': len([e for e in calculation.universal_entries if e.entry_type == EntryType.TYPE]),
                'time_entries': len([e for e in calculation.universal_entries if e.entry_type == EntryType.TIME_DIRECT]),
                'multi_entries': len([e for e in calculation.universal_entries if e.entry_type == EntryType.TIME_MULTI]),
                'direct_entries': len([e for e in calculation.universal_entries if e.entry_type == EntryType.DIRECT])
            },
            'value_distribution': {
                'pana_percentage': (calculation.pana_total / calculation.grand_total * 100) if calculation.grand_total > 0 else 0,
                'type_percentage': (calculation.type_total / calculation.grand_total * 100) if calculation.grand_total > 0 else 0,
                'time_percentage': (calculation.time_total / calculation.grand_total * 100) if calculation.grand_total > 0 else 0,
                'multi_percentage': (calculation.multi_total / calculation.grand_total * 100) if calculation.grand_total > 0 else 0,
                'direct_percentage': (calculation.direct_total / calculation.grand_total * 100) if calculation.grand_total > 0 else 0
            },
            'breakdown_available': bool(calculation.breakdown),
            'calculation_timestamp': date.today().isoformat()
        }
    
    def validate_calculation(self, calculation: BusinessCalculation) -> Tuple[bool, List[str]]:
        """Validate calculation results for consistency"""
        errors = []
        
        # Check total consistency
        calculated_total = (calculation.pana_total + calculation.type_total + 
                          calculation.time_total + calculation.multi_total + 
                          calculation.direct_total)
        if calculated_total != calculation.bazar_total:
            errors.append(f"Bazar total mismatch: {calculation.bazar_total} != {calculated_total}")
        
        if calculation.bazar_total != calculation.grand_total:
            errors.append(f"Grand total mismatch: {calculation.grand_total} != {calculation.bazar_total}")
        
        # Check universal entries
        if not calculation.universal_entries:
            errors.append("No universal entries generated")
        
        # Validate individual universal entries
        for i, entry in enumerate(calculation.universal_entries):
            if entry.value <= 0:
                errors.append(f"Universal entry {i} has invalid value: {entry.value}")
            if not (0 <= entry.number <= 999):
                errors.append(f"Universal entry {i} has invalid number: {entry.number}")
        
        # Check for negative totals
        if calculation.grand_total < 0:
            errors.append(f"Negative grand total: {calculation.grand_total}")
        
        is_valid = len(errors) == 0
        return is_valid, errors


class CalculationValidator:
    """Validator for calculation engine results"""
    
    def __init__(self, max_total_value: int = 10000000, max_entries: int = 10000):
        self.max_total_value = max_total_value
        self.max_entries = max_entries
        self.logger = get_logger(__name__)
    
    def validate_context(self, context: CalculationContext) -> Tuple[bool, List[str]]:
        """Validate calculation context"""
        errors = []
        
        if context.customer_id <= 0:
            errors.append("Invalid customer ID")
        
        if not context.customer_name.strip():
            errors.append("Customer name cannot be empty")
        
        if not context.bazar.strip():
            errors.append("Bazar cannot be empty")
        
        if context.source_data.is_empty:
            errors.append("No source data provided")
        
        return len(errors) == 0, errors
    
    def validate_result(self, calculation: BusinessCalculation) -> Tuple[bool, List[str]]:
        """Validate calculation result"""
        errors = []
        
        if calculation.grand_total > self.max_total_value:
            errors.append(f"Total value exceeds limit: {calculation.grand_total} > {self.max_total_value}")
        
        if len(calculation.universal_entries) > self.max_entries:
            errors.append(f"Too many entries: {len(calculation.universal_entries)} > {self.max_entries}")
        
        return len(errors) == 0, errors