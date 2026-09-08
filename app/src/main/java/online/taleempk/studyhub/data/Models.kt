package online.taleempk.studyhub.data

data class User(
    val id: Long,
    val name: String,
    val username: String,
    val role: String,
    val avatar: String?,
    val verified: Boolean
)

data class Stats(
    val members: Int = 0,
    val activeToday: Int = 0,
    val messagesToday: Int = 0,
    val quizAttempts: Int = 0
)

data class Shortcut(val title: String, val subtitle: String, val route: String, val icon: String)

data class Bootstrap(val user: User, val stats: Stats, val shortcuts: List<Shortcut>)

data class FeedPost(
    val id: Long,
    val author: String,
    val username: String,
    val avatar: String?,
    val type: String,
    val content: String,
    val createdAt: String,
    val likes: Int,
    val comments: Int,
    val solved: Boolean,
    val liked: Boolean = false
)

data class FeedComment(
    val id: Long,
    val author: String,
    val content: String,
    val createdAt: String,
    val mine: Boolean = false
)

data class ModuleItem(
    val id: Long,
    val title: String,
    val subtitle: String,
    val meta: String,
    val kind: String,
    val done: Boolean = false
)

data class ModuleContent(
    val key: String,
    val title: String,
    val subtitle: String,
    val items: List<ModuleItem>
)

data class Conversation(
    val id: Long,
    val title: String,
    val avatar: String?,
    val lastMessage: String,
    val lastActivity: String,
    val unread: Int,
    val group: Boolean,
    val online: Boolean = false,
    val statusText: String = "",
    val muted: Boolean = false
)

data class ChatReaction(val emoji: String, val count: Int, val mine: Boolean)

data class ChatPresence(
    val active: Boolean = false,
    val kind: String = "",
    val name: String = "",
    val readThrough: Long = 0
)

data class ReplyPreview(
    val id: Long,
    val sender: String,
    val text: String
)

data class ChatMessage(
    val id: Long,
    val senderId: Long,
    val sender: String,
    val content: String,
    val time: String,
    val mine: Boolean,
    val voiceSeconds: Int,
    val attachmentUrl: String?,
    val attachmentName: String?,
    val read: Boolean,
    val attachmentType: String? = null,
    val dateLabel: String = "",
    val deleted: Boolean = false,
    val edited: Boolean = false,
    val forwarded: Boolean = false,
    val starred: Boolean = false,
    val pinned: Boolean = false,
    val canEdit: Boolean = false,
    val reply: ReplyPreview? = null,
    val reactions: List<ChatReaction> = emptyList()
)

data class AuthResult(
    val token: String? = null,
    val challenge: String? = null,
    val needsTwoFactor: Boolean = false,
    val user: User? = null
)

data class VoiceClip(val filePath: String, val seconds: Int)

class ApiException(message: String, val status: Int = 0) : Exception(message)
