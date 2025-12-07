package com.rickymama.notifier

import android.util.Log
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.io.OutputStreamWriter
import java.net.HttpURLConnection
import java.net.URL

object ApiClient {
    private const val TAG = "RickyMamaApiClient"
    private const val TIMEOUT = 10000

    suspend fun sendMessage(
        host: String,
        port: Int,
        senderName: String,
        senderPhone: String,
        groupName: String,
        message: String
    ): Boolean = withContext(Dispatchers.IO) {
        try {
            val url = URL("http://$host:$port/message")
            val connection = url.openConnection() as HttpURLConnection

            connection.apply {
                requestMethod = "POST"
                setRequestProperty("Content-Type", "application/json; charset=UTF-8")
                setRequestProperty("Accept", "application/json")
                connectTimeout = TIMEOUT
                readTimeout = TIMEOUT
                doOutput = true
                doInput = true
            }

            val payload = JSONObject().apply {
                put("sender_name", senderName)
                put("sender_phone", senderPhone)
                put("group_name", groupName)
                put("message", message)
                put("timestamp", System.currentTimeMillis())
            }

            OutputStreamWriter(connection.outputStream, "UTF-8").use { writer ->
                writer.write(payload.toString())
                writer.flush()
            }

            val responseCode = connection.responseCode
            Log.d(TAG, "Server response code: $responseCode")

            if (responseCode == HttpURLConnection.HTTP_OK) {
                val response = connection.inputStream.bufferedReader().use { it.readText() }
                val jsonResponse = JSONObject(response)
                val success = jsonResponse.optBoolean("success", false)
                Log.d(TAG, "Server response: $response")
                return@withContext success
            }

            return@withContext false

        } catch (e: Exception) {
            Log.e(TAG, "Error sending message: ${e.message}", e)
            return@withContext false
        }
    }

    suspend fun testConnection(host: String, port: Int): Boolean = withContext(Dispatchers.IO) {
        try {
            val url = URL("http://$host:$port/ping")
            val connection = url.openConnection() as HttpURLConnection

            connection.apply {
                requestMethod = "POST"
                setRequestProperty("Content-Type", "application/json")
                connectTimeout = 5000
                readTimeout = 5000
                doOutput = true
            }

            OutputStreamWriter(connection.outputStream).use { writer ->
                writer.write("{}")
                writer.flush()
            }

            val responseCode = connection.responseCode
            Log.d(TAG, "Ping response code: $responseCode")

            if (responseCode == HttpURLConnection.HTTP_OK) {
                val response = connection.inputStream.bufferedReader().use { it.readText() }
                val jsonResponse = JSONObject(response)
                return@withContext jsonResponse.optBoolean("success", false)
            }

            return@withContext false

        } catch (e: Exception) {
            Log.e(TAG, "Connection test failed: ${e.message}", e)
            return@withContext false
        }
    }

    suspend fun getServerStatus(host: String, port: Int): ServerStatus? = withContext(Dispatchers.IO) {
        try {
            val url = URL("http://$host:$port/status")
            val connection = url.openConnection() as HttpURLConnection

            connection.apply {
                requestMethod = "GET"
                setRequestProperty("Accept", "application/json")
                connectTimeout = TIMEOUT
                readTimeout = TIMEOUT
            }

            if (connection.responseCode == HttpURLConnection.HTTP_OK) {
                val response = connection.inputStream.bufferedReader().use { it.readText() }
                val json = JSONObject(response)

                return@withContext ServerStatus(
                    status = json.optString("status", "unknown"),
                    pendingCount = json.optInt("pending_count", 0),
                    timestamp = json.optString("timestamp", "")
                )
            }

            return@withContext null

        } catch (e: Exception) {
            Log.e(TAG, "Error getting server status: ${e.message}", e)
            return@withContext null
        }
    }

    data class ServerStatus(
        val status: String,
        val pendingCount: Int,
        val timestamp: String
    )
}
