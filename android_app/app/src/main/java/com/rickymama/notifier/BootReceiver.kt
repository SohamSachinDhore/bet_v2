package com.rickymama.notifier

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.util.Log

class BootReceiver : BroadcastReceiver() {

    companion object {
        private const val TAG = "RickyMamaBootReceiver"
    }

    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action == Intent.ACTION_BOOT_COMPLETED ||
            intent.action == "android.intent.action.QUICKBOOT_POWERON") {

            Log.d(TAG, "Boot completed, checking service state")

            val settingsManager = SettingsManager(context)

            if (settingsManager.isServiceEnabled()) {
                Log.d(TAG, "Reactivating notification service")
                NotificationService.setActive(context, true)
            }
        }
    }
}
