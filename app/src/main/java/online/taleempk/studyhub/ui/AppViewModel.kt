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
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.cancelChildren
import java.util.UUID
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
    var notifications by mutableStateOf<List<AppNotification>>(emptyList()); private set
    var notificationUnread by mutableStateOf(0); private set
    var frontNotification by mutableStateOf<AppNotification?>(null); private set
    fun dismissFrontNotification(){frontNotification=null}
    var notificationsOpen by mutableStateOf(false); private set
    var notificationLoading by mutableStateOf(false); private set
    var feedLoadingMore by mutableStateOf(false); private set
    var feedHasMore by mutableStateOf(true); private set
    var publishing by mutableStateOf(false); private set
    var lookupTitle by mutableStateOf<String?>(null); private set
    var lookupResults by mutableStateOf<List<ChatLookup>>(emptyList());private set
    fun closeLookup(){lookupTitle=null;lookupResults=emptyList()}
    fun findMessages(query:String?=null)=launch {
        lookupResults=withContext(Dispatchers.IO){api.findMessages(query)}
        lookupTitle=if(query==null)"Starred messages" else "Message search"
    }
    fun openLookup(result:ChatLookup){closeLookup();openNativeRoute("chat.php?id=${result.conversationId}")}
    var publishProgress by mutableStateOf<Float?>(null); private set
    private val postActions = mutableSetOf<Long>()
    var chatLoading by mutableStateOf(false); private set
    var historyLoading by mutableStateOf(false); private set
    var hasOlderMessages by mutableStateOf(false); private set
    private var chatGeneration = 0L
    private var syncingGeneration: Long? = null
    private var presenceGeneration: Long? = null
    private val pendingByChat = mutableMapOf<Long, List<ChatMessage>>()
    private val sendsInFlight = mutableSetOf<String>()
    private val playedVoiceIds = mutableSetOf<Long>()
    fun voiceStarted(message: ChatMessage){
        if(message.mine || message.id<=0 || !playedVoiceIds.add(message.id))return
        viewModelScope.launch {try{withContext(Dispatchers.IO){api.voicePlayed(message.id)}}
            catch(e:CancellationException){throw e}catch(_:Exception){playedVoiceIds.remove(message.id)}}
    }
    private val drafts = mutableMapOf<Long, String>()
    private var visibleMessageIds = emptyList<Long>()
    fun visibleMessages(ids:List<Long>){visibleMessageIds=ids.filter{it>0}.take(60)}
    fun draft(id: Long) = drafts[id].orEmpty()
    fun saveDraft(id: Long, text: String) { drafts[id] = text }

    init { restore() }

    fun clearError() { error = null }
    fun reportError(message:String){error=message}
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
    fun refreshFeed() = launch { posts = withContext(Dispatchers.IO) { api.feed() }; feedHasMore=posts.size==20 }
    fun refreshChats() = launch { conversations = withContext(Dispatchers.IO) { api.conversations() } }

    fun openNativeRoute(route: String) {
        val uri = Uri.parse(route)
        val path = uri.path.orEmpty().substringAfterLast('/')
        when (path) {
            "post.php" -> {
                val id = uri.getQueryParameter("id")?.toLongOrNull() ?: return
                launch { val post = withContext(Dispatchers.IO) { api.feed(postId=id) }.firstOrNull()
                    if(post==null) error="This post is no longer available." else {
                        posts=(listOf(post)+posts).distinctBy{it.id}; screen=RootScreen.FEED; openComments(post)
                    } }
            }
            "feed.php" -> selectScreen(RootScreen.FEED)
            "chat.php" -> {
                val id = (uri.getQueryParameter("id") ?: uri.getQueryParameter("c"))?.toLongOrNull()
                if(id==null) selectScreen(RootScreen.CHATS) else launch {
                    conversations=withContext(Dispatchers.IO){api.conversations()}
                    conversations.firstOrNull{it.id==id}?.let(::openConversation)
                        ?: run { screen=RootScreen.CHATS; error="This conversation is no longer available." }
                }
            }
            "study.php" -> openModule("study")
            "library.php" -> openModule("library")
            "quiz.php" -> openModule("quizzes")
            "groups.php" -> openModule("groups")
            "planner.php" -> openModule("planner")
            "results.php" -> openModule("results")
            "edit-profile.php" -> openModule("profile")
            "settings.php" -> openModule("settings")
            "notifications.php" -> openNotifications()
            "support.php" -> openModule("support")
            else -> error = "This section is being prepared for the native app."
        }
    }

    fun openModule(key: String) = launch {
        activeModule = withContext(Dispatchers.IO) { api.module(key) }
    }
    fun closeModule() { activeModule = null }

    fun refreshNotifications() {
        if(notificationLoading || authStage!=AuthStage.SIGNED_IN) return
        notificationLoading=true
        val token=session.token
        viewModelScope.launch { try {
            val batch=withContext(Dispatchers.IO){api.notifications()}
            if(session.token==token && authStage==AuthStage.SIGNED_IN) {
                val previous=notifications.firstOrNull()?.id
                if(previous!=null)batch.items.firstOrNull{it.id>previous && !it.read}?.let{frontNotification=it}
                notifications=batch.items; notificationUnread=batch.unread
            }
        } catch(e: CancellationException){throw e} catch(_:Exception){} finally{notificationLoading=false} }
    }
    fun openNotifications(){ notificationsOpen=true; refreshNotifications() }
    fun closeNotifications(){ notificationsOpen=false }
    fun readNotification(item: AppNotification?)=launch(showSpinner=false){
        withContext(Dispatchers.IO){api.readNotification(item?.id ?: 0)}
        notifications=notifications.map{if(item==null || item.id==it.id) it.copy(read=true) else it}
        notificationUnread=if(item==null) 0 else (notificationUnread-if(item.read) 0 else 1).coerceAtLeast(0)
        if(item!=null && item.route.isNotBlank()){notificationsOpen=false; openNativeRoute(item.route)}
    }
    fun loadMoreFeed(){
        if(feedLoadingMore || !feedHasMore || posts.isEmpty())return
        feedLoadingMore=true
        val before=posts.minOf{it.id}
        launch(showSpinner=false){try{
            val more=withContext(Dispatchers.IO){api.feed(before)}
            posts=(posts+more).distinctBy{it.id};feedHasMore=more.size==20
        }finally{feedLoadingMore=false}}
    }
    fun publish(draft: PostDraft, after:()->Unit){
        if(publishing)return
        publishing=true
        launch(showSpinner=false){try{
            notice=withContext(Dispatchers.IO){api.publishPost(draft){p->viewModelScope.launch{publishProgress=p}}}
            after() // Mutation acknowledged; a refresh failure must never prompt a duplicate post.
            refreshFeed()
        }finally{publishing=false;publishProgress=null}}
    }
    fun postReaction(post: FeedPost,type:String){
        if(!postActions.add(post.id))return
        launch(showSpinner=false){try{
            val result=withContext(Dispatchers.IO){api.reactPost(post.id,type)}
            posts=posts.map{if(it.id==post.id)it.copy(likes=result.optInt("likes",it.likes),
                dislikes=result.optInt("dislikes",it.dislikes),liked=result.optBoolean("liked"),
                reaction=result.optString("reaction").takeUnless{it=="null"}.orEmpty())else it}
        }finally{postActions.remove(post.id)}}
    }
    fun savePost(post:FeedPost){
        if(!postActions.add(post.id))return
        launch(showSpinner=false){try{
            val saved=withContext(Dispatchers.IO){api.savePost(post.id)}
            posts=posts.map{if(it.id==post.id)it.copy(saved=saved)else it}
        }finally{postActions.remove(post.id)}}
    }
    fun repost(post:FeedPost){
        if(!postActions.add(post.id))return
        launch(showSpinner=false){try{
            val reposted=withContext(Dispatchers.IO){api.repost(post.id)}
            notice=if(reposted)"Reposted to your community." else "Repost removed."
            refreshFeed()
        }finally{postActions.remove(post.id)}}
    }
    fun refreshModule() { activeModule?.key?.let(::openModule) }

    fun createPost(content: String, question: Boolean, after: () -> Unit) = launch {
        withContext(Dispatchers.IO) { api.createPost(content.trim(), question) }
        after()
        refreshFeed()
    }

    fun togglePostLike(post: FeedPost) = launch(showSpinner = false) {
        postReaction(post,"like")
    }

    fun openComments(post: FeedPost) {
        commentPost = post
        feedComments = emptyList()
        launch(showSpinner = false) { val rows = withContext(Dispatchers.IO) { api.comments(post.id) }
            if(commentPost?.id==post.id)feedComments=rows }
    }

    fun closeComments() { commentPost = null; feedComments = emptyList() }

    fun addComment(content: String, after: () -> Unit) {
        val post = commentPost ?: return
        launch(showSpinner = false) {
            withContext(Dispatchers.IO) { api.addComment(post.id, content.trim()) }
            after()
            val rows=withContext(Dispatchers.IO){api.comments(post.id)}
            if(commentPost?.id==post.id)feedComments=rows
            posts=posts.map{if(it.id==post.id)it.copy(comments=it.comments+1)else it}
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
        selectedConversation?.let { sendPresence(it.id, "") }
        chatGeneration++
        screen = RootScreen.CHATS
        activeModule = null
        selectedConversation = item
        remotePresence = ChatPresence()
        messages = pendingByChat[item.id].orEmpty()
        hasOlderMessages = false
        chatLoading = true
        refreshMessages()
    }

    fun closeConversation() {
        selectedConversation?.let { sendPresence(it.id, "") }
        chatGeneration++
        selectedConversation = null; messages = emptyList(); remotePresence = ChatPresence(); chatLoading = false; refreshChats()
    }
    fun refreshMessages() {
        val c = selectedConversation ?: return
        val generation = chatGeneration
        if (syncingGeneration == generation) return
        syncingGeneration = generation
        val after = messages.filter { it.id > 0 }.maxOfOrNull { it.id } ?: 0L
        val refreshIds = (visibleMessageIds+messages.filter { it.id > 0 }.takeLast(40).map { it.id }).distinct().take(100)
        launch(showSpinner = false) {
            try {
                val batch = withContext(Dispatchers.IO) { api.messageBatch(c.id, after, refreshIds = refreshIds) }
                if (generation == chatGeneration) {
                    messages = ChatSync.merge(messages, batch)
                    pendingByChat[c.id] = messages.filter { it.id < 0 }
                    if (after == 0L) hasOlderMessages = batch.hasMore
                }
            } finally { if (syncingGeneration == generation) syncingGeneration = null
                if (generation == chatGeneration) chatLoading = false }
        }
    }

    fun loadOlderMessages() {
        val c = selectedConversation ?: return
        val before = messages.filter { it.id > 0 }.minOfOrNull { it.id } ?: return
        if (historyLoading) return
        val generation = chatGeneration
        historyLoading = true
        launch(showSpinner = false) { try {
            val batch = withContext(Dispatchers.IO) { api.messageBatch(c.id, beforeId = before) }
            if (generation == chatGeneration) { messages = ChatSync.merge(messages,batch); hasOlderMessages = batch.hasMore }
        } finally { historyLoading = false } }
    }

    fun syncPresence(kind: String) {
        val c = selectedConversation ?: return
        val generation = chatGeneration
        if (presenceGeneration == generation) return
        presenceGeneration = generation
        viewModelScope.launch {
            try {
                val presence = withContext(Dispatchers.IO) { api.presence(c.id, kind) }
                if (generation != chatGeneration) return@launch
                remotePresence = presence
                if (presence.readThrough > 0) messages = messages.map { m ->
                    if (m.mine && m.id <= presence.readThrough && !m.read) m.copy(read = true) else m
                }
            } catch (e: CancellationException) { throw e }
            catch (_: Exception) { }
            finally { if (presenceGeneration == generation) presenceGeneration = null }
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
        val pending = ChatMessage(
            id = pendingId, senderId = bootstrap?.user?.id ?: 0, sender = bootstrap?.user?.name ?: "You",
            content = body, time = SimpleDateFormat("h:mm a", Locale.getDefault()).format(Date()), mine = true,
            voiceSeconds = 0, attachmentUrl = null, attachmentName = null, read = false,
            dateLabel = "Today", clientToken = UUID.randomUUID().toString(), reply = replyMessage?.let { ReplyPreview(it.id, it.sender,
                it.content.ifBlank { it.attachmentName ?: "Voice message" }) }
        )
        pendingByChat[c.id] = pendingByChat[c.id].orEmpty() + pending
        messages = messages + pending
        after()
        sendPending(c.id, pending)
    }

    fun retryMessage(message: ChatMessage) {
        val c = selectedConversation ?: return
        if (message.id < 0 && message.failed) sendPending(c.id, message)
    }

    private fun sendPending(conversationId: Long, pending: ChatMessage) {
        val accountToken=session.token
        val token = pending.clientToken ?: return
        if (!sendsInFlight.add(token)) return
        fun update(row: ChatMessage?) {
            if(session.token!=accountToken)return
            pendingByChat[conversationId] = pendingByChat[conversationId].orEmpty().mapNotNull {
                if (it.clientToken == token) row?.takeIf { it.id < 0 } else it
            }
            if (selectedConversation?.id == conversationId) messages = messages.mapNotNull {
                if (it.clientToken == token) row else it
            }.distinctBy { it.id }
        }
        update(pending.copy(failed = false))
        launch(showSpinner = false) {
            try {
                val id = withContext(Dispatchers.IO) { api.sendText(conversationId, pending.content, pending.reply?.id, token) }
                if (id <= 0) throw ApiException("Message acknowledgement was missing. Tap the message to retry.")
                update(pending.copy(id = id, failed = false, canEdit = true))
                if (selectedConversation?.id == conversationId) refreshMessages()
            } catch (e: CancellationException) { throw e
            } catch (e: Exception) {
                update(pending.copy(failed = true))
                throw e
            } finally { sendsInFlight.remove(token) }
        }
    }

    fun sendVoice(clip: VoiceClip, after: () -> Unit) {
        val c = selectedConversation ?: return
        if (uploadProgress != null) return
        launch(showSpinner = false) {
            uploadLabel = "Sending voice message…"; uploadProgress = 0f
            try {
                withContext(Dispatchers.IO) { api.sendVoice(c.id, clip) { p ->
                    viewModelScope.launch { uploadProgress = p }
                } }
                java.io.File(clip.filePath).delete()
                after()
                if (selectedConversation?.id == c.id) refreshMessages()
            } finally { uploadProgress = null; uploadLabel = "" }
        }
    }

    fun sendAttachment(uri: Uri) {
        val c = selectedConversation ?: return
        if (uploadProgress != null) return
        launch(showSpinner = false) {
            uploadLabel = "Uploading attachment…"; uploadProgress = 0f
            try {
                withContext(Dispatchers.IO) { api.sendAttachment(c.id, uri) { p ->
                    viewModelScope.launch { uploadProgress = p }
                } }
                if (selectedConversation?.id == c.id) refreshMessages()
            } finally { uploadProgress = null; uploadLabel = "" }
        }
    }

    fun sendEditedImage(uri: Uri, rotation: Int, squareCrop: Boolean, caption: String, after: () -> Unit) {
        val c = selectedConversation ?: return
        if (uploadProgress != null) return
        launch(showSpinner = false) {
            uploadLabel = "Optimising photo…"; uploadProgress = 0f
            try {
                withContext(Dispatchers.IO) { api.sendEditedImage(c.id, uri, rotation, squareCrop, caption) { p ->
                    viewModelScope.launch { uploadLabel = "Uploading photo…"; uploadProgress = p }
                } }
                after()
                if (selectedConversation?.id == c.id) refreshMessages()
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

    fun openPostMedia(media:PostMedia)=launch {
        val file=withContext(Dispatchers.IO){api.downloadPostMedia(media)}
        val app=getApplication<Application>()
        val uri=FileProvider.getUriForFile(app,"${app.packageName}.fileprovider",file)
        val mime=when(media.type.lowercase()){ "pdf"->"application/pdf";"txt"->"text/plain";"doc"->"application/msword";"docx"->"application/vnd.openxmlformats-officedocument.wordprocessingml.document";else->"application/octet-stream" }
        val intent=Intent(Intent.ACTION_VIEW).setDataAndType(uri,mime).addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_ACTIVITY_NEW_TASK)
        app.startActivity(Intent.createChooser(intent,"Open document").addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
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
        launch(showSpinner = false) {
            withContext(Dispatchers.IO) { api.toggleMute(c.id) }
            if (selectedConversation?.id == c.id) selectedConversation = c.copy(muted = !c.muted)
        }
    }

    private fun chatAction(after: () -> Unit = {}, action: () -> Unit) {
        val c = selectedConversation ?: return
        launch(showSpinner = false) {
            withContext(Dispatchers.IO) { action() }
            after()
            if (selectedConversation?.id == c.id) refreshMessages()
        }
    }

    fun logout() = launch {
        try { withContext(Dispatchers.IO) { api.logout() } }
        finally {
            resetSignedOut()
        }
    }

    private fun resetSignedOut(){
        chatGeneration++;session.token=null;pendingByChat.clear();drafts.clear();playedVoiceIds.clear()
        notifications=emptyList();notificationUnread=0;notificationsOpen=false;frontNotification=null
        bootstrap=null;posts=emptyList();commentPost=null;feedComments=emptyList();conversations=emptyList();messages=emptyList()
        selectedConversation=null;activeModule=null;remotePresence=ChatPresence();uploadProgress=null;uploadLabel="";lookupTitle=null;lookupResults=emptyList()
        publishing=false;publishProgress=null;visibleMessageIds=emptyList();busy=false;authStage=AuthStage.LOGIN;notice=null
        viewModelScope.coroutineContext.cancelChildren()
    }

    private fun launch(showSpinner: Boolean = true, work: suspend () -> Unit) {
        if (busy && showSpinner) return
        viewModelScope.launch {
            val requestToken = session.token
            if (showSpinner) busy = true
            if(showSpinner)error = null
            try { work() }
            catch (e: CancellationException) { throw e }
            catch (e: ApiException) {
                error = e.message ?: "Request failed."
                if (e.status == 401 && session.token == requestToken) {
                    /* A shared action may return 401 with an intact bearer session.
                       Confirm revocation before discarding the user's account state. */
                    val revoked = withContext(Dispatchers.IO) {
                        try { api.bootstrap(); false } catch (check: ApiException) { check.status == 401 }
                        catch (_: Exception) { false }
                    }
                    if (revoked && session.token == requestToken) {
                        resetSignedOut()
                    }
                }
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
