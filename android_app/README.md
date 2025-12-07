# RickyMama WhatsApp Notification Listener

Android app that listens to WhatsApp notifications and forwards them to the RickyMama desktop application.

## Features

- Listens to WhatsApp notifications using NotificationListenerService
- Filters messages by specific WhatsApp groups
- Extracts sender name and message content
- Sends data to desktop app via HTTP POST over local WiFi
- Configurable server address and port
- Background service that runs continuously

## Setup Instructions

### 1. Create Android Project in Android Studio

1. Open Android Studio
2. Create New Project → Empty Activity
3. Name: `RickyMamaNotifier`
4. Package: `com.rickymama.notifier`
5. Language: Kotlin
6. Minimum SDK: API 26 (Android 8.0)

### 2. Copy Project Files

Copy the following files to your Android project:

```
app/
├── src/main/
│   ├── AndroidManifest.xml
│   ├── java/com/rickymama/notifier/
│   │   ├── MainActivity.kt        # Jetpack Compose UI
│   │   ├── NotificationService.kt # Notification listener
│   │   ├── ApiClient.kt           # HTTP client
│   │   ├── SettingsManager.kt     # Settings storage
│   │   └── BootReceiver.kt        # Boot receiver
│   └── res/
│       └── values/
│           ├── strings.xml
│           ├── colors.xml
│           └── themes.xml
├── build.gradle.kts
└── proguard-rules.pro
```

**Note:** This app uses Jetpack Compose for UI, so no XML layouts are needed.

### 3. Required Permissions

The app needs Notification Access permission which must be granted manually:
1. Go to Settings → Apps → Special access → Notification access
2. Enable for "RickyMama Notifier"

### 4. Configuration

1. Enter the desktop computer's IP address (shown in RickyMama WhatsApp panel)
2. Enter the port (default: 8765)
3. Add WhatsApp group names to filter (comma separated)
4. Click "Save Settings"
5. Click "Start Service"

### 5. Testing

1. Send a test message in your WhatsApp group
2. Check the desktop app's WhatsApp panel for the message
3. Approve or edit before inserting into database

## Building the APK

```bash
cd android_app
./gradlew assembleDebug
# APK will be at app/build/outputs/apk/debug/app-debug.apk
```

## Troubleshooting

1. **No messages received**: Check if both devices are on the same WiFi network
2. **Permission denied**: Grant Notification Access permission in Android settings
3. **Connection refused**: Ensure desktop app's WhatsApp server is running
4. **Wrong IP**: Use the IP shown in the desktop app's WhatsApp panel
