package online.taleempk.studyhub

import android.Manifest
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Matrix
import android.os.Build
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel
import java.io.File
import java.io.FileOutputStream
import kotlin.math.roundToInt

class MainActivity : FlutterActivity() {
    private val notificationBridge = "taleempk/native_notifications"
    private val mediaBridge = "taleempk/media_tools"
    private val notificationChannelId = "taleempk_messages"

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        createMessageChannel()

        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, notificationBridge)
            .setMethodCallHandler { call, result ->
                when (call.method) {
                    "requestPermission" -> {
                        requestNotificationPermissionIfNeeded()
                        result.success(null)
                    }
                    "showNotification" -> {
                        val id = call.argument<Int>("id") ?: 1
                        val title = call.argument<String>("title") ?: "TaleemPK"
                        val body = call.argument<String>("body") ?: "You have a new update."
                        val payload = call.argument<String>("payload") ?: ""
                        showSystemNotification(id, title, body, payload)
                        result.success(null)
                    }
                    else -> result.notImplemented()
                }
            }

        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, mediaBridge)
            .setMethodCallHandler { call, result ->
                when (call.method) {
                    "editPhoto" -> {
                        try {
                            val path = call.argument<String>("path")
                                ?: throw IllegalArgumentException("Missing photo path")
                            val turns = call.argument<Int>("turns") ?: 0
                            val flip = call.argument<Boolean>("flip") ?: false
                            val crop = call.argument<String>("crop") ?: "original"
                            result.success(editPhoto(path, turns, flip, crop))
                        } catch (error: Throwable) {
                            result.error("PHOTO_EDIT", error.message ?: "Photo edit failed", null)
                        }
                    }
                    else -> result.notImplemented()
                }
            }
    }

    private fun createMessageChannel() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val channel = NotificationChannel(
            notificationChannelId,
            "Messages and activity",
            NotificationManager.IMPORTANCE_HIGH,
        ).apply {
            description = "TaleemPK messages, replies and account activity"
            enableVibration(true)
            lockscreenVisibility = Notification.VISIBILITY_PRIVATE
        }
        getSystemService(NotificationManager::class.java).createNotificationChannel(channel)
    }

    private fun requestNotificationPermissionIfNeeded() {
        if (Build.VERSION.SDK_INT >= 33 &&
            checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED
        ) {
            requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), 2901)
        }
    }

    private fun showSystemNotification(id: Int, title: String, body: String, payload: String) {
        if (Build.VERSION.SDK_INT >= 33 &&
            checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED
        ) return

        val intent = Intent(this, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_SINGLE_TOP or Intent.FLAG_ACTIVITY_CLEAR_TOP
            putExtra("taleempk_payload", payload)
        }
        val pendingIntent = PendingIntent.getActivity(
            this,
            id,
            intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        val builder = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            Notification.Builder(this, notificationChannelId)
        } else {
            @Suppress("DEPRECATION")
            Notification.Builder(this)
        }
        builder
            .setSmallIcon(applicationInfo.icon)
            .setContentTitle(title)
            .setContentText(body)
            .setStyle(Notification.BigTextStyle().bigText(body))
            .setContentIntent(pendingIntent)
            .setAutoCancel(true)
            .setCategory(Notification.CATEGORY_MESSAGE)
            .setVisibility(Notification.VISIBILITY_PRIVATE)
            .setOnlyAlertOnce(true)

        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) {
            @Suppress("DEPRECATION")
            builder.setPriority(Notification.PRIORITY_HIGH)
        }
        val manager = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        manager.notify(id.coerceAtLeast(1), builder.build())
    }

    private fun editPhoto(path: String, turns: Int, flip: Boolean, crop: String): String {
        var bitmap = BitmapFactory.decodeFile(path)
            ?: throw IllegalArgumentException("Android could not decode this image")

        val normalizedTurns = ((turns % 4) + 4) % 4
        if (normalizedTurns != 0 || flip) {
            val matrix = Matrix().apply {
                if (normalizedTurns != 0) postRotate(90f * normalizedTurns)
                if (flip) postScale(-1f, 1f)
            }
            val transformed = Bitmap.createBitmap(
                bitmap,
                0,
                0,
                bitmap.width,
                bitmap.height,
                matrix,
                true,
            )
            if (transformed !== bitmap) bitmap.recycle()
            bitmap = transformed
        }

        val targetRatio = when (crop) {
            "square" -> 1.0
            "portrait" -> 4.0 / 5.0
            "landscape" -> 16.0 / 9.0
            else -> null
        }
        if (targetRatio != null) {
            val currentRatio = bitmap.width.toDouble() / bitmap.height.toDouble()
            val cropped = if (currentRatio > targetRatio) {
                val width = (bitmap.height * targetRatio).roundToInt().coerceIn(1, bitmap.width)
                Bitmap.createBitmap(bitmap, (bitmap.width - width) / 2, 0, width, bitmap.height)
            } else if (currentRatio < targetRatio) {
                val height = (bitmap.width / targetRatio).roundToInt().coerceIn(1, bitmap.height)
                Bitmap.createBitmap(bitmap, 0, (bitmap.height - height) / 2, bitmap.width, height)
            } else {
                bitmap
            }
            if (cropped !== bitmap) bitmap.recycle()
            bitmap = cropped
        }

        val output = File(cacheDir, "taleempk_photo_${System.nanoTime()}.jpg")
        FileOutputStream(output).use { stream ->
            if (!bitmap.compress(Bitmap.CompressFormat.JPEG, 93, stream)) {
                throw IllegalStateException("Android could not save the edited image")
            }
            stream.flush()
        }
        bitmap.recycle()
        if (!output.exists() || output.length() < 256L) {
            throw IllegalStateException("Edited photo output is empty")
        }
        return output.absolutePath
    }
}
