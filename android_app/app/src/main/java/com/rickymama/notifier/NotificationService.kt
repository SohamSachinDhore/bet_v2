package com.rickymama.notifier

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.ComponentName
import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import android.service.notification.NotificationListenerService
import android.service.notification.StatusBarNotification
import android.util.Log
import androidx.core.app.NotificationCompat
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch

class NotificationService : NotificationListenerService() {

    companion object {
        private const val TAG = "RickyMamaNotifier"
        private const val WHATSAPP_PACKAGE = "com.whatsapp"
        private const val WHATSAPP_BUSINESS_PACKAGE = "com.whatsapp.w4b"
        private const val CHANNEL_ID = "rickymama_notifier_channel"
        private const val NOTIFICATION_ID = 1001
        private const val PREF_SERVICE_ACTIVE = "service_active"
        private const val PREF_DEBUG_INFO = "debug_info"
        private const val PREF_NOTIF_COUNT = "notification_count"
        private const val PREF_LAST_PACKAGE = "last_package"

        @Volatile
        private var instance: NotificationService? = null

        private fun getPrefs(context: android.content.Context) =
            context.getSharedPreferences("rickymama_service", android.content.Context.MODE_PRIVATE)

        fun setActive(context: android.content.Context, active: Boolean) {
            getPrefs(context).edit().putBoolean(PREF_SERVICE_ACTIVE, active).apply()
            Log.d(TAG, "Service active state saved: $active")
        }

        fun isServiceActive(context: android.content.Context): Boolean {
            return getPrefs(context).getBoolean(PREF_SERVICE_ACTIVE, false)
        }

        fun saveDebugInfo(context: android.content.Context, info: String) {
            val count = getPrefs(context).getInt(PREF_NOTIF_COUNT, 0) + 1
            getPrefs(context).edit()
                .putString(PREF_DEBUG_INFO, info)
                .putInt(PREF_NOTIF_COUNT, count)
                .apply()
        }

        fun saveLastPackage(context: android.content.Context, pkg: String) {
            getPrefs(context).edit().putString(PREF_LAST_PACKAGE, pkg).apply()
        }

        fun getDebugInfo(context: android.content.Context): String {
            return getPrefs(context).getString(PREF_DEBUG_INFO, "No notifications yet") ?: "No notifications yet"
        }

        fun getNotificationCount(context: android.content.Context): Int {
            return getPrefs(context).getInt(PREF_NOTIF_COUNT, 0)
        }

        fun getLastPackage(context: android.content.Context): String {
            return getPrefs(context).getString(PREF_LAST_PACKAGE, "None") ?: "None"
        }

        fun clearDebugInfo(context: android.content.Context) {
            getPrefs(context).edit()
                .putInt(PREF_NOTIF_COUNT, 0)
                .putString(PREF_DEBUG_INFO, "Cleared")
                .putString(PREF_LAST_PACKAGE, "None")
                .apply()
        }

        // Keep old method for compatibility
        @Deprecated("Use setActive(context, active) instead")
        fun setActive(active: Boolean) {
            instance?.let {
                setActive(it.applicationContext, active)
            } ?: Log.w(TAG, "No instance available, cannot set active state")
        }

        fun isServiceActive(): Boolean {
            return instance?.let { isServiceActive(it.applicationContext) } ?: false
        }
    }

    private val serviceScope = CoroutineScope(Dispatchers.IO + SupervisorJob())
    private lateinit var settingsManager: SettingsManager

    override fun onCreate() {
        super.onCreate()
        instance = this
        settingsManager = SettingsManager(this)
        createNotificationChannel()
        Log.d(TAG, "NotificationService created")
    }

    override fun onDestroy() {
        super.onDestroy()
        instance = null
        Log.d(TAG, "NotificationService destroyed")
    }

    override fun onListenerConnected() {
        super.onListenerConnected()
        Log.d(TAG, "NotificationListener connected")
        saveDebugInfo(applicationContext, "Listener CONNECTED at ${System.currentTimeMillis()}")
        // Note: Do NOT call startForeground() - system manages NotificationListenerService
    }

    override fun onListenerDisconnected() {
        super.onListenerDisconnected()
        Log.d(TAG, "NotificationListener disconnected")
        saveDebugInfo(applicationContext, "Listener DISCONNECTED at ${System.currentTimeMillis()}")
    }

    override fun onNotificationPosted(sbn: StatusBarNotification?) {
        Log.d(TAG, ">>> onNotificationPosted called")

        if (sbn == null) {
            Log.d(TAG, "Notification is null, ignoring")
            return
        }

        // Always log the package for debugging
        val packageName = sbn.packageName
        saveLastPackage(applicationContext, packageName)
        Log.d(TAG, "Received notification from: $packageName")

        val isActive = isServiceActive(applicationContext)
        Log.d(TAG, "Package: $packageName, isActive: $isActive")

        // Save debug info for ALL notifications
        saveDebugInfo(applicationContext, "Got notif from: $packageName (active=$isActive)")

        if (!isActive) {
            Log.d(TAG, "Service not active, ignoring notification")
            return
        }

        if (packageName != WHATSAPP_PACKAGE && packageName != WHATSAPP_BUSINESS_PACKAGE) {
            Log.d(TAG, "Not a WhatsApp notification, ignoring: $packageName")
            return
        }

        Log.d(TAG, "Processing WhatsApp notification...")
        saveDebugInfo(applicationContext, "Processing WhatsApp from: $packageName")

        try {
            processWhatsAppNotification(sbn)
        } catch (e: Exception) {
            Log.e(TAG, "Error processing notification", e)
            saveDebugInfo(applicationContext, "ERROR: ${e.message}")
        }
    }

    private fun processWhatsAppNotification(sbn: StatusBarNotification) {
        val notification = sbn.notification
        val extras = notification.extras

        val title = extras.getCharSequence(Notification.EXTRA_TITLE)?.toString() ?: ""
        val text = extras.getCharSequence(Notification.EXTRA_TEXT)?.toString() ?: ""
        val bigText = extras.getCharSequence(Notification.EXTRA_BIG_TEXT)?.toString() ?: ""

        val messageContent = when {
            bigText.isNotBlank() -> bigText
            text.isNotBlank() -> text
            else -> return
        }

        val (senderName, groupName) = parseWhatsAppTitle(title)

        if (text.contains(" messages") || title.contains(" messages")) {
            Log.d(TAG, "Skipping summary notification: $title")
            return
        }

        val allowedGroups = settingsManager.getAllowedGroups()
            .split(",")
            .map { it.trim() }
            .filter { it.isNotBlank() }

        if (allowedGroups.isNotEmpty() && groupName !in allowedGroups) {
            Log.d(TAG, "Group not in allowed list: $groupName")
            return
        }

        Log.d(TAG, "Processing WhatsApp message - Sender: $senderName, Group: $groupName")
        Log.d(TAG, "Message content: $messageContent")

        sendToServer(senderName, groupName, messageContent)
    }

    private fun parseWhatsAppTitle(title: String): Pair<String, String> {
        return when {
            title.contains(" @ ") -> {
                val parts = title.split(" @ ", limit = 2)
                Pair(parts[0].trim(), parts.getOrElse(1) { "" }.trim())
            }
            title.contains(":") -> {
                val parts = title.split(":", limit = 2)
                Pair(parts.getOrElse(1) { parts[0] }.trim(), parts[0].trim())
            }
            else -> {
                Pair(title.trim(), "")
            }
        }
    }

    private fun sendToServer(senderName: String, groupName: String, message: String) {
        val host = settingsManager.getServerHost()
        val port = settingsManager.getServerPort()

        if (host.isBlank()) {
            Log.w(TAG, "Server host not configured")
            return
        }

        serviceScope.launch {
            try {
                val success = ApiClient.sendMessage(
                    host = host,
                    port = port,
                    senderName = senderName,
                    senderPhone = "",
                    groupName = groupName,
                    message = message
                )

                if (success) {
                    Log.d(TAG, "Message sent successfully to server")
                } else {
                    Log.w(TAG, "Failed to send message to server")
                }
            } catch (e: Exception) {
                Log.e(TAG, "Error sending message to server", e)
            }
        }
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID,
                "RickyMama Notifier Service",
                NotificationManager.IMPORTANCE_LOW
            ).apply {
                description = "Notification listener service for RickyMama"
                setShowBadge(false)
            }

            val notificationManager = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
            notificationManager.createNotificationChannel(channel)
        }
    }

    private fun createForegroundNotification(): Notification {
        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("RickyMama Notifier")
            .setContentText("Listening for WhatsApp messages...")
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .setOngoing(true)
            .build()
    }
}
