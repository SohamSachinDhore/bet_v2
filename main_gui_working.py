#!/usr/bin/env python3
"""Working Main GUI for RickyMama - Enhanced with Table Views and Date Support"""

import sys
import os
from pathlib import Path
import time
from datetime import datetime, date

# Add src directory to Python path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

import dearpygui.dearpygui as dpg

# Global variables
customers = []
bazars = []
db_manager = None
config_manager = None

def create_working_main_gui():
    """Create a working main GUI with all features"""
    global customers, bazars, db_manager, config_manager
    
    # Initialize database and config
    try:
        from src.database.db_manager import create_database_manager
        from src.config.config_manager import create_config_manager
        
        db_manager = create_database_manager()
        config_manager = create_config_manager()
        
        # Initialize database
        db_manager.initialize_database()
        
        print("✅ Database and config initialized")
        
        try:
            customers = [{"id": row["id"], "name": row["name"], 
                         "commission_type": row["commission_type"] if "commission_type" in row.keys() else "commission"} 
                        for row in db_manager.get_all_customers()]
            bazars = [{"name": row["name"], "display_name": row["display_name"]} 
                     for row in db_manager.get_all_bazars()]
        except Exception as e:
            print(f"Error loading the data ({e})")
            # Ensure fallback values are set
            customers = []
            bazars = []

    except Exception as e:
        print(f"⚠️ Database setup failed: {e}")
        print("🔄 Using fallback mode")
        db_manager = None
        config_manager = None
        customers = []
        bazars = []
    
    # Helper functions
    def get_customer_name_color(customer_name: str):
        """Get color for customer name based on commission type"""
        # Default to blue (commission)
        default_color = (52, 152, 219, 255)  # Blue
        
        try:
            # Find customer in the customers list
            for customer in customers:
                if customer['name'] == customer_name:
                    commission_type = customer.get('commission_type', 'commission')
                    if commission_type == 'commission':
                        return (52, 152, 219, 255)  # Blue
                    else:
                        return (230, 126, 34, 255)  # Orange
            
            # If not found in memory, try database
            if db_manager:
                customer_row = db_manager.get_customer_by_name(customer_name)
                if customer_row:
                    commission_type = customer_row['commission_type'] if 'commission_type' in customer_row.keys() else 'commission'
                    if commission_type == 'commission':
                        return (52, 152, 219, 255)  # Blue
                    else:
                        return (230, 126, 34, 255)  # Orange
        except Exception as e:
            print(f"Error getting customer color: {e}")
        
        return default_color
    
    # Callback functions
    
    def validate_input():
        """Validate and preview input using smart parser"""
        try:
            input_text = dpg.get_value("input_area")
            
            if not input_text.strip():
                dpg.set_value("validation_text", "Status: Ready")
                dpg.configure_item("preview_area", default_value="Enter data above to see preview...")
                return
            
            # Use advanced parsing system
            try:
                from src.business.data_processor import DataProcessor
                from src.business.calculation_engine import CalculationEngine
                from src.parsing.mixed_input_parser import MixedInputParser
                from datetime import date
                
                # Create processor with full parsing system
                processor = DataProcessor(db_manager)
                
                # Test parsing without saving
                from src.business.data_processor import ProcessingContext
                test_context = ProcessingContext(
                    customer_name=dpg.get_value("customer_combo"),
                    bazar=dpg.get_value("bazar_combo"),
                    entry_date=date.today(),
                    input_text=input_text,
                    validate_references=True,
                    auto_create_customer=False
                )
                
                # Parse input to get preview
                mixed_parser = processor.mixed_parser
                parsed_result = mixed_parser.parse(input_text)
                
                if not parsed_result.is_empty:
                    # Calculate totals
                    calc_engine = processor.calculation_engine
                    calc_result = calc_engine.calculate_total(parsed_result)
                    total_entries = (len(parsed_result.pana_entries or []) + 
                                   len(parsed_result.type_entries or []) + 
                                   len(parsed_result.time_entries or []) + 
                                   len(parsed_result.multi_entries or []) +
                                   len(parsed_result.direct_entries or []) +
                                   len(getattr(parsed_result, 'jodi_entries', []) or []))
                    
                    # Update validation status
                    dpg.set_value("validation_status", f"✓ {total_entries} entries detected")
                    
                    # Update calculated total
                    if hasattr(calc_result, 'grand_total'):
                        total_value = calc_result.grand_total
                    else:
                        # Calculate total from all components
                        total_value = (getattr(calc_result, 'pana_total', 0) + 
                                     getattr(calc_result, 'type_total', 0) + 
                                     getattr(calc_result, 'time_total', 0) + 
                                     getattr(calc_result, 'multi_total', 0) + 
                                     getattr(calc_result, 'direct_total', 0) + 
                                     getattr(calc_result, 'jodi_total', 0))
                    
                    dpg.set_value("calculated_total", f"₹{total_value:,}")
                    
                    # Enable breakdown button if there are entries
                    dpg.configure_item("breakdown_btn", enabled=total_entries > 0)
                    
                    # Create comprehensive detailed preview showing ALL entries
                    preview_lines = []
                    
                    if parsed_result.pana_entries:
                        preview_lines.append(f"[PANA] Entries ({len(parsed_result.pana_entries)}):")
                        # Group pana entries by value to show more efficiently
                        pana_by_value = {}
                        for entry in parsed_result.pana_entries:
                            if entry.value not in pana_by_value:
                                pana_by_value[entry.value] = []
                            pana_by_value[entry.value].append(entry.number)
                        
                        for value, numbers in pana_by_value.items():
                            numbers_str = ", ".join(map(str, sorted(numbers)))
                            if len(numbers) <= 8:  # Reduced from 10 to 8 for better line width
                                preview_lines.append(f"   {numbers_str} = ₹{value:,}")
                            else:
                                # Show first 8 and count
                                first_eight = ", ".join(map(str, sorted(numbers)[:8]))
                                preview_lines.append(f"   {first_eight}... (+{len(numbers)-8}) = ₹{value:,}")
                        
                        if hasattr(calc_result, 'pana_total') and calc_result.pana_total > 0:
                            preview_lines.append(f"   → Subtotal: ₹{calc_result.pana_total:,}")
                        preview_lines.append("")
                    
                    # Check for direct entries (new pattern type)
                    if hasattr(parsed_result, 'direct_entries') and parsed_result.direct_entries:
                        preview_lines.append(f"[DIRECT] Number Assignments ({len(parsed_result.direct_entries)}):")
                        # Group direct entries by value to show more efficiently
                        direct_by_value = {}
                        for entry in parsed_result.direct_entries:
                            if entry.value not in direct_by_value:
                                direct_by_value[entry.value] = []
                            direct_by_value[entry.value].append(entry.number)
                        
                        for value, numbers in direct_by_value.items():
                            numbers_str = ", ".join(map(str, sorted(numbers)))
                            if len(numbers) <= 8:  # Reduced for better line width
                                preview_lines.append(f"   {numbers_str} = ₹{value:,}")
                            else:
                                # Show first 8 and count
                                first_eight = ", ".join(map(str, sorted(numbers)[:8]))
                                preview_lines.append(f"   {first_eight}... (+{len(numbers)-8}) = ₹{value:,}")
                        
                        if hasattr(calc_result, 'direct_total') and calc_result.direct_total > 0:
                            preview_lines.append(f"   → Subtotal: ₹{calc_result.direct_total:,}")
                        preview_lines.append("")
                    
                    if parsed_result.type_entries:
                        preview_lines.append(f"[TYPE] Table Entries ({len(parsed_result.type_entries)}):")
                        # Group by table type
                        type_by_table = {}
                        for entry in parsed_result.type_entries:
                            if entry.table_type not in type_by_table:
                                type_by_table[entry.table_type] = []
                            type_by_table[entry.table_type].append(f"{entry.column}={entry.value}")
                        
                        for table_type, entries in type_by_table.items():
                            entries_str = ", ".join(entries[:10])  # Show up to 10 entries
                            if len(entries) > 10:
                                entries_str += f"... (+{len(entries)-10})"
                            preview_lines.append(f"   {table_type}: {entries_str}")
                        
                        if hasattr(calc_result, 'type_total') and calc_result.type_total > 0:
                            preview_lines.append(f"   → Subtotal: ₹{calc_result.type_total:,}")
                        preview_lines.append("")
                    
                    if parsed_result.time_entries:
                        preview_lines.append(f"[TIME] Column Assignments ({len(parsed_result.time_entries)}):")
                        for entry in parsed_result.time_entries:
                            columns_str = " ".join(map(str, sorted(entry.columns)))
                            preview_lines.append(f"   Columns {columns_str} = ₹{entry.value:,}")
                        
                        if hasattr(calc_result, 'time_total') and calc_result.time_total > 0:
                            preview_lines.append(f"   → Subtotal: ₹{calc_result.time_total:,}")
                        preview_lines.append("")
                    
                    # Check for jodi entries (new pattern type)
                    if hasattr(parsed_result, 'jodi_entries') and parsed_result.jodi_entries:
                        preview_lines.append(f"[JODI] Jodi Numbers ({len(parsed_result.jodi_entries)}):")
                        for entry in parsed_result.jodi_entries:
                            jodi_numbers_str = "-".join(map(str, entry.jodi_numbers))
                            if len(jodi_numbers_str) > 50:  # Truncate if too long
                                jodi_numbers_str = jodi_numbers_str[:50] + "..."
                            preview_lines.append(f"   {jodi_numbers_str} = ₹{entry.value:,}")
                            preview_lines.append(f"   → {len(entry.jodi_numbers)} jodi numbers × ₹{entry.value:,} = ₹{len(entry.jodi_numbers) * entry.value:,}")
                        
                        if hasattr(calc_result, 'jodi_total') and calc_result.jodi_total > 0:
                            preview_lines.append(f"   → Subtotal: ₹{calc_result.jodi_total:,}")
                        preview_lines.append("")
                    
                    if parsed_result.multi_entries:
                        preview_lines.append(f"[MULTI] Multiplication Entries ({len(parsed_result.multi_entries)}):")
                        # Group by value to show more efficiently
                        multi_by_value = {}
                        for entry in parsed_result.multi_entries:
                            if entry.value not in multi_by_value:
                                multi_by_value[entry.value] = []
                            multi_by_value[entry.value].append(f"{entry.number:02d}")
                        
                        for value, numbers in multi_by_value.items():
                            numbers_str = ", ".join(numbers[:12])  # Show up to 12 entries
                            if len(numbers) > 12:
                                numbers_str += f"... (+{len(numbers)-12})"
                            preview_lines.append(f"   {numbers_str} × ₹{value:,}")
                        
                        if hasattr(calc_result, 'multi_total') and calc_result.multi_total > 0:
                            preview_lines.append(f"   → Subtotal: ₹{calc_result.multi_total:,}")
                        preview_lines.append("")
                    
                    # Add grand total summary
                    preview_lines.append("=" * 40)
                    preview_lines.append(f"GRAND TOTAL: ₹{total_value:,}")
                    preview_lines.append(f"Total Entries: {total_entries}")
                    
                    preview_text = "\\n".join(preview_lines)
                    dpg.configure_item("preview_area", default_value=preview_text)
                else:
                    dpg.set_value("validation_text", "Status: No valid entries found")
                    dpg.configure_item("preview_area", default_value="No valid data format detected")
                    
            except ImportError as ie:
                # Fallback to simple parsing
                lines = [line.strip() for line in input_text.split('\n') if line.strip()]
                
                if lines:
                    dpg.set_value("validation_text", f"Status: {len(lines)} lines detected")
                    
                    # Create preview
                    preview = f"Preview - {len(lines)} data entries:\\n"
                    for i, line in enumerate(lines[:5]):
                        preview += f"{i+1}. {line[:60]}{'...' if len(line) > 60 else ''}\\n"
                    
                    if len(lines) > 5:
                        preview += f"... and {len(lines) - 5} more lines"
                    
                    dpg.configure_item("preview_area", default_value=preview)
                else:
                    dpg.set_value("validation_text", "Status: No valid data")
                    dpg.configure_item("preview_area", default_value="No valid data detected")
                
        except Exception as e:
            dpg.set_value("validation_text", f"Status: Error - {e}")
    
    def on_input_change():
        """Handle input text changes"""
        validate_input()
    
    def submit_data():
        """Submit data to database"""
        global customers
        try:
            input_text = dpg.get_value("input_area")
            customer_name = dpg.get_value("customer_combo")
            bazar_name = dpg.get_value("bazar_combo")
            
            if not input_text.strip():
                dpg.set_value("status_text", "Error: No data to submit")
                return
            
            lines = [line.strip() for line in input_text.split('\n') if line.strip()]
            
            if db_manager:
                try:
                    # Get or create customer
                    customer = next((c for c in customers if c["name"] == customer_name), None)
                    if customer:
                        customer_id = customer["id"]
                    else:
                        customer_id = db_manager.add_customer(customer_name)
                        customers.append({"id": customer_id, "name": customer_name})
                    
                    # Parse input using advanced parsing system
                    try:
                        from src.business.data_processor import DataProcessor
                        from datetime import date
                        
                        # Create processor with full parsing system
                        processor = DataProcessor(db_manager)
                        
                        # Create processing context
                        # Get date from date display field
                        date_str = dpg.get_value("date_display")
                        try:
                            entry_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                        except:
                            entry_date = date.today()
                        
                        from src.business.data_processor import ProcessingContext
                        context = ProcessingContext(
                            customer_name=customer_name,
                            bazar=bazar_name,
                            entry_date=entry_date,
                            input_text=input_text,
                            validate_references=True,
                            auto_create_customer=True
                        )
                        
                        # Process the input
                        result = processor.process_mixed_input(context)
                        
                        if result.success:
                            total_entries = result.pana_count + result.type_count + result.time_count + result.multi_count + result.direct_count + getattr(result, 'jodi_count', 0)
                            total_value = result.total_value or 0
                            
                            dpg.set_value("status_text", f"✅ Success: {total_entries} entries saved! Total: ₹{total_value:.2f}")
                            
                            # Update last entry timestamp
                            now = datetime.now()
                            dpg.set_value("last_entry_text", f"Last Entry: {now.strftime('%d-%m-%Y %H:%M')}")
                            
                            # Refresh table window if open, and refresh data for next time tables are opened
                            if dpg.does_item_exist("table_window"):
                                refresh_customers_table()
                                refresh_universal_table()
                                refresh_pana_table()
                                refresh_time_table()
                                refresh_jodi_table()
                                refresh_summary_table()
                            
                            # Also refresh customer list for the dropdown
                            try:
                                customers = db_manager.get_all_customers()
                                customer_names = [c["name"] for c in customers]
                                dpg.configure_item("customer_combo", items=customer_names)
                            except:
                                pass
                        else:
                            error_message = f"❌ Processing failed: {result.error_message}"
                            if result.validation_errors:
                                error_message += f"\nValidation errors: {', '.join(result.validation_errors)}"
                            dpg.set_value("status_text", error_message)
                            return
                        
                    except ImportError as ie:
                        # Fallback to simple processing
                        entries_saved = 0
                        for i, line in enumerate(lines):
                            entry_data = {
                                'customer_id': customer_id,
                                'customer_name': customer_name,
                                'entry_date': datetime.now().strftime('%Y-%m-%d'),
                                'bazar': bazar_name,
                                'number': 100 + i,  # Simple number assignment
                                'value': len(line.split()) * 10,  # Simple value calculation
                                'entry_type': 'PANA',  # Use valid entry type
                                'source_line': line
                            }
                            
                            db_manager.add_universal_log_entry(entry_data)
                            entries_saved += 1
                        
                        dpg.set_value("status_text", f"Success: {entries_saved} entries saved (simple mode)!")
                    
                    # Clear input
                    dpg.set_value("input_area", "")
                    validate_input()
                    
                except Exception as e:
                    dpg.set_value("status_text", f"Database error: {e}")
            else:
                # Mock save
                dpg.set_value("status_text", f"Mock: {len(lines)} entries for {customer_name}")
                
        except Exception as e:
            dpg.set_value("status_text", f"Submit error: {e}")
    
    def clear_data():
        """Clear all data"""
        dpg.set_value("input_area", "")
        validate_input()
        dpg.set_value("status_text", "Data cleared")
    
    def add_customer():
        """Add new customer"""
        if dpg.does_item_exist("add_customer_window"):
            dpg.delete_item("add_customer_window")
        
        with dpg.window(
            label="Add Customer",
            tag="add_customer_window",
            modal=True,
            width=350,
            height=180,
            pos=[400, 300]
        ):
            dpg.add_input_text(label="Name", tag="new_customer_input", width=-1)
            dpg.add_spacer(height=10)
            
            dpg.add_text("Customer Type:")
            dpg.add_radio_button(
                items=["Commission", "Non-Commission"],
                tag="new_customer_type",
                default_value="Commission",
                horizontal=True
            )
            dpg.add_spacer(height=10)
            
            with dpg.group(horizontal=True):
                dpg.add_button(label="Add", callback=confirm_add_customer, width=100)
                dpg.add_button(label="Cancel", callback=lambda: dpg.delete_item("add_customer_window"), width=100)
    
    def confirm_add_customer():
        """Confirm customer addition"""
        try:
            name = dpg.get_value("new_customer_input").strip()
            if not name:
                dpg.set_value("status_text", "Error: Name cannot be empty")
                return
            
            if any(c["name"].lower() == name.lower() for c in customers):
                dpg.set_value("status_text", "Error: Customer already exists")
                return
            
            # Get commission type
            customer_type = dpg.get_value("new_customer_type")
            commission_type = "commission" if customer_type == "Commission" else "non_commission"
            
            if db_manager:
                customer_id = db_manager.add_customer(name, commission_type)
            else:
                customer_id = len(customers) + 1
            
            customers.append({"id": customer_id, "name": name, "commission_type": commission_type})
            
            # Update combo
            customer_names = [c["name"] for c in customers]
            dpg.configure_item("customer_combo", items=customer_names, default_value=name)
            
            dpg.delete_item("add_customer_window")
            dpg.set_value("status_text", f"Customer '{name}' ({customer_type}) added")
            
        except Exception as e:
            dpg.set_value("status_text", f"Add error: {e}")
    
    def on_customer_selected(sender, app_data, user_data):
        """Handle customer selection from dropdown"""
        customer_name = app_data
        
        if customer_name == "No Customers":
            return
        
        # Find customer ID and auto-fill
        for customer in customers:
            if customer['name'] == customer_name:
                dpg.set_value("customer_id_input", str(customer['id']))
                break
        
        dpg.set_value("status_text", f"Selected customer: {customer_name}")
    
    def on_customer_id_entered(sender, app_data, user_data):
        """Handle customer ID entry"""
        try:
            customer_id = int(app_data) if app_data else None
            
            if customer_id is None:
                return
            
            # Find customer by ID and auto-fill name
            for customer in customers:
                if customer['id'] == customer_id:
                    dpg.set_value("customer_combo", customer['name'])
                    dpg.set_value("status_text", f"Selected customer: {customer['name']}")
                    return
            
            # Customer ID not found
            dpg.set_value("status_text", f"Customer ID {customer_id} not found")
            
        except ValueError:
            dpg.set_value("status_text", "Invalid customer ID format")
    
    def on_date_changed(sender, app_data, user_data):
        """Handle date change"""
        try:
            date_dict = app_data
            selected_date = date(
                year=date_dict['year'],
                month=date_dict['month'] + 1,  # Convert from 0-based to 1-based
                day=date_dict['month_day']
            )
            dpg.set_value("status_text", f"Date set to: {selected_date.strftime('%d-%m-%Y')}")
            
        except Exception as e:
            dpg.set_value("status_text", f"Invalid date: {e}")
    
    def apply_date_change():
        """Apply the selected date from picker to display"""
        try:
            date_dict = dpg.get_value("entry_date")
            selected_date = date(
                year=date_dict['year'],
                month=date_dict['month'] + 1,  # Convert from 0-based to 1-based
                day=date_dict['month_day']
            )
            # Update the display field
            dpg.set_value("date_display", selected_date.strftime("%Y-%m-%d"))
            # Close the popup
            dpg.configure_item("date_picker_popup", show=False)
            # Update status
            dpg.set_value("status_text", f"Date changed to: {selected_date.strftime('%d-%m-%Y')}")
            
        except Exception as e:
            dpg.set_value("status_text", f"Error applying date: {e}")
    
    def apply_pana_date_change():
        """Apply the selected date from pana date picker"""
        try:
            date_dict = dpg.get_value("pana_date_filter")
            selected_date = date(
                year=date_dict['year'],
                month=date_dict['month'] + 1,
                day=date_dict['month_day']
            )
            dpg.set_value("pana_date_display", selected_date.strftime("%Y-%m-%d"))
            dpg.configure_item("pana_date_picker_popup", show=False)
            refresh_pana_table()
        except Exception as e:
            dpg.set_value("status_text", f"Error applying pana date: {e}")
    
    def set_pana_date_today():
        """Set pana date to today"""
        today = date.today()
        dpg.set_value("pana_date_display", today.strftime("%Y-%m-%d"))
        dpg.set_value("pana_date_filter", {
            'month_day': today.day,
            'month': today.month - 1,
            'year': today.year
        })
        dpg.configure_item("pana_date_picker_popup", show=False)
        refresh_pana_table()
    
    def apply_time_date_change():
        """Apply the selected date from time date picker"""
        try:
            date_dict = dpg.get_value("time_date_filter")
            selected_date = date(
                year=date_dict['year'],
                month=date_dict['month'] + 1,
                day=date_dict['month_day']
            )
            dpg.set_value("time_date_display", selected_date.strftime("%Y-%m-%d"))
            dpg.configure_item("time_date_picker_popup", show=False)
            refresh_time_table()
        except Exception as e:
            dpg.set_value("status_text", f"Error applying time date: {e}")
    
    def set_time_date_today():
        """Set time date to today"""
        today = date.today()
        dpg.set_value("time_date_display", today.strftime("%Y-%m-%d"))
        dpg.set_value("time_date_filter", {
            'month_day': today.day,
            'month': today.month - 1,
            'year': today.year
        })
        dpg.configure_item("time_date_picker_popup", show=False)
        refresh_time_table()
    
    def apply_jodi_date_change():
        """Apply the selected date from jodi date picker"""
        try:
            date_dict = dpg.get_value("jodi_date_filter")
            selected_date = date(
                year=date_dict['year'],
                month=date_dict['month'] + 1,
                day=date_dict['month_day']
            )
            dpg.set_value("jodi_date_display", selected_date.strftime("%Y-%m-%d"))
            dpg.configure_item("jodi_date_picker_popup", show=False)
            refresh_jodi_table()
        except Exception as e:
            dpg.set_value("status_text", f"Error applying jodi date: {e}")
    
    def set_jodi_date_today():
        """Set jodi date to today"""
        today = date.today()
        dpg.set_value("jodi_date_display", today.strftime("%Y-%m-%d"))
        dpg.set_value("jodi_date_filter", {
            'month_day': today.day,
            'month': today.month - 1,
            'year': today.year
        })
        dpg.configure_item("jodi_date_picker_popup", show=False)
        refresh_jodi_table()
    
    def apply_summary_date_change():
        """Apply the selected date from summary date picker"""
        try:
            date_dict = dpg.get_value("summary_date_filter")
            selected_date = date(
                year=date_dict['year'],
                month=date_dict['month'] + 1,
                day=date_dict['month_day']
            )
            dpg.set_value("summary_date_display", selected_date.strftime("%Y-%m-%d"))
            dpg.configure_item("summary_date_picker_popup", show=False)
            refresh_summary_table()
        except Exception as e:
            dpg.set_value("status_text", f"Error applying summary date: {e}")
    
    def set_summary_date_today():
        """Set summary date to today"""
        today = date.today()
        dpg.set_value("summary_date_display", today.strftime("%Y-%m-%d"))
        dpg.set_value("summary_date_filter", {
            'month_day': today.day,
            'month': today.month - 1,
            'year': today.year
        })
        dpg.configure_item("summary_date_picker_popup", show=False)
        refresh_summary_table()
    
    def on_bazar_selected(sender, app_data, user_data):
        """Handle bazar selection"""
        bazar_name = app_data
        if bazar_name != "No Bazars":
            dpg.set_value("status_text", f"Selected bazar: {bazar_name}")
    
    def add_bazar():
        """Add new bazar dialog"""
        if dpg.does_item_exist("add_bazar_window"):
            dpg.delete_item("add_bazar_window")
        
        with dpg.window(
            label="Add Bazar",
            tag="add_bazar_window",
            modal=True,
            width=300,
            height=150,
            pos=[400, 300]
        ):
            dpg.add_input_text(label="Name", tag="new_bazar_name", width=-1)
            dpg.add_input_text(label="Display Name", tag="new_bazar_display", width=-1)
            dpg.add_spacer(height=5)
            with dpg.group(horizontal=True):
                dpg.add_button(label="Add", callback=confirm_add_bazar, width=100)
                dpg.add_button(label="Cancel", callback=lambda: dpg.delete_item("add_bazar_window"), width=100)
    
    def confirm_add_bazar():
        """Confirm bazar addition"""
        try:
            name = dpg.get_value("new_bazar_name").strip()
            display_name = dpg.get_value("new_bazar_display").strip()
            
            if not name or not display_name:
                dpg.set_value("status_text", "Error: Both name and display name required")
                return
            
            if any(b["name"].lower() == name.lower() for b in bazars):
                dpg.set_value("status_text", "Error: Bazar already exists")
                return
            
            bazars.append({"name": name, "display_name": display_name})
            
            # Update combo
            bazar_names = [b["display_name"] for b in bazars]
            dpg.configure_item("bazar_combo", items=bazar_names, default_value=display_name)
            
            dpg.delete_item("add_bazar_window")
            dpg.set_value("status_text", f"Bazar '{display_name}' added")
            
        except Exception as e:
            dpg.set_value("status_text", f"Add bazar error: {e}")
    
    def on_auto_preview_toggled(sender, app_data, user_data):
        """Handle auto-preview toggle"""
        if app_data:
            dpg.set_value("status_text", "Auto-preview enabled")
            # Trigger preview if there's input
            input_text = dpg.get_value("input_area")
            if input_text.strip():
                validate_input()
        else:
            dpg.set_value("status_text", "Auto-preview disabled")
    
    def show_calculation_breakdown():
        """Show detailed calculation breakdown"""
        # Placeholder - will be implemented later
        dpg.set_value("status_text", "Calculation breakdown not yet implemented")
    
    def create_table_window():
        """Create separate table window with all data tables"""
        if dpg.does_item_exist("table_window"):
            dpg.show_item("table_window")
            dpg.focus_item("table_window")
            return
        
        with dpg.window(
            label="RickyMama - Data Tables",
            tag="table_window",
            width=1400,
            height=900,
            pos=[150, 150],
            on_close=lambda: dpg.hide_item("table_window")
        ):
            with dpg.tab_bar(tag="main_table_tabs"):
                # Customers tab
                with dpg.tab(label="Customers", tag="customers_tab"):
                    create_customers_table()
                
                # Universal log tab
                with dpg.tab(label="Universal Log", tag="universal_tab"):
                    create_universal_table()
                
                # Pana table tab (unique to date+bazar)
                with dpg.tab(label="Pana Table", tag="pana_tab"):
                    create_pana_table()
                
                # Time table tab (unique to date+bazar+customer)
                with dpg.tab(label="Time Table", tag="time_tab"):
                    create_time_table()
                
                # Jodi table tab (unique to date+bazar)
                with dpg.tab(label="Jodi Table", tag="jodi_tab"):
                    create_jodi_table()
                
                # Summary tab (unique to date+customer)
                with dpg.tab(label="Customer Summary", tag="summary_tab"):
                    create_summary_table()
                
                # Export tab
                with dpg.tab(label="Export", tag="export_tab"):
                    create_export_interface()
    
    def create_customers_table():
        """Create customers table view"""
        # Search and controls
        with dpg.group(horizontal=True):
            dpg.add_input_text(hint="Search customers...", tag="customers_search", width=200)
            dpg.add_button(label="Add Customer", callback=add_customer, width=120)
            dpg.add_button(label="Refresh", callback=refresh_customers_table, width=80)
        
        dpg.add_separator()
        
        # Customers table
        with dpg.table(
            header_row=True,
            resizable=True,
            sortable=True,
            scrollY=True,
            tag="customers_table",
            height=-50
        ):
            dpg.add_table_column(label="ID", width=60)
            dpg.add_table_column(label="Name", width=200)
            dpg.add_table_column(label="Type", width=120)
            dpg.add_table_column(label="Created", width=150)
            dpg.add_table_column(label="Last Activity", width=150)
            dpg.add_table_column(label="Total Entries", width=120)
            dpg.add_table_column(label="Total Value", width=120)
        
        # Load initial data
        refresh_customers_table()
    
    def create_universal_table():
        """Create universal log table view"""
        # Filters
        with dpg.group(horizontal=True):
            dpg.add_input_text(hint="Search...", tag="universal_search", width=200)
            dpg.add_combo(
                items=["All Customers"] + [c["name"] for c in customers],
                tag="universal_customer_filter",
                default_value="All Customers",
                width=150
            )
            dpg.add_combo(
                items=["All Bazars"] + [b["display_name"] for b in bazars],
                tag="universal_bazar_filter",
                default_value="All Bazars",
                width=120
            )
            dpg.add_button(label="Apply Filters", callback=refresh_universal_table, width=100)
            dpg.add_button(label="Clear", callback=clear_universal_filters, width=80)
            dpg.add_button(label="Refresh", callback=refresh_universal_table, width=80)
        
        dpg.add_separator()
        
        # Universal log table
        with dpg.table(
            header_row=True,
            resizable=True,
            sortable=True,
            scrollY=True,
            tag="universal_table",
            height=-50
        ):
            dpg.add_table_column(label="ID", width=60)
            dpg.add_table_column(label="Customer", width=150)
            dpg.add_table_column(label="Date", width=100)
            dpg.add_table_column(label="Bazar", width=80)
            dpg.add_table_column(label="Number", width=80)
            dpg.add_table_column(label="Value", width=100)
            dpg.add_table_column(label="Type", width=100)
            dpg.add_table_column(label="Created", width=140)
        
        # Load initial data
        refresh_universal_table()
    
    def create_pana_table():
        """Create pana table view (unique to date+bazar)"""
        # Date and Bazar filters
        with dpg.group(horizontal=True):
            dpg.add_text("Date:")
            today = date.today()
            # Date display field with current date as default
            dpg.add_input_text(
                tag="pana_date_display",
                default_value=today.strftime("%Y-%m-%d"),
                width=100,
                readonly=True
            )
            dpg.add_button(
                label="📅",
                tag="pana_date_toggle_btn",
                callback=lambda: dpg.configure_item("pana_date_picker_popup", show=not dpg.is_item_shown("pana_date_picker_popup")),
                width=30,
                height=23
            )
            
            dpg.add_spacer(width=20)
            
            dpg.add_text("Bazar:")
            dpg.add_combo(
                items=[b["display_name"] for b in bazars],
                tag="pana_bazar_filter",
                default_value=bazars[0]["display_name"] if bazars else "No Bazars",
                width=120,
                callback=refresh_pana_table
            )
            
            dpg.add_spacer(width=20)
            
            dpg.add_text("SP Filter:")
            dpg.add_input_int(
                tag="pana_upper_value_filter",
                default_value=0,
                width=80,
                callback=refresh_pana_table,
                min_value=0,
                min_clamped=True
            )
            with dpg.tooltip("pana_upper_value_filter"):
                dpg.add_text("Filter upper section (above separator)")
                dpg.add_text("Shows only numbers with values > filter")
                dpg.add_text("Set to 0 to show all numbers")
            
            dpg.add_spacer(width=10)
            
            dpg.add_text("DP Filter:")
            dpg.add_input_int(
                tag="pana_lower_value_filter", 
                default_value=0,
                width=80,
                callback=refresh_pana_table,
                min_value=0,
                min_clamped=True
            )
            with dpg.tooltip("pana_lower_value_filter"):
                dpg.add_text("Filter lower section (below separator)")
                dpg.add_text("Shows only numbers with values > filter")
                dpg.add_text("Set to 0 to show all numbers")
            
            dpg.add_spacer(width=20)
            
            dpg.add_button(label="Load Data", callback=refresh_pana_table, width=100)
            dpg.add_button(label="Clear Filters", callback=clear_pana_filters, width=100)
            dpg.add_button(label="Export", callback=export_pana_table, width=80)
        
        # Collapsible date picker popup
        with dpg.popup("pana_date_toggle_btn", tag="pana_date_picker_popup", modal=False):
            dpg.add_text("Select Date:")
            dpg.add_date_picker(
                tag="pana_date_filter",
                default_value={
                    'month_day': today.day,
                    'month': today.month - 1,
                    'year': today.year
                }
            )
            with dpg.group(horizontal=True):
                dpg.add_button(
                    label="Apply",
                    callback=lambda: apply_pana_date_change(),
                    width=60
                )
                dpg.add_button(
                    label="Today",
                    callback=lambda: set_pana_date_today(),
                    width=60
                )
                dpg.add_button(
                    label="Close",
                    callback=lambda: dpg.configure_item("pana_date_picker_popup", show=False),
                    width=60
                )
        
        dpg.add_separator()
        
        # Pana table display in grid format (unique per Date + Bazar)
        dpg.add_text("Pana Table Data (Unique per Date + Bazar):")
        
        # Create pana grid table with proper layout
        with dpg.table(
            header_row=True,
            resizable=False,
            borders_innerH=True,
            borders_innerV=True,
            borders_outerH=True,
            borders_outerV=True,
            tag="pana_grid_table",
            height=-50
        ):
            # Create 20 columns (10 Number|Value pairs)
            for i in range(10):
                dpg.add_table_column(label="Number", width=60)
                dpg.add_table_column(label="Value", width=60)
        
        # Load initial data
        refresh_pana_table()
    
    def create_time_table():
        """Create time table view (unique to date+bazar+customer)"""
        # Filters
        with dpg.group(horizontal=True):
            dpg.add_text("Date:")
            today = date.today()
            # Date display field with current date as default
            dpg.add_input_text(
                tag="time_date_display",
                default_value=today.strftime("%Y-%m-%d"),
                width=100,
                readonly=True
            )
            dpg.add_button(
                label="📅",
                tag="time_date_toggle_btn",
                callback=lambda: dpg.configure_item("time_date_picker_popup", show=not dpg.is_item_shown("time_date_picker_popup")),
                width=30,
                height=23
            )
            
            dpg.add_spacer(width=20)
            
            dpg.add_text("Customer:")
            dpg.add_combo(
                items=["All Customers"] + [c["name"] for c in customers],
                tag="time_customer_filter",
                default_value="All Customers",
                width=150
            )
            
            dpg.add_spacer(width=20)
            
            dpg.add_text("Bazar:")
            dpg.add_combo(
                items=["All Bazars"] + [b["display_name"] for b in bazars],
                tag="time_bazar_filter",
                default_value="All Bazars",
                width=120
            )
            
            dpg.add_spacer(width=20)
            
            dpg.add_button(label="Load Data", callback=refresh_time_table, width=100)
            dpg.add_button(label="Export", callback=export_time_table, width=80)
        
        # Collapsible date picker popup
        with dpg.popup("time_date_toggle_btn", tag="time_date_picker_popup", modal=False):
            dpg.add_text("Select Date:")
            dpg.add_date_picker(
                tag="time_date_filter",
                default_value={
                    'month_day': today.day,
                    'month': today.month - 1,
                    'year': today.year
                }
            )
            with dpg.group(horizontal=True):
                dpg.add_button(
                    label="Apply",
                    callback=lambda: apply_time_date_change(),
                    width=60
                )
                dpg.add_button(
                    label="Today",
                    callback=lambda: set_time_date_today(),
                    width=60
                )
                dpg.add_button(
                    label="Close",
                    callback=lambda: dpg.configure_item("time_date_picker_popup", show=False),
                    width=60
                )
        
        dpg.add_separator()
        
        # Time table display
        dpg.add_text("Time Table Data (Unique per Date + Bazar + Customer):")
        with dpg.table(
            header_row=True,
            resizable=True,
            sortable=True,
            scrollY=True,
            tag="time_table",
            height=-50
        ):
            dpg.add_table_column(label="Customer", width=150)
            dpg.add_table_column(label="Bazar", width=80)
            dpg.add_table_column(label="1", width=60)
            dpg.add_table_column(label="2", width=60)
            dpg.add_table_column(label="3", width=60)
            dpg.add_table_column(label="4", width=60)
            dpg.add_table_column(label="5", width=60)
            dpg.add_table_column(label="6", width=60)
            dpg.add_table_column(label="7", width=60)
            dpg.add_table_column(label="8", width=60)
            dpg.add_table_column(label="9", width=60)
            dpg.add_table_column(label="0", width=60)
            dpg.add_table_column(label="Total", width=100)
            dpg.add_table_column(label="Updated", width=140)
        
        # Load initial data
        refresh_time_table()
    
    def create_jodi_table():
        """Create jodi table view (unique to customer+date+bazar)"""
        # Customer, Date and Bazar filters
        with dpg.group(horizontal=True):
            dpg.add_text("Customer:")
            dpg.add_combo(
                items=["All Customers"] + [customer['name'] for customer in customers],
                tag="jodi_customer_filter",
                default_value="All Customers",
                width=150,
                callback=refresh_jodi_table
            )
            
            dpg.add_spacer(width=10)
            
            dpg.add_text("Date:")
            today = date.today()
            # Date display field with current date as default
            dpg.add_input_text(
                tag="jodi_date_display",
                default_value=today.strftime("%Y-%m-%d"),
                width=100,
                readonly=True
            )
            dpg.add_button(
                label="📅",
                tag="jodi_date_toggle_btn",
                callback=lambda: dpg.configure_item("jodi_date_picker_popup", show=not dpg.is_item_shown("jodi_date_picker_popup")),
                width=30,
                height=23
            )
            
            dpg.add_spacer(width=10)
            
            dpg.add_text("Bazar:")
            dpg.add_combo(
                items=[b["display_name"] for b in bazars],
                tag="jodi_bazar_filter",
                default_value=bazars[0]["display_name"] if bazars else "No Bazars",
                width=120,
                callback=refresh_jodi_table
            )
            
            dpg.add_spacer(width=10)
            
            dpg.add_button(label="Load Data", callback=refresh_jodi_table, width=100)
            dpg.add_button(label="Export", callback=export_jodi_table, width=80)
        
        # Collapsible date picker popup
        with dpg.popup("jodi_date_toggle_btn", tag="jodi_date_picker_popup", modal=False):
            dpg.add_text("Select Date:")
            dpg.add_date_picker(
                tag="jodi_date_filter",
                default_value={
                    'month_day': today.day,
                    'month': today.month - 1,
                    'year': today.year
                }
            )
            with dpg.group(horizontal=True):
                dpg.add_button(
                    label="Apply",
                    callback=lambda: apply_jodi_date_change(),
                    width=60
                )
                dpg.add_button(
                    label="Today",
                    callback=lambda: set_jodi_date_today(),
                    width=60
                )
                dpg.add_button(
                    label="Close",
                    callback=lambda: dpg.configure_item("jodi_date_picker_popup", show=False),
                    width=60
                )
        
        dpg.add_separator()
        
        # Jodi table display in grid format (unique per Customer + Date + Bazar)
        dpg.add_text("Jodi Table Data (Unique per Customer + Date + Bazar) - Jodi Numbers 00-99:")
        
        # Create jodi grid table - 10x10 grid arranged by tens digit columns
        with dpg.table(
            header_row=True,
            resizable=False,
            borders_innerH=True,
            borders_innerV=True,
            borders_outerH=True,
            borders_outerV=True,
            tag="jodi_grid_table",
            height=-50
        ):
            # Create 20 columns (10 pairs of Number|Value for each column)
            column_headers = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0"]
            for i in range(10):
                dpg.add_table_column(label=column_headers[i], width=35)
                dpg.add_table_column(label="", width=40)
        
        # Load initial data
        refresh_jodi_table()
    
    def create_summary_table():
        """Create customer summary table view (unique to date+customer)"""
        # Filters
        with dpg.group(horizontal=True):
            dpg.add_text("Date:")
            today = date.today()
            # Date display field with current date as default
            dpg.add_input_text(
                tag="summary_date_display",
                default_value=today.strftime("%Y-%m-%d"),
                width=100,
                readonly=True
            )
            dpg.add_button(
                label="📅",
                tag="summary_date_toggle_btn",
                callback=lambda: dpg.configure_item("summary_date_picker_popup", show=not dpg.is_item_shown("summary_date_picker_popup")),
                width=30,
                height=23
            )
            
            dpg.add_spacer(width=20)
            
            dpg.add_text("Customer:")
            dpg.add_combo(
                items=["All Customers"] + [c["name"] for c in customers],
                tag="summary_customer_filter",
                default_value="All Customers",
                width=150
            )
            
            dpg.add_spacer(width=20)
            
            dpg.add_button(label="Load Data", callback=refresh_summary_table, width=100)
            dpg.add_button(label="Export", callback=export_summary_table, width=80)
        
        # Collapsible date picker popup
        with dpg.popup("summary_date_toggle_btn", tag="summary_date_picker_popup", modal=False):
            dpg.add_text("Select Date:")
            dpg.add_date_picker(
                tag="summary_date_filter",
                default_value={
                    'month_day': today.day,
                    'month': today.month - 1,
                    'year': today.year
                }
            )
            with dpg.group(horizontal=True):
                dpg.add_button(
                    label="Apply",
                    callback=lambda: apply_summary_date_change(),
                    width=60
                )
                dpg.add_button(
                    label="Today",
                    callback=lambda: set_summary_date_today(),
                    width=60
                )
                dpg.add_button(
                    label="Close",
                    callback=lambda: dpg.configure_item("summary_date_picker_popup", show=False),
                    width=60
                )
        
        dpg.add_separator()
        
        # Summary table display
        dpg.add_text("Customer Summary (Unique per Date + Customer):")
        with dpg.table(
            header_row=True,
            resizable=True,
            sortable=True,
            scrollY=True,
            tag="summary_table",
            height=-50
        ):
            dpg.add_table_column(label="Customer", width=150)
            dpg.add_table_column(label="T.O", width=80)
            dpg.add_table_column(label="T.K", width=80)
            dpg.add_table_column(label="M.O", width=80)
            dpg.add_table_column(label="M.K", width=80)
            dpg.add_table_column(label="K.O", width=80)
            dpg.add_table_column(label="K.K", width=80)
            dpg.add_table_column(label="NMO", width=80)
            dpg.add_table_column(label="NMK", width=80)
            dpg.add_table_column(label="B.O", width=80)
            dpg.add_table_column(label="B.K", width=80)
            dpg.add_table_column(label="Grand Total", width=120)
            dpg.add_table_column(label="Updated", width=140)
        
        # Load initial data
        refresh_summary_table()
    
    def create_export_interface():
        """Create export interface"""
        dpg.add_text("Export Data", color=(41, 128, 185, 255))
        dpg.add_separator()
        
        # Table selection
        dpg.add_text("Select Tables to Export:")
        with dpg.group():
            dpg.add_checkbox(label="Customers", tag="export_customers", default_value=True)
            dpg.add_checkbox(label="Universal Log", tag="export_universal", default_value=True)
            dpg.add_checkbox(label="Pana Table", tag="export_pana", default_value=False)
            dpg.add_checkbox(label="Time Table", tag="export_time", default_value=False)
            dpg.add_checkbox(label="Customer Summary", tag="export_summary", default_value=True)
        
        dpg.add_spacer(height=20)
        
        # Date range
        dpg.add_text("Date Range (for time-series tables):")
        with dpg.group(horizontal=True):
            dpg.add_date_picker(tag="export_start_date", label="From")
            dpg.add_date_picker(tag="export_end_date", label="To")
        
        dpg.add_spacer(height=20)
        
        # Export format
        dpg.add_text("Export Format:")
        dpg.add_radio_button(
            items=["CSV", "Excel"],
            tag="export_format",
            default_value="CSV",
            horizontal=True
        )
        
        dpg.add_spacer(height=20)
        
        # Export buttons
        with dpg.group(horizontal=True):
            dpg.add_button(
                label="Export Selected",
                callback=perform_export,
                width=120
            )
            dpg.add_spacer(width=20)
            dpg.add_button(
                label="Full Backup",
                callback=create_full_backup,
                width=120
            )
        
        dpg.add_spacer(height=20)
        
        # Progress bar
        dpg.add_progress_bar(
            tag="export_progress",
            width=-1,
            overlay="Ready to export..."
        )
    
    def open_table_window():
        """Open separate table window"""
        create_table_window()
        dpg.set_value("status_text", "Table window opened")
    
    def open_export_dialog():
        """Open export dialog"""
        # If table window exists, switch to export tab
        if dpg.does_item_exist("table_window"):
            dpg.show_item("table_window")
            if dpg.does_item_exist("main_table_tabs"):
                dpg.set_value("main_table_tabs", "export_tab")
        else:
            create_table_window()
            if dpg.does_item_exist("main_table_tabs"):
                dpg.set_value("main_table_tabs", "export_tab")
        dpg.set_value("status_text", "Export interface opened")
    
    
    # Table refresh functions
    def refresh_customers_table():
        """Refresh customers table data"""
        try:
            # Clear existing data
            if dpg.does_item_exist("customers_table"):
                dpg.delete_item("customers_table", children_only=True, slot=1)
            
                # Get fresh customer data from database
                if db_manager:
                    try:
                        db_customers = db_manager.get_all_customers()
                        for customer in db_customers:
                            with dpg.table_row(parent="customers_table"):
                                dpg.add_text(str(customer['id']))
                                
                                # Show commission type and apply color coding
                                commission_type = customer['commission_type'] if 'commission_type' in customer.keys() else 'commission'
                                display_type = "Commission" if commission_type == 'commission' else "Non-Commission"
                                
                                # Color coding: Blue for Commission, Orange for Non-Commission
                                if commission_type == 'commission':
                                    name_color = (52, 152, 219, 255)  # Blue
                                else:
                                    name_color = (230, 126, 34, 255)  # Orange
                                
                                dpg.add_text(customer['name'], color=name_color)
                                dpg.add_text(display_type)
                                dpg.add_text(customer['created_at'])
                                
                                # Get customer statistics
                                stats_query = """
                                    SELECT COUNT(*) as entries, COALESCE(SUM(value), 0) as total_value,
                                           MAX(created_at) as last_activity
                                    FROM universal_log 
                                    WHERE customer_id = ?
                                """
                                stats = db_manager.execute_query(stats_query, (customer['id'],))
                                if stats:
                                    dpg.add_text(stats[0]['last_activity'] or 'Never')
                                    dpg.add_text(str(stats[0]['entries']))
                                    dpg.add_text(f"{stats[0]['total_value']:,}")
                                else:
                                    dpg.add_text("Never")
                                    dpg.add_text("0")
                                    dpg.add_text("0")
                    except Exception as e:
                        print(f"Error loading customer stats: {e}")
                        # Fallback to simple customer list
                        for customer in customers:
                            with dpg.table_row(parent="customers_table"):
                                dpg.add_text(str(customer['id']))
                                
                                # Show commission type and apply color coding
                                commission_type = customer['commission_type'] if 'commission_type' in customer.keys() else 'commission'
                                display_type = "Commission" if commission_type == 'commission' else "Non-Commission"
                                
                                # Color coding: Blue for Commission, Orange for Non-Commission
                                if commission_type == 'commission':
                                    name_color = (52, 152, 219, 255)  # Blue
                                else:
                                    name_color = (230, 126, 34, 255)  # Orange
                                
                                dpg.add_text(customer['name'], color=name_color)
                                dpg.add_text(display_type)
                                dpg.add_text("2024-01-01")
                                dpg.add_text("Today")
                                dpg.add_text("0")
                                dpg.add_text("0")
                else:
                    # Fallback when no database
                    for customer in customers:
                        with dpg.table_row(parent="customers_table"):
                            dpg.add_text(str(customer['id']))
                            
                            # Show commission type and apply color coding
                            commission_type = customer.get('commission_type', 'commission')
                            display_type = "Commission" if commission_type == 'commission' else "Non-Commission"
                            
                            # Color coding: Blue for Commission, Orange for Non-Commission
                            if commission_type == 'commission':
                                name_color = (52, 152, 219, 255)  # Blue
                            else:
                                name_color = (230, 126, 34, 255)  # Orange
                            
                            dpg.add_text(customer['name'], color=name_color)
                            dpg.add_text(display_type)
                            dpg.add_text("2024-01-01")
                            dpg.add_text("Today")
                            dpg.add_text("0")
                            dpg.add_text("0")
        except Exception as e:
            dpg.set_value("status_text", f"Error refreshing customers: {e}")
    
    def refresh_universal_table():
        """Refresh universal log table data"""
        try:
            if dpg.does_item_exist("universal_table"):
                dpg.delete_item("universal_table", children_only=True, slot=1)
                
                # Get real data from database
                if db_manager:
                    try:
                        entries = db_manager.get_universal_log_entries(limit=1000)
                        if entries:
                            for entry in entries:
                                with dpg.table_row(parent="universal_table"):
                                    dpg.add_text(str(entry['id']))
                                    # Apply color coding based on commission type
                                    customer_color = get_customer_name_color(entry['customer_name'])
                                    dpg.add_text(entry['customer_name'], color=customer_color)
                                    dpg.add_text(entry['entry_date'])
                                    dpg.add_text(entry['bazar'])
                                    dpg.add_text(str(entry['number']))
                                    dpg.add_text(f"₹{entry['value']}")
                                    dpg.add_text(entry['entry_type'])
                                    dpg.add_text(entry['created_at'])
                        else:
                            # No entries found
                            with dpg.table_row(parent="universal_table"):
                                dpg.add_text("No entries found - Start by submitting some data", color=(150, 150, 150, 255))
                                for _ in range(7):
                                    dpg.add_text("", color=(150, 150, 150, 255))
                    except AttributeError:
                        # No data available
                        pass
                else:
                    # No database - show empty table message
                    with dpg.table_row(parent="universal_table"):
                        dpg.add_text("No data available - Database not connected", color=(150, 150, 150, 255))
                        for _ in range(7):  # Fill remaining columns
                            dpg.add_text("")
        except Exception as e:
            dpg.set_value("status_text", f"Error refreshing universal log: {e}")
    
    def clear_universal_filters():
        """Clear universal table filters"""
        dpg.set_value("universal_search", "")
        dpg.set_value("universal_customer_filter", "All Customers")
        dpg.set_value("universal_bazar_filter", "All Bazars")
        refresh_universal_table()
    
    def clear_pana_filters():
        """Clear pana table value filters"""
        if dpg.does_item_exist("pana_upper_value_filter"):
            dpg.set_value("pana_upper_value_filter", 0)
        if dpg.does_item_exist("pana_lower_value_filter"):
            dpg.set_value("pana_lower_value_filter", 0)
        refresh_pana_table()
        dpg.set_value("status_text", "Pana table filters cleared")
    
    def get_pana_layout():
        """Get the complete pana table layout as specified"""
        # Upper section (first 12 rows)
        upper_section = [
            [128, 129, 120, 130, 140, 123, 124, 125, 126, 127],
            [137, 138, 139, 149, 159, 150, 160, 134, 135, 136],
            [146, 147, 148, 158, 168, 169, 179, 170, 180, 145],
            [236, 156, 157, 167, 230, 178, 250, 189, 234, 190],
            [245, 237, 238, 239, 249, 240, 269, 260, 270, 235],
            [290, 246, 247, 248, 258, 259, 278, 279, 289, 280],
            [380, 345, 256, 257, 267, 268, 340, 350, 360, 370],
            [470, 390, 346, 347, 348, 349, 359, 369, 379, 389],
            [489, 480, 490, 356, 357, 358, 368, 378, 450, 460],
            [560, 570, 580, 590, 456, 367, 458, 459, 478, 479],
            [579, 589, 670, 680, 690, 457, 467, 468, 469, 569],
            [678, 679, 689, 789, 780, 790, 890, 567, 568, 578]
        ]
        
        # Lower section (after gap - 10 rows)
        lower_section = [
            [100, 110, 166, 112, 113, 114, 115, 116, 117, 118],
            [119, 200, 229, 220, 122, 277, 133, 224, 144, 226],
            [155, 228, 300, 266, 177, 330, 188, 233, 199, 244],
            [227, 255, 337, 338, 339, 448, 223, 288, 225, 299],
            [335, 336, 355, 400, 366, 466, 377, 440, 388, 334],
            [344, 499, 445, 446, 447, 556, 449, 477, 559, 488],
            [399, 660, 599, 455, 500, 880, 557, 558, 577, 550],
            [588, 688, 779, 699, 799, 899, 566, 800, 667, 668],
            [669, 778, 788, 770, 889, 600, 700, 990, 900, 677],
            [777, 444, 111, 888, 555, 222, 999, 666, 333, 0]
        ]
        
        return upper_section, lower_section
    
    def refresh_pana_table():
        """Refresh pana table data for selected date+bazar"""
        try:
            if dpg.does_item_exist("pana_grid_table"):
                dpg.delete_item("pana_grid_table", children_only=True, slot=1)
                
                # Get selected date and bazar from display fields
                date_str = dpg.get_value("pana_date_display")
                bazar_value = dpg.get_value("pana_bazar_filter")
                
                if date_str and bazar_value and bazar_value != "No Bazars":
                    upper_section, lower_section = get_pana_layout()
                    
                    # Get pana data from database for selected date+bazar
                    pana_values = {}  # number -> value mapping
                    
                    if db_manager:
                        try:
                            # Get bazar name (not display name)
                            bazar_name = bazar_value
                            for bazar in bazars:
                                if bazar['display_name'] == bazar_value:
                                    bazar_name = bazar['name']
                                    break
                            
                            # Fetch pana data from database using new method
                            if hasattr(db_manager, 'get_pana_table_values'):
                                pana_data = db_manager.get_pana_table_values(bazar_name, date_str)
                                for entry in pana_data:
                                    if hasattr(entry, '__getitem__'):  # Row object or dict
                                        pana_values[entry['number']] = entry['value']
                        except Exception as e:
                            print(f"Database error: {e}")
                    
                    # Show empty table if no data
                    # No dummy values added
                    
                    # Get filter values
                    upper_filter = dpg.get_value("pana_upper_value_filter") if dpg.does_item_exist("pana_upper_value_filter") else 0
                    lower_filter = dpg.get_value("pana_lower_value_filter") if dpg.does_item_exist("pana_lower_value_filter") else 0
                    
                    # Add upper section rows with filter applied
                    for row_numbers in upper_section:
                        with dpg.table_row(parent="pana_grid_table"):
                            for number in row_numbers:
                                value = pana_values.get(number, 0)
                                
                                # Number cell - always show
                                dpg.add_text(str(number))
                                
                                # Value cell - apply upper section filter
                                if upper_filter > 0 and value > 0 and value <= upper_filter:
                                    # Hide value if it doesn't pass filter
                                    dpg.add_text("", color=(108, 117, 125, 255))  # Empty value cell
                                else:
                                    # Show value normally
                                    if value > 0:
                                        dpg.add_text(str(value), color=(39, 174, 96, 255))  # Green for non-zero
                                    else:
                                        dpg.add_text("0", color=(108, 117, 125, 255))  # Gray for zero
                    
                    # Add separator row (empty row)
                    with dpg.table_row(parent="pana_grid_table"):
                        for i in range(20):  # 20 columns total
                            dpg.add_text("", color=(200, 200, 200, 255))
                    
                    # Add lower section rows with filter applied
                    for row_numbers in lower_section:
                        with dpg.table_row(parent="pana_grid_table"):
                            for number in row_numbers:
                                value = pana_values.get(number, 0)
                                
                                # Number cell - always show
                                dpg.add_text(str(number))
                                
                                # Value cell - apply lower section filter
                                if lower_filter > 0 and value > 0 and value <= lower_filter:
                                    # Hide value if it doesn't pass filter
                                    dpg.add_text("", color=(108, 117, 125, 255))  # Empty value cell
                                else:
                                    # Show value normally
                                    if value > 0:
                                        dpg.add_text(str(value), color=(39, 174, 96, 255))  # Green for non-zero
                                    else:
                                        dpg.add_text("0", color=(108, 117, 125, 255))  # Gray for zero
                    
                    # Add summary information with filter status
                    total_numbers = len(upper_section) * 10 + len(lower_section) * 10  # 220 total
                    non_zero_count = len([v for v in pana_values.values() if v > 0])
                    total_value = sum(pana_values.values())
                    
                    # Count visible values for each section (numbers always visible)
                    upper_visible_values = 0
                    lower_visible_values = 0
                    upper_total_values = 0
                    lower_total_values = 0
                    
                    # Count upper section values
                    for row_numbers in upper_section:
                        for number in row_numbers:
                            value = pana_values.get(number, 0)
                            if value > 0:
                                upper_total_values += 1
                                if upper_filter == 0 or value > upper_filter:
                                    upper_visible_values += 1
                    
                    # Count lower section values
                    for row_numbers in lower_section:
                        for number in row_numbers:
                            value = pana_values.get(number, 0)
                            if value > 0:
                                lower_total_values += 1
                                if lower_filter == 0 or value > lower_filter:
                                    lower_visible_values += 1
                    
                    filter_status = ""
                    if upper_filter > 0 or lower_filter > 0:
                        filter_status = f" | Visible values: Upper {upper_visible_values}/{upper_total_values}, Lower {lower_visible_values}/{lower_total_values}"
                    
                    dpg.set_value("status_text", 
                        f"Pana table loaded for {bazar_value} | "
                        f"Numbers: {non_zero_count}/{total_numbers} active | "
                        f"Total value: ₹{total_value:,}{filter_status}")
                else:
                    dpg.set_value("status_text", "Please select date and bazar to load Pana table")
        except Exception as e:
            dpg.set_value("status_text", f"Error refreshing pana table: {e}")
    
    def refresh_time_table():
        """Refresh time table data for selected filters"""
        try:
            if dpg.does_item_exist("time_table"):
                dpg.delete_item("time_table", children_only=True, slot=1)
                
                # Get selected filters from display fields
                date_str = dpg.get_value("time_date_display")
                customer_value = dpg.get_value("time_customer_filter")
                bazar_value = dpg.get_value("time_bazar_filter")
                
                # Get real time table data from database
                if date_str and bazar_value and bazar_value != "No Bazars":
                    # Get bazar name (not display name)
                    bazar_name = bazar_value
                    for bazar in bazars:
                        if bazar['display_name'] == bazar_value:
                            bazar_name = bazar['name']
                            break
                    
                    if db_manager and hasattr(db_manager, 'get_time_table_by_bazar_date'):
                        try:
                            time_data = db_manager.get_time_table_by_bazar_date(bazar_name, date_str)
                            
                            if time_data:
                                for entry in time_data:
                                    # Filter by customer if specific customer selected
                                    if customer_value == "All Customers" or entry['customer_name'] == customer_value:
                                        with dpg.table_row(parent="time_table"):
                                            # Apply color coding based on commission type
                                            customer_color = get_customer_name_color(entry['customer_name'])
                                            dpg.add_text(entry['customer_name'], color=customer_color)
                                            dpg.add_text(bazar_name)
                                            # Columns 1-9, then 0 (as per table header order)
                                            for i in [1, 2, 3, 4, 5, 6, 7, 8, 9, 0]:
                                                value = entry[f'col_{i}'] if entry[f'col_{i}'] > 0 else "-"
                                                dpg.add_text(str(value))
                                            dpg.add_text(f"{entry['total']:,}")
                                            dpg.add_text(entry['updated_at'] or entry['created_at'])
                            else:
                                # Show empty row if no data
                                with dpg.table_row(parent="time_table"):
                                    dpg.add_text("No time data available for selected filters", color=(150, 150, 150, 255))
                                    for i in range(12):  # Bazar + 10 columns + Total + Date
                                        dpg.add_text("", color=(150, 150, 150, 255))
                        except Exception as e:
                            print(f"Database error loading time table: {e}")
                            # Show error row
                            with dpg.table_row(parent="time_table"):
                                dpg.add_text("Error loading data")
                                for i in range(12):
                                    dpg.add_text("-")
                    
                    # Add Jodi column totals row at the bottom
                    jodi_column_totals = _calculate_jodi_column_totals(bazar_name, date_str, customer_value)
                    with dpg.table_row(parent="time_table"):
                        dpg.add_text("JODI TOTALS", color=(255, 193, 7, 255))  # Yellow/gold color
                        dpg.add_text(bazar_name, color=(255, 193, 7, 255))
                        # Display jodi totals for columns 1-9, then 0
                        for i in [1, 2, 3, 4, 5, 6, 7, 8, 9, 0]:
                            total = jodi_column_totals.get(i, 0)
                            if total > 0:
                                dpg.add_text(f"{total:,}", color=(255, 193, 7, 255))
                            else:
                                dpg.add_text("-", color=(108, 117, 125, 255))
                        # Grand total of all jodi columns
                        grand_total = sum(jodi_column_totals.values())
                        dpg.add_text(f"{grand_total:,}", color=(255, 193, 7, 255))
                        dpg.add_text("Live", color=(255, 193, 7, 255))
                        
                dpg.set_value("status_text", f"Time table loaded for {date_str} (includes Jodi totals)")
        except Exception as e:
            dpg.set_value("status_text", f"Error refreshing time table: {e}")
    
    def _calculate_jodi_column_totals(bazar_name: str, date_str: str, customer_value: str):
        """Calculate jodi column totals for display in time table"""
        column_totals = {i: 0 for i in range(10)}  # Initialize columns 0-9
        
        try:
            jodi_data = []  # Initialize empty list
            if db_manager:
                # Get jodi data based on customer selection (same logic as jodi table)
                if customer_value == "All Customers":
                    # Get aggregated data from jodi_table
                    if hasattr(db_manager, 'get_jodi_table_values'):
                        jodi_data = db_manager.get_jodi_table_values(bazar_name, date_str)
                else:
                    # Get customer-specific data from universal_log
                    if hasattr(db_manager, 'get_jodi_table_values_by_customer'):
                        jodi_data = db_manager.get_jodi_table_values_by_customer(customer_value, bazar_name, date_str)
                
                # Process jodi data and sum by column
                for entry in jodi_data:
                    if hasattr(entry, '__getitem__'):
                        jodi_number = entry['jodi_number']
                        value = entry['value']
                        
                        # Map jodi number to column based on tens digit
                        # Jodi layout: Col 1: 11,12,13,14,15,16,17,18,19,10
                        #              Col 2: 21,22,23,24,25,26,27,28,29,20
                        #              ...
                        #              Col 0: 01,02,03,04,05,06,07,08,09,00
                        if jodi_number == 0:
                            column = 0  # 00 goes to column 0
                        elif 1 <= jodi_number <= 9:
                            column = 0  # 01-09 go to column 0
                        elif jodi_number == 10:
                            column = 1  # 10 goes to column 1
                        elif jodi_number == 20:
                            column = 2  # 20 goes to column 2
                        elif jodi_number == 30:
                            column = 3  # 30 goes to column 3
                        elif jodi_number == 40:
                            column = 4  # 40 goes to column 4
                        elif jodi_number == 50:
                            column = 5  # 50 goes to column 5
                        elif jodi_number == 60:
                            column = 6  # 60 goes to column 6
                        elif jodi_number == 70:
                            column = 7  # 70 goes to column 7
                        elif jodi_number == 80:
                            column = 8  # 80 goes to column 8
                        elif jodi_number == 90:
                            column = 9  # 90 goes to column 9
                        else:
                            # For numbers like 11-19, 21-29, etc., use tens digit
                            tens_digit = jodi_number // 10
                            if tens_digit >= 1 and tens_digit <= 9:
                                column = tens_digit
                            else:
                                continue  # Skip invalid numbers
                        
                        column_totals[column] += value
                        
        except Exception as e:
            print(f"Error calculating jodi column totals: {e}")
        
        return column_totals
    
    def refresh_jodi_table():
        """Refresh jodi table data for selected customer+date+bazar"""
        try:
            if dpg.does_item_exist("jodi_grid_table"):
                dpg.delete_item("jodi_grid_table", children_only=True, slot=1)
                
                # Get selected filters from display fields
                customer_value = dpg.get_value("jodi_customer_filter")
                date_str = dpg.get_value("jodi_date_display")
                bazar_value = dpg.get_value("jodi_bazar_filter")
                
                if date_str and bazar_value and bazar_value != "No Bazars":
                    # Get jodi data from database for selected filters
                    jodi_values = {}  # jodi_number -> value mapping
                    
                    if db_manager:
                        try:
                            # Get bazar name (not display name)
                            bazar_name = bazar_value
                            for bazar in bazars:
                                if bazar['display_name'] == bazar_value:
                                    bazar_name = bazar['name']
                                    break
                            
                            # Fetch jodi data based on customer selection
                            if customer_value == "All Customers":
                                # Show aggregated data for all customers (existing behavior)
                                if hasattr(db_manager, 'get_jodi_table_values'):
                                    jodi_data = db_manager.get_jodi_table_values(bazar_name, date_str)
                                    for entry in jodi_data:
                                        if hasattr(entry, '__getitem__'):  # Row object or dict
                                            jodi_values[entry['jodi_number']] = entry['value']
                            else:
                                # Show data for specific customer from universal_log
                                if hasattr(db_manager, 'get_jodi_table_values_by_customer'):
                                    jodi_data = db_manager.get_jodi_table_values_by_customer(customer_value, bazar_name, date_str)
                                    for entry in jodi_data:
                                        if hasattr(entry, '__getitem__'):  # Row object or dict
                                            jodi_values[entry['jodi_number']] = entry['value']
                        except Exception as e:
                            print(f"Database error: {e}")
                    
                    # Show empty table if no data
                    # No dummy values added
                    
                    # Create 10x10 grid arranged as per user's layout
                    # Row 1: 11, 21, 31, 41, 51, 61, 71, 81, 91, 1
                    # Row 2: 12, 22, 32, 42, 52, 62, 72, 82, 92, 2
                    # ...
                    # Row 9: 19, 29, 39, 49, 59, 69, 79, 89, 99, 9
                    # Row 10: 10, 20, 30, 40, 50, 60, 70, 80, 90, 0
                    for row in range(10):
                        with dpg.table_row(parent="jodi_grid_table"):
                            for col in range(10):
                                # Calculate jodi number for this position
                                if col == 9:  # Last column (0X numbers)
                                    if row == 9:  # Last row, last column = 00
                                        jodi_number = 0
                                    else:  # Other rows in last column = 1,2,3,4,5,6,7,8,9
                                        jodi_number = row + 1
                                else:  # Other columns (1X, 2X, 3X, 4X, 5X, 6X, 7X, 8X, 9X)
                                    tens_digit = col + 1  # 1,2,3,4,5,6,7,8,9
                                    if row == 9:  # Last row = X0 (10,20,30,40,50,60,70,80,90)
                                        jodi_number = tens_digit * 10
                                    else:  # Other rows = X1,X2,X3,X4,X5,X6,X7,X8,X9
                                        jodi_number = tens_digit * 10 + (row + 1)
                                
                                # Jodi number cell
                                dpg.add_text(f"{jodi_number:02d}")
                                
                                # Value cell
                                value = jodi_values.get(jodi_number, 0)
                                if value > 0:
                                    dpg.add_text(str(value), color=(39, 174, 96, 255))  # Green for non-zero
                                else:
                                    dpg.add_text("0", color=(108, 117, 125, 255))  # Gray for zero
                    
                    # Add summary information
                    total_jodi_numbers = 100  # 00-99
                    non_zero_count = len([v for v in jodi_values.values() if v > 0])
                    total_value = sum(jodi_values.values())
                    
                    if customer_value == "All Customers":
                        dpg.set_value("status_text", 
                            f"Jodi table loaded for All Customers in {bazar_value} | "
                            f"Jodi numbers: {non_zero_count}/{total_jodi_numbers} active | "
                            f"Total value: ₹{total_value:,}")
                    else:
                        dpg.set_value("status_text", 
                            f"Jodi table loaded for {customer_value} in {bazar_value} | "
                            f"Jodi numbers: {non_zero_count}/{total_jodi_numbers} active | "
                            f"Total value: ₹{total_value:,}")
                else:
                    dpg.set_value("status_text", "Please select customer, date and bazar to load Jodi table")
        except Exception as e:
            dpg.set_value("status_text", f"Error refreshing jodi table: {e}")
    
    def refresh_summary_table():
        """Refresh customer summary table data"""
        try:
            if dpg.does_item_exist("summary_table"):
                dpg.delete_item("summary_table", children_only=True, slot=1)
                
                # Get selected filters from display fields
                date_str = dpg.get_value("summary_date_display")
                customer_value = dpg.get_value("summary_customer_filter")
                
                # Get real customer summary data from database
                if date_str and db_manager and hasattr(db_manager, 'get_customer_bazar_summary_by_date'):
                    try:
                        summary_data = db_manager.get_customer_bazar_summary_by_date(date_str)
                        
                        if summary_data:
                            for entry in summary_data:
                                # Filter by customer if specific customer selected
                                if customer_value == "All Customers" or entry['customer_name'] == customer_value:
                                    with dpg.table_row(parent="summary_table"):
                                        # Apply color coding based on commission type
                                        customer_color = get_customer_name_color(entry['customer_name'])
                                        dpg.add_text(entry['customer_name'], color=customer_color)
                                        # Bazar totals in order: T.O, T.K, M.O, M.K, K.O, K.K, NMO, NMK, B.O, B.K
                                        dpg.add_text(f"{entry['to_total']:,}")
                                        dpg.add_text(f"{entry['tk_total']:,}")
                                        dpg.add_text(f"{entry['mo_total']:,}")
                                        dpg.add_text(f"{entry['mk_total']:,}")
                                        dpg.add_text(f"{entry['ko_total']:,}")
                                        dpg.add_text(f"{entry['kk_total']:,}")
                                        dpg.add_text(f"{entry['nmo_total']:,}")
                                        dpg.add_text(f"{entry['nmk_total']:,}")
                                        dpg.add_text(f"{entry['bo_total']:,}")
                                        dpg.add_text(f"{entry['bk_total']:,}")
                                        dpg.add_text(f"{entry['grand_total']:,}")  # Grand total
                                        dpg.add_text(entry['updated_at'] or entry['created_at'])
                        else:
                            # Show empty row if no data
                            with dpg.table_row(parent="summary_table"):
                                dpg.add_text("No summary data available for selected date", color=(150, 150, 150, 255))
                                for i in range(12):  # 11 bazars + Total + Date (now includes K.K)
                                    dpg.add_text("", color=(150, 150, 150, 255))
                    except Exception as e:
                        print(f"Database error loading summary: {e}")
                        # Show error row
                        with dpg.table_row(parent="summary_table"):
                            dpg.add_text("Error loading data")
                            for i in range(12):  # 11 bazars + Total + Date (now includes K.K)
                                dpg.add_text("-")
                        
                dpg.set_value("status_text", f"Summary table loaded for {date_str}")
        except Exception as e:
            dpg.set_value("status_text", f"Error refreshing summary table: {e}")
    
    # Export functions using ExportManager
    def export_pana_table():
        """Export pana table data"""
        try:
            if db_manager:
                from src.utils.export_manager import ExportManager
                export_manager = ExportManager()
                
                # Get current filters
                date_str = dpg.get_value("pana_date_display")
                bazar_value = dpg.get_value("pana_bazar_filter")
                
                if date_str and bazar_value and bazar_value != "No Bazars":
                    # Get bazar name
                    bazar_name = bazar_value
                    for bazar in bazars:
                        if bazar['display_name'] == bazar_value:
                            bazar_name = bazar['name']
                            break
                    
                    filepath = export_manager.export_pana_table(db_manager, bazar_name, date_str)
                    dpg.set_value("status_text", f"Pana table exported to: {filepath}")
                else:
                    dpg.set_value("status_text", "Please select date and bazar for pana export")
            else:
                dpg.set_value("status_text", "Database not available for export")
        except Exception as e:
            dpg.set_value("status_text", f"Export error: {e}")
    
    def export_time_table():
        """Export time table data"""
        try:
            if db_manager:
                from src.utils.export_manager import ExportManager
                export_manager = ExportManager()
                
                # Get current filters
                date_str = dpg.get_value("time_date_display")
                bazar_value = dpg.get_value("time_bazar_filter")
                
                if date_str and bazar_value and bazar_value != "No Bazars":
                    # Get bazar name
                    bazar_name = bazar_value
                    for bazar in bazars:
                        if bazar['display_name'] == bazar_value:
                            bazar_name = bazar['name']
                            break
                    
                    filepath = export_manager.export_time_table(db_manager, bazar_name, date_str)
                    dpg.set_value("status_text", f"Time table exported to: {filepath}")
                else:
                    dpg.set_value("status_text", "Please select date and bazar for time export")
            else:
                dpg.set_value("status_text", "Database not available for export")
        except Exception as e:
            dpg.set_value("status_text", f"Export error: {e}")
    
    def export_jodi_table():
        """Export jodi table data"""
        try:
            if db_manager:
                from src.utils.export_manager import ExportManager
                export_manager = ExportManager()
                
                # Get current filters
                date_str = dpg.get_value("jodi_date_display")
                bazar_value = dpg.get_value("jodi_bazar_filter")
                
                if date_str and bazar_value and bazar_value != "No Bazars":
                    # Get bazar name
                    bazar_name = bazar_value
                    for bazar in bazars:
                        if bazar['display_name'] == bazar_value:
                            bazar_name = bazar['name']
                            break
                    
                    # Export jodi table data (may need to add this method to ExportManager)
                    try:
                        if hasattr(export_manager, 'export_jodi_table'):
                            filepath = export_manager.export_jodi_table(db_manager, bazar_name, date_str)
                        else:
                            # Fallback to generic export
                            filepath = f"./exports/jodi_table_{bazar_name}_{date_str}.csv"
                            dpg.set_value("status_text", "Jodi export method not yet implemented in ExportManager")
                            return
                        
                        dpg.set_value("status_text", f"Jodi table exported to: {filepath}")
                    except Exception as e:
                        dpg.set_value("status_text", f"Jodi export error: {e}")
                else:
                    dpg.set_value("status_text", "Please select date and bazar for jodi export")
            else:
                dpg.set_value("status_text", "Database not available for export")
        except Exception as e:
            dpg.set_value("status_text", f"Export error: {e}")
    
    def export_summary_table():
        """Export summary table data"""
        try:
            if db_manager:
                from src.utils.export_manager import ExportManager
                export_manager = ExportManager()
                
                # Get current date
                date_str = dpg.get_value("summary_date_display")
                
                if date_str:
                    filepath = export_manager.export_customer_summary(db_manager, date_str)
                    dpg.set_value("status_text", f"Summary table exported to: {filepath}")
                else:
                    dpg.set_value("status_text", "Please select date for summary export")
            else:
                dpg.set_value("status_text", "Database not available for export")
        except Exception as e:
            dpg.set_value("status_text", f"Export error: {e}")
    
    def perform_export():
        """Perform data export based on selections"""
        try:
            if db_manager:
                from src.utils.export_manager import ExportManager
                export_manager = ExportManager()
                
                # Export all tables for today's date
                from datetime import date
                today = date.today().isoformat()
                
                dpg.set_value("export_progress", 0.2)
                dpg.configure_item("export_progress", overlay="Exporting universal log...")
                
                exported_files = export_manager.export_all_tables(db_manager, today)
                
                dpg.set_value("export_progress", 1.0)
                dpg.configure_item("export_progress", overlay="Export complete!")
                
                file_count = len(exported_files)
                dpg.set_value("status_text", f"Export complete! {file_count} files exported to ./exports/")
            else:
                dpg.set_value("status_text", "Database not available for export")
        except Exception as e:
            dpg.set_value("status_text", f"Export error: {e}")
    
    def create_full_backup():
        """Create full database backup"""
        dpg.set_value("status_text", "Full backup not yet implemented")
        dpg.set_value("export_progress", 0.3)
        dpg.configure_item("export_progress", overlay="Creating backup...")
    
    # Create Dear PyGui context
    dpg.create_context()
    
    # Configure larger font for better readability
    with dpg.font_registry():
        # Try to use system font, fallback to built-in if not available
        try:
            # For macOS, try Helvetica
            default_font = dpg.add_font("/System/Library/Fonts/Helvetica.ttc", 18)
            header_font = dpg.add_font("/System/Library/Fonts/Helvetica.ttc", 20)
        except:
            try:
                # Fallback to Arial if available
                default_font = dpg.add_font("/System/Library/Fonts/Arial.ttf", 18)
                header_font = dpg.add_font("/System/Library/Fonts/Arial.ttf", 20)
            except:
                # Use DearPyGui's built-in font with scaling
                default_font = dpg.add_font(None, 18)
                header_font = dpg.add_font(None, 20)
    
    # Bind the default font
    dpg.bind_font(default_font)
    
    # Create main window
    with dpg.window(label="RickyMama Data Entry System", tag="main_window"):
        # Single Row - Name, ID, Bazar, Date (reordered and optimized)
        with dpg.group(horizontal=True):
            dpg.add_text("Name:")
            customer_names = [c["name"] for c in customers]
            dpg.add_combo(
                items=customer_names,
                default_value=customer_names[0] if customer_names else "No Customers",
                tag="customer_combo",
                width=150,
                callback=on_customer_selected
            )
            
            dpg.add_spacer(width=10)
            
            dpg.add_text("ID:")
            dpg.add_input_text(
                tag="customer_id_input",
                width=60,
                hint="Auto",
                callback=on_customer_id_entered
            )
            
            dpg.add_spacer(width=10)
            
            dpg.add_text("Bazar:")
            bazar_names = [b["display_name"] for b in bazars]
            dpg.add_combo(
                items=bazar_names,
                default_value=bazar_names[0] if bazar_names else "No Bazars",
                tag="bazar_combo",
                width=100,
                callback=on_bazar_selected
            )
            
            dpg.add_spacer(width=10)
            
            dpg.add_text("Date:")
            # Compact date display with today's date as default
            today = date.today()
            dpg.add_input_text(
                tag="date_display",
                default_value=today.strftime("%Y-%m-%d"),
                width=85,
                readonly=True
            )
            dpg.add_button(
                label="▼",
                tag="date_change_btn",
                callback=lambda: dpg.configure_item("date_picker_popup", show=True),
                width=20
            )
            
            dpg.add_spacer(width=10)
            
            # Compact action buttons
            dpg.add_button(label="+User", callback=add_customer, width=50)
            dpg.add_button(label="+Bazar", callback=add_bazar, width=55)
        
        
        # Hidden date picker popup
        with dpg.popup("date_change_btn", tag="date_picker_popup", modal=True):
            dpg.add_text("Select Date:")
            dpg.add_date_picker(
                tag="entry_date",
                default_value={
                    'month_day': today.day,
                    'month': today.month - 1,  # DearPyGui uses 0-based months
                    'year': today.year
                },
                callback=on_date_changed
            )
            with dpg.group(horizontal=True):
                dpg.add_button(
                    label="Apply",
                    callback=lambda: apply_date_change(),
                    width=80
                )
                dpg.add_button(
                    label="Cancel",
                    callback=lambda: dpg.configure_item("date_picker_popup", show=False),
                    width=80
                )
        
        dpg.add_spacer(height=5)
        
        # Main Content - Optimized Full Width Layout
        with dpg.group(horizontal=True):
            # Left Column - Input Section
            with dpg.child_window(width=590, height=480, border=True):
                dpg.add_text("INPUT - Data Entry", color=[100, 150, 255])
                dpg.add_separator()
                dpg.add_spacer(height=3)
                
                dpg.add_input_text(
                    tag="input_area",
                    multiline=True,
                    width=-1,
                    height=400,
                    hint="Enter your data here...\\n\\nSupported formats:\\n- PANA: 128/129/120 = 100\\n- Type: 1SP=100, 5DP=200\\n- Time: 1=100, 2 4 6=300\\n- Multi: 38x700, 83x500\\n- Jodi: 22-24-26\\n42-44-46=500",
                    callback=on_input_change
                )
                
                dpg.add_spacer(height=3)
                dpg.add_text("Status: Ready", tag="validation_text", color=[150, 150, 150])
            
            dpg.add_spacer(width=8)
            
            # Right Column - Preview Section
            with dpg.child_window(width=590, height=480, border=True):
                dpg.add_text("PREVIEW - Live Preview", color=[100, 150, 255])
                dpg.add_separator()
                dpg.add_spacer(height=3)
                
                with dpg.child_window(height=400, horizontal_scrollbar=True, border=True, tag="preview_window"):
                    dpg.add_text(
                        "Enter data above to see preview...",
                        tag="preview_area",
                        wrap=480  # Set wrap width for better text display
                    )
        
        dpg.add_spacer(height=8)
        
        # Compact Total Display and Actions
        with dpg.child_window(height=55, border=True):
            dpg.add_spacer(height=5)
            with dpg.group(horizontal=True):
                dpg.add_spacer(width=20)
                dpg.add_text("TOTAL:", color=[100, 150, 255])
                dpg.add_input_text(
                    readonly=True,
                    tag="calculated_total",
                    width=120,
                    default_value="₹0"
                )
                
                dpg.add_spacer(width=20)
                
                # Validation status
                dpg.add_text("", tag="validation_status", color=(108, 117, 125, 255))
                
                dpg.add_spacer(width=20)
                
                # Show breakdown button
                dpg.add_button(
                    label="Breakdown",
                    callback=show_calculation_breakdown,
                    tag="breakdown_btn",
                    enabled=False,
                    width=100,
                    height=28
                )
        
        dpg.add_spacer(height=8)
        
        # Compact Action Buttons
        with dpg.group(horizontal=True):
            dpg.add_button(label="Preview", callback=validate_input, width=120, height=35)
            dpg.add_spacer(width=15)
            dpg.add_button(label="Submit", callback=submit_data, width=120, height=35, tag="submit_btn")
            dpg.add_spacer(width=15)
            dpg.add_button(label="Clear", callback=clear_data, width=120, height=35)
            
            dpg.add_spacer(width=30)
            
            # Auto-preview checkbox
            dpg.add_checkbox(
                label="Auto Preview",
                tag="auto_preview_checkbox",
                default_value=True,
                callback=on_auto_preview_toggled
            )
            
            dpg.add_spacer(width=30)
            
            # Quick actions in same row
            dpg.add_button(
                label="Tables",
                callback=open_table_window,
                tag="view_tables_btn",
                width=100,
                height=35
            )
            
            dpg.add_spacer(width=15)
            
            dpg.add_button(
                label="Export",
                callback=open_export_dialog,
                tag="export_data_btn",
                width=100,
                height=35
            )
        
        dpg.add_spacer(height=15)
        
        # Status Bar
        dpg.add_separator()
        with dpg.group(horizontal=True):
            dpg.add_text("Status:", color=[100, 150, 255])
            dpg.add_text("Ready", tag="status_text", color=[100, 255, 100])
            dpg.add_spacer(width=50)
            dpg.add_text("", tag="last_entry_text", color=[150, 150, 150])
        
        # Info
        with dpg.group(horizontal=True):
            dpg.add_text(f"Database: {'Connected' if db_manager else 'Mock Mode'}")
            dpg.add_spacer(width=50)
            dpg.add_text(f"Customers: {len(customers)}")
            dpg.add_spacer(width=50)
            dpg.add_text(f"Bazars: {len(bazars)}")
    
    # Setup viewport with larger size for side-by-side layout
    dpg.create_viewport(
        title="RickyMama Data Entry System - Enhanced GUI",
        width=1200,
        height=900,
        min_width=1000,
        min_height=700,
        resizable=True
    )
    
    dpg.setup_dearpygui()
    dpg.show_viewport()
    dpg.set_primary_window("main_window", True)
    
    return db_manager

def main():
    """Main function"""
    print("🚀 RickyMama Main GUI - Working Version")
    print("=" * 50)
    
    try:
        # Create GUI
        db_manager = create_working_main_gui()
        
        print("✅ Main GUI created successfully!")
        print("🖥️ Window should be visible now")
        print("⏱️ Running GUI... (Close window to exit)")
        print("💡 Features:")
        print("   • Customer management")
        print("   • Real-time validation")
        print("   • Data preview")
        print("   • Database storage")
        print("   • Enhanced layout")
        
        # Main loop
        frame_count = 0
        
        while dpg.is_dearpygui_running():
            dpg.render_dearpygui_frame()
            
            # Progress indicator
            frame_count += 1
            if frame_count % 300 == 0:  # Every 5 seconds
                print("⏱️ GUI running smoothly...")
            
            time.sleep(0.016)  # ~60 FPS
        
        print("🛑 GUI closed by user")
        
        # Cleanup
        if db_manager:
            db_manager.close()
        
        dpg.destroy_context()
        print("✅ Cleanup completed")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    print("👋 Goodbye!")

if __name__ == "__main__":
    main()