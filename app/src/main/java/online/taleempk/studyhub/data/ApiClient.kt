package online.taleempk.studyhub.data

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Matrix
import android.net.Uri
import android.provider.OpenableColumns
import online.taleempk.studyhub.BuildConfig
import org.json.JSONArray
import org.json.JSONObject
import java.io.BufferedInputStream
import java.io.ByteArrayOutputStream
import java.io.File
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder
import java.util.UUID

class ApiClient(private val context: Context, private val session: SessionStore) {
    private val endpoint = BuildConfig.API_URL

    fun login(identifier: String, password: String): AuthResult = authResult(request(
        mapOf("action" to "login", "identifier" to identifier, "password" to password,
            "device" to "TaleemPK Android")
    ))

    fun register(
        role: String,
        name: String,
        username: String,
        email: String,
        phone: String,
        dob: String,
        password: String
    ): String {
        val data = request(mapOf(
            "action" to "register", "role" to role, "name" to name,
            "username" to username, "email" to email, "phone" to phone,
            "dob" to dob, "password" to password, "device" to "TaleemPK Android"
        )).getJSONObject("data")
        return data.optString("message", "Account created. You can now sign in.")
    }

    fun verifyTwoFactor(challenge: String, code: String): AuthResult = authResult(request(
        mapOf("action" to "verify_2fa", "challenge" to challenge, "code" to code,
            "device" to "TaleemPK Android")
    ))

    fun bootstrap(): Bootstrap {
        val data = request(mapOf("action" to "bootstrap"), authenticated = true).getJSONObject("data")
        val user = parseUser(data.getJSONObject("user"))
        val s = data.optJSONObject("stats") ?: JSONObject()
        val stats = Stats(s.optInt("members"), s.optInt("active_today"),
            s.optInt("messages_today"), s.optInt("quiz_attempts"))
        val shortcuts = data.optJSONArray("shortcuts").toObjects { o ->
            Shortcut(o.optString("title"), o.optString("subtitle"), o.optString("route"), o.optString("icon"))
        }
        return Bootstrap(user, stats, shortcuts)
    }

    fun feed(page: Int = 1): List<FeedPost> {
        val arr = request(mapOf("action" to "feed", "page" to page.toString()), true)
            .getJSONObject("data").optJSONArray("posts") ?: JSONArray()
        return arr.toObjects { o -> FeedPost(
            o.optLong("id"), o.optString("author"), o.optString("username"), o.nullable("avatar"),
            o.optString("type", "post"), o.optString("content"), o.optString("created_at"),
            o.optInt("likes"), o.optInt("comments"), o.optBoolean("solved"), o.optBoolean("liked")
        ) }
    }

    fun createPost(content: String, question: Boolean) {
        request(mapOf("action" to "create_post", "content" to content,
            "type" to if (question) "question" else "text", "visibility" to "public"), true)
    }

    fun togglePostLike(postId: Long) {
        request(mapOf("action" to "react_post", "target" to "post:$postId", "type" to "like"), true)
    }

    fun comments(postId: Long): List<FeedComment> {
        val arr = request(mapOf("action" to "feed_comments", "post_id" to postId.toString()), true)
            .getJSONObject("data").optJSONArray("comments") ?: JSONArray()
        return arr.toObjects { o -> FeedComment(o.optLong("id"), o.optString("author"),
            o.optString("content"), o.optString("created_at"), o.optBoolean("mine")) }
    }

    fun addComment(postId: Long, content: String) {
        request(mapOf("action" to "create_comment", "post_id" to postId.toString(), "content" to content), true)
    }

    fun module(key: String): ModuleContent {
        val data = request(mapOf("action" to "module", "module" to key), true).getJSONObject("data")
        val items = (data.optJSONArray("items") ?: JSONArray()).toObjects { o -> ModuleItem(
            o.optLong("id"), o.optString("title"), o.optString("subtitle"), o.optString("meta"),
            o.optString("kind"), o.optBoolean("done")
        ) }
        return ModuleContent(data.optString("key", key), data.optString("title"), data.optString("subtitle"), items)
    }

    fun toggleTask(taskId: Long) {
        request(mapOf("action" to "module_action", "do" to "toggle_task", "id" to taskId.toString()), true)
    }

    fun moduleAction(action: String, id: Long = 0) {
        request(mapOf("action" to "module_action", "do" to action, "id" to id.toString()), true)
    }

    fun updateProfile(name: String, city: String, headline: String, bio: String) {
        request(mapOf("action" to "update_profile", "name" to name, "city" to city,
            "headline" to headline, "bio" to bio), true)
    }

    fun createTicket(topic: String, subject: String, body: String): String = request(
        mapOf("action" to "create_ticket", "topic" to topic, "subject" to subject, "body" to body), true
    ).getJSONObject("data").optString("message", "Support request created.")

    fun conversations(): List<Conversation> {
        val arr = request(mapOf("action" to "conversations"), true)
            .getJSONObject("data").optJSONArray("conversations") ?: JSONArray()
        return arr.toObjects { o -> Conversation(
            o.optLong("id"), o.optString("title"), o.nullable("avatar"),
            o.optString("last_message"), o.optString("last_activity"), o.optInt("unread"),
            o.optBoolean("is_group"), o.optBoolean("online"), o.optString("status_text"),
            o.optBoolean("muted")
        ) }
    }

    fun messages(conversationId: Long, afterId: Long = 0): List<ChatMessage> {
        val arr = request(mapOf("action" to "messages", "conversation_id" to conversationId.toString(),
            "after_id" to afterId.toString()), true)
            .getJSONObject("data").optJSONArray("messages") ?: JSONArray()
        return arr.toObjects { o ->
            val reply = o.optJSONObject("reply")?.let { r -> ReplyPreview(
                r.optLong("id"), r.optString("sender"), r.optString("text")
            ) }
            val reactions = (o.optJSONArray("reactions") ?: JSONArray()).toObjects { r ->
                ChatReaction(r.optString("emoji"), r.optInt("count"), r.optBoolean("mine"))
            }
            ChatMessage(
                o.optLong("id"), o.optLong("sender_id"), o.optString("sender"), o.optString("content"),
                o.optString("time"), o.optBoolean("mine"), o.optInt("voice_seconds"),
                o.nullable("attachment_url"), o.nullable("attachment_name"), o.optBoolean("read"),
                o.nullable("attachment_type"), o.optString("date_label"), o.optBoolean("deleted"),
                o.optBoolean("edited"), o.optBoolean("forwarded"), o.optBoolean("starred"),
                o.optBoolean("pinned"), o.optBoolean("can_edit"), reply, reactions
            )
        }
    }

    fun sendText(conversationId: Long, text: String, replyTo: Long? = null) {
        val fields = mutableMapOf("action" to "send", "conversation_id" to conversationId.toString(),
            "content" to text, "client_token" to UUID.randomUUID().toString())
        replyTo?.let { fields["reply_to"] = it.toString() }
        request(fields, true)
    }

    fun sendVoice(conversationId: Long, clip: VoiceClip, progress: (Float) -> Unit = {}) {
        val file = File(clip.filePath)
        multipart(
            fields = mapOf("action" to "send", "conversation_id" to conversationId.toString(),
                "voice_seconds" to clip.seconds.toString(), "client_token" to UUID.randomUUID().toString()),
            fieldName = "voice", fileName = "voice.m4a", mime = "audio/mp4", bytes = file.readBytes(),
            onProgress = progress
        )
    }

    fun sendAttachment(conversationId: Long, uri: Uri, progress: (Float) -> Unit = {}) {
        val resolver = context.contentResolver
        val mime = resolver.getType(uri) ?: "application/octet-stream"
        val name = resolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)?.use { cursor ->
            if (cursor.moveToFirst()) cursor.getString(0) else null
        }?.take(180)?.replace(Regex("[\\r\\n\\\"]"), "_")
            ?: uri.lastPathSegment?.substringAfterLast('/')?.take(180) ?: "attachment"
        val maxBytes = 10 * 1024 * 1024
        val bytes = resolver.openInputStream(uri)?.use { input ->
            val output = ByteArrayOutputStream()
            val buffer = ByteArray(32 * 1024)
            var total = 0
            while (true) {
                val read = input.read(buffer)
                if (read < 0) break
                total += read
                if (total > maxBytes) throw ApiException("Attachments can be up to 10 MB.")
                output.write(buffer, 0, read)
            }
            output.toByteArray()
        }
            ?: throw ApiException("Could not read that file.")
        multipart(mapOf("action" to "send", "conversation_id" to conversationId.toString(),
            "client_token" to UUID.randomUUID().toString()), "attachment", name, mime, bytes, progress)
    }

    fun sendEditedImage(
        conversationId: Long,
        uri: Uri,
        rotation: Int,
        squareCrop: Boolean,
        caption: String,
        progress: (Float) -> Unit = {}
    ) {
        val bitmap = decodeForUpload(uri, 2048)
        val rotated = if (rotation % 360 == 0) bitmap else Bitmap.createBitmap(
            bitmap, 0, 0, bitmap.width, bitmap.height, Matrix().apply { postRotate(rotation.toFloat()) }, true
        ).also { if (it !== bitmap) bitmap.recycle() }
        val edited = if (squareCrop) {
            val side = minOf(rotated.width, rotated.height)
            Bitmap.createBitmap(rotated, (rotated.width - side) / 2, (rotated.height - side) / 2, side, side)
                .also { if (it !== rotated) rotated.recycle() }
        } else rotated
        val bytes = ByteArrayOutputStream().use { output ->
            if (!edited.compress(Bitmap.CompressFormat.JPEG, 90, output)) {
                edited.recycle(); throw ApiException("The edited photo could not be prepared.")
            }
            edited.recycle(); output.toByteArray()
        }
        if (bytes.size > 10 * 1024 * 1024) throw ApiException("The edited photo is larger than 10 MB.")
        multipart(mapOf("action" to "send", "conversation_id" to conversationId.toString(),
            "content" to caption.trim(), "client_token" to UUID.randomUUID().toString()),
            "attachment", "TaleemPK-photo-${System.currentTimeMillis()}.jpg", "image/jpeg", bytes, progress)
    }

    private fun decodeForUpload(uri: Uri, maxSide: Int): Bitmap {
        val resolver = context.contentResolver
        val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        resolver.openInputStream(uri)?.use { BitmapFactory.decodeStream(it, null, bounds) }
        if (bounds.outWidth <= 0 || bounds.outHeight <= 0) throw ApiException("That photo could not be opened.")
        var sample = 1
        while (bounds.outWidth / sample > maxSide * 2 || bounds.outHeight / sample > maxSide * 2) sample *= 2
        val options = BitmapFactory.Options().apply { inSampleSize = sample; inPreferredConfig = Bitmap.Config.ARGB_8888 }
        val decoded = resolver.openInputStream(uri)?.use { BitmapFactory.decodeStream(it, null, options) }
            ?: throw ApiException("That photo could not be opened.")
        if (maxOf(decoded.width, decoded.height) <= maxSide) return decoded
        val ratio = maxSide.toFloat() / maxOf(decoded.width, decoded.height)
        return Bitmap.createScaledBitmap(decoded, (decoded.width * ratio).toInt().coerceAtLeast(1),
            (decoded.height * ratio).toInt().coerceAtLeast(1), true).also { if (it !== decoded) decoded.recycle() }
    }

    fun react(messageId: Long, emoji: String) {
        request(mapOf("action" to "reaction", "message_id" to messageId.toString(), "emoji" to emoji), true)
    }

    fun toggleStar(messageId: Long) {
        request(mapOf("action" to "star", "message_id" to messageId.toString()), true)
    }

    fun togglePin(messageId: Long) {
        request(mapOf("action" to "pin", "message_id" to messageId.toString()), true)
    }

    fun editMessage(messageId: Long, content: String) {
        request(mapOf("action" to "message_action", "do" to "edit", "id" to messageId.toString(),
            "content" to content), true)
    }

    fun deleteMessage(messageId: Long, everyone: Boolean) {
        request(mapOf("action" to "message_action", "do" to "delete", "ids" to messageId.toString(),
            "scope" to if (everyone) "all" else "me"), true)
    }

    fun toggleMute(conversationId: Long) {
        request(mapOf("action" to "manage_chat", "do" to "toggle_mute", "id" to conversationId.toString()), true)
    }

    fun forwardMessage(messageId: Long, conversationId: Long) {
        request(mapOf("action" to "message_action", "do" to "forward", "id" to messageId.toString(),
            "to" to conversationId.toString()), true)
    }

    fun presence(conversationId: Long, kind: String): ChatPresence {
        val data = request(mapOf("action" to "presence", "conversation_id" to conversationId.toString(),
            "kind" to kind), true).getJSONObject("data")
        return ChatPresence(data.optBoolean("active"), data.optString("kind"), data.optString("name"),
            data.optLong("read_through"))
    }

    fun downloadAttachment(message: ChatMessage): File {
        val safeName = (message.attachmentName ?: "attachment.${message.attachmentType ?: "bin"}")
            .replace(Regex("[^A-Za-z0-9._ -]"), "_").take(160)
        val directory = File(context.cacheDir, "shared").apply { mkdirs() }
        val target = File(directory, "${message.id}-$safeName")
        val conn = (URL("$endpoint?action=file&id=${message.id}").openConnection() as HttpURLConnection).apply {
            requestMethod = "GET"; connectTimeout = 15_000; readTimeout = 60_000
            setRequestProperty("User-Agent", "TaleemPK-Android/${BuildConfig.VERSION_NAME}")
            session.token?.let { setRequestProperty("Authorization", "Bearer $it") }
        }
        try {
            val status = conn.responseCode
            if (status !in 200..299) throw ApiException("That attachment is no longer available.", status)
            conn.inputStream.buffered().use { input ->
                target.outputStream().buffered().use { output -> input.copyTo(output) }
            }
        } finally { conn.disconnect() }
        return target
    }

    fun logout() {
        try { request(mapOf("action" to "logout"), true) } finally { session.token = null }
    }

    private fun authResult(root: JSONObject): AuthResult {
        val d = root.getJSONObject("data")
        val needs = d.optBoolean("needs_2fa")
        val result = AuthResult(
            token = d.optString("token").ifBlank { null },
            challenge = d.optString("challenge").ifBlank { null },
            needsTwoFactor = needs,
            user = d.optJSONObject("user")?.let(::parseUser)
        )
        if (result.token != null) session.token = result.token
        return result
    }

    private fun parseUser(o: JSONObject) = User(
        o.optLong("id"), o.optString("name"), o.optString("username"), o.optString("role"),
        o.nullable("avatar"), o.optBoolean("verified")
    )

    private fun request(fields: Map<String, String>, authenticated: Boolean = false): JSONObject {
        val body = fields.entries.joinToString("&") {
            URLEncoder.encode(it.key, "UTF-8") + "=" + URLEncoder.encode(it.value, "UTF-8")
        }.toByteArray()
        val conn = (URL(endpoint).openConnection() as HttpURLConnection).apply {
            requestMethod = "POST"
            connectTimeout = 15_000
            readTimeout = 25_000
            doOutput = true
            setRequestProperty("Accept", "application/json")
            setRequestProperty("Content-Type", "application/x-www-form-urlencoded; charset=UTF-8")
            setRequestProperty("User-Agent", "TaleemPK-Android/${BuildConfig.VERSION_NAME}")
            if (authenticated) session.token?.let { setRequestProperty("Authorization", "Bearer $it") }
        }
        conn.outputStream.use { it.write(body) }
        return parseResponse(conn)
    }

    private fun multipart(
        fields: Map<String, String>,
        fieldName: String,
        fileName: String,
        mime: String,
        bytes: ByteArray,
        onProgress: (Float) -> Unit = {}
    ) {
        val boundary = "TaleemPK-${UUID.randomUUID()}"
        val conn = (URL(endpoint).openConnection() as HttpURLConnection).apply {
            requestMethod = "POST"; connectTimeout = 20_000; readTimeout = 60_000; doOutput = true
            setRequestProperty("Accept", "application/json")
            setRequestProperty("Content-Type", "multipart/form-data; boundary=$boundary")
            setRequestProperty("User-Agent", "TaleemPK-Android/${BuildConfig.VERSION_NAME}")
            session.token?.let { setRequestProperty("Authorization", "Bearer $it") }
        }
        conn.outputStream.buffered().use { out ->
            fun text(value: String) = out.write(value.toByteArray())
            fields.forEach { (key, value) ->
                text("--$boundary\r\nContent-Disposition: form-data; name=\"$key\"\r\n\r\n$value\r\n")
            }
            text("--$boundary\r\nContent-Disposition: form-data; name=\"$fieldName\"; filename=\"${fileName.replace("\"", "")}\"\r\n")
            text("Content-Type: $mime\r\n\r\n")
            var sent = 0
            while (sent < bytes.size) {
                val count = minOf(32 * 1024, bytes.size - sent)
                out.write(bytes, sent, count)
                sent += count
                onProgress(sent.toFloat() / bytes.size.coerceAtLeast(1))
            }
            text("\r\n--$boundary--\r\n")
        }
        parseResponse(conn)
    }

    private fun parseResponse(conn: HttpURLConnection): JSONObject {
        val status: Int
        val raw: String
        try {
            status = conn.responseCode
            val stream = if (status in 200..299) conn.inputStream else conn.errorStream
            raw = stream?.use { BufferedInputStream(it).readBytes().toString(Charsets.UTF_8) }
                .orEmpty()
                .trimStart('\uFEFF')
                .trim()
        } finally {
            conn.disconnect()
        }
        /* Some shared-hosting setups prepend a warning/banner or append a
           second response around otherwise valid API JSON. Extract balanced
           objects and choose the final TaleemPK envelope instead of treating
           a successfully processed message as an outdated backend. */
        val json = extractJsonEnvelopes(raw).lastOrNull { it.has("ok") } ?: try {
            JSONObject(raw)
        } catch (_: Exception) {
            val message = when {
                status >= 500 -> "TaleemPK mobile service is temporarily unavailable. Please try again shortly. (HTTP $status)"
                status == 404 -> "The TaleemPK mobile service is not installed correctly. (HTTP 404)"
                raw.isBlank() -> "The server returned an empty response. (HTTP $status)"
                status == 200 -> "The website returned a page instead of chat data. Upload the included backend update to public_html/api/mobile.php."
                else -> "The server returned an invalid response. (HTTP $status)"
            }
            throw ApiException(message, status)
        }
        if (status !in 200..299 || !json.optBoolean("ok")) {
            throw ApiException(json.optString("error", "Request failed."), status)
        }
        return json
    }

    private fun extractJsonEnvelopes(raw: String): List<JSONObject> {
        val found = mutableListOf<JSONObject>()
        var start = -1
        var depth = 0
        var quoted = false
        var escaped = false
        raw.forEachIndexed { index, char ->
            if (start < 0) {
                if (char == '{') { start = index; depth = 1 }
                return@forEachIndexed
            }
            if (quoted) {
                if (escaped) escaped = false
                else if (char == '\\') escaped = true
                else if (char == '"') quoted = false
                return@forEachIndexed
            }
            when (char) {
                '"' -> quoted = true
                '{' -> depth++
                '}' -> {
                    depth--
                    if (depth == 0) {
                        try { found += JSONObject(raw.substring(start, index + 1)) } catch (_: Exception) { }
                        start = -1
                    }
                }
            }
        }
        return found
    }

    private fun JSONObject.nullable(key: String): String? = if (isNull(key)) null else optString(key).ifBlank { null }
    private fun <T> JSONArray.toObjects(mapper: (JSONObject) -> T): List<T> =
        (0 until length()).map { mapper(getJSONObject(it)) }
}
