"""
WhatsApp Notification Server
HTTP server to receive WhatsApp notifications from Android app
"""

import json
import threading
import socket
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Callable, Optional, Dict, Any, List
from urllib.parse import parse_qs, urlparse

from .pending_queue import PendingQueueManager, PendingEntry, PendingStatus


class WhatsAppRequestHandler(BaseHTTPRequestHandler):
    """HTTP Request Handler for WhatsApp notifications"""

    # Class-level references set by WhatsAppServer
    pending_queue: PendingQueueManager = None
    parser_callback: Callable = None
    allowed_groups: List[str] = []
    on_message_callback: Callable = None

    def log_message(self, format, *args):
        """Override to customize logging"""
        print(f"[WhatsApp Server] {args[0]}")

    def _set_headers(self, status_code: int = 200, content_type: str = 'application/json'):
        """Set response headers"""
        self.send_response(status_code)
        self.send_header('Content-Type', content_type)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def _send_json_response(self, data: Dict, status_code: int = 200):
        """Send JSON response"""
        self._set_headers(status_code)
        self.wfile.write(json.dumps(data).encode('utf-8'))

    def do_OPTIONS(self):
        """Handle CORS preflight requests"""
        self._set_headers(200)

    def do_GET(self):
        """Handle GET requests"""
        parsed_path = urlparse(self.path)

        if parsed_path.path == '/status':
            # Server status endpoint
            self._send_json_response({
                'status': 'running',
                'pending_count': self.pending_queue.get_pending_count() if self.pending_queue else 0,
                'timestamp': datetime.now().isoformat()
            })

        elif parsed_path.path == '/pending':
            # Get pending entries
            if self.pending_queue:
                entries = self.pending_queue.get_pending_entries()
                self._send_json_response({
                    'success': True,
                    'entries': [e.to_dict() for e in entries],
                    'count': len(entries)
                })
            else:
                self._send_json_response({'success': False, 'error': 'Queue not initialized'}, 500)

        elif parsed_path.path == '/config':
            # Get server configuration
            self._send_json_response({
                'allowed_groups': self.allowed_groups,
                'server_time': datetime.now().isoformat()
            })

        else:
            self._send_json_response({'error': 'Not found'}, 404)

    def do_POST(self):
        """Handle POST requests"""
        parsed_path = urlparse(self.path)

        # Read request body
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8') if content_length > 0 else '{}'

        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            self._send_json_response({'error': 'Invalid JSON'}, 400)
            return

        if parsed_path.path == '/message':
            # Receive WhatsApp message
            self._handle_message(data)

        elif parsed_path.path == '/batch':
            # Receive multiple messages
            self._handle_batch(data)

        elif parsed_path.path == '/ping':
            # Ping from Android app
            self._send_json_response({
                'success': True,
                'message': 'pong',
                'server_time': datetime.now().isoformat()
            })

        else:
            self._send_json_response({'error': 'Not found'}, 404)

    def _handle_message(self, data: Dict):
        """Handle incoming WhatsApp message"""
        required_fields = ['sender_name', 'message', 'group_name']
        missing_fields = [f for f in required_fields if f not in data]

        if missing_fields:
            self._send_json_response({
                'success': False,
                'error': f'Missing required fields: {missing_fields}'
            }, 400)
            return

        # Check if group is allowed
        group_name = data.get('group_name', '')
        if self.allowed_groups and group_name not in self.allowed_groups:
            self._send_json_response({
                'success': False,
                'error': f'Group not in allowed list: {group_name}'
            }, 403)
            return

        # Parse the message to get preview
        parsed_preview = ""
        total_value = 0
        entry_count = 0

        if self.parser_callback:
            try:
                parse_result = self.parser_callback(data['message'])
                if parse_result:
                    parsed_preview = parse_result.get('preview', '')
                    total_value = parse_result.get('total_value', 0)
                    entry_count = parse_result.get('entry_count', 0)
            except Exception as e:
                print(f"Parser error: {e}")
                parsed_preview = f"Parse error: {e}"

        # Create pending entry
        entry = PendingEntry(
            id=None,
            sender_name=data['sender_name'],
            sender_phone=data.get('sender_phone', ''),
            group_name=group_name,
            raw_message=data['message'],
            parsed_preview=parsed_preview,
            customer_name=data.get('mapped_customer', data['sender_name']),
            bazar=data.get('default_bazar', ''),
            edited_content='',
            status=PendingStatus.PENDING,
            received_at=datetime.now(),
            total_value=total_value,
            entry_count=entry_count
        )

        # Add to queue
        if self.pending_queue:
            entry_id = self.pending_queue.add_entry(entry)

            # Notify callback
            if self.on_message_callback:
                try:
                    self.on_message_callback(entry)
                except Exception as e:
                    print(f"Callback error: {e}")

            self._send_json_response({
                'success': True,
                'entry_id': entry_id,
                'message': 'Message queued for approval',
                'parsed_preview': parsed_preview,
                'total_value': total_value,
                'entry_count': entry_count
            })
        else:
            self._send_json_response({
                'success': False,
                'error': 'Queue not initialized'
            }, 500)

    def _handle_batch(self, data: Dict):
        """Handle batch of messages"""
        messages = data.get('messages', [])

        if not messages:
            self._send_json_response({
                'success': False,
                'error': 'No messages provided'
            }, 400)
            return

        results = []
        for msg in messages:
            try:
                # Process each message
                parsed_preview = ""
                total_value = 0
                entry_count = 0

                if self.parser_callback:
                    try:
                        parse_result = self.parser_callback(msg.get('message', ''))
                        if parse_result:
                            parsed_preview = parse_result.get('preview', '')
                            total_value = parse_result.get('total_value', 0)
                            entry_count = parse_result.get('entry_count', 0)
                    except Exception:
                        pass

                entry = PendingEntry(
                    id=None,
                    sender_name=msg.get('sender_name', 'Unknown'),
                    sender_phone=msg.get('sender_phone', ''),
                    group_name=msg.get('group_name', ''),
                    raw_message=msg.get('message', ''),
                    parsed_preview=parsed_preview,
                    customer_name=msg.get('sender_name', 'Unknown'),
                    bazar='',
                    edited_content='',
                    status=PendingStatus.PENDING,
                    received_at=datetime.now(),
                    total_value=total_value,
                    entry_count=entry_count
                )

                if self.pending_queue:
                    entry_id = self.pending_queue.add_entry(entry)
                    results.append({'success': True, 'entry_id': entry_id})
                else:
                    results.append({'success': False, 'error': 'Queue not initialized'})

            except Exception as e:
                results.append({'success': False, 'error': str(e)})

        self._send_json_response({
            'success': True,
            'processed': len(results),
            'results': results
        })


class WhatsAppServer:
    """WhatsApp Notification Server Manager"""

    def __init__(self, host: str = '0.0.0.0', port: int = 8765, db_path: str = "./data/rickymama.db"):
        self.host = host
        self.port = port
        self.db_path = db_path
        self.server: Optional[HTTPServer] = None
        self.server_thread: Optional[threading.Thread] = None
        self.running = False

        # Initialize queue manager
        self.pending_queue = PendingQueueManager(db_path)

        # Configuration
        self.allowed_groups: List[str] = []
        self.parser_callback: Optional[Callable] = None
        self.on_message_callback: Optional[Callable] = None

    def set_allowed_groups(self, groups: List[str]):
        """Set list of allowed WhatsApp groups"""
        self.allowed_groups = groups
        WhatsAppRequestHandler.allowed_groups = groups

    def set_parser_callback(self, callback: Callable):
        """Set callback for parsing messages"""
        self.parser_callback = callback
        WhatsAppRequestHandler.parser_callback = callback

    def set_message_callback(self, callback: Callable):
        """Set callback for when new message is received"""
        self.on_message_callback = callback
        WhatsAppRequestHandler.on_message_callback = callback

    def get_local_ip(self) -> str:
        """Get local IP address for display"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    def start(self) -> bool:
        """Start the HTTP server in a background thread"""
        if self.running:
            print("Server already running")
            return False

        try:
            # Set class-level references
            WhatsAppRequestHandler.pending_queue = self.pending_queue
            WhatsAppRequestHandler.parser_callback = self.parser_callback
            WhatsAppRequestHandler.allowed_groups = self.allowed_groups
            WhatsAppRequestHandler.on_message_callback = self.on_message_callback

            self.server = HTTPServer((self.host, self.port), WhatsAppRequestHandler)
            self.running = True

            # Start server in background thread
            self.server_thread = threading.Thread(target=self._run_server, daemon=True)
            self.server_thread.start()

            local_ip = self.get_local_ip()
            print(f"WhatsApp Server started at http://{local_ip}:{self.port}")
            print(f"Android app should POST to: http://{local_ip}:{self.port}/message")

            return True

        except Exception as e:
            print(f"Failed to start server: {e}")
            self.running = False
            return False

    def _run_server(self):
        """Run the server (called in background thread)"""
        try:
            self.server.serve_forever()
        except Exception as e:
            print(f"Server error: {e}")
        finally:
            self.running = False

    def stop(self):
        """Stop the HTTP server"""
        if self.server:
            self.server.shutdown()
            self.running = False
            print("WhatsApp Server stopped")

    def is_running(self) -> bool:
        """Check if server is running"""
        return self.running

    def get_pending_entries(self) -> List[PendingEntry]:
        """Get all pending entries"""
        return self.pending_queue.get_pending_entries()

    def get_pending_count(self) -> int:
        """Get count of pending entries"""
        return self.pending_queue.get_pending_count()

    def approve_entry(self, entry_id: int) -> bool:
        """Approve a pending entry"""
        return self.pending_queue.approve_entry(entry_id)

    def reject_entry(self, entry_id: int) -> bool:
        """Reject a pending entry"""
        return self.pending_queue.reject_entry(entry_id)

    def update_entry(self, entry_id: int, **kwargs) -> bool:
        """Update entry fields"""
        return self.pending_queue.update_entry(entry_id, **kwargs)

    def delete_entry(self, entry_id: int) -> bool:
        """Delete an entry"""
        return self.pending_queue.delete_entry(entry_id)

    def get_entry_by_id(self, entry_id: int) -> Optional[PendingEntry]:
        """Get entry by ID"""
        return self.pending_queue.get_entry_by_id(entry_id)


# Convenience function to create parser callback
def create_parser_callback(mixed_parser, calc_engine):
    """Create parser callback for WhatsApp server"""

    def parse_message(message: str) -> Dict[str, Any]:
        """Parse message and return preview info"""
        try:
            parsed_result = mixed_parser.parse(message)

            if parsed_result.is_empty:
                return {
                    'preview': 'No valid entries detected',
                    'total_value': 0,
                    'entry_count': 0
                }

            # Calculate totals
            calc_result = calc_engine.calculate_total(parsed_result)

            # Count entries
            entry_count = (
                len(parsed_result.pana_entries or []) +
                len(parsed_result.type_entries or []) +
                len(parsed_result.time_entries or []) +
                len(parsed_result.multi_entries or []) +
                len(getattr(parsed_result, 'direct_entries', []) or []) +
                len(getattr(parsed_result, 'jodi_entries', []) or []) +
                len(getattr(parsed_result, 'family_pana_entries', []) or [])
            )

            # Build preview
            preview_parts = []

            if parsed_result.pana_entries:
                preview_parts.append(f"PANA: {len(parsed_result.pana_entries)} entries")

            if parsed_result.type_entries:
                preview_parts.append(f"TYPE: {len(parsed_result.type_entries)} entries")

            if parsed_result.time_entries:
                preview_parts.append(f"TIME: {len(parsed_result.time_entries)} entries")

            if getattr(parsed_result, 'jodi_entries', None):
                preview_parts.append(f"JODI: {len(parsed_result.jodi_entries)} entries")

            if parsed_result.multi_entries:
                preview_parts.append(f"MULTI: {len(parsed_result.multi_entries)} entries")

            if getattr(parsed_result, 'family_pana_entries', None):
                preview_parts.append(f"FAMILY: {len(parsed_result.family_pana_entries)} entries")

            preview = " | ".join(preview_parts)
            total_value = getattr(calc_result, 'grand_total', 0)

            return {
                'preview': preview,
                'total_value': total_value,
                'entry_count': entry_count
            }

        except Exception as e:
            return {
                'preview': f'Parse error: {str(e)}',
                'total_value': 0,
                'entry_count': 0
            }

    return parse_message


# Test/demo function
if __name__ == '__main__':
    print("Starting WhatsApp Server in standalone mode...")

    server = WhatsAppServer(port=8765)

    # Set allowed groups (empty = allow all)
    server.set_allowed_groups([])

    if server.start():
        print("\nServer endpoints:")
        print(f"  POST /message - Submit WhatsApp message")
        print(f"  POST /batch - Submit multiple messages")
        print(f"  GET /status - Server status")
        print(f"  GET /pending - Get pending entries")
        print(f"  POST /ping - Ping test")
        print("\nPress Ctrl+C to stop...")

        try:
            while True:
                import time
                time.sleep(1)
        except KeyboardInterrupt:
            server.stop()
            print("\nServer stopped")
