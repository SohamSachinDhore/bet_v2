"""Database Manager with SQLite connection pooling and transaction management"""

import sqlite3
import threading
import json
from contextlib import contextmanager
from typing import Dict, List, Optional, Any, Tuple
import os
import logging

class DatabaseManager:
    """Centralized database operations with connection pooling"""
    
    def __init__(self, db_path: str = "./data/rickymama.db"):
        self.db_path = db_path
        self.local = threading.local()
        self.lock = threading.Lock()
        self.logger = logging.getLogger(__name__)
        
        # Ensure database directory exists (skip for in-memory DB)
        if self.db_path != ":memory:" and os.path.dirname(self.db_path):
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
    
    def get_connection(self) -> sqlite3.Connection:
        """Thread-safe connection management"""
        if not hasattr(self.local, 'connection') or self.local.connection is None:
            self.local.connection = sqlite3.connect(
                self.db_path,
                check_same_thread=False,
                timeout=30.0
            )
            # Enable foreign keys and optimizations
            self.local.connection.execute("PRAGMA foreign_keys = ON")
            self.local.connection.execute("PRAGMA journal_mode = WAL")
            self.local.connection.execute("PRAGMA synchronous = NORMAL")
            self.local.connection.execute("PRAGMA cache_size = 10240")
            
            # Set row factory for dict-like access
            self.local.connection.row_factory = sqlite3.Row
            
        return self.local.connection
    
    @contextmanager
    def transaction(self):
        """Context manager for database transactions"""
        conn = self.get_connection()
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            self.logger.error(f"Transaction failed: {e}")
            raise
    
    def initialize_database(self):
        """Create all tables and initial data"""
        # Check if database already exists and has tables
        if self._database_exists():
            self.logger.info("Database already exists, skipping initialization")
            return
        
        schema_path = os.path.join(os.path.dirname(__file__), 'schema.sql')
        
        # Check if schema file exists
        if not os.path.exists(schema_path):
            self.logger.warning(f"Schema file not found at {schema_path}, creating basic schema")
            self.create_basic_schema()
            return
        
        with open(schema_path, 'r') as f:
            schema_sql = f.read()
        
        with self.transaction() as conn:
            conn.executescript(schema_sql)
            self.logger.info("Database initialized successfully")
    
    def _database_exists(self) -> bool:
        """Check if database exists and has tables"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='customers'")
            result = cursor.fetchone()
            return result is not None
        except Exception:
            return False
    
    def create_basic_schema(self):
        """Create basic schema if schema.sql is not available"""
        basic_schema = """
        -- Create customers table
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE COLLATE NOCASE,
            commission_type TEXT DEFAULT 'commission',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_active BOOLEAN DEFAULT 1,
            
            -- Constraints
            CONSTRAINT customers_commission_type_valid CHECK (commission_type IN ('commission', 'non_commission'))
        );
        
        -- Create bazars table
        CREATE TABLE IF NOT EXISTS bazars (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE COLLATE NOCASE,
            display_name TEXT NOT NULL,
            sort_order INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_active BOOLEAN DEFAULT 1
        );
        
        -- Create universal_log table
        CREATE TABLE IF NOT EXISTS universal_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            customer_name TEXT NOT NULL,
            entry_date DATE NOT NULL,
            bazar TEXT NOT NULL,
            number INTEGER NOT NULL,
            value INTEGER NOT NULL,
            entry_type TEXT NOT NULL,
            source_line TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE
        );
        
        -- Create indexes
        CREATE INDEX IF NOT EXISTS idx_customers_name ON customers(name);
        CREATE INDEX IF NOT EXISTS idx_universal_log_customer_date ON universal_log(customer_id, entry_date);
        CREATE INDEX IF NOT EXISTS idx_universal_log_bazar_date ON universal_log(bazar, entry_date);
        """
        
        with self.transaction() as conn:
            conn.executescript(basic_schema)
    
    def execute_query(self, query: str, params: Optional[Tuple] = None) -> List[sqlite3.Row]:
        """Execute a SELECT query and return results"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        
        return cursor.fetchall()
    
    def execute_update(self, query: str, params: Optional[Tuple] = None) -> int:
        """Execute an INSERT/UPDATE/DELETE query and return affected rows"""
        with self.transaction() as conn:
            cursor = conn.cursor()
            
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            return cursor.rowcount
    
    def execute_many(self, query: str, params_list: List[Tuple]) -> int:
        """Execute multiple INSERT/UPDATE/DELETE queries"""
        with self.transaction() as conn:
            cursor = conn.cursor()
            cursor.executemany(query, params_list)
            return cursor.rowcount
    
    def insert_and_get_id(self, query: str, params: Tuple) -> int:
        """Insert a record and return the last inserted ID"""
        with self.transaction() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return cursor.lastrowid
    
    # Customer Operations
    def add_customer(self, name: str, commission_type: str = 'commission') -> int:
        """Add a new customer and return their ID"""
        query = "INSERT INTO customers (name, commission_type) VALUES (?, ?)"
        return self.insert_and_get_id(query, (name, commission_type))
    
    def get_customer_by_name(self, name: str) -> Optional[sqlite3.Row]:
        """Get customer by name"""
        query = "SELECT * FROM customers WHERE name = ? AND is_active = 1"
        results = self.execute_query(query, (name,))
        return results[0] if results else None
    
    def get_customer_by_id(self, customer_id: int) -> Optional[sqlite3.Row]:
        """Get customer by ID"""
        query = "SELECT * FROM customers WHERE id = ? AND is_active = 1"
        results = self.execute_query(query, (customer_id,))
        return results[0] if results else None
    
    def get_all_customers(self) -> List[sqlite3.Row]:
        """Get all active customers"""
        query = "SELECT * FROM customers WHERE is_active = 1 ORDER BY name"
        return self.execute_query(query)
    
    def update_customer(self, customer_id: int, name: str, commission_type: str = 'commission') -> bool:
        """Update customer details and cascade name changes to all related tables"""
        try:
            with self.transaction() as conn:
                # First, get the old customer name for logging
                old_customer_query = "SELECT name FROM customers WHERE id = ? AND is_active = 1"
                old_customer = self.execute_query(old_customer_query, (customer_id,))
                old_name = old_customer[0]['name'] if old_customer else None
                
                # Update customer table
                customer_query = """
                UPDATE customers 
                SET name = ?, commission_type = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND is_active = 1
                """
                customer_cursor = conn.cursor()
                customer_cursor.execute(customer_query, (name, commission_type, customer_id))
                customer_rows_affected = customer_cursor.rowcount
                
                if customer_rows_affected == 0:
                    return False
                
                # Update customer_name in universal_log table (denormalized field)
                universal_log_query = """
                UPDATE universal_log 
                SET customer_name = ?
                WHERE customer_id = ?
                """
                universal_cursor = conn.cursor()
                universal_cursor.execute(universal_log_query, (name, customer_id))
                universal_rows_affected = universal_cursor.rowcount
                
                # Update customer_name in time_table (denormalized field)
                time_table_query = """
                UPDATE time_table 
                SET customer_name = ?, updated_at = CURRENT_TIMESTAMP
                WHERE customer_id = ?
                """
                time_cursor = conn.cursor()
                time_cursor.execute(time_table_query, (name, customer_id))
                time_rows_affected = time_cursor.rowcount
                
                # Update customer_name in customer_bazar_summary (denormalized field)
                summary_query = """
                UPDATE customer_bazar_summary 
                SET customer_name = ?, updated_at = CURRENT_TIMESTAMP
                WHERE customer_id = ?
                """
                summary_cursor = conn.cursor()
                summary_cursor.execute(summary_query, (name, customer_id))
                summary_rows_affected = summary_cursor.rowcount
                
                self.logger.info(f"Customer update cascaded: customer={customer_rows_affected}, "
                               f"universal_log={universal_rows_affected}, time_table={time_rows_affected}, "
                               f"summary={summary_rows_affected} rows affected")
                               
                if old_name and old_name != name:
                    self.logger.info(f"Customer name changed from '{old_name}' to '{name}' for ID {customer_id}")
                
                return True
                
        except Exception as e:
            self.logger.error(f"Failed to update customer {customer_id}: {e}")
            return False
    
    def delete_customer(self, customer_id: int) -> bool:
        """Delete customer (soft delete by setting is_active = 0)"""
        try:
            query = """
            UPDATE customers 
            SET is_active = 0, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """
            rows_affected = self.execute_update(query, (customer_id,))
            return rows_affected > 0
        except Exception as e:
            self.logger.error(f"Failed to delete customer {customer_id}: {e}")
            return False
    
    # Bazar Operations
    def get_all_bazars(self) -> List[sqlite3.Row]:
        """Get all active bazars"""
        query = "SELECT * FROM bazars WHERE is_active = 1 ORDER BY sort_order, name"
        return self.execute_query(query)
    
    def add_bazar(self, name: str, display_name: str = None) -> int:
        """Add a new bazar"""
        if display_name is None:
            display_name = name
        query = "INSERT INTO bazars (name, display_name) VALUES (?, ?)"
        return self.insert_and_get_id(query, (name, display_name))
    
    # Universal Log Operations
    def add_universal_log_entry(self, entry_data: Dict[str, Any]) -> int:
        """Add an entry to universal log"""
        query = """
        INSERT INTO universal_log 
        (customer_id, customer_name, entry_date, bazar, number, value, entry_type, source_line)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            entry_data['customer_id'],
            entry_data['customer_name'],
            entry_data['entry_date'],
            entry_data['bazar'],
            entry_data['number'],
            entry_data['value'],
            entry_data['entry_type'],
            entry_data.get('source_line', '')
        )
        return self.insert_and_get_id(query, params)
    
    def add_universal_log_entries(self, entries: List[Dict[str, Any]]) -> int:
        """Add multiple entries to universal log"""
        query = """
        INSERT INTO universal_log 
        (customer_id, customer_name, entry_date, bazar, number, value, entry_type, source_line)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        params_list = [
            (
                entry['customer_id'],
                entry['customer_name'],
                entry['entry_date'],
                entry['bazar'],
                entry['number'],
                entry['value'],
                entry['entry_type'],
                entry.get('source_line', '')
            )
            for entry in entries
        ]
        return self.execute_many(query, params_list)
    
    def get_universal_log_entries(self, filters: Optional[Dict[str, Any]] = None, 
                                 limit: int = 1000, offset: int = 0) -> List[sqlite3.Row]:
        """Get universal log entries with optional filters"""
        query = "SELECT * FROM universal_log WHERE 1=1"
        params = []
        
        if filters:
            if 'customer_id' in filters:
                query += " AND customer_id = ?"
                params.append(filters['customer_id'])
            
            if 'bazar' in filters:
                query += " AND bazar = ?"
                params.append(filters['bazar'])
            
            if 'start_date' in filters:
                query += " AND entry_date >= ?"
                params.append(filters['start_date'])
            
            if 'end_date' in filters:
                query += " AND entry_date <= ?"
                params.append(filters['end_date'])
            
            if 'entry_type' in filters:
                query += " AND entry_type = ?"
                params.append(filters['entry_type'])
        
        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        return self.execute_query(query, tuple(params))
    
    def update_universal_log_entry(self, entry_id: int, updates: Dict[str, Any]) -> bool:
        """Update a universal log entry with customer name consistency and recalculate affected tables"""
        try:
            with self.transaction() as conn:
                # First get the current entry for both validation and later recalculation
                current_entry_query = "SELECT customer_id, customer_name, entry_date, bazar, entry_type FROM universal_log WHERE id = ?"
                current_entry = self.execute_query(current_entry_query, (entry_id,))
                
                if not current_entry:
                    return False
                
                entry = current_entry[0]
                customer_id = entry['customer_id']
                current_customer_name = entry['customer_name']
                old_entry_date = entry['entry_date']
                old_bazar = entry['bazar']
                old_entry_type = entry['entry_type']
                
                # Get the correct customer name from customers table
                customer_query = "SELECT name FROM customers WHERE id = ? AND is_active = 1"
                customer_result = self.execute_query(customer_query, (customer_id,))
                
                if not customer_result:
                    self.logger.warning(f"Customer {customer_id} not found or inactive")
                    return False
                
                correct_customer_name = customer_result[0]['name']
                
                # Build dynamic update query
                update_fields = []
                params = []
                
                allowed_fields = ['number', 'value', 'entry_type', 'bazar', 'source_line']
                for field in allowed_fields:
                    if field in updates:
                        update_fields.append(f"{field} = ?")
                        params.append(updates[field])
                
                # Always ensure customer_name is correct (in case it was out of sync)
                if current_customer_name != correct_customer_name:
                    update_fields.append("customer_name = ?")
                    params.append(correct_customer_name)
                    self.logger.info(f"Correcting customer_name from '{current_customer_name}' to '{correct_customer_name}' for entry {entry_id}")
                
                if not update_fields:
                    return False
                
                query = f"""
                UPDATE universal_log 
                SET {', '.join(update_fields)}
                WHERE id = ?
                """
                params.append(entry_id)
                
                cursor = conn.cursor()
                cursor.execute(query, tuple(params))
                rows_affected = cursor.rowcount
                
                if rows_affected > 0:
                    # Determine what contexts need recalculation
                    contexts_to_recalc = set()
                    
                    # Always recalculate the old context
                    contexts_to_recalc.add((customer_id, correct_customer_name, old_entry_date, old_bazar, old_entry_type))
                    
                    # If bazar or entry_date changed, also recalculate new context
                    new_bazar = updates.get('bazar', old_bazar)
                    new_entry_type = updates.get('entry_type', old_entry_type)
                    
                    if new_bazar != old_bazar or new_entry_type != old_entry_type:
                        contexts_to_recalc.add((customer_id, correct_customer_name, old_entry_date, new_bazar, new_entry_type))
                    
                    # Recalculate all affected contexts
                    for context in contexts_to_recalc:
                        cust_id, cust_name, ent_date, baz, ent_type = context
                        self._recalculate_aggregated_tables_for_context(
                            conn, cust_id, cust_name, ent_date, baz, ent_type
                        )
                
                return rows_affected > 0
                
        except Exception as e:
            self.logger.error(f"Failed to update universal log entry {entry_id}: {e}")
            return False
    
    def delete_universal_log_entry(self, entry_id: int) -> bool:
        """Delete a universal log entry and update related aggregated tables"""
        try:
            with self.transaction() as conn:
                # First get the entry details before deletion for recalculation
                entry_query = "SELECT customer_id, customer_name, entry_date, bazar, entry_type FROM universal_log WHERE id = ?"
                entry_result = self.execute_query(entry_query, (entry_id,))
                
                if not entry_result:
                    return False
                
                entry = entry_result[0]
                customer_id = entry['customer_id']
                customer_name = entry['customer_name']
                entry_date = entry['entry_date']
                bazar = entry['bazar']
                entry_type = entry['entry_type']
                
                # Delete the universal log entry
                delete_cursor = conn.cursor()
                delete_cursor.execute("DELETE FROM universal_log WHERE id = ?", (entry_id,))
                rows_affected = delete_cursor.rowcount
                
                if rows_affected > 0:
                    # Recalculate affected aggregated tables
                    self._recalculate_aggregated_tables_for_context(
                        conn, customer_id, customer_name, entry_date, bazar, entry_type
                    )
                
                return rows_affected > 0
                
        except Exception as e:
            self.logger.error(f"Failed to delete universal log entry {entry_id}: {e}")
            return False
    
    def _recalculate_aggregated_tables_for_context(self, conn, customer_id: int, customer_name: str, 
                                                  entry_date: str, bazar: str, entry_type: str):
        """Recalculate aggregated tables for a specific context after universal log changes"""
        try:
            # Recalculate pana_table (for PANA entries by bazar+date)
            if entry_type == 'PANA':
                self._recalculate_pana_table(conn, bazar, entry_date)
            
            # Recalculate time_table (for TIME_DIRECT and TIME_MULTI entries by customer+bazar+date)
            if entry_type in ['TIME_DIRECT', 'TIME_MULTI']:
                self._recalculate_time_table(conn, customer_id, customer_name, bazar, entry_date)
            
            # Recalculate jodi_table (for JODI entries by bazar+date) - if it exists
            if entry_type == 'JODI':
                self._recalculate_jodi_table(conn, bazar, entry_date)
            
            # Recalculate customer_bazar_summary for the affected customer+date
            self._recalculate_customer_summary(conn, customer_id, customer_name, entry_date)
            
            self.logger.info(f"Recalculated aggregated tables for customer {customer_id}, date {entry_date}, bazar {bazar}")
            
        except Exception as e:
            self.logger.error(f"Failed to recalculate aggregated tables: {e}")
            raise
    
    def _recalculate_pana_table(self, conn, bazar: str, entry_date: str):
        """Recalculate pana_table entries for a specific bazar and date"""
        try:
            # Clear existing pana_table entries for this bazar+date
            clear_cursor = conn.cursor()
            clear_cursor.execute("DELETE FROM pana_table WHERE bazar = ? AND entry_date = ?", (bazar, entry_date))
            
            # Recalculate from universal_log
            recalc_query = """
            INSERT INTO pana_table (bazar, entry_date, number, value, updated_at)
            SELECT bazar, entry_date, number, SUM(value), CURRENT_TIMESTAMP
            FROM universal_log
            WHERE bazar = ? AND entry_date = ? AND entry_type = 'PANA'
            GROUP BY bazar, entry_date, number
            HAVING SUM(value) > 0
            """
            recalc_cursor = conn.cursor()
            recalc_cursor.execute(recalc_query, (bazar, entry_date))
            
            self.logger.debug(f"Recalculated pana_table for {bazar} on {entry_date}")
            
        except Exception as e:
            self.logger.error(f"Failed to recalculate pana_table: {e}")
            raise
    
    def _recalculate_time_table(self, conn, customer_id: int, customer_name: str, bazar: str, entry_date: str):
        """Recalculate time_table entry for a specific customer, bazar, and date"""
        try:
            # Clear existing time_table entry for this customer+bazar+date
            clear_cursor = conn.cursor()
            clear_cursor.execute(
                "DELETE FROM time_table WHERE customer_id = ? AND bazar = ? AND entry_date = ?",
                (customer_id, bazar, entry_date)
            )
            
            # Recalculate column totals from universal_log
            recalc_query = """
            SELECT number, SUM(value) as total_value
            FROM universal_log
            WHERE customer_id = ? AND bazar = ? AND entry_date = ? 
                AND entry_type IN ('TIME_DIRECT', 'TIME_MULTI')
                AND number BETWEEN 0 AND 9
            GROUP BY number
            """
            recalc_cursor = conn.cursor()
            recalc_cursor.execute(recalc_query, (customer_id, bazar, entry_date))
            column_totals = recalc_cursor.fetchall()
            
            if column_totals:
                # Build column values
                col_values = [0] * 10  # Initialize all columns to 0
                for row in column_totals:
                    column_num = row['number']
                    if 0 <= column_num <= 9:
                        col_values[column_num] = row['total_value']
                
                # Insert new time_table entry
                insert_query = """
                INSERT INTO time_table 
                (customer_id, customer_name, bazar, entry_date, 
                 col_0, col_1, col_2, col_3, col_4, col_5, col_6, col_7, col_8, col_9)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """
                insert_cursor = conn.cursor()
                insert_cursor.execute(insert_query, [customer_id, customer_name, bazar, entry_date] + col_values)
                
                self.logger.debug(f"Recalculated time_table for customer {customer_id}, {bazar} on {entry_date}")
            
        except Exception as e:
            self.logger.error(f"Failed to recalculate time_table: {e}")
            raise
    
    def _recalculate_jodi_table(self, conn, bazar: str, entry_date: str):
        """Recalculate jodi_table entries for a specific bazar and date (if jodi_table exists)"""
        try:
            # Check if jodi_table exists
            check_cursor = conn.cursor()
            check_cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='jodi_table'")
            if not check_cursor.fetchone():
                return  # jodi_table doesn't exist, skip
            
            # Clear existing jodi_table entries for this bazar+date
            clear_cursor = conn.cursor()
            clear_cursor.execute("DELETE FROM jodi_table WHERE bazar = ? AND entry_date = ?", (bazar, entry_date))
            
            # Recalculate from universal_log
            recalc_query = """
            INSERT INTO jodi_table (bazar, entry_date, jodi_number, value, updated_at)
            SELECT bazar, entry_date, number, SUM(value), CURRENT_TIMESTAMP
            FROM universal_log
            WHERE bazar = ? AND entry_date = ? AND entry_type = 'JODI'
                AND number BETWEEN 0 AND 99
            GROUP BY bazar, entry_date, number
            HAVING SUM(value) > 0
            """
            recalc_cursor = conn.cursor()
            recalc_cursor.execute(recalc_query, (bazar, entry_date))
            
            self.logger.debug(f"Recalculated jodi_table for {bazar} on {entry_date}")
            
        except Exception as e:
            self.logger.error(f"Failed to recalculate jodi_table: {e}")
            # Don't raise - jodi_table might not exist
    
    def _recalculate_customer_summary(self, conn, customer_id: int, customer_name: str, entry_date: str):
        """Recalculate customer_bazar_summary for a specific customer and date"""
        try:
            # Clear existing summary for this customer+date
            clear_cursor = conn.cursor()
            clear_cursor.execute(
                "DELETE FROM customer_bazar_summary WHERE customer_id = ? AND entry_date = ?",
                (customer_id, entry_date)
            )
            
            # Recalculate bazar totals from universal_log
            recalc_query = """
            SELECT bazar, SUM(value) as total_value
            FROM universal_log
            WHERE customer_id = ? AND entry_date = ?
            GROUP BY bazar
            HAVING SUM(value) > 0
            """
            recalc_cursor = conn.cursor()
            recalc_cursor.execute(recalc_query, (customer_id, entry_date))
            bazar_totals = recalc_cursor.fetchall()
            
            if bazar_totals:
                # Build bazar totals dict and map to column names
                bazar_dict = {}
                for row in bazar_totals:
                    bazar_dict[row['bazar']] = row['total_value']
                
                # Map bazar names to column names
                bazar_mapping = {
                    'T.O': 'to_total', 'T.K': 'tk_total', 'M.O': 'mo_total', 'M.K': 'mk_total',
                    'K.O': 'ko_total', 'K.K': 'kk_total', 'NMO': 'nmo_total', 'NMK': 'nmk_total',
                    'B.O': 'bo_total', 'B.K': 'bk_total'
                }
                
                # Build column values
                column_values = {col: 0 for col in bazar_mapping.values()}  # Initialize all to 0
                for bazar, total in bazar_dict.items():
                    if bazar in bazar_mapping:
                        column_values[bazar_mapping[bazar]] = total
                
                # Build INSERT query with actual column names
                columns = ['customer_id', 'customer_name', 'entry_date'] + list(column_values.keys()) + ['updated_at']
                values = [customer_id, customer_name, entry_date] + list(column_values.values()) + ['CURRENT_TIMESTAMP']
                placeholders = ['?'] * (len(values) - 1) + ['CURRENT_TIMESTAMP']
                
                insert_query = f"""
                INSERT INTO customer_bazar_summary 
                ({', '.join(columns)})
                VALUES ({', '.join(placeholders)})
                """
                
                insert_cursor = conn.cursor()
                insert_cursor.execute(insert_query, values[:-1])  # Exclude CURRENT_TIMESTAMP from params
                
                self.logger.debug(f"Recalculated customer_bazar_summary for customer {customer_id} on {entry_date}")
            
        except Exception as e:
            self.logger.error(f"Failed to recalculate customer_bazar_summary: {e}")
            raise
    
    # Pana Table Operations
    def update_pana_table_entry(self, bazar: str, entry_date: str, number: int, value_to_add: int) -> None:
        """Update or insert pana table entry by adding value"""
        # First, try to get existing entry
        check_query = """
        SELECT id, value FROM pana_table 
        WHERE bazar = ? AND entry_date = ? AND number = ?
        """
        existing = self.execute_query(check_query, (bazar, entry_date, number))
        
        if existing:
            # Update existing entry by adding value
            update_query = """
            UPDATE pana_table 
            SET value = value + ?, updated_at = CURRENT_TIMESTAMP
            WHERE bazar = ? AND entry_date = ? AND number = ?
            """
            self.execute_update(update_query, (value_to_add, bazar, entry_date, number))
        else:
            # Insert new entry
            insert_query = """
            INSERT INTO pana_table (bazar, entry_date, number, value)
            VALUES (?, ?, ?, ?)
            """
            self.execute_update(insert_query, (bazar, entry_date, number, value_to_add))
    
    def get_pana_table_values(self, bazar: str, entry_date: str) -> List[sqlite3.Row]:
        """Get all pana values for a specific bazar and date"""
        query = """
        SELECT number, value FROM pana_table
        WHERE bazar = ? AND entry_date = ?
        ORDER BY number
        """
        return self.execute_query(query, (bazar, entry_date))
    
    def get_pana_reference_numbers(self) -> set:
        """Get all valid pana reference numbers from pana_numbers table"""
        query = "SELECT DISTINCT number FROM pana_numbers"
        rows = self.execute_query(query)
        return {row['number'] for row in rows} if rows else set()
    
    # Jodi Table Operations
    def get_jodi_table_values(self, bazar: str, entry_date: str) -> List[sqlite3.Row]:
        """Get all jodi values for a specific bazar and date (aggregated for all customers)"""
        query = """
        SELECT jodi_number, value FROM jodi_table
        WHERE bazar = ? AND entry_date = ?
        ORDER BY jodi_number
        """
        return self.execute_query(query, (bazar, entry_date))
    
    def get_jodi_table_values_by_customer(self, customer_name: str, bazar: str, entry_date: str) -> List[sqlite3.Row]:
        """Get jodi values for a specific customer, bazar and date from universal_log"""
        query = """
        SELECT number as jodi_number, SUM(value) as value 
        FROM universal_log
        WHERE customer_name = ? AND bazar = ? AND entry_date = ? AND entry_type = 'JODI'
        GROUP BY number
        ORDER BY number
        """
        return self.execute_query(query, (customer_name, bazar, entry_date))
    
    # Time Table Operations
    def update_time_table_entry(self, customer_id: int, customer_name: str, 
                               bazar: str, entry_date: str, column_values: Dict[int, int]) -> None:
        """Update or insert time table entry"""
        # First, try to get existing entry
        check_query = """
        SELECT id FROM time_table 
        WHERE customer_id = ? AND bazar = ? AND entry_date = ?
        """
        existing = self.execute_query(check_query, (customer_id, bazar, entry_date))
        
        if existing:
            # Build dynamic update query for columns
            update_parts = []
            params = []
            
            for col_num, value in column_values.items():
                if 0 <= col_num <= 9:
                    update_parts.append(f"col_{col_num} = col_{col_num} + ?")
                    params.append(value)
            
            if update_parts:
                update_query = f"""
                UPDATE time_table 
                SET {', '.join(update_parts)}, updated_at = CURRENT_TIMESTAMP
                WHERE customer_id = ? AND bazar = ? AND entry_date = ?
                """
                params.extend([customer_id, bazar, entry_date])
                self.execute_update(update_query, tuple(params))
        else:
            # Insert new entry
            insert_query = """
            INSERT INTO time_table 
            (customer_id, customer_name, bazar, entry_date, 
             col_0, col_1, col_2, col_3, col_4, col_5, col_6, col_7, col_8, col_9)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            # Initialize all columns to 0, then set provided values
            col_values = [0] * 10
            for col_num, value in column_values.items():
                if 0 <= col_num <= 9:
                    col_values[col_num] = value
            
            params = [customer_id, customer_name, bazar, entry_date] + col_values
            self.execute_update(insert_query, tuple(params))
    
    def get_time_table_entry(self, customer_id: int, bazar: str, entry_date: str) -> Optional[sqlite3.Row]:
        """Get time table entry for a customer, bazar, and date"""
        query = """
        SELECT * FROM time_table
        WHERE customer_id = ? AND bazar = ? AND entry_date = ?
        """
        results = self.execute_query(query, (customer_id, bazar, entry_date))
        return results[0] if results else None
    
    def get_time_table_by_bazar_date(self, bazar: str, entry_date: str) -> List[sqlite3.Row]:
        """Get all time table entries for a specific bazar and date"""
        query = """
        SELECT * FROM time_table
        WHERE bazar = ? AND entry_date = ?
        ORDER BY customer_name
        """
        return self.execute_query(query, (bazar, entry_date))
    
    # Customer Bazar Summary Operations
    def update_customer_bazar_summary(self, customer_id: int, customer_name: str, 
                                     entry_date: str, bazar_totals: Dict[str, int]) -> None:
        """Update or insert customer bazar summary"""
        # Map bazar names to column names
        bazar_column_map = {
            'T.O': 'to_total',
            'T.K': 'tk_total',
            'M.O': 'mo_total',
            'M.K': 'mk_total',
            'K.O': 'ko_total',
            'K.K': 'kk_total',
            'NMO': 'nmo_total',
            'NMK': 'nmk_total',
            'B.O': 'bo_total',
            'B.K': 'bk_total'
        }
        
        # Check if entry exists
        check_query = """
        SELECT id FROM customer_bazar_summary
        WHERE customer_id = ? AND entry_date = ?
        """
        existing = self.execute_query(check_query, (customer_id, entry_date))
        
        if existing:
            # Build update query
            update_parts = []
            params = []
            
            for bazar, total in bazar_totals.items():
                if bazar in bazar_column_map:
                    column = bazar_column_map[bazar]
                    update_parts.append(f"{column} = {column} + ?")
                    params.append(total)
            
            if update_parts:
                update_query = f"""
                UPDATE customer_bazar_summary
                SET {', '.join(update_parts)}, updated_at = CURRENT_TIMESTAMP
                WHERE customer_id = ? AND entry_date = ?
                """
                params.extend([customer_id, entry_date])
                self.execute_update(update_query, tuple(params))
        else:
            # Insert new entry
            # Initialize all totals to 0
            totals = {col: 0 for col in bazar_column_map.values()}
            
            # Set provided totals
            for bazar, total in bazar_totals.items():
                if bazar in bazar_column_map:
                    totals[bazar_column_map[bazar]] = total
            
            insert_query = """
            INSERT INTO customer_bazar_summary
            (customer_id, customer_name, entry_date, 
             to_total, tk_total, mo_total, mk_total, ko_total, 
             kk_total, nmo_total, nmk_total, bo_total, bk_total)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            params = [customer_id, customer_name, entry_date] + [
                totals['to_total'], totals['tk_total'], totals['mo_total'], 
                totals['mk_total'], totals['ko_total'], totals['kk_total'], 
                totals['nmo_total'], totals['nmk_total'], totals['bo_total'], 
                totals['bk_total']
            ]
            self.execute_update(insert_query, tuple(params))
    
    def get_customer_bazar_summary_by_date(self, entry_date: str) -> List[sqlite3.Row]:
        """Get all customer summaries for a specific date"""
        query = """
        SELECT * FROM customer_bazar_summary
        WHERE entry_date = ?
        ORDER BY customer_name
        """
        return self.execute_query(query, (entry_date,))
    
    def close(self):
        """Close database connection"""
        if hasattr(self.local, 'connection') and self.local.connection:
            self.local.connection.close()
            self.local.connection = None
            self.logger.info("Database connection closed")
    
    def __del__(self):
        """Cleanup on destruction"""
        self.close()


def create_database_manager(db_path: str = "./data/rickymama.db") -> DatabaseManager:
    """Factory function to create database manager"""
    return DatabaseManager(db_path)