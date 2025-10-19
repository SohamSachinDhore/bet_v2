"""Data models for RickyMama application using dataclasses"""

from dataclasses import dataclass, field
from datetime import datetime, date
from typing import List, Dict, Optional, Any
from enum import Enum

class EntryType(Enum):
    """Entry type enumeration"""
    PANA = "PANA"
    TYPE = "TYPE"
    TIME_DIRECT = "TIME_DIRECT"
    TIME_MULTI = "TIME_MULTI"
    DIRECT = "DIRECT"
    JODI = "JODI"

class PatternType(Enum):
    """Input pattern type enumeration"""
    PANA_TABLE = "pana_table"
    TYPE_TABLE = "type_table"
    TIME_DIRECT = "time_direct"
    TIME_MULTIPLY = "time_multiply"
    JODI_TABLE = "jodi_table"
    MIXED = "mixed"
    UNKNOWN = "unknown"

@dataclass
class Customer:
    """Customer data model"""
    id: int
    name: str
    created_at: datetime
    updated_at: datetime = None
    is_active: bool = True
    
    def __post_init__(self):
        if self.updated_at is None:
            self.updated_at = self.created_at

@dataclass
class Bazar:
    """Bazar data model"""
    id: int
    name: str
    display_name: str
    sort_order: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = None
    is_active: bool = True
    
    def __post_init__(self):
        if self.updated_at is None:
            self.updated_at = self.created_at

@dataclass
class UniversalLogEntry:
    """Universal log entry data model"""
    customer_id: int
    customer_name: str
    entry_date: date
    bazar: str
    number: int
    value: int
    entry_type: EntryType
    source_line: str = ""
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    
    def __post_init__(self):
        # Validate number range
        if not (0 <= self.number <= 999):
            raise ValueError(f"Invalid number: {self.number}. Must be between 0 and 999")
        
        # Validate value
        if self.value < 0:
            raise ValueError(f"Invalid value: {self.value}. Must be non-negative")
        
        # Convert entry_type to Enum if string
        if isinstance(self.entry_type, str):
            self.entry_type = EntryType(self.entry_type)

@dataclass
class PanaTableEntry:
    """Pana table entry data model"""
    bazar: str
    entry_date: date
    number: int
    value: int
    id: Optional[int] = None
    updated_at: Optional[datetime] = None
    
    def __post_init__(self):
        # Validate pana number range
        if not (100 <= self.number <= 999):
            raise ValueError(f"Invalid pana number: {self.number}. Must be between 100 and 999")
        
        # Validate value
        if self.value < 0:
            raise ValueError(f"Invalid value: {self.value}. Must be non-negative")

@dataclass
class TimeTableEntry:
    """Time table entry data model"""
    customer_id: int
    customer_name: str
    bazar: str
    entry_date: date
    columns: Dict[int, int] = field(default_factory=dict)  # column_number: value
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    @property
    def total(self) -> int:
        """Calculate total from all columns"""
        return sum(self.columns.values())
    
    def get_column_value(self, col_num: int) -> int:
        """Get value for specific column (0-9)"""
        if not (0 <= col_num <= 9):
            raise ValueError(f"Invalid column number: {col_num}. Must be between 0 and 9")
        return self.columns.get(col_num, 0)
    
    def set_column_value(self, col_num: int, value: int):
        """Set value for specific column (0-9)"""
        if not (0 <= col_num <= 9):
            raise ValueError(f"Invalid column number: {col_num}. Must be between 0 and 9")
        if value < 0:
            raise ValueError(f"Invalid value: {value}. Must be non-negative")
        self.columns[col_num] = value

@dataclass
class CustomerBazarSummary:
    """Customer bazar summary data model"""
    customer_id: int
    customer_name: str
    entry_date: date
    bazar_totals: Dict[str, int] = field(default_factory=dict)
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    @property
    def grand_total(self) -> int:
        """Calculate grand total from all bazars"""
        return sum(self.bazar_totals.values())
    
    def get_bazar_total(self, bazar: str) -> int:
        """Get total for specific bazar"""
        return self.bazar_totals.get(bazar, 0)
    
    def set_bazar_total(self, bazar: str, value: int):
        """Set total for specific bazar"""
        if value < 0:
            raise ValueError(f"Invalid value: {value}. Must be non-negative")
        self.bazar_totals[bazar] = value

# Parse Result Models

@dataclass
class PanaEntry:
    """Parsed pana table entry"""
    number: int
    value: int
    
    def __post_init__(self):
        if not (100 <= self.number <= 999):
            raise ValueError(f"Invalid pana number: {self.number}")
        if self.value < 0:
            raise ValueError(f"Invalid value: {self.value}")

@dataclass
class TypeTableEntry:
    """Type table entry data model (for TypeTableParser)"""
    column: int
    table_type: str  # SP, DP, or CP
    value: int
    
    def __post_init__(self):
        if self.table_type not in ['SP', 'DP', 'CP']:
            raise ValueError(f"Invalid table type: {self.table_type}")
        if self.value < 0:
            raise ValueError(f"Invalid value: {self.value}")
        
        # Validate column ranges based on table type
        if self.table_type == 'SP' and not (1 <= self.column <= 10):
            raise ValueError(f"SP column must be 1-10, got: {self.column}")
        elif self.table_type == 'DP' and not (1 <= self.column <= 10):
            raise ValueError(f"DP column must be 1-10, got: {self.column}")
        elif self.table_type == 'CP' and not ((11 <= self.column <= 99) or self.column == 0):
            raise ValueError(f"CP column must be 11-99 or 0, got: {self.column}")

@dataclass
class TypeEntry:
    """Parsed type table entry"""
    table_type: str  # SP, DP, or CP
    column: int
    value: int
    numbers: List[int] = field(default_factory=list)
    
    def __post_init__(self):
        if self.table_type not in ['SP', 'DP', 'CP']:
            raise ValueError(f"Invalid table type: {self.table_type}")
        if self.value < 0:
            raise ValueError(f"Invalid value: {self.value}")

@dataclass
class TimeEntry:
    """Parsed time table entry"""
    columns: List[int]  # List of column numbers (0-99, extended range)
    value: int
    
    def __post_init__(self):
        for col in self.columns:
            if not (0 <= col <= 99):
                raise ValueError(f"Invalid column number: {col}. Must be between 0 and 99")
        if self.value < 0:
            raise ValueError(f"Invalid value: {self.value}")

@dataclass
class MultiEntry:
    """Parsed multiplication entry"""
    number: int  # Full 2-digit number
    tens_digit: int
    units_digit: int
    value: int
    
    def __post_init__(self):
        if not (0 <= self.number <= 99):
            raise ValueError(f"Invalid number: {self.number}")
        if not (0 <= self.tens_digit <= 9):
            raise ValueError(f"Invalid tens digit: {self.tens_digit}")
        if not (0 <= self.units_digit <= 9):
            raise ValueError(f"Invalid units digit: {self.units_digit}")
        if self.value < 0:
            raise ValueError(f"Invalid value: {self.value}")

@dataclass
class DirectNumberEntry:
    """Direct number assignment entry"""
    number: int
    value: int
    
    def __post_init__(self):
        if not (1 <= self.number <= 999):
            raise ValueError(f"Invalid number: {self.number}")
        if self.value <= 0:
            raise ValueError(f"Invalid value: {self.value}")

@dataclass
class JodiEntry:
    """Jodi number assignment entry"""
    jodi_numbers: List[int]
    value: int
    
    def __post_init__(self):
        if not self.jodi_numbers:
            raise ValueError("Jodi numbers list cannot be empty")
        for jodi_number in self.jodi_numbers:
            if not (0 <= jodi_number <= 99):
                raise ValueError(f"Invalid jodi number: {jodi_number}")
        if self.value <= 0:
            raise ValueError(f"Invalid value: {self.value}")

@dataclass
class ParsedInputResult:
    """Result of parsing user input"""
    pana_entries: List[PanaEntry] = field(default_factory=list)
    type_entries: List[TypeEntry] = field(default_factory=list)
    time_entries: List[TimeEntry] = field(default_factory=list)
    multi_entries: List[MultiEntry] = field(default_factory=list)
    direct_entries: List[DirectNumberEntry] = field(default_factory=list)
    jodi_entries: List[JodiEntry] = field(default_factory=list)
    
    @property
    def is_empty(self) -> bool:
        """Check if no entries were parsed"""
        return not (self.pana_entries or self.type_entries or 
                   self.time_entries or self.multi_entries or self.direct_entries or self.jodi_entries)
    
    @property
    def total_entries(self) -> int:
        """Get total number of parsed entries"""
        return (len(self.pana_entries) + len(self.type_entries) + 
                len(self.time_entries) + len(self.multi_entries) + len(self.direct_entries) + len(self.jodi_entries))

@dataclass
class CalculationResult:
    """Result of calculation engine"""
    grand_total: int
    details: Dict[str, Any] = field(default_factory=dict)
    
    def add_detail(self, key: str, value: Any):
        """Add calculation detail"""
        self.details[key] = value
    
    def get_detail(self, key: str, default=None):
        """Get calculation detail"""
        return self.details.get(key, default)

@dataclass
class ValidationResult:
    """Result of input validation"""
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    def add_error(self, error: str):
        """Add validation error"""
        self.errors.append(error)
        self.is_valid = False
    
    def add_warning(self, warning: str):
        """Add validation warning"""
        self.warnings.append(warning)

@dataclass
class ExportData:
    """Data for export operations"""
    table_name: str
    data: List[Dict[str, Any]]
    filters: Dict[str, Any] = field(default_factory=dict)
    export_date: datetime = field(default_factory=datetime.now)
    
    @property
    def row_count(self) -> int:
        """Get number of rows to export"""
        return len(self.data)

# Factory functions for creating models from database rows

def customer_from_row(row: Any) -> Customer:
    """Create Customer model from database row"""
    return Customer(
        id=row['id'],
        name=row['name'],
        created_at=row['created_at'],
        updated_at=row['updated_at'],
        is_active=bool(row['is_active'])
    )

def bazar_from_row(row: Any) -> Bazar:
    """Create Bazar model from database row"""
    return Bazar(
        id=row['id'],
        name=row['name'],
        display_name=row['display_name'],
        sort_order=row['sort_order'],
        created_at=row['created_at'],
        updated_at=row['updated_at'],
        is_active=bool(row['is_active'])
    )

def universal_log_from_row(row: Any) -> UniversalLogEntry:
    """Create UniversalLogEntry model from database row"""
    return UniversalLogEntry(
        id=row['id'],
        customer_id=row['customer_id'],
        customer_name=row['customer_name'],
        entry_date=row['entry_date'],
        bazar=row['bazar'],
        number=row['number'],
        value=row['value'],
        entry_type=EntryType(row['entry_type']),
        source_line=row['source_line'],
        created_at=row['created_at']
    )