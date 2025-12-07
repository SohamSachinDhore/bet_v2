"""
Pending Queue Manager for WhatsApp Messages
Handles temporary storage of incoming WhatsApp messages pending approval
"""

import sqlite3
import threading
from datetime import datetime
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
from enum import Enum


class PendingStatus(Enum):
    """Status of pending entries"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EDITED = "edited"


@dataclass
class PendingEntry:
    """Pending WhatsApp entry awaiting approval"""
    id: Optional[int]
    sender_name: str           # WhatsApp sender name (identifier)
    sender_phone: str          # Phone number if available
    group_name: str            # WhatsApp group name
    raw_message: str           # Original message content
    parsed_preview: str        # Preview of parsed data
    customer_name: str         # Mapped customer name (can be edited)
    bazar: str                 # Selected bazar (can be edited)
    edited_content: str        # Edited content (if modified)
    status: PendingStatus
    received_at: datetime
    processed_at: Optional[datetime] = None
    total_value: int = 0       # Calculated total value
    entry_count: int = 0       # Number of entries detected

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'sender_name': self.sender_name,
            'sender_phone': self.sender_phone,
            'group_name': self.group_name,
            'raw_message': self.raw_message,
            'parsed_preview': self.parsed_preview,
            'customer_name': self.customer_name,
            'bazar': self.bazar,
            'edited_content': self.edited_content,
            'status': self.status.value,
            'received_at': self.received_at.isoformat(),
            'processed_at': self.processed_at.isoformat() if self.processed_at else None,
            'total_value': self.total_value,
            'entry_count': self.entry_count
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PendingEntry':
        return cls(
            id=data.get('id'),
            sender_name=data['sender_name'],
            sender_phone=data.get('sender_phone', ''),
            group_name=data['group_name'],
            raw_message=data['raw_message'],
            parsed_preview=data.get('parsed_preview', ''),
            customer_name=data.get('customer_name', ''),
            bazar=data.get('bazar', ''),
            edited_content=data.get('edited_content', ''),
            status=PendingStatus(data.get('status', 'pending')),
            received_at=datetime.fromisoformat(data['received_at']) if isinstance(data['received_at'], str) else data['received_at'],
            processed_at=datetime.fromisoformat(data['processed_at']) if data.get('processed_at') and isinstance(data['processed_at'], str) else data.get('processed_at'),
            total_value=data.get('total_value', 0),
            entry_count=data.get('entry_count', 0)
        )


class PendingQueueManager:
    """Manager for WhatsApp pending entries queue"""

    def __init__(self, db_path: str = "./data/rickymama.db"):
        self.db_path = db_path
        self.local = threading.local()
        self.lock = threading.Lock()
        self._callbacks = []  # Callbacks for new entries
        self._ensure_table_exists()

    def get_connection(self) -> sqlite3.Connection:
        """Thread-safe connection management"""
        if not hasattr(self.local, 'connection') or self.local.connection is None:
            self.local.connection = sqlite3.connect(
                self.db_path,
                check_same_thread=False,
                timeout=30.0
            )
            self.local.connection.row_factory = sqlite3.Row
        return self.local.connection

    def _ensure_table_exists(self):
        """Create pending_whatsapp_entries table if not exists"""
        schema = """
        CREATE TABLE IF NOT EXISTS pending_whatsapp_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_name TEXT NOT NULL,
            sender_phone TEXT DEFAULT '',
            group_name TEXT NOT NULL,
            raw_message TEXT NOT NULL,
            parsed_preview TEXT DEFAULT '',
            customer_name TEXT DEFAULT '',
            bazar TEXT DEFAULT '',
            edited_content TEXT DEFAULT '',
            status TEXT DEFAULT 'pending',
            received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            processed_at TIMESTAMP,
            total_value INTEGER DEFAULT 0,
            entry_count INTEGER DEFAULT 0
        );

        CREATE INDEX IF NOT EXISTS idx_pending_status ON pending_whatsapp_entries(status);
        CREATE INDEX IF NOT EXISTS idx_pending_received ON pending_whatsapp_entries(received_at);
        """
        conn = self.get_connection()
        conn.executescript(schema)
        conn.commit()

    def add_callback(self, callback):
        """Add callback for new entry notifications"""
        self._callbacks.append(callback)

    def remove_callback(self, callback):
        """Remove callback"""
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    def _notify_callbacks(self, entry: PendingEntry):
        """Notify all callbacks about new entry"""
        for callback in self._callbacks:
            try:
                callback(entry)
            except Exception as e:
                print(f"Callback error: {e}")

    def add_entry(self, entry: PendingEntry) -> int:
        """Add a new pending entry and return its ID"""
        with self.lock:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO pending_whatsapp_entries
                (sender_name, sender_phone, group_name, raw_message, parsed_preview,
                 customer_name, bazar, edited_content, status, received_at,
                 total_value, entry_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                entry.sender_name,
                entry.sender_phone,
                entry.group_name,
                entry.raw_message,
                entry.parsed_preview,
                entry.customer_name,
                entry.bazar,
                entry.edited_content,
                entry.status.value,
                entry.received_at,
                entry.total_value,
                entry.entry_count
            ))

            conn.commit()
            entry_id = cursor.lastrowid
            entry.id = entry_id

            # Notify callbacks
            self._notify_callbacks(entry)

            return entry_id

    def get_pending_entries(self) -> List[PendingEntry]:
        """Get all pending entries"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM pending_whatsapp_entries
            WHERE status = 'pending'
            ORDER BY received_at DESC
        """)

        rows = cursor.fetchall()
        return [self._row_to_entry(row) for row in rows]

    def get_entry_by_id(self, entry_id: int) -> Optional[PendingEntry]:
        """Get entry by ID"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM pending_whatsapp_entries WHERE id = ?", (entry_id,))
        row = cursor.fetchone()

        return self._row_to_entry(row) if row else None

    def update_entry(self, entry_id: int, **kwargs) -> bool:
        """Update entry fields"""
        if not kwargs:
            return False

        with self.lock:
            conn = self.get_connection()
            cursor = conn.cursor()

            # Build update query
            set_clauses = []
            values = []

            for key, value in kwargs.items():
                if key == 'status' and isinstance(value, PendingStatus):
                    value = value.value
                set_clauses.append(f"{key} = ?")
                values.append(value)

            values.append(entry_id)

            query = f"UPDATE pending_whatsapp_entries SET {', '.join(set_clauses)} WHERE id = ?"
            cursor.execute(query, tuple(values))
            conn.commit()

            return cursor.rowcount > 0

    def approve_entry(self, entry_id: int) -> bool:
        """Mark entry as approved"""
        return self.update_entry(
            entry_id,
            status=PendingStatus.APPROVED,
            processed_at=datetime.now()
        )

    def reject_entry(self, entry_id: int) -> bool:
        """Mark entry as rejected"""
        return self.update_entry(
            entry_id,
            status=PendingStatus.REJECTED,
            processed_at=datetime.now()
        )

    def delete_entry(self, entry_id: int) -> bool:
        """Delete entry from queue"""
        with self.lock:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute("DELETE FROM pending_whatsapp_entries WHERE id = ?", (entry_id,))
            conn.commit()

            return cursor.rowcount > 0

    def get_pending_count(self) -> int:
        """Get count of pending entries"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM pending_whatsapp_entries WHERE status = 'pending'")
        return cursor.fetchone()[0]

    def clear_old_entries(self, days: int = 7) -> int:
        """Clear entries older than specified days"""
        with self.lock:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                DELETE FROM pending_whatsapp_entries
                WHERE status != 'pending'
                AND processed_at < datetime('now', ? || ' days')
            """, (-days,))

            conn.commit()
            return cursor.rowcount

    def _row_to_entry(self, row: sqlite3.Row) -> PendingEntry:
        """Convert database row to PendingEntry"""
        return PendingEntry(
            id=row['id'],
            sender_name=row['sender_name'],
            sender_phone=row['sender_phone'] or '',
            group_name=row['group_name'],
            raw_message=row['raw_message'],
            parsed_preview=row['parsed_preview'] or '',
            customer_name=row['customer_name'] or '',
            bazar=row['bazar'] or '',
            edited_content=row['edited_content'] or '',
            status=PendingStatus(row['status']),
            received_at=datetime.fromisoformat(row['received_at']) if row['received_at'] else datetime.now(),
            processed_at=datetime.fromisoformat(row['processed_at']) if row['processed_at'] else None,
            total_value=row['total_value'] or 0,
            entry_count=row['entry_count'] or 0
        )
