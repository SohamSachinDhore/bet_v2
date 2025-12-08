package com.rickymama.notifier

import android.content.Intent
import android.os.Bundle
import android.provider.Settings
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.launch

class MainActivity : ComponentActivity() {

    private lateinit var settingsManager: SettingsManager

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        settingsManager = SettingsManager(this)

        setContent {
            MaterialTheme {
                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = MaterialTheme.colorScheme.background
                ) {
                    MainScreen(settingsManager)
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MainScreen(settingsManager: SettingsManager) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()

    // State - restore saved service state
    val savedServiceState = NotificationService.isServiceActive(context)
    var serverHost by remember { mutableStateOf(settingsManager.getServerHost()) }
    var serverPort by remember { mutableStateOf(settingsManager.getServerPort().toString()) }
    var allowedGroups by remember { mutableStateOf(settingsManager.getAllowedGroups()) }
    var isServiceRunning by remember { mutableStateOf(savedServiceState) }
    var connectionStatus by remember { mutableStateOf(if (savedServiceState) "Service active - listening" else "Not connected") }
    var lastMessageTime by remember { mutableStateOf("Never") }
    var messageCount by remember { mutableStateOf(0) }

    // Check notification access
    val hasNotificationAccess = remember {
        mutableStateOf(isNotificationServiceEnabled(context))
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("RickyMama Notifier") },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.primaryContainer
                )
            )
        }
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(16.dp)
                .verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            // Permission Status Card
            Card(
                modifier = Modifier.fillMaxWidth(),
                colors = CardDefaults.cardColors(
                    containerColor = if (hasNotificationAccess.value)
                        Color(0xFF4CAF50).copy(alpha = 0.1f)
                    else
                        Color(0xFFF44336).copy(alpha = 0.1f)
                )
            ) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(16.dp),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Column {
                        Text(
                            "Notification Access",
                            style = MaterialTheme.typography.titleMedium
                        )
                        Text(
                            if (hasNotificationAccess.value) "Granted" else "Not Granted",
                            style = MaterialTheme.typography.bodySmall,
                            color = if (hasNotificationAccess.value) Color(0xFF4CAF50) else Color(0xFFF44336)
                        )
                    }
                    if (!hasNotificationAccess.value) {
                        Button(
                            onClick = {
                                context.startActivity(Intent(Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS))
                            }
                        ) {
                            Text("Grant")
                        }
                    }
                }
            }

            // Server Configuration Card
            Card(modifier = Modifier.fillMaxWidth()) {
                Column(
                    modifier = Modifier.padding(16.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp)
                ) {
                    Text("Server Configuration", style = MaterialTheme.typography.titleMedium)

                    OutlinedTextField(
                        value = serverHost,
                        onValueChange = { serverHost = it },
                        label = { Text("Server IP Address") },
                        placeholder = { Text("192.168.1.100") },
                        modifier = Modifier.fillMaxWidth(),
                        singleLine = true
                    )

                    OutlinedTextField(
                        value = serverPort,
                        onValueChange = { serverPort = it.filter { c -> c.isDigit() } },
                        label = { Text("Port") },
                        placeholder = { Text("8765") },
                        modifier = Modifier.fillMaxWidth(),
                        singleLine = true,
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number)
                    )

                    OutlinedTextField(
                        value = allowedGroups,
                        onValueChange = { allowedGroups = it },
                        label = { Text("Allowed WhatsApp Groups") },
                        placeholder = { Text("Group1, Group2 (leave empty for all)") },
                        modifier = Modifier.fillMaxWidth(),
                        minLines = 2,
                        maxLines = 4
                    )

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        Button(
                            onClick = {
                                settingsManager.saveSettings(
                                    serverHost,
                                    serverPort.toIntOrNull() ?: 8765,
                                    allowedGroups
                                )
                                Toast.makeText(context, "Settings saved", Toast.LENGTH_SHORT).show()
                            },
                            modifier = Modifier.weight(1f)
                        ) {
                            Text("Save Settings")
                        }

                        OutlinedButton(
                            onClick = {
                                scope.launch {
                                    connectionStatus = "Testing..."
                                    val result = ApiClient.testConnection(
                                        serverHost,
                                        serverPort.toIntOrNull() ?: 8765
                                    )
                                    connectionStatus = if (result) "Connected!" else "Failed"
                                }
                            },
                            modifier = Modifier.weight(1f)
                        ) {
                            Text("Test Connection")
                        }
                    }
                }
            }

            // Service Control Card
            Card(modifier = Modifier.fillMaxWidth()) {
                Column(
                    modifier = Modifier.padding(16.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp)
                ) {
                    Text("Service Control", style = MaterialTheme.typography.titleMedium)

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Column {
                            Text("Status: $connectionStatus")
                            Text("Messages sent: $messageCount", style = MaterialTheme.typography.bodySmall)
                            Text("Last message: $lastMessageTime", style = MaterialTheme.typography.bodySmall)
                        }

                        Switch(
                            checked = isServiceRunning,
                            onCheckedChange = { enabled ->
                                if (!hasNotificationAccess.value) {
                                    Toast.makeText(
                                        context,
                                        "Please grant notification access first",
                                        Toast.LENGTH_LONG
                                    ).show()
                                    return@Switch
                                }

                                isServiceRunning = enabled
                                NotificationService.setActive(context, enabled)
                                connectionStatus = if (enabled) "Service active - listening" else "Service inactive"
                                Toast.makeText(
                                    context,
                                    if (enabled) "Service enabled - listening for WhatsApp" else "Service disabled",
                                    Toast.LENGTH_SHORT
                                ).show()
                            }
                        )
                    }

                    // Send test message button
                    OutlinedButton(
                        onClick = {
                            scope.launch {
                                val result = ApiClient.sendMessage(
                                    host = serverHost,
                                    port = serverPort.toIntOrNull() ?: 8765,
                                    senderName = "Test User",
                                    senderPhone = "+1234567890",
                                    groupName = "Test Group",
                                    message = "123=100\n456=200\n1SP=50"
                                )
                                if (result) {
                                    messageCount++
                                    lastMessageTime = java.text.SimpleDateFormat(
                                        "HH:mm:ss",
                                        java.util.Locale.getDefault()
                                    ).format(java.util.Date())
                                    Toast.makeText(context, "Test message sent!", Toast.LENGTH_SHORT).show()
                                } else {
                                    Toast.makeText(context, "Failed to send test message", Toast.LENGTH_SHORT).show()
                                }
                            }
                        },
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Text("Send Test Message")
                    }
                }
            }

            // Debug Card - Shows notification listener status
            Card(
                modifier = Modifier.fillMaxWidth(),
                colors = CardDefaults.cardColors(
                    containerColor = Color(0xFF2196F3).copy(alpha = 0.1f)
                )
            ) {
                Column(
                    modifier = Modifier.padding(16.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    Text("Debug Info", style = MaterialTheme.typography.titleMedium)

                    var debugInfo by remember { mutableStateOf(NotificationService.getDebugInfo(context)) }
                    var notifCount by remember { mutableStateOf(NotificationService.getNotificationCount(context)) }
                    var lastPackage by remember { mutableStateOf(NotificationService.getLastPackage(context)) }

                    Text("Notifications received: $notifCount", style = MaterialTheme.typography.bodySmall)
                    Text("Last package: $lastPackage", style = MaterialTheme.typography.bodySmall)
                    Text("Last event: $debugInfo", style = MaterialTheme.typography.bodySmall)

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        OutlinedButton(
                            onClick = {
                                debugInfo = NotificationService.getDebugInfo(context)
                                notifCount = NotificationService.getNotificationCount(context)
                                lastPackage = NotificationService.getLastPackage(context)
                            }
                        ) {
                            Text("Refresh")
                        }

                        OutlinedButton(
                            onClick = {
                                NotificationService.clearDebugInfo(context)
                                debugInfo = "Cleared"
                                notifCount = 0
                                lastPackage = "None"
                            }
                        ) {
                            Text("Clear")
                        }
                    }
                }
            }

            // Instructions Card
            Card(modifier = Modifier.fillMaxWidth()) {
                Column(
                    modifier = Modifier.padding(16.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    Text("Instructions", style = MaterialTheme.typography.titleMedium)
                    Text("1. Grant Notification Access permission", style = MaterialTheme.typography.bodySmall)
                    Text("2. Enter the IP address shown in RickyMama desktop app", style = MaterialTheme.typography.bodySmall)
                    Text("3. Enter the port (default: 8765)", style = MaterialTheme.typography.bodySmall)
                    Text("4. Optionally filter specific WhatsApp groups", style = MaterialTheme.typography.bodySmall)
                    Text("5. Save settings and enable the service", style = MaterialTheme.typography.bodySmall)
                    Text("6. WhatsApp messages will appear in the desktop app", style = MaterialTheme.typography.bodySmall)
                    Text("", style = MaterialTheme.typography.bodySmall)
                    Text("Troubleshooting:", style = MaterialTheme.typography.titleSmall)
                    Text("• Disable battery optimization for this app", style = MaterialTheme.typography.bodySmall)
                    Text("• Toggle Notification Access OFF and ON", style = MaterialTheme.typography.bodySmall)
                    Text("• Reboot phone if notifications not captured", style = MaterialTheme.typography.bodySmall)
                }
            }
        }
    }
}

private fun isNotificationServiceEnabled(context: android.content.Context): Boolean {
    val pkgName = context.packageName
    val flat = Settings.Secure.getString(
        context.contentResolver,
        "enabled_notification_listeners"
    )
    return flat?.contains(pkgName) == true
}
