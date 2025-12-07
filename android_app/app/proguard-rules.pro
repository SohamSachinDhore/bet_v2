# Add project specific ProGuard rules here.
# By default, the flags in this file are appended to flags specified
# in /sdk/tools/proguard/proguard-android.txt

# Keep notification listener service
-keep class com.rickymama.notifier.NotificationService { *; }
-keep class com.rickymama.notifier.BootReceiver { *; }

# Keep data classes
-keep class com.rickymama.notifier.ApiClient$* { *; }

# Coroutines
-keepnames class kotlinx.coroutines.internal.MainDispatcherFactory {}
-keepnames class kotlinx.coroutines.CoroutineExceptionHandler {}

# JSON
-keepattributes Signature
-keepattributes *Annotation*
