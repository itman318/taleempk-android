package online.taleempk.studyhub.ui

import android.Manifest
import android.content.Intent
import android.media.MediaPlayer
import android.net.Uri
import android.os.SystemClock
import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.viewmodel.compose.viewModel
import kotlinx.coroutines.delay
import online.taleempk.studyhub.data.*
import online.taleempk.studyhub.media.VoiceRecorder
import java.io.File

private val Navy = Color(0xFF12213E)
private val Navy2 = Color(0xFF1D3156)
private val Lime = Color(0xFFB9F227)
private val Ink = Color(0xFF172033)
private val Mist = Color(0xFFF4F6FB)
private val Green = Color(0xFF14966B)

@Composable
fun TaleemPkRoot(vm: AppViewModel = viewModel()) {
    val scheme = lightColorScheme(
        primary = Navy, onPrimary = Color.White, secondary = Lime, onSecondary = Navy,
        background = Mist, surface = Color.White, onSurface = Ink, error = Color(0xFFB3261E)
    )
    MaterialTheme(colorScheme = scheme, typography = Typography(), shapes = Shapes(
        small = RoundedCornerShape(10.dp), medium = RoundedCornerShape(18.dp), large = RoundedCornerShape(28.dp)
    )) {
        Surface(Modifier.fillMaxSize()) {
            when (vm.authStage) {
                AuthStage.STARTING -> BrandSplash()
                AuthStage.LOGIN -> LoginScreen(vm)
                AuthStage.TWO_FACTOR -> TwoFactorScreen(vm)
                AuthStage.SIGNED_IN -> MainShell(vm)
            }
        }
    }
}

@Composable
private fun BrandSplash() {
    Box(Modifier.fillMaxSize().background(Navy), contentAlignment = Alignment.Center) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            BrandMark(82)
            Spacer(Modifier.height(18.dp))
            Text("TaleemPK", color = Color.White, fontSize = 30.sp, fontWeight = FontWeight.Black)
            Text("Learn. Connect. Grow.", color = Lime, fontWeight = FontWeight.SemiBold)
        }
    }
}

@Composable
private fun BrandMark(size: Int = 54) {
    Box(
        Modifier.size(size.dp).clip(RoundedCornerShape((size / 4).dp)).background(Navy2),
        contentAlignment = Alignment.Center
    ) {
        Text("T", color = Lime, fontWeight = FontWeight.Black, fontSize = (size * .58f).sp)
    }
}

@Composable
private fun LoginScreen(vm: AppViewModel) {
    var ident by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    Column(
        Modifier.fillMaxSize().statusBarsPadding().padding(horizontal = 24.dp),
        verticalArrangement = Arrangement.Center
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            BrandMark(62); Spacer(Modifier.width(14.dp))
            Column { Text("TaleemPK", fontSize = 30.sp, fontWeight = FontWeight.Black, color = Navy)
                Text("Pakistan's learning community", color = Color.Gray) }
        }
        Spacer(Modifier.height(36.dp))
        Text("Welcome back", fontSize = 28.sp, fontWeight = FontWeight.Bold)
        Text("Sign in with your existing TaleemPK account.", color = Color.Gray)
        Spacer(Modifier.height(22.dp))
        OutlinedTextField(ident, { ident = it }, Modifier.fillMaxWidth(), label = { Text("Email or username") },
            leadingIcon = { Icon(Icons.Default.Person, null) }, singleLine = true,
            keyboardOptions = KeyboardOptions(imeAction = ImeAction.Next))
        Spacer(Modifier.height(12.dp))
        OutlinedTextField(password, { password = it }, Modifier.fillMaxWidth(), label = { Text("Password") },
            leadingIcon = { Icon(Icons.Default.Lock, null) }, singleLine = true,
            visualTransformation = PasswordVisualTransformation(),
            keyboardOptions = KeyboardOptions(imeAction = ImeAction.Done),
            keyboardActions = KeyboardActions(onDone = { if (ident.isNotBlank() && password.isNotBlank()) vm.login(ident, password) }))
        ErrorBanner(vm.error, vm::clearError)
        Spacer(Modifier.height(18.dp))
        Button(onClick = { vm.login(ident, password) }, Modifier.fillMaxWidth().height(54.dp),
            enabled = !vm.busy && ident.isNotBlank() && password.isNotBlank()) {
            if (vm.busy) CircularProgressIndicator(Modifier.size(22.dp), strokeWidth = 2.dp, color = Color.White)
            else Text("Sign in", fontWeight = FontWeight.Bold)
        }
        Spacer(Modifier.height(16.dp))
        Text("Secure connection · Your website account and data stay the same.", color = Color.Gray,
            fontSize = 12.sp, modifier = Modifier.align(Alignment.CenterHorizontally))
    }
}

@Composable
private fun TwoFactorScreen(vm: AppViewModel) {
    var code by remember { mutableStateOf("") }
    Column(Modifier.fillMaxSize().statusBarsPadding().padding(24.dp), verticalArrangement = Arrangement.Center) {
        BrandMark(58); Spacer(Modifier.height(28.dp))
        Text("Check your email", fontSize = 28.sp, fontWeight = FontWeight.Bold)
        Text("Enter the six-digit verification code to finish signing in.", color = Color.Gray)
        Spacer(Modifier.height(20.dp))
        OutlinedTextField(code, { if (it.length <= 6) code = it.filter(Char::isDigit) }, Modifier.fillMaxWidth(),
            label = { Text("Verification code") }, singleLine = true,
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.NumberPassword, imeAction = ImeAction.Done),
            keyboardActions = KeyboardActions(onDone = { if (code.length == 6) vm.verify(code) }))
        ErrorBanner(vm.error, vm::clearError)
        Spacer(Modifier.height(18.dp))
        Button({ vm.verify(code) }, Modifier.fillMaxWidth().height(54.dp), enabled = !vm.busy && code.length == 6) {
            if (vm.busy) CircularProgressIndicator(Modifier.size(22.dp), strokeWidth = 2.dp, color = Color.White)
            else Text("Verify and continue", fontWeight = FontWeight.Bold)
        }
    }
}

@Composable
private fun MainShell(vm: AppViewModel) {
    val context = LocalContext.current
    val activeChat = vm.selectedConversation
    BackHandler(enabled = activeChat != null) { vm.closeConversation() }
    Scaffold(
        containerColor = Mist,
        topBar = {
            if (activeChat == null) AppTopBar(vm.bootstrap?.user?.name ?: "TaleemPK")
            else ChatTopBar(activeChat, vm::closeConversation)
        },
        bottomBar = {
            if (activeChat == null) NavigationBar(containerColor = Color.White) {
                NavItem("Home", Icons.Default.Home, RootScreen.HOME, vm)
                NavItem("Feed", Icons.Default.DynamicFeed, RootScreen.FEED, vm)
                NavItem("Chat", Icons.Default.ChatBubble, RootScreen.CHATS, vm)
                NavItem("Profile", Icons.Default.Person, RootScreen.PROFILE, vm)
            }
        }
    ) { pad ->
        Box(Modifier.fillMaxSize().padding(pad)) {
            when (vm.screen) {
                RootScreen.HOME -> HomeScreen(vm.bootstrap, vm::refreshHome) { route ->
                    when (route) {
                        "feed.php" -> vm.selectScreen(RootScreen.FEED)
                        "chat.php" -> vm.selectScreen(RootScreen.CHATS)
                        else -> context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse("https://taleempk.online/$route")))
                    }
                }
                RootScreen.FEED -> FeedScreen(vm.posts, vm::refreshFeed)
                RootScreen.CHATS -> if (activeChat == null) ChatList(vm.conversations, vm::refreshChats, vm::openConversation)
                    else ChatThread(vm, activeChat)
                RootScreen.PROFILE -> ProfileScreen(vm.bootstrap?.user, vm::logout)
            }
            if (vm.busy && vm.authStage == AuthStage.SIGNED_IN) LinearProgressIndicator(Modifier.fillMaxWidth().align(Alignment.TopCenter), color = Lime)
            vm.error?.let { Snackbar(Modifier.align(Alignment.BottomCenter).padding(16.dp), action = {
                TextButton(vm::clearError) { Text("Dismiss") }
            }) { Text(it) } }
        }
    }
}

@Composable
private fun AppTopBar(name: String) {
    Surface(color = Navy, shadowElevation = 4.dp) {
        Row(Modifier.fillMaxWidth().statusBarsPadding().height(68.dp).padding(horizontal = 18.dp),
            verticalAlignment = Alignment.CenterVertically) {
            BrandMark(42); Spacer(Modifier.width(12.dp))
            Column(Modifier.weight(1f)) {
                Text("TaleemPK", color = Color.White, fontWeight = FontWeight.Black, fontSize = 20.sp)
                Text("Hello, ${name.substringBefore(' ')}", color = Color.White.copy(alpha = .68f), fontSize = 12.sp)
            }
        }
    }
}

@Composable
private fun ChatTopBar(c: Conversation, back: () -> Unit) {
    Surface(color = Navy) {
        Row(Modifier.fillMaxWidth().statusBarsPadding().height(68.dp), verticalAlignment = Alignment.CenterVertically) {
            IconButton(back) { Icon(Icons.Default.ArrowBack, "Back", tint = Color.White) }
            InitialAvatar(c.title, 42); Spacer(Modifier.width(10.dp))
            Column(Modifier.weight(1f)) { Text(c.title, color = Color.White, fontWeight = FontWeight.Bold)
                Text(if (c.group) "Study group" else "Private conversation", color = Color.White.copy(.65f), fontSize = 12.sp) }
        }
    }
}

@Composable
private fun RowScope.NavItem(label: String, icon: ImageVector, target: RootScreen, vm: AppViewModel) {
    NavigationBarItem(selected = vm.screen == target, onClick = { vm.selectScreen(target) },
        icon = { Icon(icon, label) }, label = { Text(label) },
        colors = NavigationBarItemDefaults.colors(selectedIconColor = Navy, indicatorColor = Lime.copy(alpha = .42f)))
}

@Composable
private fun HomeScreen(data: Bootstrap?, refresh: () -> Unit, open: (String) -> Unit) {
    if (data == null) { EmptyState("Loading your study space…", Icons.Default.School, refresh); return }
    LazyColumn(contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
        item {
            Surface(color = Navy, shape = RoundedCornerShape(24.dp)) {
                Column(Modifier.padding(22.dp)) {
                    Text("Learn without limits", color = Color.White, fontWeight = FontWeight.Black, fontSize = 25.sp)
                    Text("Your classes, community and progress in one place.", color = Color.White.copy(.72f))
                    Spacer(Modifier.height(16.dp))
                    Button({ open("study.php") }, colors = ButtonDefaults.buttonColors(containerColor = Lime, contentColor = Navy)) {
                        Icon(Icons.Default.AutoStories, null); Spacer(Modifier.width(8.dp)); Text("Continue learning", fontWeight = FontWeight.Bold)
                    }
                }
            }
        }
        item { Text("Community today", fontSize = 19.sp, fontWeight = FontWeight.Bold) }
        item {
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                StatCard("Members", data.stats.members, Modifier.weight(1f))
                StatCard("Active", data.stats.activeToday, Modifier.weight(1f))
            }
        }
        item {
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                StatCard("Messages", data.stats.messagesToday, Modifier.weight(1f))
                StatCard("Quiz attempts", data.stats.quizAttempts, Modifier.weight(1f))
            }
        }
        item { Text("Explore", fontSize = 19.sp, fontWeight = FontWeight.Bold) }
        items(data.shortcuts) { item ->
            Surface(Modifier.fillMaxWidth().clickable { open(item.route) }, shape = RoundedCornerShape(18.dp), shadowElevation = 1.dp) {
                Row(Modifier.padding(16.dp), verticalAlignment = Alignment.CenterVertically) {
                    Box(Modifier.size(46.dp).clip(RoundedCornerShape(14.dp)).background(Lime.copy(.25f)), contentAlignment = Alignment.Center) {
                        Icon(shortcutIcon(item.icon), null, tint = Navy)
                    }
                    Spacer(Modifier.width(14.dp)); Column(Modifier.weight(1f)) {
                        Text(item.title, fontWeight = FontWeight.Bold); Text(item.subtitle, color = Color.Gray, fontSize = 13.sp)
                    }; Icon(Icons.Default.ChevronRight, null, tint = Color.Gray)
                }
            }
        }
        item { Spacer(Modifier.height(6.dp)) }
    }
}

@Composable private fun StatCard(label: String, number: Int, modifier: Modifier) {
    Surface(modifier, shape = RoundedCornerShape(18.dp), color = Color.White) {
        Column(Modifier.padding(16.dp)) { Text(number.toString(), fontWeight = FontWeight.Black, fontSize = 23.sp, color = Navy)
            Text(label, color = Color.Gray, fontSize = 12.sp) }
    }
}

@Composable
private fun FeedScreen(posts: List<FeedPost>, refresh: () -> Unit) {
    if (posts.isEmpty()) { EmptyState("Your feed is ready to refresh.", Icons.Default.DynamicFeed, refresh); return }
    LazyColumn(contentPadding = PaddingValues(14.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item { Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
            Text("Community feed", fontSize = 22.sp, fontWeight = FontWeight.Black); IconButton(refresh) { Icon(Icons.Default.Refresh, "Refresh") }
        } }
        items(posts, key = { it.id }) { p ->
            Surface(shape = RoundedCornerShape(20.dp), color = Color.White, shadowElevation = 1.dp) {
                Column(Modifier.padding(16.dp)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        InitialAvatar(p.author, 42); Spacer(Modifier.width(10.dp)); Column(Modifier.weight(1f)) {
                            Text(p.author, fontWeight = FontWeight.Bold); Text("@${p.username} · ${p.createdAt}", color = Color.Gray, fontSize = 12.sp)
                        }; if (p.solved) AssistChip({}, { Text("Solved") }, leadingIcon = { Icon(Icons.Default.CheckCircle, null, tint = Green) })
                    }
                    if (p.content.isNotBlank()) { Spacer(Modifier.height(14.dp)); Text(p.content, lineHeight = 22.sp) }
                    Spacer(Modifier.height(12.dp)); HorizontalDivider(color = Mist); Spacer(Modifier.height(8.dp))
                    Row { Icon(Icons.Default.ThumbUp, null, Modifier.size(18.dp), tint = Color.Gray); Text(" ${p.likes}", color = Color.Gray)
                        Spacer(Modifier.width(26.dp)); Icon(Icons.Default.ChatBubbleOutline, null, Modifier.size(18.dp), tint = Color.Gray); Text(" ${p.comments}", color = Color.Gray) }
                }
            }
        }
    }
}

@Composable
private fun ChatList(chats: List<Conversation>, refresh: () -> Unit, open: (Conversation) -> Unit) {
    if (chats.isEmpty()) { EmptyState("No conversations yet—or tap refresh.", Icons.Default.ChatBubble, refresh); return }
    LazyColumn(contentPadding = PaddingValues(vertical = 8.dp)) {
        item { Row(Modifier.fillMaxWidth().padding(horizontal = 18.dp), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
            Text("Messages", fontSize = 22.sp, fontWeight = FontWeight.Black); IconButton(refresh) { Icon(Icons.Default.Refresh, "Refresh") }
        } }
        items(chats, key = { it.id }) { c ->
            Row(Modifier.fillMaxWidth().clickable { open(c) }.padding(horizontal = 18.dp, vertical = 12.dp), verticalAlignment = Alignment.CenterVertically) {
                InitialAvatar(c.title, 52); Spacer(Modifier.width(12.dp)); Column(Modifier.weight(1f)) {
                    Row { Text(c.title, Modifier.weight(1f), fontWeight = FontWeight.Bold, maxLines = 1)
                        Text(c.lastActivity, color = Color.Gray, fontSize = 11.sp) }
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(c.lastMessage.ifBlank { "Start a conversation" }, Modifier.weight(1f), color = Color.Gray, maxLines = 1, overflow = TextOverflow.Ellipsis)
                        if (c.unread > 0) Badge(containerColor = Lime, contentColor = Navy) { Text(c.unread.toString()) }
                    }
                }
            }
        }
    }
}

@Composable
private fun ChatThread(vm: AppViewModel, chat: Conversation) {
    val context = LocalContext.current
    val recorder = remember { VoiceRecorder(context) }
    var recording by remember { mutableStateOf(false) }
    var recordingStart by remember { mutableLongStateOf(0L) }
    var elapsed by remember { mutableIntStateOf(0) }
    var preview by remember { mutableStateOf<VoiceClip?>(null) }
    var text by remember { mutableStateOf("") }

    DisposableEffect(Unit) { onDispose { recorder.cancel(); preview?.let { File(it.filePath).delete() } } }
    LaunchedEffect(recording) {
        while (recording) {
            elapsed = ((SystemClock.elapsedRealtime() - recordingStart) / 1000L).toInt()
            if (elapsed >= 120) {
                try { preview = recorder.stop() } catch (_: Exception) { recorder.cancel() }
                recording = false
            }
            delay(250)
        }
    }
    val micPermission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { allowed ->
        if (allowed) try { recorder.start(); recordingStart = SystemClock.elapsedRealtime(); elapsed = 0; recording = true } catch (_: Exception) { }
    }
    val picker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri -> uri?.let(vm::sendAttachment) }

    Column(Modifier.fillMaxSize()) {
        LazyColumn(Modifier.weight(1f), reverseLayout = true, contentPadding = PaddingValues(12.dp), verticalArrangement = Arrangement.spacedBy(7.dp)) {
            items(vm.messages.asReversed(), key = { it.id }) { m -> MessageBubble(m, vm.authHeaders()) }
        }
        if (preview != null) {
            Surface(color = Lime.copy(.18f)) { Row(Modifier.fillMaxWidth().padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
                Icon(Icons.Default.GraphicEq, null, tint = Navy); Spacer(Modifier.width(10.dp)); Text("Voice message · ${preview!!.seconds}s", Modifier.weight(1f), fontWeight = FontWeight.SemiBold)
                IconButton({ File(preview!!.filePath).delete(); preview = null }) { Icon(Icons.Default.Delete, "Delete") }
                FilledIconButton({ val clip = preview!!; vm.sendVoice(clip) { preview = null } }, colors = IconButtonDefaults.filledIconButtonColors(containerColor = Navy)) { Icon(Icons.Default.Send, "Send") }
            } }
        } else if (recording) {
            Surface(color = Color(0xFFFFECEA)) { Row(Modifier.fillMaxWidth().padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
                Icon(Icons.Default.Mic, null, tint = Color.Red); Spacer(Modifier.width(10.dp)); Text("Recording… ${elapsed}s", Modifier.weight(1f), fontWeight = FontWeight.Bold)
                TextButton({ recorder.cancel(); recording = false }) { Text("Cancel") }
                FilledIconButton({ try { preview = recorder.stop() } catch (_: Exception) { }; recording = false }, colors = IconButtonDefaults.filledIconButtonColors(containerColor = Navy)) { Icon(Icons.Default.Stop, "Stop") }
            } }
        } else {
            Surface(shadowElevation = 8.dp, color = Color.White) {
                Row(Modifier.fillMaxWidth().navigationBarsPadding().padding(10.dp), verticalAlignment = Alignment.Bottom) {
                    IconButton({ picker.launch(arrayOf("image/*", "application/pdf", "text/plain", "application/msword", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")) }) { Icon(Icons.Default.AttachFile, "Attach") }
                    OutlinedTextField(text, { if (it.length <= 4000) text = it }, Modifier.weight(1f), placeholder = { Text("Message…") }, maxLines = 5, shape = RoundedCornerShape(24.dp))
                    Spacer(Modifier.width(8.dp))
                    FilledIconButton(onClick = {
                        if (text.isNotBlank()) vm.sendText(text) { text = "" }
                        else micPermission.launch(Manifest.permission.RECORD_AUDIO)
                    }, colors = IconButtonDefaults.filledIconButtonColors(containerColor = Navy), modifier = Modifier.size(52.dp)) {
                        Icon(if (text.isNotBlank()) Icons.Default.Send else Icons.Default.Mic, if (text.isNotBlank()) "Send" else "Record voice")
                    }
                }
            }
        }
    }
}

@Composable
private fun MessageBubble(m: ChatMessage, headers: Map<String, String>) {
    Row(Modifier.fillMaxWidth(), horizontalArrangement = if (m.mine) Arrangement.End else Arrangement.Start) {
        Surface(color = if (m.mine) Navy else Color.White, contentColor = if (m.mine) Color.White else Ink,
            shape = RoundedCornerShape(18.dp), shadowElevation = if (m.mine) 0.dp else 1.dp, modifier = Modifier.widthIn(max = 310.dp)) {
            Column(Modifier.padding(horizontal = 14.dp, vertical = 10.dp)) {
                if (!m.mine) Text(m.sender, color = Green, fontWeight = FontWeight.Bold, fontSize = 12.sp)
                if (m.voiceSeconds > 0) VoicePlayer(m.attachmentUrl, m.voiceSeconds, headers)
                else if (m.attachmentUrl != null) Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(Icons.Default.InsertDriveFile, null); Spacer(Modifier.width(7.dp)); Text(m.attachmentName ?: "Attachment", maxLines = 1)
                }
                if (m.content.isNotBlank()) Text(m.content, lineHeight = 21.sp)
                Row(Modifier.align(Alignment.End), verticalAlignment = Alignment.CenterVertically) {
                    Text(m.time, color = if (m.mine) Color.White.copy(.6f) else Color.Gray, fontSize = 10.sp)
                    if (m.mine) { Spacer(Modifier.width(4.dp)); Icon(if (m.read) Icons.Default.DoneAll else Icons.Default.Done, null, Modifier.size(15.dp), tint = if (m.read) Lime else Color.White.copy(.6f)) }
                }
            }
        }
    }
}

@Composable
private fun VoicePlayer(url: String?, seconds: Int, headers: Map<String, String>) {
    val context = LocalContext.current
    var player by remember { mutableStateOf<MediaPlayer?>(null) }
    var playing by remember { mutableStateOf(false) }
    DisposableEffect(url) { onDispose { player?.release(); player = null } }
    Row(verticalAlignment = Alignment.CenterVertically) {
        IconButton({
            if (playing) { player?.pause(); playing = false }
            else if (url != null) {
                val current = player
                if (current != null) {
                    try { current.start(); playing = true } catch (_: Exception) { }
                } else try {
                    MediaPlayer().also { mp ->
                        mp.setDataSource(context, Uri.parse(url), headers)
                        mp.setOnPreparedListener { it.start(); playing = true }
                        mp.setOnCompletionListener { playing = false; it.seekTo(0) }
                        mp.setOnErrorListener { failed, _, _ ->
                            failed.release(); player = null; playing = false; true
                        }
                        player = mp
                        mp.prepareAsync()
                    }
                } catch (_: Exception) {
                    player?.release(); player = null; playing = false
                }
            }
        }) { Icon(if (playing) Icons.Default.Pause else Icons.Default.PlayArrow, if (playing) "Pause voice" else "Play voice") }
        Icon(Icons.Default.GraphicEq, null, Modifier.width(90.dp)); Text(" ${seconds}s", fontSize = 12.sp)
    }
}

@Composable
private fun ProfileScreen(user: User?, logout: () -> Unit) {
    Column(Modifier.fillMaxSize().padding(22.dp), horizontalAlignment = Alignment.CenterHorizontally) {
        Spacer(Modifier.height(20.dp)); InitialAvatar(user?.name ?: "T", 92); Spacer(Modifier.height(14.dp))
        Text(user?.name ?: "TaleemPK member", fontSize = 25.sp, fontWeight = FontWeight.Black)
        Text("@${user?.username.orEmpty()} · ${user?.role.orEmpty().replaceFirstChar { it.uppercase() }}", color = Color.Gray)
        if (user?.verified == true) AssistChip({}, { Text("Verified profile") }, leadingIcon = { Icon(Icons.Default.Verified, null, tint = Green) })
        Spacer(Modifier.height(30.dp))
        Surface(Modifier.fillMaxWidth(), shape = RoundedCornerShape(20.dp)) { Column {
            ProfileRow(Icons.Default.Security, "Security", "Encrypted session and 2-step verification")
            HorizontalDivider(); ProfileRow(Icons.Default.Notifications, "Notifications", "Messages, replies and account alerts")
            HorizontalDivider(); ProfileRow(Icons.Default.Help, "Help & support", "Tickets, appeals and safety")
        } }
        Spacer(Modifier.weight(1f))
        OutlinedButton(logout, Modifier.fillMaxWidth().navigationBarsPadding(), colors = ButtonDefaults.outlinedButtonColors(contentColor = MaterialTheme.colorScheme.error)) {
            Icon(Icons.Default.Logout, null); Spacer(Modifier.width(8.dp)); Text("Sign out")
        }
    }
}

@Composable private fun ProfileRow(icon: ImageVector, title: String, subtitle: String) {
    Row(Modifier.fillMaxWidth().padding(16.dp), verticalAlignment = Alignment.CenterVertically) {
        Icon(icon, null, tint = Navy); Spacer(Modifier.width(13.dp)); Column { Text(title, fontWeight = FontWeight.Bold); Text(subtitle, color = Color.Gray, fontSize = 12.sp) }
    }
}

@Composable private fun InitialAvatar(name: String, size: Int) {
    Box(Modifier.size(size.dp).clip(CircleShape).background(Lime.copy(.32f)), contentAlignment = Alignment.Center) {
        Text(name.trim().take(2).uppercase(), color = Navy, fontWeight = FontWeight.Black, fontSize = (size * .34f).sp)
    }
}

@Composable private fun EmptyState(text: String, icon: ImageVector, refresh: () -> Unit) {
    Column(Modifier.fillMaxSize().padding(28.dp), verticalArrangement = Arrangement.Center, horizontalAlignment = Alignment.CenterHorizontally) {
        Icon(icon, null, Modifier.size(64.dp), tint = Navy.copy(.35f)); Spacer(Modifier.height(14.dp)); Text(text, color = Color.Gray)
        Spacer(Modifier.height(12.dp)); OutlinedButton(refresh) { Icon(Icons.Default.Refresh, null); Spacer(Modifier.width(7.dp)); Text("Refresh") }
    }
}

@Composable private fun ErrorBanner(error: String?, dismiss: () -> Unit) {
    if (error != null) Surface(Modifier.fillMaxWidth().padding(top = 14.dp).clickable(onClick = dismiss), color = MaterialTheme.colorScheme.errorContainer, shape = RoundedCornerShape(12.dp)) {
        Text(error, Modifier.padding(13.dp), color = MaterialTheme.colorScheme.onErrorContainer)
    }
}

private fun shortcutIcon(name: String): ImageVector = when (name) {
    "quiz" -> Icons.Default.Quiz; "library" -> Icons.Default.LocalLibrary; "chat" -> Icons.Default.ChatBubble
    "groups" -> Icons.Default.Groups; "planner" -> Icons.Default.EventNote; "results" -> Icons.Default.Assessment
    else -> Icons.Default.School
}
