package online.taleempk.studyhub.ui

import android.Manifest
import android.content.Intent
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Matrix
import android.media.MediaPlayer
import android.net.Uri
import android.os.SystemClock
import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.combinedClickable
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.detectHorizontalDragGestures
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.Image
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items as gridItems
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
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalClipboardManager
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.AnnotatedString
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
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import online.taleempk.studyhub.R
import online.taleempk.studyhub.data.*
import online.taleempk.studyhub.media.VoiceRecorder
import java.io.File
import java.io.BufferedInputStream
import java.net.HttpURLConnection
import java.net.URL
import kotlin.math.abs

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
    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
        Image(painterResource(R.drawable.auth_study_wallpaper), null, Modifier.fillMaxSize(), contentScale = ContentScale.Crop)
        Box(Modifier.fillMaxSize().background(Brush.verticalGradient(listOf(Navy.copy(.54f), Navy.copy(.88f), Navy))))
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Surface(shape = RoundedCornerShape(28.dp), color = Navy.copy(.74f), border = BorderStroke(1.dp, Color.White.copy(.18f))) {
                Box(Modifier.padding(12.dp)) { BrandMark(82) }
            }
            Spacer(Modifier.height(18.dp))
            Text("TaleemPK", color = Color.White, fontSize = 34.sp, fontWeight = FontWeight.Black)
            Text("Pakistan's learning community", color = Color.White.copy(.72f), fontWeight = FontWeight.Medium)
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
        Surface(color = SoftLime, shape = RoundedCornerShape(50)) {
            Row(Modifier.padding(horizontal = 10.dp, vertical = 6.dp), verticalAlignment = Alignment.CenterVertically) {
                Icon(Icons.Default.AutoStories, null, Modifier.size(14.dp), tint = Navy)
                Spacer(Modifier.width(6.dp)); Text("YOUR LEARNING SPACE", color = Navy, fontSize = 9.sp, fontWeight = FontWeight.Black)
            }
        }
        Spacer(Modifier.height(14.dp))
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
    Box(Modifier.fillMaxSize()) {
        Image(
            painter = painterResource(R.drawable.auth_study_wallpaper), contentDescription = null,
            modifier = Modifier.fillMaxSize(), contentScale = ContentScale.Crop
        )
        Box(Modifier.fillMaxSize().background(Brush.verticalGradient(listOf(
            Navy.copy(alpha = .58f), Navy.copy(alpha = .74f), Color(0xFF09152B).copy(alpha = .94f)
        ))))
        Column(
            Modifier.fillMaxSize().verticalScroll(rememberScrollState()).statusBarsPadding()
                .navigationBarsPadding().padding(horizontal = 18.dp, vertical = 22.dp)
        ) {
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                BrandMark(48)
                Spacer(Modifier.width(12.dp))
                Column(Modifier.weight(1f)) {
                    Text("TaleemPK", fontSize = 25.sp, fontWeight = FontWeight.Black, color = Color.White)
                    Text("Learn · Connect · Grow", color = Color.White.copy(.68f), fontSize = 11.sp)
                }
                Surface(color = Lime, shape = RoundedCornerShape(50), contentColor = Navy) {
                    Text("PRIVATE & SECURE", Modifier.padding(horizontal = 10.dp, vertical = 6.dp),
                        fontSize = 9.sp, fontWeight = FontWeight.Black)
                }
            }
            Spacer(Modifier.height(24.dp))
            Surface(
                Modifier.fillMaxWidth(), shape = RoundedCornerShape(30.dp), color = Color.White.copy(alpha = .965f),
                border = BorderStroke(1.dp, Color.White.copy(.7f)), shadowElevation = 14.dp
            ) {
                Column(Modifier.padding(horizontal = 20.dp, vertical = 25.dp), content = content)
            }
            Row(Modifier.fillMaxWidth().padding(top = 18.dp), horizontalArrangement = Arrangement.SpaceEvenly) {
                AuthBenefit(Icons.Default.VerifiedUser, "Protected")
                AuthBenefit(Icons.Default.Groups, "Community")
                AuthBenefit(Icons.Default.School, "Learning")
            }
            Spacer(Modifier.height(18.dp))
        }
    }
}

@Composable
private fun AuthBenefit(icon: ImageVector, label: String) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        Icon(icon, null, Modifier.size(15.dp), tint = Lime)
        Spacer(Modifier.width(5.dp)); Text(label, color = Color.White.copy(.78f), fontSize = 10.sp, fontWeight = FontWeight.SemiBold)
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
    val activeChat = vm.selectedConversation
    val activeModule = vm.activeModule
    var chatSearch by remember(activeChat?.id) { mutableStateOf(false) }
    BackHandler(enabled = activeChat != null || activeModule != null) {
        if (activeChat != null) vm.closeConversation() else vm.closeModule()
    }
    Scaffold(
        containerColor = Mist,
        topBar = {
            when {
                activeChat != null -> ChatTopBar(activeChat, vm::closeConversation, { chatSearch = !chatSearch }, vm::toggleMute)
                activeModule != null -> NativeModuleTopBar(activeModule.title, vm::closeModule, vm::refreshModule)
                else -> AppTopBar(vm.bootstrap?.user?.name ?: "TaleemPK")
            }
        },
        bottomBar = {
            if (activeChat == null && activeModule == null) Surface(color = Mist) {
                NavigationBar(
                    Modifier.padding(horizontal = 10.dp, vertical = 7.dp).clip(RoundedCornerShape(24.dp)),
                    containerColor = Color.White, tonalElevation = 10.dp
                ) {
                    NavItem("Home", Icons.Default.Home, RootScreen.HOME, vm)
                    NavItem("Feed", Icons.Default.DynamicFeed, RootScreen.FEED, vm)
                    NavItem("Chat", Icons.Default.ChatBubble, RootScreen.CHATS, vm)
                    NavItem("Profile", Icons.Default.Person, RootScreen.PROFILE, vm)
                }
            }
        }
    ) { pad ->
        Box(Modifier.fillMaxSize().padding(pad)) {
            if (activeModule != null) NativeModuleScreen(
                activeModule, vm::moduleItemAction, vm::updateProfile, vm::createTicket
            )
            else when (vm.screen) {
                RootScreen.HOME -> HomeScreen(vm.bootstrap, vm::refreshHome, vm::openNativeRoute)
                RootScreen.FEED -> FeedScreen(
                    vm.posts, vm.commentPost, vm.feedComments, vm::refreshFeed, vm::createPost,
                    vm::togglePostLike, vm::openComments, vm::closeComments, vm::addComment
                )
                RootScreen.CHATS -> if (activeChat == null) ChatList(vm.conversations, vm::refreshChats, vm::openConversation) else ChatThread(vm, activeChat, chatSearch)
                RootScreen.PROFILE -> ProfileScreen(vm.bootstrap?.user, vm::logout, vm::openNativeRoute)
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
    Surface(color = Navy, shadowElevation = 7.dp) {
        Row(Modifier.fillMaxWidth().statusBarsPadding().height(72.dp).padding(horizontal = 18.dp),
            verticalAlignment = Alignment.CenterVertically) {
            Surface(color = Color.White.copy(.08f), shape = RoundedCornerShape(14.dp), border = BorderStroke(1.dp, Color.White.copy(.12f))) {
                Box(Modifier.padding(4.dp)) { BrandMark(38) }
            }
            Spacer(Modifier.width(12.dp))
            Column(Modifier.weight(1f)) {
                Text("TaleemPK", color = Color.White, fontWeight = FontWeight.Black, fontSize = 19.sp)
                Text("Welcome back, ${name.substringBefore(' ')}", color = Color.White.copy(alpha = .68f), fontSize = 11.sp)
            }
            Surface(color = Lime.copy(.13f), shape = CircleShape, border = BorderStroke(1.dp, Lime.copy(.45f))) {
                Box(Modifier.padding(3.dp)) { InitialAvatar(name, 36) }
            }
        }
    }
}

@Composable
private fun NativeModuleTopBar(title: String, back: () -> Unit, refresh: () -> Unit) {
    Surface(color = Navy, shadowElevation = 5.dp) {
        Row(Modifier.fillMaxWidth().statusBarsPadding().height(68.dp).padding(end = 6.dp), verticalAlignment = Alignment.CenterVertically) {
            IconButton(back) { Icon(Icons.Default.ArrowBack, "Back", tint = Color.White) }
            Text(title, Modifier.weight(1f), color = Color.White, fontWeight = FontWeight.Bold, fontSize = 18.sp,
                maxLines = 1, overflow = TextOverflow.Ellipsis)
            IconButton(refresh) { Icon(Icons.Default.Refresh, "Refresh", tint = Color.White) }
        }
    }
}

@Composable
private fun NativeModuleScreen(
    content: ModuleContent,
    itemAction: (ModuleItem) -> Unit,
    updateProfile: (String, String, String, String, () -> Unit) -> Unit,
    createTicket: (String, String, String, () -> Unit) -> Unit
) {
    var profileEditor by remember(content.key) { mutableStateOf(false) }
    var supportComposer by remember(content.key) { mutableStateOf(false) }
    val actionable: (ModuleItem) -> Boolean = {
        it.kind == "task" || it.kind == "notification" || (it.kind == "setting" && it.id in 2L..3L)
    }
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(14.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        item {
            Surface(Modifier.fillMaxWidth(), color = Navy, shape = RoundedCornerShape(24.dp)) {
                Row(Modifier.padding(20.dp), verticalAlignment = Alignment.CenterVertically) {
                    Surface(Modifier.size(52.dp), color = Lime, shape = RoundedCornerShape(16.dp)) {
                        Box(contentAlignment = Alignment.Center) { Icon(moduleIcon(content.key), null, tint = Navy) }
                    }
                    Spacer(Modifier.width(14.dp)); Column {
                        Text(content.title, color = Color.White, fontSize = 21.sp, fontWeight = FontWeight.Black)
                        Text(content.subtitle, color = Color.White.copy(.67f), fontSize = 12.sp, lineHeight = 17.sp)
                    }
                }
            }
        }
        if (content.key == "profile" || content.key == "support") item {
            Button(
                onClick = { if (content.key == "profile") profileEditor = true else supportComposer = true },
                modifier = Modifier.fillMaxWidth().height(52.dp),
                shape = RoundedCornerShape(16.dp),
                colors = ButtonDefaults.buttonColors(containerColor = Lime, contentColor = Navy)
            ) {
                Icon(if (content.key == "profile") Icons.Default.Edit else Icons.Default.AddComment, null)
                Spacer(Modifier.width(8.dp))
                Text(if (content.key == "profile") "Edit profile in app" else "New support request", fontWeight = FontWeight.Bold)
            }
        }
        if (content.items.isEmpty()) item {
            Surface(Modifier.fillMaxWidth(), color = Color.White, shape = RoundedCornerShape(20.dp), border = BorderStroke(1.dp, Line)) {
                Column(Modifier.padding(28.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                    Icon(Icons.Default.Inbox, null, Modifier.size(42.dp), tint = Navy.copy(.35f))
                    Spacer(Modifier.height(10.dp)); Text("Nothing here yet", fontWeight = FontWeight.Bold)
                    Text("New items will appear here automatically.", color = Muted, fontSize = 12.sp)
                }
            }
        }
        items(content.items, key = { "${it.kind}-${it.id}" }) { item ->
            Surface(
                modifier = Modifier.fillMaxWidth().clickable(enabled = actionable(item)) { itemAction(item) },
                color = Color.White, shape = RoundedCornerShape(18.dp), border = BorderStroke(1.dp, Line)
            ) {
                Row(Modifier.padding(15.dp), verticalAlignment = Alignment.CenterVertically) {
                    Surface(Modifier.size(44.dp), color = if (item.done) SoftLime else Mist, shape = RoundedCornerShape(13.dp)) {
                        Box(contentAlignment = Alignment.Center) { Icon(
                            if (item.kind == "task") (if (item.done) Icons.Default.CheckCircle else Icons.Default.RadioButtonUnchecked)
                            else moduleItemIcon(item.kind), null, tint = if (item.done) Green else Navy
                        ) }
                    }
                    Spacer(Modifier.width(12.dp)); Column(Modifier.weight(1f)) {
                        Text(item.title, fontWeight = FontWeight.Bold, color = if (item.done) Muted else Ink,
                            maxLines = 2, overflow = TextOverflow.Ellipsis)
                        if (item.subtitle.isNotBlank()) Text(item.subtitle, color = Muted, fontSize = 11.sp,
                            maxLines = 2, overflow = TextOverflow.Ellipsis)
                        if (item.meta.isNotBlank()) Text(item.meta, color = Green, fontSize = 10.sp,
                            fontWeight = FontWeight.SemiBold, modifier = Modifier.padding(top = 4.dp))
                    }
                    if (actionable(item)) Icon(Icons.Default.ChevronRight, null, tint = Navy.copy(.35f))
                }
            }
        }
        item { Spacer(Modifier.height(8.dp)) }
    }

    if (profileEditor) {
        val identity = content.items.firstOrNull { it.id == 1L }
        val location = content.items.firstOrNull { it.id == 2L }
        val about = content.items.firstOrNull { it.id == 3L }
        var name by remember { mutableStateOf(identity?.title.orEmpty()) }
        var city by remember { mutableStateOf(location?.subtitle?.takeUnless { it == "Not added" }.orEmpty()) }
        var headline by remember { mutableStateOf(identity?.meta.orEmpty()) }
        var bio by remember { mutableStateOf(about?.subtitle?.takeUnless { it == "Add a short introduction" }.orEmpty()) }
        AlertDialog(
            onDismissRequest = { profileEditor = false },
            icon = { Icon(Icons.Default.Badge, null, tint = Navy) },
            title = { Text("Edit your profile", fontWeight = FontWeight.Black) },
            text = { Column(Modifier.verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(9.dp)) {
                OutlinedTextField(name, { if (it.length <= 120) name = it }, label = { Text("Full name") }, singleLine = true)
                OutlinedTextField(headline, { if (it.length <= 160) headline = it }, label = { Text("Headline") }, singleLine = true)
                OutlinedTextField(city, { if (it.length <= 80) city = it }, label = { Text("City") }, singleLine = true)
                OutlinedTextField(bio, { if (it.length <= 480) bio = it }, label = { Text("About you") }, minLines = 3, maxLines = 6)
            } },
            confirmButton = { Button({ updateProfile(name, city, headline, bio) { profileEditor = false } },
                enabled = name.trim().length >= 3, colors = ButtonDefaults.buttonColors(containerColor = Navy)) { Text("Save") } },
            dismissButton = { TextButton({ profileEditor = false }) { Text("Cancel") } }
        )
    }

    if (supportComposer) {
        var topic by remember { mutableStateOf("bug") }
        var subject by remember { mutableStateOf("") }
        var body by remember { mutableStateOf("") }
        AlertDialog(
            onDismissRequest = { supportComposer = false },
            icon = { Icon(Icons.Default.SupportAgent, null, tint = Navy) },
            title = { Text("Contact TaleemPK support", fontWeight = FontWeight.Black) },
            text = { Column(verticalArrangement = Arrangement.spacedBy(9.dp)) {
                Row(horizontalArrangement = Arrangement.spacedBy(7.dp)) {
                    FilterChip(topic == "bug", { topic = "bug" }, { Text("Bug") })
                    FilterChip(topic == "access", { topic = "access" }, { Text("Access") })
                    FilterChip(topic == "other", { topic = "other" }, { Text("Other") })
                }
                OutlinedTextField(subject, { if (it.length <= 180) subject = it }, label = { Text("Subject") }, singleLine = true)
                OutlinedTextField(body, { if (it.length <= 5000) body = it }, label = { Text("Describe the issue") }, minLines = 4, maxLines = 8)
            } },
            confirmButton = { Button({ createTicket(topic, subject, body) { supportComposer = false } },
                enabled = subject.trim().length >= 5 && body.trim().length >= 10,
                colors = ButtonDefaults.buttonColors(containerColor = Navy)) { Text("Send") } },
            dismissButton = { TextButton({ supportComposer = false }) { Text("Cancel") } }
        )
    }
}

private fun moduleIcon(key: String): ImageVector = when (key) {
    "library" -> Icons.Default.LocalLibrary; "quizzes" -> Icons.Default.Quiz; "groups" -> Icons.Default.Groups
    "planner" -> Icons.Default.EventNote; "results" -> Icons.Default.Assessment; "notifications" -> Icons.Default.Notifications
    "support" -> Icons.Default.SupportAgent; "profile" -> Icons.Default.Badge; "settings" -> Icons.Default.Security
    else -> Icons.Default.AutoStories
}

private fun moduleItemIcon(kind: String): ImageVector = when (kind) {
    "resource" -> Icons.Default.Description; "quiz" -> Icons.Default.Quiz; "group" -> Icons.Default.Groups
    "board" -> Icons.Default.School; "notification" -> Icons.Default.Notifications; "ticket" -> Icons.Default.SupportAgent
    "setting" -> Icons.Default.Security; "profile" -> Icons.Default.Person; else -> Icons.Default.AutoStories
}

@Composable
private fun ChatTopBar(c: Conversation, back: () -> Unit, search: () -> Unit, mute: () -> Unit) {
    var menu by remember { mutableStateOf(false) }
    Surface(color = Navy, shadowElevation = 5.dp) {
        Row(Modifier.fillMaxWidth().statusBarsPadding().height(72.dp).padding(end = 6.dp), verticalAlignment = Alignment.CenterVertically) {
            IconButton(back) { Icon(Icons.Default.ArrowBack, "Back", tint = Color.White) }
            Box {
                InitialAvatar(c.title, 43)
                if (c.online) Box(Modifier.size(12.dp).align(Alignment.BottomEnd).clip(CircleShape)
                    .background(Color.White).padding(2.dp).clip(CircleShape).background(Lime))
            }
            Spacer(Modifier.width(11.dp))
            Column(Modifier.weight(1f)) {
                Text(c.title, color = Color.White, fontWeight = FontWeight.Bold, maxLines = 1, overflow = TextOverflow.Ellipsis)
                Text(c.statusText.ifBlank { if (c.group) "Study group" else "Private conversation" },
                    color = if (c.online) Lime else Color.White.copy(.64f), fontSize = 11.sp, maxLines = 1)
            }
            IconButton(search) { Icon(Icons.Default.Search, "Search messages", tint = Color.White) }
            Box {
                IconButton({ menu = true }) { Icon(Icons.Default.MoreVert, "Chat options", tint = Color.White) }
                DropdownMenu(menu, { menu = false }) {
                    DropdownMenuItem(
                        text = { Text(if (c.muted) "Turn notifications on" else "Mute notifications") },
                        leadingIcon = { Icon(if (c.muted) Icons.Default.NotificationsActive else Icons.Default.NotificationsOff, null) },
                        onClick = { menu = false; mute() }
                    )
                    DropdownMenuItem(text = { Text("Chat safety & details") },
                        leadingIcon = { Icon(Icons.Default.Security, null) }, onClick = { menu = false })
                }
            }
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
private fun FeedScreen(
    posts: List<FeedPost>,
    commentPost: FeedPost?,
    comments: List<FeedComment>,
    refresh: () -> Unit,
    create: (String, Boolean, () -> Unit) -> Unit,
    like: (FeedPost) -> Unit,
    openComments: (FeedPost) -> Unit,
    closeComments: () -> Unit,
    addComment: (String, () -> Unit) -> Unit
) {
    var composer by remember { mutableStateOf(false) }
    var draft by remember { mutableStateOf("") }
    var question by remember { mutableStateOf(true) }
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
            Surface(Modifier.fillMaxWidth().clickable { composer = true }, color = Color.White,
                shape = RoundedCornerShape(18.dp), border = BorderStroke(1.dp, Line)) {
                Row(Modifier.padding(14.dp), verticalAlignment = Alignment.CenterVertically) {
                    InitialAvatar("You", 40); Spacer(Modifier.width(11.dp))
                    Text("Ask a question or share an update…", Modifier.weight(1f), color = Muted, fontSize = 13.sp)
                    Icon(Icons.Default.Edit, null, tint = Navy, modifier = Modifier.size(20.dp))
                }
            }
        }
        if (posts.isEmpty()) item {
            Surface(Modifier.fillMaxWidth(), color = Color.White, shape = RoundedCornerShape(18.dp), border = BorderStroke(1.dp, Line)) {
                Column(Modifier.padding(24.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                    Icon(Icons.Default.DynamicFeed, null, Modifier.size(38.dp), tint = Navy.copy(.35f))
                    Spacer(Modifier.height(8.dp)); Text("Your feed is ready", fontWeight = FontWeight.Bold)
                    Text("Refresh or start the first conversation.", color = Muted, fontSize = 12.sp)
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
                    Spacer(Modifier.height(12.dp)); HorizontalDivider(color = Mist); Spacer(Modifier.height(5.dp))
                    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                        Row(Modifier.weight(1f).clip(RoundedCornerShape(12.dp)).clickable { like(p) }.padding(9.dp),
                            horizontalArrangement = Arrangement.Center, verticalAlignment = Alignment.CenterVertically) {
                            Icon(if (p.liked) Icons.Default.ThumbUp else Icons.Default.ThumbUpOffAlt, null,
                                Modifier.size(18.dp), tint = if (p.liked) Green else Muted)
                            Spacer(Modifier.width(6.dp)); Text("Helpful · ${p.likes}", color = if (p.liked) Green else Muted,
                                fontSize = 12.sp, fontWeight = if (p.liked) FontWeight.Bold else FontWeight.Medium)
                        }
                        Spacer(Modifier.width(6.dp))
                        Row(Modifier.weight(1f).clip(RoundedCornerShape(12.dp)).clickable { openComments(p) }.padding(9.dp),
                            horizontalArrangement = Arrangement.Center, verticalAlignment = Alignment.CenterVertically) {
                            Icon(Icons.Default.ChatBubbleOutline, null, Modifier.size(18.dp), tint = Muted)
                            Spacer(Modifier.width(6.dp)); Text("Replies · ${p.comments}", color = Muted, fontSize = 12.sp, fontWeight = FontWeight.Medium)
                        }
                    }
                }
            }
        }
    }
    if (composer) AlertDialog(
        onDismissRequest = { composer = false },
        icon = { Surface(Modifier.size(44.dp), color = SoftLime, shape = CircleShape) { Box(contentAlignment = Alignment.Center) { Icon(Icons.Default.Edit, null, tint = Navy) } } },
        title = { Text(if (question) "Ask the community" else "Share an update", fontWeight = FontWeight.Black) },
        text = { Column {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                FilterChip(question, { question = true }, { Text("Question") }, leadingIcon = { Icon(Icons.Default.HelpOutline, null) })
                FilterChip(!question, { question = false }, { Text("Update") }, leadingIcon = { Icon(Icons.Default.Campaign, null) })
            }
            Spacer(Modifier.height(8.dp))
            OutlinedTextField(draft, { if (it.length <= 8000) draft = it }, Modifier.fillMaxWidth(),
                placeholder = { Text(if (question) "What would you like help with?" else "Share something useful…") },
                minLines = 4, maxLines = 8, shape = RoundedCornerShape(16.dp))
        } },
        confirmButton = { Button({ create(draft, question) { draft = ""; composer = false } }, enabled = draft.isNotBlank(),
            colors = ButtonDefaults.buttonColors(containerColor = Navy)) { Text("Publish") } },
        dismissButton = { TextButton({ composer = false }) { Text("Cancel") } }
    )
    commentPost?.let { post ->
        var reply by remember(post.id) { mutableStateOf("") }
        AlertDialog(
            onDismissRequest = closeComments,
            icon = { Icon(Icons.Default.Forum, null, tint = Navy) },
            title = { Column {
                Text("Community replies", fontWeight = FontWeight.Black)
                Text("${post.author}'s ${if (post.type == "question") "question" else "post"}", color = Muted, fontSize = 11.sp)
            } },
            text = { Column {
                if (comments.isEmpty()) Text("No replies yet. Be the first to help.", color = Muted, modifier = Modifier.padding(vertical = 12.dp))
                else LazyColumn(Modifier.heightIn(max = 300.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    items(comments, key = { it.id }) { c ->
                        Surface(color = Mist, shape = RoundedCornerShape(14.dp)) {
                            Column(Modifier.fillMaxWidth().padding(11.dp)) {
                                Row { Text(c.author, Modifier.weight(1f), fontWeight = FontWeight.Bold, fontSize = 12.sp)
                                    Text(c.createdAt, color = Muted, fontSize = 9.sp) }
                                Spacer(Modifier.height(3.dp)); Text(c.content, fontSize = 13.sp, lineHeight = 18.sp)
                            }
                        }
                    }
                }
                Spacer(Modifier.height(10.dp))
                OutlinedTextField(reply, { if (it.length <= 5000) reply = it }, Modifier.fillMaxWidth(),
                    placeholder = { Text("Write a thoughtful reply…") }, minLines = 2, maxLines = 5,
                    shape = RoundedCornerShape(15.dp))
            } },
            confirmButton = { Button({ addComment(reply) { reply = "" } }, enabled = reply.isNotBlank(),
                colors = ButtonDefaults.buttonColors(containerColor = Navy)) { Text("Reply") } },
            dismissButton = { TextButton(closeComments) { Text("Close") } }
        )
    }
}

@Composable
private fun ChatList(chats: List<Conversation>, refresh: () -> Unit, open: (Conversation) -> Unit) {
    var query by remember { mutableStateOf("") }
    val filtered = remember(chats, query) { if (query.isBlank()) chats else chats.filter {
        it.title.contains(query, true) || it.lastMessage.contains(query, true)
    } }
    if (chats.isEmpty()) { EmptyState("No conversations yet—or tap refresh.", Icons.Default.ChatBubble, refresh); return }
    LazyColumn(contentPadding = PaddingValues(horizontal = 14.dp, vertical = 10.dp), verticalArrangement = Arrangement.spacedBy(9.dp)) {
        item { Row(Modifier.fillMaxWidth().padding(horizontal = 3.dp, vertical = 4.dp), verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text("Messages", fontSize = 22.sp, fontWeight = FontWeight.Black)
                Text("Private, secure conversations", color = Muted, fontSize = 12.sp)
            }
            IconButton(refresh) { Icon(Icons.Default.Refresh, "Refresh") }
        } }
        item {
            TextField(query, { query = it.take(80) }, Modifier.fillMaxWidth(), placeholder = { Text("Search conversations") },
                leadingIcon = { Icon(Icons.Default.Search, null) }, singleLine = true, shape = RoundedCornerShape(17.dp),
                colors = TextFieldDefaults.colors(focusedContainerColor = Color.White, unfocusedContainerColor = Color.White,
                    focusedIndicatorColor = Color.Transparent, unfocusedIndicatorColor = Color.Transparent))
        }
        items(filtered, key = { it.id }) { c ->
            Surface(Modifier.fillMaxWidth().clickable { open(c) }, shape = RoundedCornerShape(18.dp),
                color = Color.White, border = BorderStroke(1.dp, Line)) {
                Row(Modifier.padding(horizontal = 14.dp, vertical = 13.dp), verticalAlignment = Alignment.CenterVertically) {
                    Box { InitialAvatar(c.title, 50)
                        if (c.online) Box(Modifier.size(13.dp).align(Alignment.BottomEnd).clip(CircleShape)
                            .background(Color.White).padding(2.dp).clip(CircleShape).background(Green))
                    }
                    Spacer(Modifier.width(12.dp)); Column(Modifier.weight(1f)) {
                        Row { Text(c.title, Modifier.weight(1f), fontWeight = FontWeight.Bold, maxLines = 1,
                                overflow = TextOverflow.Ellipsis)
                            Text(c.lastActivity, color = Muted, fontSize = 10.sp) }
                        Spacer(Modifier.height(3.dp))
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text(c.lastMessage.ifBlank { "Start a conversation" }, Modifier.weight(1f), color = Muted,
                                fontSize = 12.sp, maxLines = 1, overflow = TextOverflow.Ellipsis)
                            if (c.muted) Icon(Icons.Default.NotificationsOff, "Muted", Modifier.size(14.dp), tint = Muted)
                            if (c.unread > 0) Badge(containerColor = Lime, contentColor = Navy) { Text(c.unread.toString()) }
                        }
                    }
                }
            }
        }
        if (filtered.isEmpty()) item { Text("No matching conversations", Modifier.fillMaxWidth().padding(28.dp), textAlign = TextAlign.Center, color = Muted) }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun ChatThread(vm: AppViewModel, chat: Conversation, searchOpen: Boolean) {
    val context = LocalContext.current
    val recorder = remember { VoiceRecorder(context) }
    val listState = rememberLazyListState()
    var recording by remember { mutableStateOf(false) }
    var recordingStart by remember { mutableLongStateOf(0L) }
    var elapsed by remember { mutableIntStateOf(0) }
    var liveWave by remember { mutableStateOf<List<Int>>(emptyList()) }
    var preview by remember { mutableStateOf<VoiceClip?>(null) }
    var imageToEdit by remember { mutableStateOf<Uri?>(null) }
    var forwarding by remember { mutableStateOf<ChatMessage?>(null) }
    var text by remember { mutableStateOf("") }
    var query by remember { mutableStateOf("") }
    var emojiOpen by remember { mutableStateOf(false) }
    var selected by remember { mutableStateOf<ChatMessage?>(null) }
    var replyTo by remember { mutableStateOf<ChatMessage?>(null) }
    var editing by remember { mutableStateOf<ChatMessage?>(null) }
    var deleteForEveryone by remember { mutableStateOf<ChatMessage?>(null) }
    var didInitialScroll by remember(chat.id) { mutableStateOf(false) }

    val shown = remember(vm.messages, query) {
        if (query.length < 2) vm.messages else vm.messages.filter {
            it.content.contains(query, true) || it.sender.contains(query, true) ||
                (it.attachmentName?.contains(query, true) == true)
        }
    }
    DisposableEffect(Unit) { onDispose { recorder.cancel(); preview?.let { File(it.filePath).delete() } } }
    LaunchedEffect(chat.id) {
        while (true) {
            vm.refreshMessages()
            delay(if (vm.remotePresence.active) 2_200 else 4_000)
        }
    }
    LaunchedEffect(chat.id) {
        while (true) {
            val kind = if (recording) "voice" else if (text.isNotBlank()) "text" else ""
            vm.syncPresence(kind)
            delay(if (kind.isNotEmpty()) 2_500 else 4_500)
        }
    }
    LaunchedEffect(shown.size) {
        if (shown.isNotEmpty()) {
            if (!didInitialScroll) { listState.scrollToItem(shown.lastIndex); didInitialScroll = true }
            else if (listState.firstVisibleItemIndex >= (shown.lastIndex - 6).coerceAtLeast(0)) {
                listState.animateScrollToItem(shown.lastIndex)
            }
        }
    }
    LaunchedEffect(recording) {
        while (recording) {
            elapsed = ((SystemClock.elapsedRealtime() - recordingStart) / 1000L).toInt()
            val level = (recorder.amplitude() / 650).coerceIn(2, 42)
            liveWave = (liveWave + level).takeLast(44)
            if (elapsed >= 120) {
                try { preview = recorder.stop() } catch (_: Exception) { recorder.cancel() }
                recording = false
            }
            delay(250)
        }
    }
    val micPermission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { allowed ->
        if (allowed) try {
            recorder.start(); recordingStart = SystemClock.elapsedRealtime(); elapsed = 0; liveWave = emptyList(); recording = true
        } catch (_: Exception) { }
    }
    val imagePicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri -> imageToEdit = uri }
    val filePicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri -> uri?.let(vm::sendAttachment) }

    val pinned = remember(shown) { shown.lastOrNull { it.pinned && !it.deleted } }
    Column(Modifier.fillMaxSize().background(Brush.verticalGradient(listOf(Color(0xFFF8FAFF), Color(0xFFF1F4FA))))) {
        if (searchOpen) {
            Surface(color = Color.White, shadowElevation = 1.dp) {
                OutlinedTextField(query, { query = it.take(100) }, Modifier.fillMaxWidth().padding(10.dp),
                    placeholder = { Text("Search this conversation") }, leadingIcon = { Icon(Icons.Default.Search, null) },
                    trailingIcon = { if (query.isNotEmpty()) IconButton({ query = "" }) { Icon(Icons.Default.Close, "Clear") } },
                    singleLine = true, shape = RoundedCornerShape(16.dp))
            }
        }
        ChatSecurityBanner()
        pinned?.let { PinnedMessageBar(it) { replyTo = it; editing = null } }
        LazyColumn(
            Modifier.weight(1f), state = listState,
            contentPadding = PaddingValues(horizontal = 12.dp, vertical = 14.dp),
            verticalArrangement = Arrangement.spacedBy(5.dp)
        ) {
            itemsIndexed(shown, key = { _, item -> item.id }) { index, message ->
                if (index == 0 || shown[index - 1].dateLabel != message.dateLabel) DatePill(message.dateLabel)
                MessageBubble(message, vm.authHeaders(), onLongPress = { selected = message },
                    onReaction = { vm.react(message, it) }, onAttachment = { vm.openAttachment(message) },
                    onReply = { replyTo = message; editing = null }, onForward = { forwarding = message },
                    showSender = !message.mine && (index == 0 || shown[index - 1].senderId != message.senderId ||
                        shown[index - 1].dateLabel != message.dateLabel))
            }
            if (vm.remotePresence.active) item(key = "typing") {
                RemotePresenceBubble(vm.remotePresence)
            }
            if (shown.isEmpty()) item {
                Box(Modifier.fillParentMaxSize(), contentAlignment = Alignment.Center) {
                    Text(if (query.isBlank()) "No messages yet. Say hello 👋" else "No matching messages", color = Muted)
                }
            }
        }
        vm.uploadProgress?.let { progress -> UploadProgressBar(vm.uploadLabel, progress) }
        when {
            preview != null -> VoicePreview(preview!!, onDelete = {
                File(preview!!.filePath).delete(); preview = null
            }, onSend = { val clip = preview!!; vm.sendVoice(clip) { preview = null } })
            recording -> RecordingBar(elapsed, liveWave, onCancel = { recorder.cancel(); recording = false }, onStop = {
                try { preview = recorder.stop() } catch (_: Exception) { }; recording = false
            })
            else -> PremiumComposer(
                text = text, onText = { if (it.length <= 4000) text = it },
                emojiOpen = emojiOpen, toggleEmoji = { emojiOpen = !emojiOpen },
                reply = replyTo, editing = editing,
                cancelContext = { replyTo = null; editing = null; text = "" },
                attachPhoto = { imagePicker.launch(arrayOf("image/*")) },
                attachFile = { filePicker.launch(arrayOf("application/pdf", "text/plain", "application/msword",
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "application/zip")) },
                send = {
                    val edit = editing
                    if (text.isNotBlank() && edit != null) vm.editMessage(edit, text) { text = ""; editing = null }
                    else if (text.isNotBlank()) vm.sendText(text, replyTo?.id) { text = ""; replyTo = null; emojiOpen = false }
                    else micPermission.launch(Manifest.permission.RECORD_AUDIO)
                }
            )
        }
    }

    imageToEdit?.let { uri -> ImageEditorDialog(uri, close = { imageToEdit = null }) { rotation, square, caption ->
        imageToEdit = null
        vm.sendEditedImage(uri, rotation, square, caption) { }
    } }

    forwarding?.let { message -> ForwardMessageDialog(message, chat, vm.conversations,
        close = { forwarding = null }, send = { target -> vm.forwardMessage(message, target) { forwarding = null } }) }

    selected?.let { message ->
        MessageActionsSheet(message, close = { selected = null }, reply = {
            replyTo = message; editing = null; selected = null
        }, edit = {
            editing = message; replyTo = null; text = message.content; selected = null
        }, star = { vm.toggleStar(message); selected = null }, pin = { vm.togglePin(message); selected = null },
            forward = { forwarding = message; selected = null },
            deleteMe = { vm.deleteMessage(message, false); selected = null }, deleteAll = {
                deleteForEveryone = message; selected = null
            }, react = { vm.react(message, it); selected = null })
    }
    deleteForEveryone?.let { message ->
        AlertDialog(onDismissRequest = { deleteForEveryone = null }, icon = { Icon(Icons.Default.DeleteForever, null) },
            title = { Text("Delete for everyone?") },
            text = { Text("The message will be replaced by a deleted-message notice for everyone in this conversation.") },
            confirmButton = { TextButton({ vm.deleteMessage(message, true); deleteForEveryone = null }) { Text("Delete", color = MaterialTheme.colorScheme.error) } },
            dismissButton = { TextButton({ deleteForEveryone = null }) { Text("Cancel") } })
    }
}

@Composable
private fun ChatSecurityBanner() {
    Row(
        Modifier.fillMaxWidth().background(Color(0xFFE8F7F2)).padding(horizontal = 14.dp, vertical = 7.dp),
        horizontalArrangement = Arrangement.Center, verticalAlignment = Alignment.CenterVertically
    ) {
        Icon(Icons.Default.Lock, null, Modifier.size(13.dp), tint = Green)
        Spacer(Modifier.width(6.dp))
        Text("Private conversation · Protected in transit", color = Green, fontSize = 10.sp, fontWeight = FontWeight.SemiBold)
        Spacer(Modifier.width(5.dp)); Icon(Icons.Default.VerifiedUser, null, Modifier.size(13.dp), tint = Green)
    }
}

@Composable
private fun PinnedMessageBar(message: ChatMessage, open: () -> Unit) {
    Surface(Modifier.fillMaxWidth().clickable(onClick = open), color = Color.White, shadowElevation = 1.dp) {
        Row(Modifier.padding(horizontal = 13.dp, vertical = 8.dp), verticalAlignment = Alignment.CenterVertically) {
            Surface(Modifier.size(31.dp), color = SoftLime, shape = RoundedCornerShape(9.dp)) {
                Box(contentAlignment = Alignment.Center) { Icon(Icons.Default.PushPin, null, Modifier.size(16.dp), tint = Navy) }
            }
            Spacer(Modifier.width(9.dp)); Column(Modifier.weight(1f)) {
                Text("Pinned message", color = Green, fontSize = 9.sp, fontWeight = FontWeight.Black)
                Text(message.content.ifBlank { message.attachmentName ?: "Voice message" }, color = Ink,
                    fontSize = 11.sp, maxLines = 1, overflow = TextOverflow.Ellipsis)
            }
            Icon(Icons.Default.ChevronRight, null, Modifier.size(18.dp), tint = Muted)
        }
    }
}

@Composable
private fun DatePill(label: String) {
    Row(Modifier.fillMaxWidth().padding(vertical = 9.dp), horizontalArrangement = Arrangement.Center) {
        Surface(color = Color.White.copy(.95f), shape = RoundedCornerShape(50), border = BorderStroke(1.dp, Line)) {
            Text(label.uppercase(), Modifier.padding(horizontal = 12.dp, vertical = 5.dp), color = Muted,
                fontSize = 9.sp, fontWeight = FontWeight.Bold)
        }
    }
}

@Composable
private fun RemotePresenceBubble(presence: ChatPresence) {
    Row(Modifier.fillMaxWidth().padding(top = 3.dp), horizontalArrangement = Arrangement.Start) {
        Surface(color = Color.White, shape = RoundedCornerShape(6.dp, 18.dp, 18.dp, 18.dp),
            border = BorderStroke(1.dp, Line)) {
            Row(Modifier.padding(horizontal = 12.dp, vertical = 9.dp), verticalAlignment = Alignment.CenterVertically) {
                if (presence.kind == "voice") {
                    Icon(Icons.Default.Mic, null, Modifier.size(15.dp), tint = Green)
                    Spacer(Modifier.width(7.dp)); repeat(4) { i ->
                        Box(Modifier.padding(horizontal = 1.dp).width(3.dp).height((7 + i * 3).dp)
                            .clip(RoundedCornerShape(2.dp)).background(Green.copy(alpha = .45f + i * .12f)))
                    }
                    Spacer(Modifier.width(8.dp)); Text("${presence.name.substringBefore(' ')} is recording voice…",
                        color = Muted, fontSize = 11.sp)
                } else {
                    Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                        repeat(3) { i -> Box(Modifier.size(6.dp).offset(y = if (i == 1) (-2).dp else 0.dp)
                            .clip(CircleShape).background(Green)) }
                    }
                    Spacer(Modifier.width(8.dp)); Text("${presence.name.substringBefore(' ')} is typing…",
                        color = Muted, fontSize = 11.sp)
                }
            }
        }
    }
}

@Composable
private fun UploadProgressBar(label: String, progress: Float) {
    Surface(color = Color.White, shadowElevation = 3.dp) {
        Column(Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 9.dp)) {
            Row {
                Text(label.ifBlank { "Uploading…" }, Modifier.weight(1f), fontSize = 11.sp,
                    color = Ink, fontWeight = FontWeight.SemiBold)
                Text("${(progress.coerceIn(0f, 1f) * 100).toInt()}%", fontSize = 11.sp, color = Green, fontWeight = FontWeight.Bold)
            }
            Spacer(Modifier.height(5.dp))
            LinearProgressIndicator({ progress.coerceIn(0f, 1f) }, Modifier.fillMaxWidth().height(5.dp).clip(CircleShape),
                color = Lime, trackColor = Line)
        }
    }
}

@Composable
private fun ForwardMessageDialog(
    message: ChatMessage,
    current: Conversation,
    conversations: List<Conversation>,
    close: () -> Unit,
    send: (Conversation) -> Unit
) {
    val targets = conversations.filter { it.id != current.id }
    AlertDialog(
        onDismissRequest = close,
        icon = { Icon(Icons.Default.Forward, null, tint = Navy) },
        title = { Text("Forward message", fontWeight = FontWeight.Black) },
        text = { Column {
            Surface(color = Mist, shape = RoundedCornerShape(13.dp)) {
                Text(message.content.ifBlank { message.attachmentName ?: "Voice message" },
                    Modifier.fillMaxWidth().padding(11.dp), maxLines = 2, overflow = TextOverflow.Ellipsis,
                    color = Muted, fontSize = 12.sp)
            }
            Spacer(Modifier.height(9.dp))
            if (targets.isEmpty()) Text("No other conversation is available.", color = Muted)
            else LazyColumn(Modifier.heightIn(max = 360.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                items(targets, key = { it.id }) { chat ->
                    Surface(Modifier.fillMaxWidth().clickable { send(chat) }, color = Color.White,
                        shape = RoundedCornerShape(14.dp), border = BorderStroke(1.dp, Line)) {
                        Row(Modifier.padding(10.dp), verticalAlignment = Alignment.CenterVertically) {
                            InitialAvatar(chat.title, 38); Spacer(Modifier.width(10.dp))
                            Column(Modifier.weight(1f)) {
                                Text(chat.title, fontWeight = FontWeight.Bold, maxLines = 1)
                                Text(if (chat.group) "Study group" else "Private conversation", color = Muted, fontSize = 10.sp)
                            }
                            Icon(Icons.Default.Send, null, Modifier.size(18.dp), tint = Navy)
                        }
                    }
                }
            }
        } },
        confirmButton = {},
        dismissButton = { TextButton(close) { Text("Cancel") } }
    )
}

@Composable
private fun ImageEditorDialog(
    uri: Uri,
    close: () -> Unit,
    send: (rotation: Int, squareCrop: Boolean, caption: String) -> Unit
) {
    val context = LocalContext.current
    var rotation by remember(uri) { mutableIntStateOf(0) }
    var square by remember(uri) { mutableStateOf(false) }
    var caption by remember(uri) { mutableStateOf("") }
    var preview by remember(uri) { mutableStateOf<Bitmap?>(null) }
    LaunchedEffect(uri, rotation, square) {
        preview = withContext(Dispatchers.IO) { loadImagePreview(context, uri, rotation, square) }
    }
    AlertDialog(
        onDismissRequest = close,
        title = { Column {
            Text("Edit photo", fontWeight = FontWeight.Black)
            Text("Preview and adjust before sending", color = Muted, fontSize = 11.sp)
        } },
        text = { Column {
            Surface(Modifier.fillMaxWidth().height(270.dp), color = Color(0xFF0C1426), shape = RoundedCornerShape(18.dp)) {
                if (preview == null) Box(contentAlignment = Alignment.Center) { CircularProgressIndicator(color = Lime) }
                else Image(preview!!.asImageBitmap(), "Photo preview", Modifier.fillMaxSize(),
                    contentScale = ContentScale.Fit)
            }
            Spacer(Modifier.height(9.dp))
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(7.dp)) {
                OutlinedButton({ rotation = (rotation + 90) % 360 }, Modifier.weight(1f), shape = RoundedCornerShape(12.dp)) {
                    Icon(Icons.Default.RotateRight, null, Modifier.size(17.dp)); Spacer(Modifier.width(5.dp)); Text("Rotate")
                }
                OutlinedButton({ square = !square }, Modifier.weight(1f), shape = RoundedCornerShape(12.dp)) {
                    Icon(Icons.Default.Crop, null, Modifier.size(17.dp)); Spacer(Modifier.width(5.dp)); Text(if (square) "Original" else "Square")
                }
            }
            Spacer(Modifier.height(8.dp))
            OutlinedTextField(caption, { if (it.length <= 4000) caption = it }, Modifier.fillMaxWidth(),
                placeholder = { Text("Add a caption…") }, minLines = 1, maxLines = 3, shape = RoundedCornerShape(14.dp))
        } },
        confirmButton = { Button({ send(rotation, square, caption) }, enabled = preview != null,
            colors = ButtonDefaults.buttonColors(containerColor = Navy)) { Icon(Icons.Default.Send, null); Spacer(Modifier.width(6.dp)); Text("Send") } },
        dismissButton = { TextButton(close) { Text("Cancel") } }
    )
}

private fun loadImagePreview(context: android.content.Context, uri: Uri, rotation: Int, square: Boolean): Bitmap? {
    return try {
        val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        context.contentResolver.openInputStream(uri)?.use { BitmapFactory.decodeStream(it, null, bounds) }
        var sample = 1
        while (bounds.outWidth / sample > 1200 || bounds.outHeight / sample > 1200) sample *= 2
        var bitmap = context.contentResolver.openInputStream(uri)?.use {
            BitmapFactory.decodeStream(it, null, BitmapFactory.Options().apply { inSampleSize = sample })
        } ?: return null
        if (rotation % 360 != 0) bitmap = Bitmap.createBitmap(bitmap, 0, 0, bitmap.width, bitmap.height,
            Matrix().apply { postRotate(rotation.toFloat()) }, true)
        if (square) {
            val side = minOf(bitmap.width, bitmap.height)
            bitmap = Bitmap.createBitmap(bitmap, (bitmap.width - side) / 2, (bitmap.height - side) / 2, side, side)
        }
        bitmap
    } catch (_: Exception) { null }
}

@OptIn(androidx.compose.foundation.ExperimentalFoundationApi::class)
@Composable
private fun MessageBubble(
    m: ChatMessage,
    headers: Map<String, String>,
    onLongPress: () -> Unit,
    onReaction: (String) -> Unit,
    onAttachment: () -> Unit,
    onReply: () -> Unit,
    onForward: () -> Unit,
    showSender: Boolean
) {
    val bubble = if (m.mine) Navy else Color.White
    val foreground = if (m.mine) Color.White else Ink
    var dragX by remember(m.id) { mutableFloatStateOf(0f) }
    val replyDirection = if (m.mine) -1 else 1
    Column(Modifier.fillMaxWidth(), horizontalAlignment = if (m.mine) Alignment.End else Alignment.Start) {
        Box(Modifier.fillMaxWidth(), contentAlignment = if (m.mine) Alignment.CenterEnd else Alignment.CenterStart) {
            if (abs(dragX) > 14f) {
                val isReply = dragX * replyDirection > 0
                Surface(
                    modifier = Modifier.align(if (dragX > 0) Alignment.CenterStart else Alignment.CenterEnd).size(35.dp),
                    color = if (isReply) SoftLime else Navy.copy(.10f), shape = CircleShape
                ) { Box(contentAlignment = Alignment.Center) { Icon(
                    if (isReply) Icons.Default.Reply else Icons.Default.Forward,
                    if (isReply) "Swipe to reply" else "Swipe to forward", Modifier.size(18.dp), tint = Navy
                ) } } }
            Surface(
                color = bubble, contentColor = foreground,
                shape = if (m.mine) RoundedCornerShape(20.dp, 6.dp, 20.dp, 20.dp) else RoundedCornerShape(6.dp, 20.dp, 20.dp, 20.dp),
                shadowElevation = if (m.mine) 0.dp else 1.dp,
                modifier = Modifier.widthIn(max = 320.dp)
                    .graphicsLayer { translationX = dragX }
                    .pointerInput(m.id) {
                        detectHorizontalDragGestures(
                            onHorizontalDrag = { change, amount ->
                                change.consume(); dragX = (dragX + amount).coerceIn(-88f, 88f)
                            },
                            onDragCancel = { dragX = 0f },
                            onDragEnd = {
                                if (!m.deleted && abs(dragX) >= 56f) {
                                    if (dragX * replyDirection > 0) onReply() else onForward()
                                }
                                dragX = 0f
                            }
                        )
                    }
                    .combinedClickable(onClick = {}, onLongClick = onLongPress)
            ) {
                Column(Modifier.padding(horizontal = 13.dp, vertical = 9.dp)) {
                if (showSender) Text(m.sender, color = Green, fontWeight = FontWeight.Bold, fontSize = 11.sp)
                if (m.forwarded) MetaLabel(Icons.Default.Forward, "Forwarded", m.mine)
                m.reply?.let { ReplyCard(it, m.mine) }
                if (m.deleted) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(Icons.Default.Block, null, Modifier.size(16.dp), tint = foreground.copy(.6f))
                        Spacer(Modifier.width(7.dp)); Text("This message was deleted", color = foreground.copy(.7f), fontSize = 13.sp)
                    }
                } else {
                    if (m.voiceSeconds > 0) VoicePlayer(m.attachmentUrl, m.voiceSeconds, headers, m.mine)
                    else if (m.attachmentUrl != null && m.attachmentType?.lowercase() in listOf("jpg", "jpeg", "png", "gif", "webp")) {
                        ProtectedNetworkImage(m.attachmentUrl, headers, m.mine, onAttachment)
                    } else if (m.attachmentUrl != null) AttachmentCard(m, m.mine, onAttachment)
                    if (m.content.isNotBlank()) Text(m.content, fontSize = 15.sp, lineHeight = 20.sp)
                }
                Row(Modifier.align(Alignment.End).padding(top = 3.dp), verticalAlignment = Alignment.CenterVertically) {
                    if (m.pinned) Icon(Icons.Default.PushPin, null, Modifier.size(12.dp), tint = foreground.copy(.58f))
                    if (m.starred) Icon(Icons.Default.Star, null, Modifier.padding(start = 3.dp).size(12.dp), tint = Lime)
                    if (m.edited) Text(" edited ·", color = foreground.copy(.55f), fontSize = 9.sp)
                    Text(m.time, color = foreground.copy(.57f), fontSize = 9.sp)
                    if (m.mine) { Spacer(Modifier.width(3.dp)); Icon(if (m.read) Icons.Default.DoneAll else Icons.Default.Done,
                        if (m.read) "Read" else "Sent", Modifier.size(14.dp), tint = if (m.read) Lime else foreground.copy(.58f)) }
                }
                }
            }
        }
        if (m.reactions.isNotEmpty()) Row(Modifier.padding(horizontal = 8.dp).offset(y = (-2).dp), horizontalArrangement = Arrangement.spacedBy(4.dp)) {
            m.reactions.forEach { reaction ->
                Surface(Modifier.clickable { onReaction(reaction.emoji) }, color = if (reaction.mine) SoftLime else Color.White,
                    shape = RoundedCornerShape(50), border = BorderStroke(1.dp, if (reaction.mine) Lime else Line)) {
                    Text("${reaction.emoji} ${reaction.count}", Modifier.padding(horizontal = 7.dp, vertical = 3.dp), fontSize = 11.sp)
                }
            }
        }
    }
}

@Composable
private fun ProtectedNetworkImage(url: String, headers: Map<String, String>, mine: Boolean, open: () -> Unit) {
    var bitmap by remember(url) { mutableStateOf<Bitmap?>(null) }
    var failed by remember(url) { mutableStateOf(false) }
    LaunchedEffect(url, headers) {
        bitmap = withContext(Dispatchers.IO) {
            try {
                val connection = (URL(url).openConnection() as HttpURLConnection).apply {
                    connectTimeout = 12_000; readTimeout = 25_000
                    headers.forEach { (name, value) -> setRequestProperty(name, value) }
                }
                try {
                    if (connection.responseCode !in 200..299) null
                    else connection.inputStream.use { BitmapFactory.decodeStream(BufferedInputStream(it)) }
                } finally { connection.disconnect() }
            } catch (_: Exception) { null }
        }
        failed = bitmap == null
    }
    Surface(
        Modifier.widthIn(min = 210.dp, max = 310.dp).heightIn(min = 120.dp, max = 300.dp)
            .padding(bottom = 6.dp).clickable(onClick = open),
        color = if (mine) Color.White.copy(.09f) else Mist, shape = RoundedCornerShape(15.dp)
    ) {
        when {
            bitmap != null -> Image(bitmap!!.asImageBitmap(), "Shared photo", Modifier.fillMaxWidth(), contentScale = ContentScale.Crop)
            failed -> Column(Modifier.padding(18.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                Icon(Icons.Default.BrokenImage, null, tint = if (mine) Color.White.copy(.65f) else Muted)
                Spacer(Modifier.height(6.dp)); Text("Tap to open photo", fontSize = 11.sp,
                    color = if (mine) Color.White.copy(.65f) else Muted)
            }
            else -> Box(contentAlignment = Alignment.Center) { CircularProgressIndicator(Modifier.size(25.dp), color = Lime, strokeWidth = 2.dp) }
        }
    }
}

@Composable private fun MetaLabel(icon: ImageVector, text: String, mine: Boolean) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        Icon(icon, null, Modifier.size(12.dp), tint = if (mine) Lime else Green)
        Spacer(Modifier.width(4.dp)); Text(text, color = if (mine) Lime else Green, fontSize = 9.sp, fontWeight = FontWeight.Bold)
    }
}

@Composable private fun ReplyCard(reply: ReplyPreview, mine: Boolean) {
    Surface(Modifier.fillMaxWidth().padding(vertical = 5.dp), color = if (mine) Color.White.copy(.10f) else Mist,
        shape = RoundedCornerShape(10.dp)) {
        Row {
            Box(Modifier.width(3.dp).height(48.dp).background(Lime))
            Column(Modifier.padding(horizontal = 9.dp, vertical = 6.dp)) {
                Text(reply.sender, color = if (mine) Lime else Green, fontSize = 10.sp, fontWeight = FontWeight.Bold)
                Text(reply.text, color = if (mine) Color.White.copy(.72f) else Muted, fontSize = 11.sp,
                    maxLines = 1, overflow = TextOverflow.Ellipsis)
            }
        }
    }
}

@Composable private fun AttachmentCard(m: ChatMessage, mine: Boolean, open: () -> Unit) {
    val image = m.attachmentType?.lowercase() in listOf("jpg", "jpeg", "png", "gif", "webp")
    Surface(color = if (mine) Color.White.copy(.10f) else Mist, shape = RoundedCornerShape(13.dp),
        modifier = Modifier.padding(bottom = 5.dp).clickable(onClick = open)) {
        Row(Modifier.padding(11.dp), verticalAlignment = Alignment.CenterVertically) {
            Surface(Modifier.size(38.dp), color = if (mine) Color.White.copy(.12f) else SoftLime, shape = RoundedCornerShape(11.dp)) {
                Box(contentAlignment = Alignment.Center) { Icon(if (image) Icons.Default.Image else Icons.Default.Description, null, tint = if (mine) Lime else Navy) }
            }
            Spacer(Modifier.width(9.dp)); Column(Modifier.weight(1f)) {
                Text(m.attachmentName ?: if (image) "Photo" else "Attachment", fontWeight = FontWeight.SemiBold,
                    fontSize = 12.sp, maxLines = 2, overflow = TextOverflow.Ellipsis)
                Text(if (image) "Image" else (m.attachmentType?.uppercase() ?: "File"),
                    color = if (mine) Color.White.copy(.58f) else Muted, fontSize = 9.sp)
            }
            Icon(Icons.Default.OpenInNew, "Open attachment", Modifier.size(18.dp))
        }
    }
}

@Composable
private fun VoicePlayer(url: String?, seconds: Int, headers: Map<String, String>, mine: Boolean) {
    val context = LocalContext.current
    var player by remember(url) { mutableStateOf<MediaPlayer?>(null) }
    var playing by remember { mutableStateOf(false) }
    var prepared by remember { mutableStateOf(false) }
    var position by remember { mutableIntStateOf(0) }
    var duration by remember(seconds) { mutableIntStateOf(seconds.coerceAtLeast(1) * 1000) }
    var speed by remember { mutableFloatStateOf(1f) }
    DisposableEffect(url) { onDispose { player?.release(); player = null } }
    LaunchedEffect(playing) {
        while (playing) { position = player?.currentPosition ?: position; delay(150) }
    }
    Column(Modifier.widthIn(min = 220.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            FilledIconButton({
                if (playing) { player?.pause(); playing = false }
                else if (url != null) {
                    val current = player
                    if (current != null && prepared) { current.start(); playing = true }
                    else try {
                        MediaPlayer().also { mp ->
                            mp.setDataSource(context, Uri.parse(url), headers)
                            mp.setOnPreparedListener {
                                prepared = true; duration = it.duration.coerceAtLeast(duration)
                                it.playbackParams = it.playbackParams.setSpeed(speed); it.start(); playing = true
                            }
                            mp.setOnCompletionListener { playing = false; position = 0; it.seekTo(0) }
                            mp.setOnErrorListener { failed, _, _ -> failed.release(); player = null; playing = false; prepared = false; true }
                            player = mp; mp.prepareAsync()
                        }
                    } catch (_: Exception) { player?.release(); player = null; playing = false; prepared = false }
                }
            }, colors = IconButtonDefaults.filledIconButtonColors(
                containerColor = if (mine) Lime else Navy, contentColor = if (mine) Navy else Color.White), modifier = Modifier.size(38.dp)) {
                Icon(if (playing) Icons.Default.Pause else Icons.Default.PlayArrow, if (playing) "Pause voice" else "Play voice", Modifier.size(20.dp))
            }
            Spacer(Modifier.width(8.dp))
            Column(Modifier.weight(1f)) {
                Row(Modifier.fillMaxWidth().height(22.dp), verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(2.dp)) {
                    repeat(28) { i ->
                        val h = (6 + ((i * 11 + seconds) % 15)).dp
                        Box(Modifier.weight(1f).height(h).clip(RoundedCornerShape(2.dp)).background(
                            if (i / 28f <= position.toFloat() / duration.coerceAtLeast(1)) Lime else
                                (if (mine) Color.White.copy(.35f) else Navy.copy(.22f))))
                    }
                }
                Slider(position.toFloat(), { value -> position = value.toInt(); if (prepared) player?.seekTo(position) },
                    valueRange = 0f..duration.coerceAtLeast(1).toFloat(), modifier = Modifier.fillMaxWidth().height(18.dp),
                    colors = SliderDefaults.colors(thumbColor = Lime, activeTrackColor = Lime,
                        inactiveTrackColor = if (mine) Color.White.copy(.22f) else Navy.copy(.14f)))
            }
        }
        Row(Modifier.fillMaxWidth().padding(start = 46.dp), horizontalArrangement = Arrangement.SpaceBetween) {
            Text(formatDuration(if (position > 0) position / 1000 else seconds), fontSize = 9.sp,
                color = if (mine) Color.White.copy(.62f) else Muted)
            Surface(Modifier.clickable {
                speed = when (speed) { 1f -> 1.5f; 1.5f -> 2f; else -> 1f }
                if (prepared) player?.let { it.playbackParams = it.playbackParams.setSpeed(speed) }
            }, color = if (mine) Color.White.copy(.10f) else Mist, shape = RoundedCornerShape(50)) {
                Text("${speed}×", Modifier.padding(horizontal = 7.dp, vertical = 2.dp), fontSize = 9.sp, fontWeight = FontWeight.Bold)
            }
        }
    }
}

private fun formatDuration(seconds: Int): String = "%d:%02d".format(seconds / 60, seconds % 60)

@Composable
private fun PremiumComposer(
    text: String,
    onText: (String) -> Unit,
    emojiOpen: Boolean,
    toggleEmoji: () -> Unit,
    reply: ChatMessage?,
    editing: ChatMessage?,
    cancelContext: () -> Unit,
    attachPhoto: () -> Unit,
    attachFile: () -> Unit,
    send: () -> Unit
) {
    var attachmentMenu by remember { mutableStateOf(false) }
    var emojiCategory by remember { mutableIntStateOf(0) }
    var recentEmojis by remember { mutableStateOf<List<String>>(emptyList()) }
    val groups = remember { fullEmojiGroups() }
    Surface(color = Color.White, shadowElevation = 10.dp) {
        Column(Modifier.navigationBarsPadding()) {
            val contextMessage = editing ?: reply
            if (contextMessage != null) {
                Row(Modifier.fillMaxWidth().background(Color(0xFFF8FAFD)).padding(horizontal = 14.dp, vertical = 8.dp),
                    verticalAlignment = Alignment.CenterVertically) {
                    Box(Modifier.width(3.dp).height(36.dp).background(Lime))
                    Spacer(Modifier.width(9.dp)); Column(Modifier.weight(1f)) {
                        Text(if (editing != null) "Editing message" else "Replying to ${contextMessage.sender}",
                            color = Green, fontSize = 10.sp, fontWeight = FontWeight.Bold)
                        Text(contextMessage.content.ifBlank { contextMessage.attachmentName ?: "Voice message" },
                            color = Muted, fontSize = 11.sp, maxLines = 1, overflow = TextOverflow.Ellipsis)
                    }
                    IconButton(cancelContext, Modifier.size(34.dp)) { Icon(Icons.Default.Close, "Cancel") }
                }
            }
            if (emojiOpen) {
                Column(Modifier.fillMaxWidth().heightIn(max = 330.dp).background(Color(0xFFFAFBFD))) {
                    LazyRow(Modifier.fillMaxWidth().padding(horizontal = 10.dp, vertical = 6.dp),
                        horizontalArrangement = Arrangement.spacedBy(5.dp)) {
                        items(groups.size) { index ->
                            val selected = emojiCategory == index
                            Surface(Modifier.clickable { emojiCategory = index },
                                color = if (selected) Lime else Color.White,
                                shape = RoundedCornerShape(10.dp), border = BorderStroke(1.dp, if (selected) Lime else Line)) {
                                Text(groups[index].second.first(), Modifier.padding(horizontal = 11.dp, vertical = 7.dp), fontSize = 18.sp)
                            }
                        }
                    }
                    HorizontalDivider(color = Line)
                    LazyVerticalGrid(GridCells.Fixed(8), Modifier.fillMaxWidth().height(240.dp).padding(horizontal = 8.dp),
                        contentPadding = PaddingValues(vertical = 7.dp)) {
                        gridItems(groups[emojiCategory].second) { emoji ->
                            Text(emoji, Modifier.size(42.dp).clip(RoundedCornerShape(10.dp)).clickable {
                                onText(text + emoji)
                                recentEmojis = (listOf(emoji) + recentEmojis.filterNot { it == emoji }).take(24)
                            }.padding(7.dp), fontSize = 21.sp, textAlign = TextAlign.Center)
                        }
                    }
                }
            }
            Row(Modifier.fillMaxWidth().padding(horizontal = 10.dp, vertical = 9.dp), verticalAlignment = Alignment.Bottom) {
                IconButton(toggleEmoji, Modifier.size(42.dp)) {
                    Icon(if (emojiOpen) Icons.Default.Keyboard else Icons.Default.SentimentSatisfiedAlt,
                        if (emojiOpen) "Keyboard" else "Emoji", tint = Navy)
                }
                Surface(Modifier.weight(1f), color = Color(0xFFF5F7FA), shape = RoundedCornerShape(23.dp),
                    border = BorderStroke(1.dp, Line)) {
                    Row(verticalAlignment = Alignment.Bottom) {
                        TextField(text, onText, Modifier.weight(1f), placeholder = { Text("Message…", color = Muted) },
                            minLines = 1, maxLines = 5, colors = TextFieldDefaults.colors(
                                focusedContainerColor = Color.Transparent, unfocusedContainerColor = Color.Transparent,
                                focusedIndicatorColor = Color.Transparent, unfocusedIndicatorColor = Color.Transparent),
                            keyboardOptions = KeyboardOptions(capitalization = KeyboardCapitalization.Sentences))
                        Box {
                            IconButton({ attachmentMenu = true }) { Icon(Icons.Default.AddCircleOutline, "Add photo or file", tint = Navy) }
                            DropdownMenu(attachmentMenu, { attachmentMenu = false }) {
                                DropdownMenuItem(text = { Text("Photo · edit before sending") },
                                    leadingIcon = { Icon(Icons.Default.AddPhotoAlternate, null) }, onClick = {
                                        attachmentMenu = false; attachPhoto()
                                    })
                                DropdownMenuItem(text = { Text("Document or file") },
                                    leadingIcon = { Icon(Icons.Default.AttachFile, null) }, onClick = {
                                        attachmentMenu = false; attachFile()
                                    })
                            }
                        }
                    }
                }
                Spacer(Modifier.width(7.dp))
                FilledIconButton(send, Modifier.size(50.dp), colors = IconButtonDefaults.filledIconButtonColors(
                    containerColor = if (text.isNotBlank()) Navy else Navy2, contentColor = Color.White)) {
                    Icon(if (text.isNotBlank()) Icons.Default.Send else Icons.Default.Mic,
                        if (text.isNotBlank()) "Send message" else "Record voice")
                }
            }
        }
    }
}

private fun fullEmojiGroups(): List<Pair<String, List<String>>> = listOf(
    "Faces" to "😀 😃 😄 😁 😆 😅 😂 🤣 😊 😇 🙂 🙃 😉 😌 😍 🥰 😘 😗 😙 😚 😋 😛 😝 😜 🤪 🤨 🧐 🤓 😎 🥸 🤩 🥳 😏 😒 😞 😔 😟 😕 🙁 ☹️ 😣 😖 😫 😩 🥺 😢 😭 😤 😠 😡 🤬 🤯 😳 🥵 🥶 😱 😨 😰 😥 😓 🤗 🤔 🫣 🤭 🫢 🫡 🤫 🫠 🤥 😶 🫥 😐 🫤 😑 😬 🙄 😯 😦 😧 😮 😲 🥱 😴 🤤 😪 😵 🤐 🥴 🤢 🤮 🤧 😷 🤒 🤕".split(" "),
    "People" to "👋 🤚 🖐️ ✋ 🖖 🫱 🫲 🫳 🫴 👌 🤌 🤏 ✌️ 🤞 🫰 🤟 🤘 🤙 👈 👉 👆 👇 ☝️ 👍 👎 ✊ 👊 🤛 🤜 👏 🙌 🫶 👐 🤲 🤝 🙏 ✍️ 💅 🤳 💪 🦾 🦿 🦵 🦶 👂 👃 🧠 🫀 🫁 👀 👁️ 👅 👄 🫦 👶 🧒 👦 👧 🧑 👱 👨 🧔 👩 🧓 👴 👵 🙍 🙎 🙅 🙆 💁 🙋 🧏 🙇 🤦 🤷 👮 👷 💂 🕵️ 👩‍⚕️ 👩‍🎓 👩‍🏫 👩‍⚖️ 👩‍🌾 👩‍🍳 👩‍🔧 👩‍💻 👩‍🎨 👩‍🚀 👩‍🚒 🧕 👳 🤵 👰 🤰 🫃 🫄 🤱".split(" "),
    "Animals" to "🐶 🐱 🐭 🐹 🐰 🦊 🐻 🐼 🐻‍❄️ 🐨 🐯 🦁 🐮 🐷 🐽 🐸 🐵 🙈 🙉 🙊 🐒 🐔 🐧 🐦 🐤 🐣 🐥 🦆 🦅 🦉 🦇 🐺 🐗 🐴 🦄 🐝 🪱 🐛 🦋 🐌 🐞 🐜 🪰 🪲 🪳 🦟 🦗 🕷️ 🦂 🐢 🐍 🦎 🐙 🦑 🦐 🦞 🦀 🐠 🐟 🐡 🐬 🐳 🐋 🦈 🐊 🐅 🐆 🦓 🦍 🦧 🐘 🦛 🦏 🐪 🐫 🦒 🦬 🐃 🐂 🐄 🐎 🐖 🐏 🐑 🦙 🐐 🦌 🐕 🐩 🦮 🐕‍🦺 🐈 🐈‍⬛ 🪶 🐓 🦃 🦚 🦜 🦢 🦩 🕊️ 🐇 🦝 🦨 🦡 🦫 🦦 🦥 🐁 🐀 🐿️ 🦔".split(" "),
    "Food" to "🍏 🍎 🍐 🍊 🍋 🍌 🍉 🍇 🍓 🫐 🍈 🍒 🍑 🥭 🍍 🥥 🥝 🍅 🍆 🥑 🥦 🥬 🥒 🌶️ 🫑 🌽 🥕 🫒 🧄 🧅 🥔 🍠 🫘 🥐 🥯 🍞 🥖 🫓 🥨 🧀 🥚 🍳 🧈 🥞 🧇 🥓 🥩 🍗 🍖 🌭 🍔 🍟 🍕 🫔 🌮 🌯 🥙 🧆 🥪 🥫 🍝 🍜 🍲 🍛 🍣 🍱 🥟 🦪 🍤 🍙 🍚 🍘 🍥 🥠 🥮 🍢 🍡 🍧 🍨 🍦 🥧 🧁 🍰 🎂 🍮 🍭 🍬 🍫 🍿 🍩 🍪 🌰 🥜 🍯 🥛 ☕ 🫖 🍵 🧃 🥤 🧋 🧊 🥄 🍴 🍽️".split(" "),
    "Activities" to "⚽ 🏀 🏈 ⚾ 🥎 🎾 🏐 🏉 🥏 🎱 🪀 🏓 🏸 🏒 🏑 🥍 🏏 🪃 🥅 ⛳ 🪁 🛝 🏹 🎣 🤿 🥊 🥋 🎽 🛹 🛼 🛷 ⛸️ 🥌 🎿 ⛷️ 🏂 🪂 🏋️ 🤼 🤸 ⛹️ 🤺 🤾 🏌️ 🏇 🧘 🏄 🏊 🤽 🚣 🧗 🚵 🚴 🏆 🥇 🥈 🥉 🏅 🎖️ 🏵️ 🎗️ 🎫 🎟️ 🎪 🤹 🎭 🩰 🎨 🎬 🎤 🎧 🎼 🎹 🥁 🪘 🎷 🎺 🪗 🎸 🪕 🎻 🎲 ♟️ 🎯 🎳 🎮 🧩".split(" "),
    "Travel" to "🚗 🚕 🚙 🚌 🚎 🏎️ 🚓 🚑 🚒 🚐 🛻 🚚 🚛 🚜 🛵 🏍️ 🛺 🚲 🛴 🚨 🚔 🚍 🚘 🚖 ✈️ 🛫 🛬 🛩️ 💺 🚁 🚀 🛸 🚂 🚆 🚇 🚊 🚉 🚢 ⛵ 🚤 🛥️ 🛳️ ⛴️ ⚓ 🛟 ⛽ 🚧 🚦 🗺️ 🗿 🗽 🗼 🏰 🏯 🏟️ 🎡 🎢 🎠 ⛲ ⛱️ 🏖️ 🏝️ 🏜️ 🌋 ⛰️ 🏕️ ⛺ 🏠 🏡 🏢 🏥 🏦 🏨 🏪 🏫 🕋 🕌 ⛪ 🛕 🕍 🌁 🌃 🏙️ 🌄 🌅 🌆 🌇 🌉 🌌".split(" "),
    "Objects" to "⌚ 📱 💻 ⌨️ 🖥️ 🖨️ 🖱️ 💾 💿 📷 📹 🎥 📞 ☎️ 📺 📻 🎙️ ⏰ ⏳ 📡 🔋 🔌 💡 🔦 🕯️ 🧯 🛢️ 💸 💵 💴 💶 💷 🪙 💳 💎 ⚖️ 🪜 🧰 🔧 🔨 ⚒️ 🛠️ ⛏️ 🔩 ⚙️ 🧱 ⛓️ 🧲 🔫 💣 🧨 🪓 🔪 🗡️ 🛡️ 🚬 ⚰️ 🪦 ⚱️ 🏺 🔮 📿 🧿 🪬 💈 🧪 🔬 🔭 📚 📖 📝 ✏️ 🖊️ 🖌️ 🖍️ 📌 📍 📎 🖇️ 📏 📐 ✂️ 🗃️ 🗄️ 🗑️ 🔒 🔓 🔐 🔑 🗝️ 🔨 🪄 🎁 🎈 ✉️ 📩 📨 📧 💌 📥 📤 📦 🏷️ 🪧 📪 📫 📬 📭 📮 📜 📄 📃 📑 📊 📈 📉 🗒️ 🗓️ 📆 📅".split(" "),
    "Symbols" to "❤️ 🧡 💛 💚 💙 💜 🖤 🤍 🤎 💔 ❣️ 💕 💞 💓 💗 💖 💘 💝 💟 ☮️ ✝️ ☪️ 🕉️ ☸️ ✡️ 🔯 🕎 ☯️ ☦️ 🛐 ⛎ ♈ ♉ ♊ ♋ ♌ ♍ ♎ ♏ ♐ ♑ ♒ ♓ 🆔 ⚛️ ☢️ ☣️ 📴 📳 🈶 🈚 🈸 🈺 🈷️ ✴️ 🆚 💮 🉐 ㊙️ ㊗️ 🈴 🈵 🈹 🈲 🅰️ 🅱️ 🆎 🆑 🅾️ 🆘 ❌ ⭕ 🛑 ⛔ 📛 🚫 💯 💢 ♨️ 🚷 🚯 🚳 🚱 🔞 📵 ❗ ❕ ❓ ❔ ‼️ ⁉️ 🔅 🔆 ⚠️ 🚸 🔱 ⚜️ 🔰 ♻️ ✅ 🈯 💹 ❇️ ✳️ ❎ 🌐 💠 Ⓜ️ 🌀 💤 🏧 🚾 ♿ 🅿️ 🛗 🈳 🈂️ 🛂 🛃 🛄 🛅 🚹 🚺 🚼 ⚧️ 🚻 🚮 🎦 📶 🈁 🔣 ℹ️ 🔤 🔡 🔠 🆖 🆗 🆙 🆒 🆕 🆓 0️⃣ 1️⃣ 2️⃣ 3️⃣ 4️⃣ 5️⃣ 6️⃣ 7️⃣ 8️⃣ 9️⃣ 🔟 ▶️ ⏸️ ⏯️ ⏹️ ⏺️ ⏭️ ⏮️ ⏩ ⏪ 🔀 🔁 🔂 ➕ ➖ ➗ ✖️ ♾️ 💲 ©️ ®️ ™️".split(" "),
    "Flags" to "🇵🇰 🇦🇪 🇸🇦 🇶🇦 🇰🇼 🇹🇷 🇦🇫 🇧🇩 🇮🇳 🇨🇳 🇯🇵 🇰🇷 🇲🇾 🇸🇬 🇦🇺 🇳🇿 🇬🇧 🇺🇸 🇨🇦 🇩🇪 🇫🇷 🇮🇹 🇪🇸 🇵🇹 🇳🇱 🇧🇪 🇨🇭 🇦🇹 🇸🇪 🇳🇴 🇩🇰 🇫🇮 🇵🇱 🇬🇷 🇮🇪 🇧🇷 🇦🇷 🇲🇽 🇿🇦 🇪🇬 🇲🇦 🇳🇬 🇰🇪 🇮🇩 🇹🇭 🇻🇳 🇵🇭 🏳️ 🏴 🏁 🚩 🏳️‍🌈".split(" ")
)

@Composable private fun VoicePreview(clip: VoiceClip, onDelete: () -> Unit, onSend: () -> Unit) {
    Surface(color = Color.White, shadowElevation = 10.dp) {
        Row(Modifier.fillMaxWidth().navigationBarsPadding().padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
            Surface(Modifier.size(42.dp), color = SoftLime, shape = CircleShape) {
                Box(contentAlignment = Alignment.Center) { Icon(Icons.Default.GraphicEq, null, tint = Navy) }
            }
            Spacer(Modifier.width(11.dp)); Column(Modifier.weight(1f)) {
                Text("Voice message ready", fontWeight = FontWeight.Bold, fontSize = 13.sp)
                Text("${formatDuration(clip.seconds)} · Review before sending", color = Muted, fontSize = 10.sp)
            }
            IconButton(onDelete) { Icon(Icons.Default.DeleteOutline, "Delete recording", tint = MaterialTheme.colorScheme.error) }
            FilledIconButton(onSend, colors = IconButtonDefaults.filledIconButtonColors(containerColor = Navy)) { Icon(Icons.Default.Send, "Send voice") }
        }
    }
}

@Composable private fun RecordingBar(seconds: Int, wave: List<Int>, onCancel: () -> Unit, onStop: () -> Unit) {
    Surface(color = Color.White, shadowElevation = 10.dp) {
        Column(Modifier.fillMaxWidth().navigationBarsPadding().padding(horizontal = 12.dp, vertical = 10.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Surface(Modifier.size(38.dp), color = Color(0xFFFFE8E8), shape = RoundedCornerShape(12.dp)) {
                    Box(contentAlignment = Alignment.Center) { Icon(Icons.Default.Mic, null, tint = Color(0xFFD92D20)) }
                }
                Spacer(Modifier.width(9.dp)); Column(Modifier.weight(1f)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Box(Modifier.size(8.dp).clip(CircleShape).background(Color(0xFFD92D20)))
                        Spacer(Modifier.width(6.dp)); Text("Recording voice…", fontWeight = FontWeight.Bold, color = Ink)
                    }
                    Text("${formatDuration(seconds)} / 2:00 · Live microphone level", color = Muted, fontSize = 10.sp)
                }
                TextButton(onCancel) { Text("Discard", color = MaterialTheme.colorScheme.error) }
                FilledIconButton(onStop, colors = IconButtonDefaults.filledIconButtonColors(containerColor = Navy)) {
                    Icon(Icons.Default.Check, "Finish and review")
                }
            }
            Spacer(Modifier.height(8.dp))
            Row(Modifier.fillMaxWidth().height(34.dp), verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(2.dp)) {
                val bars = if (wave.isEmpty()) List(34) { 3 } else wave.takeLast(34)
                bars.forEach { level -> Box(Modifier.weight(1f).height(level.coerceIn(3, 30).dp)
                    .clip(RoundedCornerShape(2.dp)).background(if (level > 6) Green else Line)) }
            }
            LinearProgressIndicator({ seconds.coerceIn(0, 120) / 120f }, Modifier.fillMaxWidth().height(4.dp).clip(CircleShape),
                color = Lime, trackColor = Line)
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable private fun MessageActionsSheet(
    message: ChatMessage,
    close: () -> Unit,
    reply: () -> Unit,
    edit: () -> Unit,
    star: () -> Unit,
    pin: () -> Unit,
    forward: () -> Unit,
    deleteMe: () -> Unit,
    deleteAll: () -> Unit,
    react: (String) -> Unit
) {
    val clipboard = LocalClipboardManager.current
    ModalBottomSheet(onDismissRequest = close, containerColor = Color.White) {
        Text("React", Modifier.padding(horizontal = 20.dp), color = Muted, fontSize = 11.sp, fontWeight = FontWeight.Bold)
        Row(Modifier.fillMaxWidth().padding(horizontal = 14.dp, vertical = 9.dp), horizontalArrangement = Arrangement.SpaceBetween) {
            listOf("👍","❤️","😂","😮","😢","🔥").forEach { emoji ->
                Surface(Modifier.size(44.dp).clickable { react(emoji) }, color = Mist, shape = CircleShape) {
                    Box(contentAlignment = Alignment.Center) { Text(emoji, fontSize = 21.sp) }
                }
            }
        }
        HorizontalDivider(color = Line)
        ActionRow(Icons.Default.Reply, "Reply", reply)
        if (message.content.isNotBlank() && !message.deleted) ActionRow(Icons.Default.ContentCopy, "Copy text", action = {
            clipboard.setText(AnnotatedString(message.content)); close()
        })
        if (message.canEdit && message.content.isNotBlank()) ActionRow(Icons.Default.Edit, "Edit message", edit)
        if (!message.deleted) ActionRow(Icons.Default.Forward, "Forward message", forward)
        if (!message.deleted) ActionRow(if (message.starred) Icons.Default.StarBorder else Icons.Default.Star,
            if (message.starred) "Remove star" else "Star message", star)
        if (!message.deleted) ActionRow(Icons.Default.PushPin, if (message.pinned) "Unpin message" else "Pin message", pin)
        ActionRow(Icons.Default.DeleteOutline, "Delete for me", deleteMe, danger = true)
        if (message.mine && !message.deleted) ActionRow(Icons.Default.DeleteForever, "Delete for everyone", deleteAll, danger = true)
        Spacer(Modifier.height(20.dp))
    }
}

@Composable private fun ActionRow(icon: ImageVector, label: String, action: () -> Unit, danger: Boolean = false) {
    Row(Modifier.fillMaxWidth().clickable(onClick = action).padding(horizontal = 20.dp, vertical = 13.dp), verticalAlignment = Alignment.CenterVertically) {
        Icon(icon, null, tint = if (danger) MaterialTheme.colorScheme.error else Navy)
        Spacer(Modifier.width(15.dp)); Text(label, color = if (danger) MaterialTheme.colorScheme.error else Ink, fontWeight = FontWeight.SemiBold)
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
