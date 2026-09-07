package online.taleempk.studyhub.data

import android.content.Context
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
            o.optInt("likes"), o.optInt("comments"), o.optBoolean("solved")
        ) }
    }

    fun conversations(): List<Conversation> {
        val arr = request(mapOf("action" to "conversations"), true)
            .getJSONObject("data").optJSONArray("conversations") ?: JSONArray()
        return arr.toObjects { o -> Conversation(
            o.optLong("id"), o.optString("title"), o.nullable("avatar"),
            o.optString("last_message"), o.optString("last_activity"), o.optInt("unread"),
            o.optBoolean("is_group")
        ) }
    }

    fun messages(conversationId: Long): List<ChatMessage> {
        val arr = request(mapOf("action" to "messages", "conversation_id" to conversationId.toString()), true)
            .getJSONObject("data").optJSONArray("messages") ?: JSONArray()
        return arr.toObjects { o -> ChatMessage(
            o.optLong("id"), o.optLong("sender_id"), o.optString("sender"), o.optString("content"),
            o.optString("time"), o.optBoolean("mine"), o.optInt("voice_seconds"),
            o.nullable("attachment_url"), o.nullable("attachment_name"), o.optBoolean("read")
        ) }
    }

    fun sendText(conversationId: Long, text: String) {
        request(mapOf("action" to "send", "conversation_id" to conversationId.toString(),
            "content" to text, "client_token" to UUID.randomUUID().toString()), true)
    }

    fun sendVoice(conversationId: Long, clip: VoiceClip) {
        val file = File(clip.filePath)
        multipart(
            fields = mapOf("action" to "send", "conversation_id" to conversationId.toString(),
                "voice_seconds" to clip.seconds.toString(), "client_token" to UUID.randomUUID().toString()),
            fieldName = "voice", fileName = "voice.m4a", mime = "audio/mp4", bytes = file.readBytes()
        )
    }

    fun sendAttachment(conversationId: Long, uri: Uri) {
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
            "client_token" to UUID.randomUUID().toString()), "attachment", name, mime, bytes)
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

    private fun multipart(fields: Map<String, String>, fieldName: String, fileName: String, mime: String, bytes: ByteArray) {
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
            out.write(bytes)
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
        val json = try { JSONObject(raw) } catch (_: Exception) {
            val message = when {
                status >= 500 -> "TaleemPK mobile service is temporarily unavailable. Please try again shortly. (HTTP $status)"
                status == 404 -> "The TaleemPK mobile service is not installed correctly. (HTTP 404)"
                raw.isBlank() -> "The server returned an empty response. (HTTP $status)"
                else -> "The server returned an invalid response. (HTTP $status)"
            }
            throw ApiException(message, status)
        }
        if (status !in 200..299 || !json.optBoolean("ok")) {
            throw ApiException(json.optString("error", "Request failed."), status)
        }
        return json
    }

    private fun JSONObject.nullable(key: String): String? = if (isNull(key)) null else optString(key).ifBlank { null }
    private fun <T> JSONArray.toObjects(mapper: (JSONObject) -> T): List<T> =
        (0 until length()).map { mapper(getJSONObject(it)) }
}
