package online.taleempk.studyhub.ui

import android.app.Application
import android.content.Intent
import android.net.Uri
import androidx.core.content.FileProvider
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import online.taleempk.studyhub.data.*
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

enum class RootScreen { HOME, FEED, CHATS, PROFILE }
enum class AuthStage { STARTING, LOGIN, REGISTER, TWO_FACTOR, SIGNED_IN }

class AppViewModel(application: Application) : AndroidViewModel(application) {
    private val session = SessionStore(application)
    private val api = ApiClient(application, session)

    var authStage by mutableStateOf(AuthStage.STARTING); private set
    var screen by mutableStateOf(RootScreen.HOME); private set
    var busy by mutableStateOf(false); private set
    var error by mutableStateOf<String?>(null); private set
    var notice by mutableStateOf<String?>(null); private set
    var challenge by mutableStateOf<String?>(null); private set
    var bootstrap by mutableStateOf<Bootstrap?>(null); private set
    var posts by mutableStateOf<List<FeedPost>>(emptyList()); private set
    var commentPost by mutableStateOf<FeedPost?>(null); private set
    var feedComments by mutableStateOf<List<FeedComment>>(emptyList()); private set
    var conversations by mutableStateOf<List<Conversation>>(emptyList()); private set
    var selectedConversation by mutableStateOf<Conversation?>(null); private set
    var messages by mutableStateOf<List<ChatMessage>>(emptyList()); private set
    var remotePresence by mutableStateOf(ChatPresence()); private set
    var uploadProgress by mutableStateOf<Float?>(null); private set
    var uploadLabel by mutableStateOf(""); private set
    var activeModule by mutableStateOf<ModuleContent?>(null); private set

    init { restore() }

    fun clearError() { error = null }
    fun clearNotice() { notice = null }
    fun showLogin() { error = null; authStage = AuthStage.LOGIN }
    fun showRegister() { error = null; notice = null; authStage = AuthStage.REGISTER }
    fun authHeaders(): Map<String, String> = session.token?.let { mapOf("Authorization" to "Bearer $it") } ?: emptyMap()

    private fun restore() {
        if (session.token.isNullOrBlank()) { authStage = AuthStage.LOGIN; return }
        launch(showSpinner = false) {
            bootstrap = withContext(Dispatchers.IO) { api.bootstrap() }
            authStage = AuthStage.SIGNED_IN
        }
    }

    fun login(identifier: String, password: String) = launch {
        val auth = withContext(Dispatchers.IO) { api.login(identifier.trim(), password) }
        if (auth.needsTwoFactor) {
            challenge = auth.challenge
            authStage = AuthStage.TWO_FACTOR
        } else {
            bootstrap = withContext(Dispatchers.IO) { api.bootstrap() }
            authStage = AuthStage.SIGNED_IN
        }
    }

    fun register(role: String, name: String, username: String, email: String, phone: String, dob: String, password: String) = launch {
        notice = withContext(Dispatchers.IO) {
            api.register(role, name.trim(), username.trim(), email.trim(), phone.trim(), dob.trim(), password)
        }
        authStage = AuthStage.LOGIN
    }

    fun verify(code: String) = launch {
        val auth = withContext(Dispatchers.IO) {
            api.verifyTwoFactor(challenge ?: throw ApiException("Sign-in expired."), code.trim())
        }
        if (auth.token == null) throw ApiException("Sign-in could not be completed.")
        bootstrap = withContext(Dispatchers.IO) { api.bootstrap() }
        authStage = AuthStage.SIGNED_IN
    }

    fun selectScreen(next: RootScreen) {
        screen = next
        error = null
        when (next) {
            RootScreen.HOME -> if (bootstrap == null) refreshHome()
            RootScreen.FEED -> if (posts.isEmpty()) refreshFeed()
            RootScreen.CHATS -> if (conversations.isEmpty()) refreshChats()
            RootScreen.PROFILE -> Unit
        }
    }

    fun refreshHome() = launch { bootstrap = withContext(Dispatchers.IO) { api.bootstrap() } }
    fun refreshFeed() = launch { posts = withContext(Dispatchers.IO) { api.feed() } }
    fun refreshChats() = launch { conversations = withContext(Dispatchers.IO) { api.conversations() } }

    fun openNativeRoute(route: String) {
        when (route.substringBefore('?')) {
            "feed.php" -> selectScreen(RootScreen.FEED)
            "chat.php" -> selectScreen(RootScreen.CHATS)
            "study.php" -> openModule("study")
            "library.php" -> openModule("library")
            "quiz.php" -> openModule("quizzes")
            "groups.php" -> openModule("groups")
            "planner.php" -> openModule("planner")
            "results.php" -> openModule("results")
            "edit-profile.php" -> openModule("profile")
            "settings.php" -> openModule("settings")
            "notifications.php" -> openModule("notifications")
            "support.php" -> openModule("support")
            else -> error = "This section is being prepared for the native app."
        }
    }

    fun openModule(key: String) = launch {
        activeModule = withContext(Dispatchers.IO) { api.module(key) }
    }
    fun closeModule() { activeModule = null }
    fun refreshModule() { activeModule?.key?.let(::openModule) }

    fun createPost(content: String, question: Boolean, after: () -> Unit) = launch {
        withContext(Dispatchers.IO) { api.createPost(content.trim(), question) }
        posts = withContext(Dispatchers.IO) { api.feed() }
        after()
    }

    fun togglePostLike(post: FeedPost) = launch(showSpinner = false) {
        withContext(Dispatchers.IO) { api.togglePostLike(post.id) }
        posts = withContext(Dispatchers.IO) { api.feed() }
    }

    fun openComments(post: FeedPost) {
        commentPost = post
        feedComments = emptyList()
        launch(showSpinner = false) { feedComments = withContext(Dispatchers.IO) { api.comments(post.id) } }
    }

    fun closeComments() { commentPost = null; feedComments = emptyList() }

    fun addComment(content: String, after: () -> Unit) {
        val post = commentPost ?: return
        launch(showSpinner = false) {
            withContext(Dispatchers.IO) { api.addComment(post.id, content.trim()) }
            feedComments = withContext(Dispatchers.IO) { api.comments(post.id) }
            posts = withContext(Dispatchers.IO) { api.feed() }
            commentPost = posts.firstOrNull { it.id == post.id } ?: post
            after()
        }
    }

    fun toggleTask(item: ModuleItem) = launch(showSpinner = false) {
        withContext(Dispatchers.IO) { api.toggleTask(item.id) }
        activeModule?.key?.let { activeModule = withContext(Dispatchers.IO) { api.module(it) } }
    }

    fun moduleItemAction(item: ModuleItem) {
        val action = when (item.kind) {
            "task" -> "toggle_task"
            "notification" -> "read_notification"
            "setting" -> when (item.id) { 2L -> "cycle_privacy"; 3L -> "toggle_online"; else -> null }
            else -> null
        } ?: return
        launch(showSpinner = false) {
            withContext(Dispatchers.IO) { api.moduleAction(action, item.id) }
            activeModule?.key?.let { activeModule = withContext(Dispatchers.IO) { api.module(it) } }
        }
    }

    fun updateProfile(name: String, city: String, headline: String, bio: String, after: () -> Unit) = launch {
        withContext(Dispatchers.IO) { api.updateProfile(name.trim(), city.trim(), headline.trim(), bio.trim()) }
        activeModule = withContext(Dispatchers.IO) { api.module("profile") }
        bootstrap = withContext(Dispatchers.IO) { api.bootstrap() }
        notice = "Profile updated."
        after()
    }

    fun createTicket(topic: String, subject: String, body: String, after: () -> Unit) = launch {
        notice = withContext(Dispatchers.IO) { api.createTicket(topic, subject.trim(), body.trim()) }
        activeModule = withContext(Dispatchers.IO) { api.module("support") }
        after()
    }

    fun openConversation(item: Conversation) {
        selectedConversation = item
        remotePresence = ChatPresence()
        launch { messages = withContext(Dispatchers.IO) { api.messages(item.id) } }
    }

    fun closeConversation() {
        selectedConversation?.let { sendPresence(it.id, "") }
        selectedConversation = null; messages = emptyList(); remotePresence = ChatPresence(); refreshChats()
    }
    fun refreshMessages() { selectedConversation?.let { c -> launch(showSpinner = false) {
        val after = messages.maxOfOrNull { it.id } ?: 0L
        val fresh = withContext(Dispatchers.IO) { api.messages(c.id, after) }
        if (fresh.isNotEmpty()) messages = (messages + fresh).distinctBy { it.id }.sortedBy { it.id }
    } } }

    fun syncPresence(kind: String) {
        val c = selectedConversation ?: return
        viewModelScope.launch {
            try {
                val presence = withContext(Dispatchers.IO) { api.presence(c.id, kind) }
                remotePresence = presence
                if (presence.readThrough > 0) messages = messages.map { m ->
                    if (m.mine && m.id <= presence.readThrough && !m.read) m.copy(read = true) else m
                }
            } catch (_: Exception) { }
        }
    }

    private fun sendPresence(conversationId: Long, kind: String) {
        viewModelScope.launch(Dispatchers.IO) { try { api.presence(conversationId, kind) } catch (_: Exception) { } }
    }

    fun sendText(text: String, replyTo: Long? = null, after: () -> Unit) {
        val c = selectedConversation ?: return
        val body = text.trim()
        if (body.isEmpty()) return
        val pendingId = -System.nanoTime()
        val replyMessage = messages.firstOrNull { it.id == replyTo }
        messages = messages + ChatMessage(
            id = pendingId, senderId = bootstrap?.user?.id ?: 0, sender = bootstrap?.user?.name ?: "You",
            content = body, time = SimpleDateFormat("h:mm a", Locale.getDefault()).format(Date()), mine = true,
            voiceSeconds = 0, attachmentUrl = null, attachmentName = null, read = false,
            dateLabel = "Today", reply = replyMessage?.let { ReplyPreview(it.id, it.sender,
                it.content.ifBlank { it.attachmentName ?: "Voice message" }) }
        )
        after()
        launch(showSpinner = false) {
            try {
                withContext(Dispatchers.IO) { api.sendText(c.id, body, replyTo) }
                messages = withContext(Dispatchers.IO) { api.messages(c.id) }
            } catch (e: Exception) {
                messages = messages.filterNot { it.id == pendingId }
                throw e
            }
        }
    }

    fun sendVoice(clip: VoiceClip, after: () -> Unit) {
        val c = selectedConversation ?: return
        launch(showSpinner = false) {
            uploadLabel = "Sending voice message…"; uploadProgress = 0f
            try {
                withContext(Dispatchers.IO) { api.sendVoice(c.id, clip) { p ->
                    viewModelScope.launch { uploadProgress = p }
                } }
                messages = withContext(Dispatchers.IO) { api.messages(c.id) }
                java.io.File(clip.filePath).delete()
                after()
            } finally { uploadProgress = null; uploadLabel = "" }
        }
    }

    fun sendAttachment(uri: Uri) {
        val c = selectedConversation ?: return
        launch(showSpinner = false) {
            uploadLabel = "Uploading attachment…"; uploadProgress = 0f
            try {
                withContext(Dispatchers.IO) { api.sendAttachment(c.id, uri) { p ->
                    viewModelScope.launch { uploadProgress = p }
                } }
                messages = withContext(Dispatchers.IO) { api.messages(c.id) }
            } finally { uploadProgress = null; uploadLabel = "" }
        }
    }

    fun sendEditedImage(uri: Uri, rotation: Int, squareCrop: Boolean, caption: String, after: () -> Unit) {
        val c = selectedConversation ?: return
        launch(showSpinner = false) {
            uploadLabel = "Optimising photo…"; uploadProgress = 0f
            try {
                withContext(Dispatchers.IO) { api.sendEditedImage(c.id, uri, rotation, squareCrop, caption) { p ->
                    viewModelScope.launch { uploadLabel = "Uploading photo…"; uploadProgress = p }
                } }
                messages = withContext(Dispatchers.IO) { api.messages(c.id) }
                after()
            } finally { uploadProgress = null; uploadLabel = "" }
        }
    }

    fun forwardMessage(message: ChatMessage, to: Conversation, after: () -> Unit) = launch(showSpinner = false) {
        withContext(Dispatchers.IO) { api.forwardMessage(message.id, to.id) }
        after()
        notice = "Message forwarded to ${to.title}."
    }

    fun openAttachment(message: ChatMessage) {
        launch {
            val file = withContext(Dispatchers.IO) { api.downloadAttachment(message) }
            val app = getApplication<Application>()
            val uri = FileProvider.getUriForFile(app, "${app.packageName}.fileprovider", file)
            val mime = when (message.attachmentType?.lowercase()) {
                "jpg", "jpeg" -> "image/jpeg"; "png" -> "image/png"; "gif" -> "image/gif"; "webp" -> "image/webp"
                "pdf" -> "application/pdf"; "txt" -> "text/plain"; "doc" -> "application/msword"
                "docx" -> "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                else -> "application/octet-stream"
            }
            val intent = Intent(Intent.ACTION_VIEW).setDataAndType(uri, mime)
                .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_ACTIVITY_NEW_TASK)
            app.startActivity(Intent.createChooser(intent, "Open attachment").addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
        }
    }

    fun react(message: ChatMessage, emoji: String) = chatAction { api.react(message.id, emoji) }
    fun toggleStar(message: ChatMessage) = chatAction { api.toggleStar(message.id) }
    fun togglePin(message: ChatMessage) = chatAction { api.togglePin(message.id) }
    fun editMessage(message: ChatMessage, content: String, after: () -> Unit) = chatAction(after) {
        api.editMessage(message.id, content.trim())
    }
    fun deleteMessage(message: ChatMessage, everyone: Boolean) = chatAction {
        api.deleteMessage(message.id, everyone)
    }
    fun toggleMute() {
        val c = selectedConversation ?: return
        chatAction {
            api.toggleMute(c.id)
            selectedConversation = c.copy(muted = !c.muted)
        }
    }

    private fun chatAction(after: () -> Unit = {}, action: () -> Unit) {
        val c = selectedConversation ?: return
        launch(showSpinner = false) {
            withContext(Dispatchers.IO) { action() }
            messages = withContext(Dispatchers.IO) { api.messages(c.id) }
            after()
        }
    }

    fun logout() = launch {
        try { withContext(Dispatchers.IO) { api.logout() } }
        finally {
            bootstrap = null; posts = emptyList(); commentPost = null; feedComments = emptyList()
            conversations = emptyList(); messages = emptyList(); remotePresence = ChatPresence()
            uploadProgress = null; uploadLabel = ""; activeModule = null
            selectedConversation = null; authStage = AuthStage.LOGIN
            notice = null
        }
    }

    private fun launch(showSpinner: Boolean = true, work: suspend () -> Unit) {
        if (busy && showSpinner) return
        viewModelScope.launch {
            if (showSpinner) busy = true
            error = null
            try { work() }
            catch (e: ApiException) {
                error = e.message ?: "Request failed."
                if (e.status == 401) { session.token = null; authStage = AuthStage.LOGIN }
                else if (authStage == AuthStage.STARTING) authStage = AuthStage.LOGIN
            }
            catch (e: Exception) {
                error = e.message ?: "Could not connect. Please try again."
                if (authStage == AuthStage.STARTING) authStage = AuthStage.LOGIN
            }
            finally { if (showSpinner) busy = false }
        }
    }
}
