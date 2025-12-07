"""
GUI Integration for WhatsApp Pending Entries
Adds WhatsApp approval panel to DearPyGUI dashboard
"""

import dearpygui.dearpygui as dpg
from datetime import datetime
from typing import Callable, Optional, List, Dict, Any
import threading
import time

from .server import WhatsAppServer, create_parser_callback
from .pending_queue import PendingEntry, PendingStatus


class WhatsAppGUIPanel:
    """
    WhatsApp pending entries panel for DearPyGUI dashboard.
    Displays incoming WhatsApp messages for approval/editing before database insertion.
    """

    def __init__(self, db_manager=None, on_approve_callback: Callable = None):
        self.db_manager = db_manager
        self.on_approve_callback = on_approve_callback
        self.server: Optional[WhatsAppServer] = None
        self.refresh_timer = None
        self.is_panel_visible = False

        # Configuration
        self.allowed_groups: List[str] = []
        self.customer_mapping: Dict[str, str] = {}  # sender_name -> customer_name
        self.default_bazar = ""

        # UI state
        self.selected_entry_id: Optional[int] = None
        self.pending_entries: List[PendingEntry] = []

    def setup_server(self, host: str = '0.0.0.0', port: int = 8765,
                     parser=None, calc_engine=None) -> bool:
        """Initialize and start the WhatsApp server"""
        try:
            db_path = self.db_manager.db_path if self.db_manager else "./data/rickymama.db"
            self.server = WhatsAppServer(host=host, port=port, db_path=db_path)

            # Set allowed groups
            if self.allowed_groups:
                self.server.set_allowed_groups(self.allowed_groups)

            # Set parser callback
            if parser and calc_engine:
                callback = create_parser_callback(parser, calc_engine)
                self.server.set_parser_callback(callback)

            # Set message callback for real-time updates
            self.server.set_message_callback(self._on_new_message)

            # Start server
            return self.server.start()

        except Exception as e:
            print(f"Failed to setup WhatsApp server: {e}")
            return False

    def stop_server(self):
        """Stop the WhatsApp server"""
        if self.server:
            self.server.stop()

    def _on_new_message(self, entry: PendingEntry):
        """Callback when new WhatsApp message arrives"""
        # Apply customer mapping if available
        if entry.sender_name in self.customer_mapping:
            entry.customer_name = self.customer_mapping[entry.sender_name]

        # Set default bazar if available
        if self.default_bazar and not entry.bazar:
            entry.bazar = self.default_bazar

        # Schedule UI refresh (thread-safe)
        if dpg.is_dearpygui_running():
            dpg.set_value("whatsapp_pending_count",
                          f"Pending: {self.server.get_pending_count()}")
            self._refresh_entries_list()

    def create_panel(self, parent_window: str = None):
        """Create the WhatsApp panel UI"""

        # Main WhatsApp panel window
        with dpg.window(label="WhatsApp Integration", tag="whatsapp_panel",
                        width=500, height=600, show=False, pos=[50, 50]):

            # Header with server status
            with dpg.group(horizontal=True):
                dpg.add_text("Server Status:", color=(150, 150, 150))
                dpg.add_text("Stopped", tag="server_status_text", color=(255, 100, 100))
                dpg.add_spacer(width=20)
                dpg.add_text("Pending: 0", tag="whatsapp_pending_count")

            dpg.add_separator()

            # Server controls
            with dpg.collapsing_header(label="Server Settings", default_open=False):
                with dpg.group(horizontal=True):
                    dpg.add_input_text(label="Port", tag="server_port_input",
                                       default_value="8765", width=100)
                    dpg.add_button(label="Start Server", tag="start_server_btn",
                                   callback=self._start_server_callback)
                    dpg.add_button(label="Stop Server", tag="stop_server_btn",
                                   callback=self._stop_server_callback, enabled=False)

                dpg.add_spacer(height=5)

                # Display IP address
                dpg.add_text("Server Address:", color=(150, 150, 150))
                dpg.add_text("Not started", tag="server_address_text")

                dpg.add_spacer(height=5)

                # Allowed groups configuration
                dpg.add_input_text(label="Allowed Groups (comma separated)",
                                   tag="allowed_groups_input",
                                   multiline=False, width=-1,
                                   hint="Leave empty to allow all groups")

                # Customer mapping
                dpg.add_input_text(label="Customer Mapping (sender=customer,)",
                                   tag="customer_mapping_input",
                                   multiline=True, width=-1, height=60,
                                   hint="john=John Doe,alice=Alice Smith")

            dpg.add_separator()

            # Pending entries list
            dpg.add_text("Pending WhatsApp Messages", color=(100, 200, 255))
            dpg.add_spacer(height=5)

            # Entries table
            with dpg.child_window(tag="entries_list_container", height=200,
                                  border=True, horizontal_scrollbar=True):
                dpg.add_text("No pending entries", tag="no_entries_text")

            dpg.add_spacer(height=5)

            # Action buttons for entries list
            with dpg.group(horizontal=True):
                dpg.add_button(label="Refresh", callback=self._refresh_entries_list)
                dpg.add_button(label="Approve Selected", tag="approve_btn",
                               callback=self._approve_selected, enabled=False)
                dpg.add_button(label="Reject Selected", tag="reject_btn",
                               callback=self._reject_selected, enabled=False)
                dpg.add_button(label="Delete Selected", tag="delete_btn",
                               callback=self._delete_selected, enabled=False)

            dpg.add_separator()

            # Entry detail/edit section
            dpg.add_text("Entry Details", color=(100, 200, 255))

            with dpg.child_window(tag="entry_detail_container", height=200, border=True):
                dpg.add_text("Select an entry to view details", tag="entry_detail_placeholder")

                # Hidden detail fields (shown when entry selected)
                with dpg.group(tag="entry_detail_group", show=False):
                    dpg.add_text("", tag="detail_sender")
                    dpg.add_text("", tag="detail_group")
                    dpg.add_text("", tag="detail_time")

                    dpg.add_spacer(height=5)
                    dpg.add_text("Original Message:", color=(150, 150, 150))
                    dpg.add_input_text(tag="detail_raw_message", multiline=True,
                                       width=-1, height=40, readonly=True)

                    dpg.add_spacer(height=5)
                    dpg.add_text("Parsed Preview:", color=(150, 150, 150))
                    dpg.add_text("", tag="detail_preview", wrap=450)

                    dpg.add_spacer(height=5)
                    dpg.add_text("Edit Content (optional):", color=(150, 150, 150))
                    dpg.add_input_text(tag="detail_edited_content", multiline=True,
                                       width=-1, height=60,
                                       hint="Edit the message content before approval")

                    dpg.add_spacer(height=5)
                    with dpg.group(horizontal=True):
                        dpg.add_combo(label="Customer", tag="detail_customer_combo",
                                      items=[], width=150)
                        dpg.add_combo(label="Bazar", tag="detail_bazar_combo",
                                      items=[], width=150)

                    dpg.add_spacer(height=5)
                    with dpg.group(horizontal=True):
                        dpg.add_text("Total Value: ", color=(150, 150, 150))
                        dpg.add_text("0", tag="detail_total_value", color=(100, 255, 100))
                        dpg.add_spacer(width=20)
                        dpg.add_text("Entries: ", color=(150, 150, 150))
                        dpg.add_text("0", tag="detail_entry_count")

            dpg.add_spacer(height=5)

            # Quick approve with current settings
            with dpg.group(horizontal=True):
                dpg.add_button(label="Save Changes", tag="save_changes_btn",
                               callback=self._save_entry_changes, enabled=False)
                dpg.add_button(label="Approve & Insert", tag="approve_insert_btn",
                               callback=self._approve_and_insert, enabled=False)

        # Create toggle button for main toolbar
        return "whatsapp_panel"

    def create_toolbar_button(self, parent: str):
        """Create WhatsApp toggle button for main toolbar"""
        with dpg.group(horizontal=True, parent=parent):
            dpg.add_button(label="WhatsApp", tag="whatsapp_toggle_btn",
                           callback=self._toggle_panel)
            dpg.add_text("0", tag="whatsapp_badge", color=(255, 100, 100))

    def _toggle_panel(self):
        """Toggle WhatsApp panel visibility"""
        self.is_panel_visible = not self.is_panel_visible
        dpg.configure_item("whatsapp_panel", show=self.is_panel_visible)

        if self.is_panel_visible:
            self._refresh_entries_list()
            self._update_combos()

    def _update_combos(self):
        """Update customer and bazar combo boxes"""
        if self.db_manager:
            try:
                customers = self.db_manager.get_all_customers()
                customer_names = [c["name"] for c in customers]
                dpg.configure_item("detail_customer_combo", items=customer_names)

                bazars = self.db_manager.get_all_bazars()
                bazar_names = [b["name"] for b in bazars]
                dpg.configure_item("detail_bazar_combo", items=bazar_names)

                if bazar_names and not self.default_bazar:
                    self.default_bazar = bazar_names[0]
            except Exception as e:
                print(f"Error updating combos: {e}")

    def _start_server_callback(self):
        """Start server button callback"""
        try:
            port = int(dpg.get_value("server_port_input"))

            # Parse allowed groups
            groups_text = dpg.get_value("allowed_groups_input").strip()
            if groups_text:
                self.allowed_groups = [g.strip() for g in groups_text.split(",") if g.strip()]

            # Parse customer mapping
            mapping_text = dpg.get_value("customer_mapping_input").strip()
            if mapping_text:
                for mapping in mapping_text.split(","):
                    if "=" in mapping:
                        sender, customer = mapping.split("=", 1)
                        self.customer_mapping[sender.strip()] = customer.strip()

            # Get parser and calc engine
            parser = None
            calc_engine = None
            try:
                from ..parsing.parser_adapter import MixedInputParser, TypeTableLoader
                from ..business.calculation_engine import CalculationEngine

                parser = MixedInputParser()
                if self.db_manager:
                    table_loader = TypeTableLoader(self.db_manager)
                    sp_table, dp_table, cp_table = table_loader.load_all_tables()
                    family_pana_table = table_loader.load_family_pana_table()
                    calc_engine = CalculationEngine(sp_table, dp_table, cp_table, family_pana_table)
                else:
                    calc_engine = CalculationEngine()
            except ImportError as e:
                print(f"Parser import error: {e}")

            if self.setup_server(port=port, parser=parser, calc_engine=calc_engine):
                dpg.set_value("server_status_text", "Running")
                dpg.configure_item("server_status_text", color=(100, 255, 100))
                dpg.configure_item("start_server_btn", enabled=False)
                dpg.configure_item("stop_server_btn", enabled=True)

                ip = self.server.get_local_ip()
                dpg.set_value("server_address_text", f"http://{ip}:{port}/message")
            else:
                dpg.set_value("server_status_text", "Failed to start")
                dpg.configure_item("server_status_text", color=(255, 100, 100))

        except Exception as e:
            print(f"Server start error: {e}")
            dpg.set_value("server_status_text", f"Error: {e}")

    def _stop_server_callback(self):
        """Stop server button callback"""
        self.stop_server()
        dpg.set_value("server_status_text", "Stopped")
        dpg.configure_item("server_status_text", color=(255, 100, 100))
        dpg.configure_item("start_server_btn", enabled=True)
        dpg.configure_item("stop_server_btn", enabled=False)
        dpg.set_value("server_address_text", "Not started")

    def _refresh_entries_list(self):
        """Refresh the pending entries list"""
        if not self.server:
            return

        self.pending_entries = self.server.get_pending_entries()

        # Update badge
        count = len(self.pending_entries)
        dpg.set_value("whatsapp_badge", str(count))
        dpg.set_value("whatsapp_pending_count", f"Pending: {count}")

        # Clear existing entries
        if dpg.does_item_exist("entries_table"):
            dpg.delete_item("entries_table")

        # Show/hide no entries text
        if not self.pending_entries:
            dpg.configure_item("no_entries_text", show=True)
            self._clear_selection()
            return

        dpg.configure_item("no_entries_text", show=False)

        # Create entries table
        with dpg.table(tag="entries_table", parent="entries_list_container",
                       header_row=True, borders_innerH=True, borders_outerH=True,
                       borders_innerV=True, borders_outerV=True, row_background=True,
                       scrollY=True, scrollX=True):

            dpg.add_table_column(label="ID", width_fixed=True, init_width_or_weight=40)
            dpg.add_table_column(label="Sender", width_fixed=True, init_width_or_weight=100)
            dpg.add_table_column(label="Preview", width_stretch=True)
            dpg.add_table_column(label="Value", width_fixed=True, init_width_or_weight=70)
            dpg.add_table_column(label="Time", width_fixed=True, init_width_or_weight=80)

            for entry in self.pending_entries:
                with dpg.table_row():
                    # Make row selectable
                    dpg.add_selectable(label=str(entry.id), span_columns=False,
                                       callback=lambda s, a, u: self._select_entry(u),
                                       user_data=entry.id)
                    dpg.add_text(entry.sender_name[:15])
                    dpg.add_text(entry.parsed_preview[:30] + "..." if len(entry.parsed_preview) > 30 else entry.parsed_preview)
                    dpg.add_text(f"{entry.total_value:,}")
                    dpg.add_text(entry.received_at.strftime("%H:%M"))

    def _select_entry(self, entry_id: int):
        """Handle entry selection"""
        self.selected_entry_id = entry_id
        entry = self.server.get_entry_by_id(entry_id)

        if not entry:
            self._clear_selection()
            return

        # Enable action buttons
        dpg.configure_item("approve_btn", enabled=True)
        dpg.configure_item("reject_btn", enabled=True)
        dpg.configure_item("delete_btn", enabled=True)
        dpg.configure_item("save_changes_btn", enabled=True)
        dpg.configure_item("approve_insert_btn", enabled=True)

        # Show detail group
        dpg.configure_item("entry_detail_placeholder", show=False)
        dpg.configure_item("entry_detail_group", show=True)

        # Populate details
        dpg.set_value("detail_sender", f"From: {entry.sender_name} ({entry.sender_phone})")
        dpg.set_value("detail_group", f"Group: {entry.group_name}")
        dpg.set_value("detail_time", f"Received: {entry.received_at.strftime('%Y-%m-%d %H:%M:%S')}")
        dpg.set_value("detail_raw_message", entry.raw_message)
        dpg.set_value("detail_preview", entry.parsed_preview or "No preview available")
        dpg.set_value("detail_edited_content", entry.edited_content or "")
        dpg.set_value("detail_total_value", f"{entry.total_value:,}")
        dpg.set_value("detail_entry_count", str(entry.entry_count))

        # Set combo values
        if entry.customer_name:
            dpg.set_value("detail_customer_combo", entry.customer_name)
        if entry.bazar:
            dpg.set_value("detail_bazar_combo", entry.bazar)

    def _clear_selection(self):
        """Clear entry selection"""
        self.selected_entry_id = None
        dpg.configure_item("approve_btn", enabled=False)
        dpg.configure_item("reject_btn", enabled=False)
        dpg.configure_item("delete_btn", enabled=False)
        dpg.configure_item("save_changes_btn", enabled=False)
        dpg.configure_item("approve_insert_btn", enabled=False)

        dpg.configure_item("entry_detail_placeholder", show=True)
        dpg.configure_item("entry_detail_group", show=False)

    def _approve_selected(self):
        """Approve selected entry without inserting"""
        if self.selected_entry_id:
            self.server.approve_entry(self.selected_entry_id)
            self._refresh_entries_list()
            self._clear_selection()

    def _reject_selected(self):
        """Reject selected entry"""
        if self.selected_entry_id:
            self.server.reject_entry(self.selected_entry_id)
            self._refresh_entries_list()
            self._clear_selection()

    def _delete_selected(self):
        """Delete selected entry"""
        if self.selected_entry_id:
            self.server.delete_entry(self.selected_entry_id)
            self._refresh_entries_list()
            self._clear_selection()

    def _save_entry_changes(self):
        """Save changes to selected entry"""
        if not self.selected_entry_id:
            return

        edited_content = dpg.get_value("detail_edited_content")
        customer_name = dpg.get_value("detail_customer_combo")
        bazar = dpg.get_value("detail_bazar_combo")

        self.server.update_entry(
            self.selected_entry_id,
            edited_content=edited_content,
            customer_name=customer_name,
            bazar=bazar
        )

        self._refresh_entries_list()

    def _approve_and_insert(self):
        """Approve entry and insert into main database"""
        if not self.selected_entry_id:
            return

        entry = self.server.get_entry_by_id(self.selected_entry_id)
        if not entry:
            return

        # Get current values from UI
        customer_name = dpg.get_value("detail_customer_combo")
        bazar = dpg.get_value("detail_bazar_combo")
        edited_content = dpg.get_value("detail_edited_content")

        # Use edited content if provided, otherwise use original
        content_to_process = edited_content.strip() if edited_content.strip() else entry.raw_message

        # Call the approval callback with the data
        if self.on_approve_callback:
            try:
                result = self.on_approve_callback(
                    content=content_to_process,
                    customer_name=customer_name,
                    bazar=bazar,
                    source_entry=entry
                )

                if result.get('success', False):
                    # Mark as approved and remove from queue
                    self.server.approve_entry(self.selected_entry_id)
                    self._refresh_entries_list()
                    self._clear_selection()

                    # Show success message
                    print(f"Approved and inserted: {result.get('entries_count', 0)} entries, Total: {result.get('total_value', 0)}")
                else:
                    print(f"Approval failed: {result.get('error', 'Unknown error')}")

            except Exception as e:
                print(f"Approval callback error: {e}")
        else:
            # No callback - just approve
            self.server.approve_entry(self.selected_entry_id)
            self._refresh_entries_list()
            self._clear_selection()


def create_approval_callback(db_manager, parser, calc_engine):
    """
    Create approval callback that processes WhatsApp entries
    and inserts them into the main database.
    """

    def approve_and_insert(content: str, customer_name: str, bazar: str,
                           source_entry: PendingEntry) -> Dict[str, Any]:
        """Process approved WhatsApp entry and insert into database"""
        try:
            from ..business.calculation_engine import CalculationContext
            from datetime import date

            # Parse the content
            parsed_result = parser.parse(content)

            if parsed_result.is_empty:
                return {'success': False, 'error': 'No valid entries found'}

            # Get or create customer
            customer = db_manager.get_customer_by_name(customer_name)
            if customer:
                customer_id = customer['id']
            else:
                customer_id = db_manager.add_customer(customer_name)

            # Create calculation context
            calc_context = CalculationContext(
                customer_id=customer_id,
                customer_name=customer_name,
                entry_date=date.today(),
                bazar=bazar,
                source_data=parsed_result
            )

            # Calculate business totals
            business_calc = calc_engine.calculate(calc_context)

            # Save universal log entries to database
            total_entries = 0
            for entry in business_calc.universal_entries:
                db_manager.add_universal_log_entry({
                    'customer_id': entry.customer_id,
                    'customer_name': entry.customer_name,
                    'entry_date': entry.entry_date,
                    'bazar': entry.bazar,
                    'number': entry.number,
                    'value': entry.value,
                    'entry_type': entry.entry_type.value,
                    'source_line': f"[WhatsApp: {source_entry.sender_name}] {entry.source_line}"
                })
                total_entries += 1

            return {
                'success': True,
                'entries_count': total_entries,
                'total_value': business_calc.grand_total
            }

        except Exception as e:
            return {'success': False, 'error': str(e)}

    return approve_and_insert
