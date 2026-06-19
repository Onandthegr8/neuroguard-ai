package com.neuroguard.app

import android.accessibilityservice.AccessibilityService
import android.accessibilityservice.AccessibilityServiceInfo
import android.content.Intent
import android.os.SystemClock
import android.view.KeyEvent
import android.view.accessibility.AccessibilityEvent
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.embedding.engine.dart.DartExecutor
import io.flutter.plugin.common.MethodChannel

/**
 * KeystrokeAccessibilityService
 *
 * Captures key-DOWN and key-UP events system-wide and forwards only
 * anonymized timing metadata to Flutter via MethodChannel.
 *
 * PRIVACY: The actual character is never sent — only a category label:
 *   'alpha', 'digit', 'backspace', 'space', 'punct', 'special'
 *
 * MANIFEST entry required in AndroidManifest.xml:
 *   <service
 *     android:name=".KeystrokeAccessibilityService"
 *     android:permission="android.permission.BIND_ACCESSIBILITY_SERVICE"
 *     android:exported="true">
 *     <intent-filter>
 *       <action android:name="android.accessibilityservice.AccessibilityService"/>
 *     </intent-filter>
 *     <meta-data
 *       android:name="android.accessibilityservice"
 *       android:resource="@xml/accessibility_service_config"/>
 *   </service>
 *
 * res/xml/accessibility_service_config.xml:
 *   <accessibility-service
 *     xmlns:android="http://schemas.android.com/apk/res/android"
 *     android:accessibilityEventTypes="typeAllMask"
 *     android:accessibilityFlags="flagRequestFilterKeyEvents"
 *     android:canRequestFilterKeyEvents="true"
 *     android:description="@string/accessibility_service_description"
 *     android:notificationTimeout="100"/>
 */
class KeystrokeAccessibilityService : AccessibilityService() {

    companion object {
        private const val CHANNEL = "com.neuroguard/keystroke"

        // Shared engine reference set by MainActivity
        var flutterEngine: FlutterEngine? = null
    }

    private var methodChannel: MethodChannel? = null

    override fun onCreate() {
        super.onCreate()
        flutterEngine?.let { engine ->
            methodChannel = MethodChannel(engine.dartExecutor.binaryMessenger, CHANNEL)
            methodChannel?.invokeMethod("onAccessibilityEnabled", mapOf("app_context" to "other"))
        }
    }

    override fun onServiceConnected() {
        val info = serviceInfo ?: AccessibilityServiceInfo()
        info.flags = info.flags or
                AccessibilityServiceInfo.FLAG_REQUEST_FILTER_KEY_EVENTS
        serviceInfo = info
    }

    override fun onKeyEvent(event: KeyEvent): Boolean {
        val action = when (event.action) {
            KeyEvent.ACTION_DOWN -> 0
            KeyEvent.ACTION_UP   -> 1
            else                 -> return false
        }

        val category = categorise(event.keyCode)
        val tsMs     = System.currentTimeMillis()

        methodChannel?.invokeMethod(
            "onKeyEvent", mapOf(
                "category"     to category,
                "action"       to action,
                "timestamp_ms" to tsMs,
            )
        )
        return false // do NOT consume — let the event propagate normally
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent) {
        // Detect app context changes (package name only — never content)
        if (event.eventType == AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED) {
            val pkg = event.packageName?.toString() ?: return
            val context = appContextLabel(pkg)
            methodChannel?.invokeMethod("onAppContextChanged", mapOf("app_context" to context))
        }
    }

    override fun onInterrupt() {
        methodChannel?.invokeMethod("onAccessibilityDisabled", null)
    }

    override fun onUnbind(intent: Intent?): Boolean {
        methodChannel?.invokeMethod("onAccessibilityDisabled", null)
        return super.onUnbind(intent)
    }

    // ── Helpers ─────────────────────────────────────────────────────────────

    private fun categorise(keyCode: Int): String = when {
        keyCode in KeyEvent.KEYCODE_A..KeyEvent.KEYCODE_Z            -> "alpha"
        keyCode in KeyEvent.KEYCODE_0..KeyEvent.KEYCODE_9            -> "digit"
        keyCode == KeyEvent.KEYCODE_DEL                              -> "backspace"
        keyCode == KeyEvent.KEYCODE_SPACE                            -> "space"
        keyCode in setOf(
            KeyEvent.KEYCODE_PERIOD, KeyEvent.KEYCODE_COMMA,
            KeyEvent.KEYCODE_SEMICOLON, KeyEvent.KEYCODE_APOSTROPHE,
            KeyEvent.KEYCODE_SLASH, KeyEvent.KEYCODE_MINUS,
        )                                                            -> "punct"
        else                                                         -> "special"
    }

    /**
     * Map package names to generalised context labels.
     * No identifying package name is transmitted — only the label.
     */
    private fun appContextLabel(pkg: String): String = when {
        pkg.contains("messenger") || pkg.contains("whatsapp") ||
        pkg.contains("telegram")  || pkg.contains("signal")   -> "messaging"
        pkg.contains("gmail")     || pkg.contains("outlook")  ||
        pkg.contains("mail")                                   -> "email"
        pkg.contains("docs")      || pkg.contains("office")   ||
        pkg.contains("word")      || pkg.contains("notes")    -> "document"
        pkg.contains("browser")   || pkg.contains("chrome")   ||
        pkg.contains("firefox")   || pkg.contains("safari")   -> "browser"
        else                                                   -> "other"
    }
}
