"""
WhatsApp Integration Example
Shows how to integrate WhatsApp panel into main_gui_working.py
"""

# ============================================================
# ADD TO main_gui_working.py - INTEGRATION CODE
# ============================================================

# 1. Add these imports at the top of main_gui_working.py:
"""
from src.whatsapp.gui_integration import WhatsAppGUIPanel, create_approval_callback
from src.whatsapp.server import WhatsAppServer
"""

# 2. Add this initialization code after db_manager and config_manager are created:
"""
# Initialize WhatsApp integration
whatsapp_panel = None
try:
    from src.whatsapp.gui_integration import WhatsAppGUIPanel, create_approval_callback
    from src.parsing.parser_adapter import MixedInputParser, TypeTableLoader
    from src.business.calculation_engine import CalculationEngine

    whatsapp_panel = WhatsAppGUIPanel(db_manager=db_manager)

    # Create parser and calculation engine for approval workflow
    parser = MixedInputParser()
    if db_manager:
        table_loader = TypeTableLoader(db_manager)
        sp_table, dp_table, cp_table = table_loader.load_all_tables()
        family_pana_table = table_loader.load_family_pana_table()
        calc_engine = CalculationEngine(sp_table, dp_table, cp_table, family_pana_table)
    else:
        calc_engine = CalculationEngine()

    # Set approval callback
    approval_callback = create_approval_callback(db_manager, parser, calc_engine)
    whatsapp_panel.on_approve_callback = approval_callback

    print("✅ WhatsApp integration initialized")
except Exception as e:
    print(f"⚠️ WhatsApp integration not available: {e}")
    whatsapp_panel = None
"""

# 3. Add this in the GUI creation section (after dpg.create_viewport):
"""
# Create WhatsApp panel
if whatsapp_panel:
    whatsapp_panel.create_panel()
"""

# 4. Add WhatsApp button to your toolbar (find where menu bar is created):
"""
# Add to menu bar or toolbar
if whatsapp_panel:
    with dpg.menu(label="WhatsApp"):
        dpg.add_menu_item(label="Open Panel", callback=lambda: dpg.configure_item("whatsapp_panel", show=True))
        dpg.add_menu_item(label="Start Server", callback=lambda: whatsapp_panel._start_server_callback())
        dpg.add_menu_item(label="Stop Server", callback=lambda: whatsapp_panel._stop_server_callback())
"""

# 5. Add cleanup on exit:
"""
# Before dpg.destroy_context()
if whatsapp_panel and whatsapp_panel.server:
    whatsapp_panel.stop_server()
"""


# ============================================================
# COMPLETE STANDALONE EXAMPLE
# ============================================================

def run_whatsapp_demo():
    """Run a standalone demo of the WhatsApp integration"""
    import sys
    from pathlib import Path

    # Add src to path
    src_path = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(src_path))

    import dearpygui.dearpygui as dpg

    # Import components
    from src.database.db_manager import create_database_manager
    from src.whatsapp.gui_integration import WhatsAppGUIPanel, create_approval_callback
    from src.parsing.parser_adapter import MixedInputParser, TypeTableLoader
    from src.business.calculation_engine import CalculationEngine

    # Initialize database
    db_manager = create_database_manager()
    db_manager.initialize_database()

    # Create WhatsApp panel
    whatsapp_panel = WhatsAppGUIPanel(db_manager=db_manager)

    # Setup parser and calc engine
    parser = MixedInputParser()
    try:
        table_loader = TypeTableLoader(db_manager)
        sp_table, dp_table, cp_table = table_loader.load_all_tables()
        family_pana_table = table_loader.load_family_pana_table()
        calc_engine = CalculationEngine(sp_table, dp_table, cp_table, family_pana_table)
    except:
        calc_engine = CalculationEngine()

    # Set approval callback
    approval_callback = create_approval_callback(db_manager, parser, calc_engine)
    whatsapp_panel.on_approve_callback = approval_callback

    # Create DearPyGUI context
    dpg.create_context()
    dpg.create_viewport(title='WhatsApp Integration Demo', width=600, height=700)

    # Create main window
    with dpg.window(label="Main Window", tag="primary_window"):
        dpg.add_text("WhatsApp Integration Demo")
        dpg.add_separator()

        dpg.add_button(label="Open WhatsApp Panel",
                       callback=lambda: dpg.configure_item("whatsapp_panel", show=True))

        dpg.add_spacer(height=10)
        dpg.add_text("Instructions:", color=(100, 200, 255))
        dpg.add_text("1. Click 'Open WhatsApp Panel'")
        dpg.add_text("2. Configure server settings")
        dpg.add_text("3. Click 'Start Server'")
        dpg.add_text("4. Note the server address")
        dpg.add_text("5. Configure Android app with the address")
        dpg.add_text("6. Send WhatsApp messages to see them appear")

    # Create WhatsApp panel
    whatsapp_panel.create_panel()

    # Setup and show
    dpg.setup_dearpygui()
    dpg.show_viewport()
    dpg.set_primary_window("primary_window", True)

    # Main loop
    while dpg.is_dearpygui_running():
        dpg.render_dearpygui_frame()

    # Cleanup
    if whatsapp_panel.server:
        whatsapp_panel.stop_server()

    dpg.destroy_context()


if __name__ == '__main__':
    run_whatsapp_demo()
