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
import android.graphics.Canvas
import android.graphics.ColorMatrix
import android.graphics.ColorMatrixColorFilter
import android.graphics.Matrix
import android.graphics.Paint
import android.os.Build
import android.util.Base64
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel
import org.json.JSONObject
import java.io.File
import java.io.FileOutputStream
import java.math.BigInteger
import java.nio.ByteBuffer
import java.security.AlgorithmParameters
import java.security.KeyFactory
import java.security.KeyPairGenerator
import java.security.MessageDigest
import java.security.SecureRandom
import java.security.interfaces.ECPublicKey
import java.security.spec.ECGenParameterSpec
import java.security.spec.ECPoint
import java.security.spec.ECParameterSpec
import java.security.spec.ECPublicKeySpec
import java.security.spec.PKCS8EncodedKeySpec
import javax.crypto.Cipher
import javax.crypto.KeyAgreement
import javax.crypto.Mac
import javax.crypto.spec.GCMParameterSpec
import javax.crypto.spec.SecretKeySpec
import kotlin.math.max
import kotlin.math.roundToInt

class MainActivity : FlutterActivity() {
    private val notificationBridge = "taleempk/native_notifications"
    private val mediaBridge = "taleempk/media_tools"
    private val e2eeBridge = "taleempk/e2ee"
    private val notificationChannelId = "taleempk_messages"
    private val random = SecureRandom()

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
                            val brightness = (call.argument<Number>("brightness")?.toFloat() ?: 0f)
                                .coerceIn(-1f, 1f)
                            val contrast = (call.argument<Number>("contrast")?.toFloat() ?: 1f)
                                .coerceIn(0.4f, 1.8f)
                            val quality = (call.argument<Int>("quality") ?: 90).coerceIn(65, 98)
                            val maxDimension = (call.argument<Int>("max_dimension") ?: 2560)
                                .coerceIn(720, 4096)
                            result.success(
                                editPhoto(
                                    path,
                                    turns,
                                    flip,
                                    crop,
                                    brightness,
                                    contrast,
                                    quality,
                                    maxDimension,
                                ),
                            )
                        } catch (error: Throwable) {
                            result.error("PHOTO_EDIT", error.message ?: "Photo edit failed", null)
                        }
                    }
                    else -> result.notImplemented()
                }
            }

        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, e2eeBridge)
            .setMethodCallHandler { call, result ->
                try {
                    when (call.method) {
                        "generateKeyPair" -> result.success(generateKeyPair())
                        "wrapPrivate" -> result.success(
                            wrapPrivate(
                                requireArg(call.argument<String>("private_key"), "private key"),
                                requireArg(call.argument<String>("passphrase"), "passphrase"),
                            ),
                        )
                        "unwrapPrivate" -> result.success(
                            unwrapPrivate(
                                requireArg(call.argument<String>("wrapped_key"), "wrapped key"),
                                requireArg(call.argument<String>("wrap_salt"), "salt"),
                                requireArg(call.argument<String>("wrap_iv"), "IV"),
                                requireArg(call.argument<String>("passphrase"), "passphrase"),
                            ),
                        )
                        "deriveShared" -> result.success(
                            deriveShared(
                                requireArg(call.argument<String>("private_key"), "private key"),
                                requireArg(call.argument<String>("public_key"), "public key"),
                            ),
                        )
                        "sealText" -> result.success(
                            sealText(
                                requireArg(call.argument<String>("key"), "key"),
                                call.argument<String>("text") ?: "",
                            ),
                        )
                        "openText" -> result.success(
                            openText(
                                requireArg(call.argument<String>("key"), "key"),
                                requireArg(call.argument<String>("packet"), "packet"),
                            ),
                        )
                        "randomKey" -> result.success(b64(randomBytes(32)))
                        "sealRawKey" -> result.success(
                            sealRawKey(
                                requireArg(call.argument<String>("key"), "key"),
                                requireArg(call.argument<String>("raw_key"), "raw key"),
                            ),
                        )
                        "openRawKey" -> result.success(
                            openRawKey(
                                requireArg(call.argument<String>("key"), "key"),
                                requireArg(call.argument<String>("packet"), "packet"),
                            ),
                        )
                        "sealFile" -> result.success(
                            sealFile(
                                requireArg(call.argument<String>("key"), "key"),
                                requireArg(call.argument<String>("path"), "file path"),
                                call.argument<String>("name") ?: "file",
                                call.argument<String>("mime") ?: "application/octet-stream",
                            ),
                        )
                        "openFile" -> result.success(
                            openFile(
                                requireArg(call.argument<String>("key"), "key"),
                                requireArg(call.argument<String>("path"), "file path"),
                            ),
                        )
                        "fingerprint" -> result.success(
                            fingerprint(
                                requireArg(call.argument<String>("public_a"), "public key"),
                                requireArg(call.argument<String>("public_b"), "peer public key"),
                            ),
                        )
                        else -> result.notImplemented()
                    }
                } catch (error: Throwable) {
                    result.error("E2EE", error.message ?: "Encryption operation failed", null)
                }
            }
    }

    private fun requireArg(value: String?, name: String): String =
        value?.takeIf { it.isNotEmpty() } ?: throw IllegalArgumentException("Missing $name")

    private fun createMessageChannel() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val channel = NotificationChannel(
            notificationChannelId,
            "Messages and activity",
            NotificationManager.IMPORTANCE_HIGH,
        ).apply {
            description = "TaleemPK messages, replies, mentions and account activity"
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
            @Suppress("DEPRECATION") Notification.Builder(this)
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
            @Suppress("DEPRECATION") builder.setPriority(Notification.PRIORITY_HIGH)
        }
        (getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager)
            .notify(id.coerceAtLeast(1), builder.build())
    }

    private fun editPhoto(
        path: String,
        turns: Int,
        flip: Boolean,
        crop: String,
        brightness: Float,
        contrast: Float,
        quality: Int,
        maxDimension: Int,
    ): String {
        var bitmap = BitmapFactory.decodeFile(path)
            ?: throw IllegalArgumentException("Android could not decode this image")
        val normalizedTurns = ((turns % 4) + 4) % 4
        if (normalizedTurns != 0 || flip) {
            val matrix = Matrix().apply {
                if (normalizedTurns != 0) postRotate(90f * normalizedTurns)
                if (flip) postScale(-1f, 1f)
            }
            val transformed = Bitmap.createBitmap(bitmap, 0, 0, bitmap.width, bitmap.height, matrix, true)
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
            } else bitmap
            if (cropped !== bitmap) bitmap.recycle()
            bitmap = cropped
        }
        val longest = max(bitmap.width, bitmap.height)
        if (longest > maxDimension) {
            val scale = maxDimension.toDouble() / longest.toDouble()
            val scaled = Bitmap.createScaledBitmap(
                bitmap,
                (bitmap.width * scale).roundToInt().coerceAtLeast(1),
                (bitmap.height * scale).roundToInt().coerceAtLeast(1),
                true,
            )
            if (scaled !== bitmap) bitmap.recycle()
            bitmap = scaled
        }
        if (brightness != 0f || contrast != 1f) {
            val shift = brightness * 255f
            val translate = (-0.5f * contrast + 0.5f) * 255f + shift
            val matrix = ColorMatrix(
                floatArrayOf(
                    contrast, 0f, 0f, 0f, translate,
                    0f, contrast, 0f, 0f, translate,
                    0f, 0f, contrast, 0f, translate,
                    0f, 0f, 0f, 1f, 0f,
                ),
            )
            val adjusted = Bitmap.createBitmap(bitmap.width, bitmap.height, Bitmap.Config.ARGB_8888)
            Canvas(adjusted).drawBitmap(bitmap, 0f, 0f, Paint().apply {
                colorFilter = ColorMatrixColorFilter(matrix)
                isAntiAlias = true
            })
            bitmap.recycle()
            bitmap = adjusted
        }
        val output = File(cacheDir, "taleempk_photo_${System.nanoTime()}.jpg")
        FileOutputStream(output).use { stream ->
            if (!bitmap.compress(Bitmap.CompressFormat.JPEG, quality, stream)) {
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

    private fun b64(bytes: ByteArray): String = Base64.encodeToString(bytes, Base64.NO_WRAP)
    private fun unb64(value: String): ByteArray = Base64.decode(value, Base64.DEFAULT)
    private fun randomBytes(size: Int): ByteArray = ByteArray(size).also(random::nextBytes)

    private fun generateKeyPair(): Map<String, String> {
        val generator = KeyPairGenerator.getInstance("EC")
        generator.initialize(ECGenParameterSpec("secp256r1"), random)
        val pair = generator.generateKeyPair()
        val pub = pair.public as ECPublicKey
        return mapOf("private_key" to b64(pair.private.encoded), "public_key" to b64(rawPublic(pub)))
    }

    private fun rawPublic(pub: ECPublicKey): ByteArray =
        byteArrayOf(4) + fixedUnsigned(pub.w.affineX, 32) + fixedUnsigned(pub.w.affineY, 32)

    private fun fixedUnsigned(value: BigInteger, size: Int): ByteArray {
        val raw = value.toByteArray()
        val unsigned = if (raw.size > 1 && raw[0].toInt() == 0) raw.copyOfRange(1, raw.size) else raw
        if (unsigned.size > size) return unsigned.copyOfRange(unsigned.size - size, unsigned.size)
        return ByteArray(size - unsigned.size) + unsigned
    }

    private fun importPrivate(value: String) =
        KeyFactory.getInstance("EC").generatePrivate(PKCS8EncodedKeySpec(unb64(value)))

    private fun ecParams(): ECParameterSpec {
        val parameters = AlgorithmParameters.getInstance("EC")
        parameters.init(ECGenParameterSpec("secp256r1"))
        return parameters.getParameterSpec(ECParameterSpec::class.java)
    }

    private fun importPublic(value: String): ECPublicKey {
        val raw = unb64(value)
        require(raw.size == 65 && raw[0].toInt() == 4) { "Invalid P-256 public key" }
        return KeyFactory.getInstance("EC").generatePublic(
            ECPublicKeySpec(
                ECPoint(BigInteger(1, raw.copyOfRange(1, 33)), BigInteger(1, raw.copyOfRange(33, 65))),
                ecParams(),
            ),
        ) as ECPublicKey
    }

    private fun deriveShared(privateKey: String, publicKey: String): String {
        val agreement = KeyAgreement.getInstance("ECDH")
        agreement.init(importPrivate(privateKey))
        agreement.doPhase(importPublic(publicKey), true)
        return b64(hkdfSha256(agreement.generateSecret(), "studyhub-chat-v1".toByteArray(Charsets.UTF_8), 32))
    }

    private fun hkdfSha256(secret: ByteArray, info: ByteArray, length: Int): ByteArray {
        val extract = Mac.getInstance("HmacSHA256")
        extract.init(SecretKeySpec(ByteArray(32), "HmacSHA256"))
        val prk = extract.doFinal(secret)
        val out = ByteArray(length)
        var previous = ByteArray(0)
        var offset = 0
        var counter = 1
        while (offset < length) {
            val mac = Mac.getInstance("HmacSHA256")
            mac.init(SecretKeySpec(prk, "HmacSHA256"))
            mac.update(previous)
            mac.update(info)
            mac.update(counter.toByte())
            previous = mac.doFinal()
            val count = minOf(previous.size, length - offset)
            System.arraycopy(previous, 0, out, offset, count)
            offset += count
            counter++
        }
        return out
    }

    private fun pbkdf2Sha256(password: ByteArray, salt: ByteArray, iterations: Int, length: Int): ByteArray {
        val out = ByteArray(length)
        val blocks = (length + 31) / 32
        var outputOffset = 0
        for (block in 1..blocks) {
            val mac = Mac.getInstance("HmacSHA256")
            mac.init(SecretKeySpec(password, "HmacSHA256"))
            val suffix = ByteBuffer.allocate(4).putInt(block).array()
            var u = mac.doFinal(salt + suffix)
            val t = u.copyOf()
            for (i in 2..iterations) {
                u = mac.doFinal(u)
                for (j in t.indices) t[j] = (t[j].toInt() xor u[j].toInt()).toByte()
            }
            val count = minOf(32, length - outputOffset)
            System.arraycopy(t, 0, out, outputOffset, count)
            outputOffset += count
        }
        return out
    }

    private fun aesEncrypt(key: ByteArray, iv: ByteArray, plain: ByteArray): ByteArray {
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.ENCRYPT_MODE, SecretKeySpec(key, "AES"), GCMParameterSpec(128, iv))
        return cipher.doFinal(plain)
    }

    private fun aesDecrypt(key: ByteArray, iv: ByteArray, cipherText: ByteArray): ByteArray {
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.DECRYPT_MODE, SecretKeySpec(key, "AES"), GCMParameterSpec(128, iv))
        return cipher.doFinal(cipherText)
    }

    private fun wrapPrivate(privateKey: String, passphrase: String): Map<String, String> {
        val salt = randomBytes(16)
        val iv = randomBytes(12)
        val key = pbkdf2Sha256(passphrase.toByteArray(Charsets.UTF_8), salt, 310000, 32)
        return mapOf(
            "wrapped_key" to b64(aesEncrypt(key, iv, unb64(privateKey))),
            "wrap_salt" to b64(salt),
            "wrap_iv" to b64(iv),
        )
    }

    private fun unwrapPrivate(wrapped: String, salt: String, iv: String, passphrase: String): String {
        val key = pbkdf2Sha256(passphrase.toByteArray(Charsets.UTF_8), unb64(salt), 310000, 32)
        return b64(aesDecrypt(key, unb64(iv), unb64(wrapped)))
    }

    private fun sealText(key: String, text: String): String {
        val iv = randomBytes(12)
        return "1.${b64(iv)}.${b64(aesEncrypt(unb64(key), iv, text.toByteArray(Charsets.UTF_8)))}"
    }

    private fun openText(key: String, packet: String): String {
        val parts = packet.split('.')
        require(parts.size == 3 && parts[0] == "1") { "Invalid encrypted text packet" }
        return aesDecrypt(unb64(key), unb64(parts[1]), unb64(parts[2])).toString(Charsets.UTF_8)
    }

    private fun sealRawKey(key: String, rawKey: String): String {
        val iv = randomBytes(12)
        return "${b64(iv)}.${b64(aesEncrypt(unb64(key), iv, unb64(rawKey)))}"
    }

    private fun openRawKey(key: String, packet: String): String {
        val parts = packet.split('.')
        require(parts.size == 2) { "Invalid sealed group key" }
        return b64(aesDecrypt(unb64(key), unb64(parts[0]), unb64(parts[1])))
    }

    private fun sealFile(key: String, inputPath: String, originalName: String, mime: String): Map<String, String> {
        val file = File(inputPath)
        require(file.exists()) { "File does not exist" }
        val meta = JSONObject().apply {
            put("n", originalName.take(200).ifBlank { "file" })
            put("t", mime.take(120).ifBlank { "application/octet-stream" })
            put("s", file.length())
        }.toString().toByteArray(Charsets.UTF_8)
        val bytes = file.readBytes()
        val plain = ByteBuffer.allocate(4 + meta.size + bytes.size).putInt(meta.size).put(meta).put(bytes).array()
        val iv = randomBytes(12)
        val output = File(cacheDir, "taleempk_enc_${System.nanoTime()}.bin")
        FileOutputStream(output).use {
            it.write(iv)
            it.write(aesEncrypt(unb64(key), iv, plain))
            it.flush()
        }
        return mapOf("path" to output.absolutePath)
    }

    private fun openFile(key: String, inputPath: String): Map<String, String> {
        val all = File(inputPath).readBytes()
        require(all.size >= 30) { "Encrypted file is too short" }
        val plain = aesDecrypt(unb64(key), all.copyOfRange(0, 12), all.copyOfRange(12, all.size))
        val buffer = ByteBuffer.wrap(plain)
        val headerLength = buffer.int
        require(headerLength in 2..(plain.size - 4)) { "Encrypted file header is invalid" }
        val headerBytes = ByteArray(headerLength)
        buffer.get(headerBytes)
        val meta = JSONObject(headerBytes.toString(Charsets.UTF_8))
        val name = meta.optString("n", "file").take(200)
        val mime = meta.optString("t", "application/octet-stream").take(120)
        val suffix = name.substringAfterLast('.', "bin").replace(Regex("[^A-Za-z0-9]"), "").take(8).ifBlank { "bin" }
        val output = File(cacheDir, "taleempk_dec_${System.nanoTime()}.$suffix")
        val content = ByteArray(buffer.remaining())
        buffer.get(content)
        FileOutputStream(output).use { it.write(content); it.flush() }
        return mapOf("path" to output.absolutePath, "name" to name, "mime" to mime)
    }

    private fun fingerprint(a: String, b: String): String {
        val left = unb64(a)
        val right = unb64(b)
        val firstLeft = compareBytes(left, right) <= 0
        val digest = MessageDigest.getInstance("SHA-256").digest(
            if (firstLeft) left + right else right + left,
        )
        val digits = BigInteger(1, digest).toString(10).padStart(78, '0').take(60)
        return digits.chunked(5).joinToString(" ")
    }

    private fun compareBytes(a: ByteArray, b: ByteArray): Int {
        val count = minOf(a.size, b.size)
        for (i in 0 until count) {
            val av = a[i].toInt() and 0xff
            val bv = b[i].toInt() and 0xff
            if (av != bv) return av - bv
        }
        return a.size - b.size
    }
}
