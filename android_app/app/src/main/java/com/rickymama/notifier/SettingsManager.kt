package com.rickymama.notifier

import android.content.Context
import android.content.SharedPreferences

class SettingsManager(context: Context) {

    companion object {
        private const val PREFS_NAME = "rickymama_notifier_prefs"
        private const val KEY_SERVER_HOST = "server_host"
        private const val KEY_SERVER_PORT = "server_port"
        private const val KEY_ALLOWED_GROUPS = "allowed_groups"
        private const val KEY_SERVICE_ENABLED = "service_enabled"

        private const val DEFAULT_HOST = ""
        private const val DEFAULT_PORT = 8765
        private const val DEFAULT_GROUPS = ""
    }

    private val prefs: SharedPreferences = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)

    fun saveSettings(host: String, port: Int, allowedGroups: String) {
        prefs.edit().apply {
            putString(KEY_SERVER_HOST, host)
            putInt(KEY_SERVER_PORT, port)
            putString(KEY_ALLOWED_GROUPS, allowedGroups)
            apply()
        }
    }

    fun getServerHost(): String {
        return prefs.getString(KEY_SERVER_HOST, DEFAULT_HOST) ?: DEFAULT_HOST
    }

    fun getServerPort(): Int {
        return prefs.getInt(KEY_SERVER_PORT, DEFAULT_PORT)
    }

    fun getAllowedGroups(): String {
        return prefs.getString(KEY_ALLOWED_GROUPS, DEFAULT_GROUPS) ?: DEFAULT_GROUPS
    }

    fun setServiceEnabled(enabled: Boolean) {
        prefs.edit().putBoolean(KEY_SERVICE_ENABLED, enabled).apply()
    }

    fun isServiceEnabled(): Boolean {
        return prefs.getBoolean(KEY_SERVICE_ENABLED, false)
    }

    fun getServerUrl(): String {
        val host = getServerHost()
        val port = getServerPort()
        return if (host.isNotBlank()) "http://$host:$port" else ""
    }
}
