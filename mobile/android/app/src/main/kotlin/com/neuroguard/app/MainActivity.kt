package com.neuroguard.app

import android.content.Intent
import android.provider.Settings
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel

class MainActivity : FlutterActivity() {

    companion object {
        private const val CHANNEL = "com.neuroguard/keystroke"
    }

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)

        // Share engine reference with the Accessibility Service
        KeystrokeAccessibilityService.flutterEngine = flutterEngine

        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, CHANNEL).apply {
            setMethodCallHandler { call, result ->
                when (call.method) {
                    "requestPermission" -> {
                        // Open system Accessibility Settings so the user can enable the service
                        startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS))
                        result.success(true)
                    }
                    "isServiceActive" -> {
                        result.success(isAccessibilityServiceEnabled())
                    }
                    else -> result.notImplemented()
                }
            }
        }
    }

    private fun isAccessibilityServiceEnabled(): Boolean {
        val enabledServices = Settings.Secure.getString(
            contentResolver,
            Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES,
        ) ?: return false
        val componentName = "$packageName/${KeystrokeAccessibilityService::class.java.canonicalName}"
        return enabledServices.split(":").any { it.equals(componentName, ignoreCase = true) }
    }
}
