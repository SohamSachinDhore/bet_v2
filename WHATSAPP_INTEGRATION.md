# WhatsApp Integration Guide for RickyMama

## Overview

This integration adds a WhatsApp notification listener that:
1. Receives WhatsApp messages from an Android phone on your local network
2. Displays them in a pending approval queue in the GUI
3. Allows editing before approval
4. Inserts approved entries into the main database

## Architecture

```
┌─────────────────────┐      HTTP POST        ┌─────────────────────────┐
│   Android Phone     │ ─────────────────────▶│   RickyMama Desktop     │
│   (Notification     │   (Same WiFi Network) │   (Python + DearPyGUI)  │
│    Listener App)    │                       │                         │
└─────────────────────┘                       └───────────┬─────────────┘
                                                          │
                                                          ▼
                                              ┌─────────────────────────┐
                                              │   Pending Queue         │
                                              │   ┌─────────────────┐   │
                                              │   │ WhatsApp Panel  │   │
                                              │   │ - View messages │   │
                                              │   │ - Edit content  │   │
                                              │   │ - Approve/Reject│   │
                                              │   └─────────────────┘   │
                                              └───────────┬─────────────┘
                                                          │
                                                          ▼
                                              ┌─────────────────────────┐
                                              │   SQLite Database       │
                                              │   (After Approval)      │
                                              └─────────────────────────┘
```

## Quick Start

### Step 1: Install Dependencies

No additional Python dependencies required - uses only standard library (http.server, json, threading, sqlite3).

### Step 2: Integrate with Main GUI

Add the following code to `main_gui_working.py`:

#### A. Add imports at the top (after existing imports):

```python
# WhatsApp Integration
whatsapp_panel = None
try:
    from src.whatsapp.gui_integration import WhatsAppGUIPanel, create_approval_callback
    WHATSAPP_AVAILABLE = True
except ImportError:
    WHATSAPP_AVAILABLE = False
```

#### B. Add initialization after database setup (around line 55):

```python
# Initialize WhatsApp integration
if WHATSAPP_AVAILABLE and db_manager:
    try:
        from src.parsing.parser_adapter import MixedInputParser, TypeTableLoader
        from src.business.calculation_engine import CalculationEngine

        whatsapp_panel = WhatsAppGUIPanel(db_manager=db_manager)

        # Create parser and calculation engine
        parser = MixedInputParser()
        table_loader = TypeTableLoader(db_manager)
        sp_table, dp_table, cp_table = table_loader.load_all_tables()
        family_pana_table = table_loader.load_family_pana_table()
        calc_engine = CalculationEngine(sp_table, dp_table, cp_table, family_pana_table)

        # Set approval callback
        approval_callback = create_approval_callback(db_manager, parser, calc_engine)
        whatsapp_panel.on_approve_callback = approval_callback

        print("✅ WhatsApp integration initialized")
    except Exception as e:
        print(f"⚠️ WhatsApp integration error: {e}")
        whatsapp_panel = None
```

#### C. Add WhatsApp button in the action buttons row (around line 3092, after Export button):

```python
# WhatsApp button
if WHATSAPP_AVAILABLE:
    dpg.add_spacer(width=15)
    dpg.add_button(
        label="WhatsApp",
        callback=lambda: open_whatsapp_panel(),
        tag="whatsapp_btn",
        width=100,
        height=35
    )
```

#### D. Add the WhatsApp panel creation and helper function (before dpg.create_viewport):

```python
# WhatsApp Panel
if WHATSAPP_AVAILABLE and whatsapp_panel:
    whatsapp_panel.create_panel()

def open_whatsapp_panel():
    """Open WhatsApp panel"""
    if WHATSAPP_AVAILABLE and whatsapp_panel:
        dpg.configure_item("whatsapp_panel", show=True)
        whatsapp_panel._refresh_entries_list()
        whatsapp_panel._update_combos()
```

#### E. Add cleanup before dpg.destroy_context() in main():

```python
# Cleanup WhatsApp server
if WHATSAPP_AVAILABLE and whatsapp_panel and whatsapp_panel.server:
    whatsapp_panel.stop_server()
```

### Step 3: Build Android App

1. Open Android Studio
2. Create New Project → Empty Activity (Compose)
3. Name: `RickyMamaNotifier`
4. Package: `com.rickymama.notifier`
5. Copy files from `android_app/app/src/main/` to your project
6. Build and install on your Android phone

### Step 4: Configure and Use

1. **Desktop App**:
   - Click "WhatsApp" button in the main GUI
   - Configure server port (default: 8765)
   - Click "Start Server"
   - Note the server address shown (e.g., `http://192.168.1.100:8765/message`)

2. **Android App**:
   - Grant Notification Access permission
   - Enter the desktop IP address and port
   - Optionally filter specific WhatsApp groups
   - Save settings and enable the service

3. **Usage**:
   - When WhatsApp messages arrive on your phone, they appear in the pending queue
   - Review, edit if needed, select customer and bazar
   - Click "Approve & Insert" to add to database

## File Structure

```
src/whatsapp/
├── __init__.py              # Module init
├── pending_queue.py         # Pending entries queue manager
├── server.py                # HTTP server for receiving messages
├── gui_integration.py       # DearPyGUI panel integration
└── integration_example.py   # Standalone demo

android_app/
├── README.md                # Android app setup instructions
├── build.gradle.kts         # Root build config
├── settings.gradle.kts      # Project settings
├── gradle.properties        # Gradle properties
└── app/
    ├── build.gradle.kts     # App build config
    └── src/main/
        ├── AndroidManifest.xml
        └── java/com/rickymama/notifier/
            ├── MainActivity.kt        # Main UI (Jetpack Compose)
            ├── NotificationService.kt # Notification listener
            ├── ApiClient.kt           # HTTP client
            ├── SettingsManager.kt     # Settings storage
            └── BootReceiver.kt        # Boot receiver
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/message` | POST | Submit WhatsApp message |
| `/batch` | POST | Submit multiple messages |
| `/status` | GET | Get server status |
| `/pending` | GET | Get pending entries |
| `/ping` | POST | Test connection |

### Message Format

```json
{
    "sender_name": "John Doe",
    "sender_phone": "+1234567890",
    "group_name": "My Trading Group",
    "message": "123=100\n456=200\n1SP=50"
}
```

## Troubleshooting

### Desktop Issues

1. **Server won't start**: Check if port is already in use
2. **No messages received**: Ensure both devices on same WiFi network
3. **Messages not parsing**: Check message format matches supported patterns

### Android Issues

1. **Notification access not working**: Re-grant permission in Settings
2. **Service stops**: Enable "Battery optimization exempt" for the app
3. **Connection fails**: Verify IP address and port are correct

## Security Notes

- The server only accepts connections from the local network
- No authentication required (relies on network security)
- Messages are stored locally in SQLite database
- No data is sent to external servers

## Supported Message Formats

The integration uses the same parser as the main app:

- **PANA**: `123=100`, `128/129/120=100`
- **TYPE**: `1SP=100`, `5DP=200`, `12CP=150`
- **TIME**: `1=100`, `1,2,3=300`
- **JODI**: `22-24-26=500`, `12:34:56=200`
- **MULTI**: `38x700`, `38*700`
- **FAMILY**: `678family=200`
