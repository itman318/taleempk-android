package online.taleempk.studyhub.ui

import android.Manifest
import android.content.Intent
import android.media.MediaPlayer
import android.net.Uri
import android.os.SystemClock
import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.text.style.TextAlign
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
private val Muted = Color(0xFF667085)
private val Line = Color(0xFFE2E7F0)
private val SoftLime = Color(0xFFF2FFD0)

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
                AuthStage.REGISTER -> RegisterScreen(vm)
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
    val context = LocalContext.current
    PremiumAuthLayout {
        AuthHeading("Welcome back", "Continue your learning journey with your TaleemPK account.")
        Spacer(Modifier.height(24.dp))
        PremiumField(
            value = ident, onValueChange = { ident = it }, label = "Email or username",
            icon = Icons.Default.Person, keyboardOptions = KeyboardOptions(
                keyboardType = KeyboardType.Email, imeAction = ImeAction.Next
            )
        )
        Spacer(Modifier.height(14.dp))
        PremiumField(
            value = password, onValueChange = { password = it }, label = "Password",
            icon = Icons.Default.Lock, password = true,
            keyboardOptions = KeyboardOptions(imeAction = ImeAction.Done),
            keyboardActions = KeyboardActions(onDone = {
                if (ident.isNotBlank() && password.isNotBlank()) vm.login(ident, password)
            })
        )
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End) {
            TextButton(onClick = {
                context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse("https://taleempk.online/forgot.php")))
            }) { Text("Forgot password?", color = Navy, fontWeight = FontWeight.SemiBold) }
        }
        NoticeBanner(vm.notice, vm::clearNotice)
        ErrorBanner(vm.error, vm::clearError)
        Spacer(Modifier.height(14.dp))
        PrimaryActionButton("Sign in", vm.busy, ident.isNotBlank() && password.isNotBlank()) {
            vm.login(ident, password)
        }
        Spacer(Modifier.height(22.dp))
        HorizontalDivider(color = Line)
        Spacer(Modifier.height(18.dp))
        Text("New to TaleemPK?", Modifier.fillMaxWidth(), textAlign = TextAlign.Center,
            color = Muted, fontSize = 13.sp)
        Spacer(Modifier.height(10.dp))
        OutlinedButton(
            onClick = vm::showRegister,
            modifier = Modifier.fillMaxWidth().height(54.dp),
            shape = RoundedCornerShape(16.dp),
            border = BorderStroke(1.2.dp, Navy)
        ) {
            Icon(Icons.Default.PersonAdd, null)
            Spacer(Modifier.width(9.dp))
            Text("Create a free account", fontWeight = FontWeight.Bold)
        }
        SecureFootnote()
    }
}

@Composable
private fun RegisterScreen(vm: AppViewModel) {
    var role by remember { mutableStateOf("student") }
    var name by remember { mutableStateOf("") }
    var username by remember { mutableStateOf("") }
    var email by remember { mutableStateOf("") }
    var phone by remember { mutableStateOf("") }
    var dob by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    val valid = name.trim().length >= 3 && username.trim().length >= 3 &&
        email.contains('@') && dob.length == 10 && password.length >= 8

    BackHandler { vm.showLogin() }
    PremiumAuthLayout {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            IconButton(vm::showLogin) { Icon(Icons.Default.ArrowBack, "Back") }
            Spacer(Modifier.width(2.dp))
            Column {
                Text("Create your account", fontSize = 26.sp, fontWeight = FontWeight.Black, color = Ink)
                Text("Free access to Pakistan's learning community.", color = Muted, fontSize = 13.sp)
            }
        }
        Spacer(Modifier.height(22.dp))
        Text("I am joining as", fontWeight = FontWeight.Bold, color = Ink)
        Spacer(Modifier.height(10.dp))
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            RoleChoice("student", "Student", Icons.Default.School, role, { role = it }, Modifier.weight(1f))
            RoleChoice("teacher", "Teacher", Icons.Default.CoPresent, role, { role = it }, Modifier.weight(1f))
            RoleChoice("institute", "Institute", Icons.Default.AccountBalance, role, { role = it }, Modifier.weight(1f))
        }
        if (role != "student") {
            Text("Teacher and institute accounts are reviewed before activation.", color = Muted,
                fontSize = 11.sp, modifier = Modifier.padding(top = 8.dp))
        }
        Spacer(Modifier.height(18.dp))
        PremiumField(name, { name = it }, "Full name", Icons.Default.Badge,
            KeyboardOptions(capitalization = KeyboardCapitalization.Words, imeAction = ImeAction.Next))
        Spacer(Modifier.height(12.dp))
        PremiumField(username, { username = it.filter { c -> c.isLetterOrDigit() || c == '_' }.take(30) },
            "Username", Icons.Default.AlternateEmail,
            KeyboardOptions(keyboardType = KeyboardType.Ascii, imeAction = ImeAction.Next))
        Spacer(Modifier.height(12.dp))
        PremiumField(email, { email = it.trim() }, "Email address", Icons.Default.Email,
            KeyboardOptions(keyboardType = KeyboardType.Email, imeAction = ImeAction.Next))
        Spacer(Modifier.height(12.dp))
        PremiumField(phone, { phone = it.filter { c -> c.isDigit() || c == '+' }.take(16) },
            "Phone number (optional)", Icons.Default.Phone,
            KeyboardOptions(keyboardType = KeyboardType.Phone, imeAction = ImeAction.Next))
        Spacer(Modifier.height(12.dp))
        PremiumField(dob, { raw ->
            val digits = raw.filter(Char::isDigit).take(8)
            dob = buildString {
                digits.forEachIndexed { index, c ->
                    if (index == 2 || index == 4) append('-')
                    append(c)
                }
            }
        }, "Date of birth (DD-MM-YYYY)", Icons.Default.Cake,
            KeyboardOptions(keyboardType = KeyboardType.Number, imeAction = ImeAction.Next))
        Spacer(Modifier.height(12.dp))
        PremiumField(password, { password = it }, "Create password", Icons.Default.Lock, password = true,
            keyboardOptions = KeyboardOptions(imeAction = ImeAction.Done),
            keyboardActions = KeyboardActions(onDone = {
                if (valid) vm.register(role, name, username, email, phone, dob, password)
            }))
        Text("Use at least 8 characters with a mix of letters, numbers and symbols.",
            color = Muted, fontSize = 11.sp, modifier = Modifier.padding(top = 7.dp, start = 3.dp))
        ErrorBanner(vm.error, vm::clearError)
        Spacer(Modifier.height(20.dp))
        PrimaryActionButton("Create account", vm.busy, valid) {
            vm.register(role, name, username, email, phone, dob, password)
        }
        Text("By creating an account, you agree to TaleemPK's community and safety rules.",
            Modifier.fillMaxWidth().padding(top = 14.dp), textAlign = TextAlign.Center,
            color = Muted, fontSize = 11.sp)
        TextButton(vm::showLogin, Modifier.align(Alignment.CenterHorizontally)) {
            Text("Already have an account? Sign in", color = Navy, fontWeight = FontWeight.Bold)
        }
    }
}

@Composable
private fun PremiumAuthLayout(content: @Composable ColumnScope.() -> Unit) {
    Box(
        Modifier.fillMaxSize().background(
            Brush.verticalGradient(listOf(Color(0xFFF8FAFF), Color.White, SoftLime.copy(alpha = .34f)))
        )
    ) {
        Column(
            Modifier.fillMaxSize().verticalScroll(rememberScrollState()).statusBarsPadding()
                .navigationBarsPadding().padding(horizontal = 20.dp, vertical = 24.dp)
        ) {
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                BrandMark(48)
                Spacer(Modifier.width(12.dp))
                Column(Modifier.weight(1f)) {
                    Text("TaleemPK", fontSize = 24.sp, fontWeight = FontWeight.Black, color = Navy)
                    Text("Learn · Connect · Grow", color = Muted, fontSize = 11.sp)
                }
                Surface(color = SoftLime, shape = RoundedCornerShape(50), contentColor = Navy) {
                    Text("SECURE", Modifier.padding(horizontal = 10.dp, vertical = 6.dp),
                        fontSize = 9.sp, fontWeight = FontWeight.Black)
                }
            }
            Spacer(Modifier.height(28.dp))
            Surface(
                Modifier.fillMaxWidth(), shape = RoundedCornerShape(26.dp), color = Color.White,
                border = BorderStroke(1.dp, Line), shadowElevation = 5.dp
            ) {
                Column(Modifier.padding(horizontal = 20.dp, vertical = 24.dp), content = content)
            }
            Spacer(Modifier.height(24.dp))
        }
    }
}

@Composable
private fun AuthHeading(title: String, subtitle: String) {
    Text(title, fontSize = 28.sp, fontWeight = FontWeight.Black, color = Ink)
    Spacer(Modifier.height(6.dp))
    Text(subtitle, color = Muted, lineHeight = 20.sp, fontSize = 14.sp)
}

@Composable
private fun PremiumField(
    value: String,
    onValueChange: (String) -> Unit,
    label: String,
    icon: ImageVector,
    keyboardOptions: KeyboardOptions = KeyboardOptions.Default,
    keyboardActions: KeyboardActions = KeyboardActions.Default,
    password: Boolean = false
) {
    var visible by remember { mutableStateOf(false) }
    OutlinedTextField(
        value = value, onValueChange = onValueChange, modifier = Modifier.fillMaxWidth(),
        label = { Text(label) }, leadingIcon = { Icon(icon, null, tint = Navy) }, singleLine = true,
        shape = RoundedCornerShape(16.dp), keyboardOptions = keyboardOptions,
        keyboardActions = keyboardActions,
        visualTransformation = if (password && !visible) PasswordVisualTransformation() else VisualTransformation.None,
        trailingIcon = if (password) {
            {
                IconButton({ visible = !visible }) {
                    Icon(if (visible) Icons.Default.VisibilityOff else Icons.Default.Visibility,
                        if (visible) "Hide password" else "Show password")
                }
            }
        } else null,
        colors = OutlinedTextFieldDefaults.colors(
            focusedBorderColor = Navy, unfocusedBorderColor = Line,
            focusedLabelColor = Navy, cursorColor = Navy,
            focusedContainerColor = Color.White, unfocusedContainerColor = Color(0xFFFBFCFE)
        )
    )
}

@Composable
private fun RoleChoice(
    value: String,
    label: String,
    icon: ImageVector,
    selected: String,
    choose: (String) -> Unit,
    modifier: Modifier = Modifier
) {
    val active = selected == value
    Surface(
        modifier.clickable { choose(value) }, shape = RoundedCornerShape(14.dp),
        color = if (active) SoftLime else Color(0xFFF8FAFD),
        border = BorderStroke(1.dp, if (active) Lime else Line)
    ) {
        Column(Modifier.padding(vertical = 12.dp, horizontal = 5.dp), horizontalAlignment = Alignment.CenterHorizontally) {
            Icon(icon, null, tint = Navy, modifier = Modifier.size(21.dp))
            Spacer(Modifier.height(5.dp))
            Text(label, fontSize = 10.sp, fontWeight = FontWeight.Bold, maxLines = 1)
        }
    }
}

@Composable
private fun PrimaryActionButton(label: String, busy: Boolean, enabled: Boolean, action: () -> Unit) {
    Button(
        onClick = action, enabled = !busy && enabled,
        modifier = Modifier.fillMaxWidth().height(56.dp), shape = RoundedCornerShape(16.dp),
        colors = ButtonDefaults.buttonColors(containerColor = Navy, contentColor = Color.White,
            disabledContainerColor = Navy.copy(alpha = .12f), disabledContentColor = Navy.copy(alpha = .38f))
    ) {
        if (busy) CircularProgressIndicator(Modifier.size(22.dp), strokeWidth = 2.dp, color = Color.White)
        else Text(label, fontWeight = FontWeight.Bold, fontSize = 15.sp)
    }
}

@Composable
private fun SecureFootnote() {
    Row(Modifier.fillMaxWidth().padding(top = 20.dp), horizontalArrangement = Arrangement.Center,
        verticalAlignment = Alignment.CenterVertically) {
        Icon(Icons.Default.Lock, null, Modifier.size(14.dp), tint = Green)
        Spacer(Modifier.width(6.dp))
        Text("Encrypted connection · Your account stays protected", color = Muted, fontSize = 10.sp)
    }
}

@Composable
private fun TwoFactorScreen(vm: AppViewModel) {
    var code by remember { mutableStateOf("") }
    BackHandler { vm.showLogin() }
    PremiumAuthLayout {
        Surface(Modifier.size(52.dp), color = SoftLime, shape = RoundedCornerShape(16.dp)) {
            Box(contentAlignment = Alignment.Center) { Icon(Icons.Default.MarkEmailRead, null, tint = Navy) }
        }
        Spacer(Modifier.height(20.dp))
        AuthHeading("Check your email", "Enter the six-digit security code we sent to finish signing in.")
        Spacer(Modifier.height(22.dp))
        PremiumField(code, { if (it.length <= 6) code = it.filter(Char::isDigit) },
            "Six-digit code", Icons.Default.Password,
            KeyboardOptions(keyboardType = KeyboardType.NumberPassword, imeAction = ImeAction.Done),
            KeyboardActions(onDone = { if (code.length == 6) vm.verify(code) }))
        ErrorBanner(vm.error, vm::clearError)
        Spacer(Modifier.height(20.dp))
        PrimaryActionButton("Verify and continue", vm.busy, code.length == 6) { vm.verify(code) }
        TextButton(vm::showLogin, Modifier.align(Alignment.CenterHorizontally)) {
            Text("Back to sign in", color = Navy, fontWeight = FontWeight.SemiBold)
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
            if (activeChat == null) NavigationBar(containerColor = Color.White, tonalElevation = 8.dp) {
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
                RootScreen.FEED -> FeedScreen(vm.posts, vm::refreshFeed) {
                    context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse("https://taleempk.online/post-new.php")))
                }
                RootScreen.CHATS -> if (activeChat == null) ChatList(vm.conversations, vm::refreshChats, vm::openConversation)
                    else ChatThread(vm, activeChat)
                RootScreen.PROFILE -> ProfileScreen(vm.bootstrap?.user, vm::logout) { route ->
                    context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse("https://taleempk.online/$route")))
                }
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
    Surface(color = Navy, shadowElevation = 5.dp) {
        Row(Modifier.fillMaxWidth().statusBarsPadding().height(72.dp).padding(horizontal = 18.dp),
            verticalAlignment = Alignment.CenterVertically) {
            BrandMark(40); Spacer(Modifier.width(12.dp))
            Column(Modifier.weight(1f)) {
                Text("TaleemPK", color = Color.White, fontWeight = FontWeight.Black, fontSize = 19.sp)
                Text("Welcome back, ${name.substringBefore(' ')}", color = Color.White.copy(alpha = .68f), fontSize = 11.sp)
            }
            InitialAvatar(name, 38)
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
    LazyColumn(contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item {
            Surface(color = Navy, shape = RoundedCornerShape(26.dp), shadowElevation = 3.dp) {
                Column(Modifier.padding(horizontal = 22.dp, vertical = 24.dp)) {
                    Surface(color = Lime.copy(alpha = .16f), shape = RoundedCornerShape(50)) {
                        Text("YOUR LEARNING SPACE", Modifier.padding(horizontal = 10.dp, vertical = 6.dp),
                            color = Lime, fontSize = 9.sp, fontWeight = FontWeight.Black)
                    }
                    Spacer(Modifier.height(14.dp))
                    Text("Everything you need to move forward", color = Color.White,
                        fontWeight = FontWeight.Black, fontSize = 24.sp, lineHeight = 29.sp)
                    Spacer(Modifier.height(7.dp))
                    Text("Study resources, people and progress—all in one focused place.",
                        color = Color.White.copy(.72f), fontSize = 13.sp, lineHeight = 19.sp)
                    Spacer(Modifier.height(20.dp))
                    Button({ open("study.php") }, shape = RoundedCornerShape(14.dp),
                        colors = ButtonDefaults.buttonColors(containerColor = Lime, contentColor = Navy)) {
                        Icon(Icons.Default.AutoStories, null)
                        Spacer(Modifier.width(8.dp))
                        Text("Continue learning", fontWeight = FontWeight.Bold)
                    }
                }
            }
        }
        item {
            Column(Modifier.padding(top = 8.dp, bottom = 2.dp)) {
                Text("Quick access", fontSize = 20.sp, fontWeight = FontWeight.Black)
                Text("Pick up where you left off", color = Muted, fontSize = 12.sp)
            }
        }
        items(data.shortcuts) { item ->
            Surface(Modifier.fillMaxWidth().clickable { open(item.route) }, shape = RoundedCornerShape(19.dp),
                color = Color.White, border = BorderStroke(1.dp, Line)) {
                Row(Modifier.padding(horizontal = 15.dp, vertical = 14.dp), verticalAlignment = Alignment.CenterVertically) {
                    Box(Modifier.size(46.dp).clip(RoundedCornerShape(14.dp)).background(SoftLime), contentAlignment = Alignment.Center) {
                        Icon(shortcutIcon(item.icon), null, tint = Navy)
                    }
                    Spacer(Modifier.width(14.dp)); Column(Modifier.weight(1f)) {
                        Text(item.title, fontWeight = FontWeight.Bold, maxLines = 1, overflow = TextOverflow.Ellipsis)
                        Text(item.subtitle, color = Muted, fontSize = 12.sp, maxLines = 2, overflow = TextOverflow.Ellipsis)
                    }; Icon(Icons.Default.ChevronRight, null, tint = Navy.copy(alpha = .45f))
                }
            }
        }
        item { Spacer(Modifier.height(6.dp)) }
    }
}

@Composable
private fun FeedScreen(posts: List<FeedPost>, refresh: () -> Unit, ask: () -> Unit) {
    if (posts.isEmpty()) { EmptyState("Your feed is ready to refresh.", Icons.Default.DynamicFeed, refresh); return }
    LazyColumn(contentPadding = PaddingValues(14.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item {
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text("Community feed", fontSize = 22.sp, fontWeight = FontWeight.Black)
                    Text("Learn from people across Pakistan", color = Muted, fontSize = 12.sp)
                }
                IconButton(refresh) { Icon(Icons.Default.Refresh, "Refresh") }
            }
        }
        item {
            Surface(Modifier.fillMaxWidth().clickable(onClick = ask), color = Color.White,
                shape = RoundedCornerShape(18.dp), border = BorderStroke(1.dp, Line)) {
                Row(Modifier.padding(14.dp), verticalAlignment = Alignment.CenterVertically) {
                    InitialAvatar("You", 40); Spacer(Modifier.width(11.dp))
                    Text("Ask a question or share an update…", Modifier.weight(1f), color = Muted, fontSize = 13.sp)
                    Icon(Icons.Default.Edit, null, tint = Navy, modifier = Modifier.size(20.dp))
                }
            }
        }
        items(posts, key = { it.id }) { p ->
            Surface(shape = RoundedCornerShape(20.dp), color = Color.White, border = BorderStroke(1.dp, Line)) {
                Column(Modifier.padding(16.dp)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        InitialAvatar(p.author, 42); Spacer(Modifier.width(10.dp)); Column(Modifier.weight(1f)) {
                            Text(p.author, fontWeight = FontWeight.Bold); Text("@${p.username} · ${p.createdAt}", color = Color.Gray, fontSize = 12.sp)
                        }
                        if (p.solved) Surface(color = Color(0xFFE8F8F1), shape = RoundedCornerShape(50)) {
                            Row(Modifier.padding(horizontal = 9.dp, vertical = 5.dp), verticalAlignment = Alignment.CenterVertically) {
                                Icon(Icons.Default.CheckCircle, null, Modifier.size(14.dp), tint = Green)
                                Spacer(Modifier.width(4.dp)); Text("Solved", color = Green, fontSize = 10.sp, fontWeight = FontWeight.Bold)
                            }
                        }
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
    LazyColumn(contentPadding = PaddingValues(horizontal = 14.dp, vertical = 10.dp), verticalArrangement = Arrangement.spacedBy(9.dp)) {
        item { Row(Modifier.fillMaxWidth().padding(horizontal = 3.dp, vertical = 4.dp), verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text("Messages", fontSize = 22.sp, fontWeight = FontWeight.Black)
                Text("Private, secure conversations", color = Muted, fontSize = 12.sp)
            }
            IconButton(refresh) { Icon(Icons.Default.Refresh, "Refresh") }
        } }
        items(chats, key = { it.id }) { c ->
            Surface(Modifier.fillMaxWidth().clickable { open(c) }, shape = RoundedCornerShape(18.dp),
                color = Color.White, border = BorderStroke(1.dp, Line)) {
                Row(Modifier.padding(horizontal = 14.dp, vertical = 13.dp), verticalAlignment = Alignment.CenterVertically) {
                    InitialAvatar(c.title, 50); Spacer(Modifier.width(12.dp)); Column(Modifier.weight(1f)) {
                        Row { Text(c.title, Modifier.weight(1f), fontWeight = FontWeight.Bold, maxLines = 1,
                                overflow = TextOverflow.Ellipsis)
                            Text(c.lastActivity, color = Muted, fontSize = 10.sp) }
                        Spacer(Modifier.height(3.dp))
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text(c.lastMessage.ifBlank { "Start a conversation" }, Modifier.weight(1f), color = Muted,
                                fontSize = 12.sp, maxLines = 1, overflow = TextOverflow.Ellipsis)
                            if (c.unread > 0) Badge(containerColor = Lime, contentColor = Navy) { Text(c.unread.toString()) }
                        }
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
private fun ProfileScreen(user: User?, logout: () -> Unit, open: (String) -> Unit) {
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(18.dp), horizontalAlignment = Alignment.CenterHorizontally) {
        item {
            Surface(Modifier.fillMaxWidth(), shape = RoundedCornerShape(24.dp), color = Navy) {
                Column(Modifier.padding(22.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                    InitialAvatar(user?.name ?: "T", 82); Spacer(Modifier.height(12.dp))
                    Text(user?.name ?: "TaleemPK member", color = Color.White, fontSize = 23.sp, fontWeight = FontWeight.Black)
                    Text("@${user?.username.orEmpty()} · ${user?.role.orEmpty().replaceFirstChar { it.uppercase() }}",
                        color = Color.White.copy(alpha = .68f), fontSize = 12.sp)
                    if (user?.verified == true) {
                        Surface(Modifier.padding(top = 10.dp), color = Lime, contentColor = Navy, shape = RoundedCornerShape(50)) {
                            Row(Modifier.padding(horizontal = 10.dp, vertical = 6.dp), verticalAlignment = Alignment.CenterVertically) {
                                Icon(Icons.Default.Verified, null, Modifier.size(15.dp))
                                Spacer(Modifier.width(5.dp)); Text("Verified profile", fontWeight = FontWeight.Bold, fontSize = 10.sp)
                            }
                        }
                    }
                }
            }
        }
        item {
            Text("Account", Modifier.fillMaxWidth().padding(top = 22.dp, bottom = 10.dp),
                fontSize = 18.sp, fontWeight = FontWeight.Black)
        }
        item {
            Surface(Modifier.fillMaxWidth(), shape = RoundedCornerShape(20.dp), color = Color.White,
                border = BorderStroke(1.dp, Line)) { Column {
                ProfileRow(Icons.Default.Edit, "Edit profile", "Photo, bio and academic details") { open("edit-profile.php") }
                HorizontalDivider(color = Line)
                ProfileRow(Icons.Default.Security, "Privacy & security", "Password, sessions and 2-step verification") { open("settings.php") }
                HorizontalDivider(color = Line)
                ProfileRow(Icons.Default.Notifications, "Notifications", "Messages, replies and account alerts") { open("notifications.php") }
                HorizontalDivider(color = Line)
                ProfileRow(Icons.Default.Help, "Help & support", "Tickets, appeals and safety") { open("support.php") }
            } }
        }
        item {
            OutlinedButton(logout, Modifier.fillMaxWidth().padding(top = 24.dp).navigationBarsPadding(),
                shape = RoundedCornerShape(15.dp), colors = ButtonDefaults.outlinedButtonColors(contentColor = MaterialTheme.colorScheme.error),
                border = BorderStroke(1.dp, MaterialTheme.colorScheme.error.copy(alpha = .45f))) {
            Icon(Icons.Default.Logout, null); Spacer(Modifier.width(8.dp)); Text("Sign out")
            }
        }
    }
}

@Composable private fun ProfileRow(icon: ImageVector, title: String, subtitle: String, action: () -> Unit) {
    Row(Modifier.fillMaxWidth().clickable(onClick = action).padding(16.dp), verticalAlignment = Alignment.CenterVertically) {
        Box(Modifier.size(40.dp).clip(RoundedCornerShape(12.dp)).background(SoftLime), contentAlignment = Alignment.Center) {
            Icon(icon, null, tint = Navy, modifier = Modifier.size(20.dp))
        }
        Spacer(Modifier.width(13.dp)); Column(Modifier.weight(1f)) {
            Text(title, fontWeight = FontWeight.Bold)
            Text(subtitle, color = Muted, fontSize = 11.sp, maxLines = 2)
        }
        Icon(Icons.Default.ChevronRight, null, tint = Navy.copy(alpha = .4f))
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

@Composable private fun NoticeBanner(notice: String?, dismiss: () -> Unit) {
    if (notice != null) Surface(Modifier.fillMaxWidth().padding(top = 14.dp).clickable(onClick = dismiss),
        color = Color(0xFFE7F8F1), shape = RoundedCornerShape(12.dp)) {
        Row(Modifier.padding(13.dp), verticalAlignment = Alignment.Top) {
            Icon(Icons.Default.CheckCircle, null, tint = Green, modifier = Modifier.size(19.dp))
            Spacer(Modifier.width(8.dp)); Text(notice, color = Color(0xFF0D684C), fontSize = 13.sp)
        }
    }
}

private fun shortcutIcon(name: String): ImageVector = when (name) {
    "quiz" -> Icons.Default.Quiz; "library" -> Icons.Default.LocalLibrary; "chat" -> Icons.Default.ChatBubble
    "groups" -> Icons.Default.Groups; "planner" -> Icons.Default.EventNote; "results" -> Icons.Default.Assessment
    else -> Icons.Default.School
}
