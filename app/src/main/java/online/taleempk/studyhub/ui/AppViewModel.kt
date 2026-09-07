package online.taleempk.studyhub.ui

import android.app.Application
import android.net.Uri
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import online.taleempk.studyhub.data.*

enum class RootScreen { HOME, FEED, CHATS, PROFILE }
enum class AuthStage { STARTING, LOGIN, TWO_FACTOR, SIGNED_IN }

class AppViewModel(application: Application) : AndroidViewModel(application) {
    private val session = SessionStore(application)
    private val api = ApiClient(application, session)

    var authStage by mutableStateOf(AuthStage.STARTING); private set
    var screen by mutableStateOf(RootScreen.HOME); private set
    var busy by mutableStateOf(false); private set
    var error by mutableStateOf<String?>(null); private set
    var challenge by mutableStateOf<String?>(null); private set
    var bootstrap by mutableStateOf<Bootstrap?>(null); private set
    var posts by mutableStateOf<List<FeedPost>>(emptyList()); private set
    var conversations by mutableStateOf<List<Conversation>>(emptyList()); private set
    var selectedConversation by mutableStateOf<Conversation?>(null); private set
    var messages by mutableStateOf<List<ChatMessage>>(emptyList()); private set

    init { restore() }

    fun clearError() { error = null }
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

    fun openConversation(item: Conversation) {
        selectedConversation = item
        launch { messages = withContext(Dispatchers.IO) { api.messages(item.id) } }
    }

    fun closeConversation() { selectedConversation = null; messages = emptyList(); refreshChats() }
    fun refreshMessages() { selectedConversation?.let { c -> launch(showSpinner = false) {
        messages = withContext(Dispatchers.IO) { api.messages(c.id) }
    } } }

    fun sendText(text: String, after: () -> Unit) {
        val c = selectedConversation ?: return
        launch(showSpinner = false) {
            withContext(Dispatchers.IO) { api.sendText(c.id, text.trim()) }
            messages = withContext(Dispatchers.IO) { api.messages(c.id) }
            after()
        }
    }

    fun sendVoice(clip: VoiceClip, after: () -> Unit) {
        val c = selectedConversation ?: return
        launch {
            withContext(Dispatchers.IO) { api.sendVoice(c.id, clip) }
            messages = withContext(Dispatchers.IO) { api.messages(c.id) }
            java.io.File(clip.filePath).delete()
            after()
        }
    }

    fun sendAttachment(uri: Uri) {
        val c = selectedConversation ?: return
        launch {
            withContext(Dispatchers.IO) { api.sendAttachment(c.id, uri) }
            messages = withContext(Dispatchers.IO) { api.messages(c.id) }
        }
    }

    fun logout() = launch {
        try { withContext(Dispatchers.IO) { api.logout() } }
        finally {
            bootstrap = null; posts = emptyList(); conversations = emptyList(); messages = emptyList()
            selectedConversation = null; authStage = AuthStage.LOGIN
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
