from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def r(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def w(path: str, text: str) -> None:
    p = ROOT / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding='utf-8')


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f'v3.8 missing target: {label}')
    return text.replace(old, new, 1)


# ---------------------------------------------------------------------------
# 1) Website-inspired native chat composer + stable compact emoji keyboard.
# ---------------------------------------------------------------------------
path = 'flutter/lib/screens/chat_screen.dart'
text = r(path)
composer_start = text.find('  Widget _composer()')
composer_end = text.find('  Future<void> _loadMentionMembers()', composer_start)
if composer_start < 0 or composer_end < 0:
    raise RuntimeError('v3.8 generated composer boundary missing')

composer = r'''  Widget _composer() {
    final suggestions = _mentionSuggestions();
    final scheme = Theme.of(context).colorScheme;
    final dark = Theme.of(context).brightness == Brightness.dark;
    return Container(
      decoration: BoxDecoration(
        color: scheme.surface,
        border: Border(
          top: BorderSide(
            color: scheme.outlineVariant.withValues(alpha: .35),
          ),
        ),
        boxShadow: const [
          BoxShadow(
            color: Color(0x0A071426),
            blurRadius: 16,
            offset: Offset(0, -3),
          ),
        ],
      ),
      padding: const EdgeInsets.fromLTRB(10, 7, 10, 9),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (suggestions.isNotEmpty) ...[
            SizedBox(
              height: 39,
              child: ListView.separated(
                scrollDirection: Axis.horizontal,
                itemCount: suggestions.length,
                separatorBuilder: (_, _) => const SizedBox(width: 6),
                itemBuilder: (_, i) {
                  final member = suggestions[i];
                  return ActionChip(
                    visualDensity: VisualDensity.compact,
                    avatar: const Icon(
                      Icons.alternate_email_rounded,
                      size: 15,
                      color: AppColors.blue,
                    ),
                    label: Text(
                      '${member['name'] ?? member['username'] ?? ''}',
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                    onPressed: () => _insertMention(member),
                  );
                },
              ),
            ),
            const SizedBox(height: 5),
          ],
          Row(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Expanded(
                child: AnimatedContainer(
                  duration: const Duration(milliseconds: 150),
                  constraints: const BoxConstraints(minHeight: 52, maxHeight: 132),
                  decoration: BoxDecoration(
                    color: dark ? const Color(0xFF151F2F) : const Color(0xFFF4F6FA),
                    borderRadius: BorderRadius.circular(29),
                    border: Border.all(
                      color: showEmoji
                          ? AppColors.blue.withValues(alpha: .35)
                          : scheme.outlineVariant.withValues(alpha: .50),
                    ),
                  ),
                  child: TextField(
                    controller: textController,
                    minLines: 1,
                    maxLines: 5,
                    maxLength: 4000,
                    keyboardType: TextInputType.multiline,
                    textCapitalization: TextCapitalization.sentences,
                    buildCounter: (
                      _, {
                      required currentLength,
                      required isFocused,
                      maxLength,
                    }) => null,
                    onTap: () {
                      if (showEmoji) setState(() => showEmoji = false);
                    },
                    style: TextStyle(
                      fontSize: 16,
                      height: 1.32,
                      color: scheme.onSurface,
                    ),
                    decoration: InputDecoration(
                      hintText: 'Message...',
                      hintStyle: TextStyle(
                        color: scheme.onSurfaceVariant.withValues(alpha: .68),
                        fontSize: 16,
                      ),
                      isDense: true,
                      filled: false,
                      border: InputBorder.none,
                      enabledBorder: InputBorder.none,
                      focusedBorder: InputBorder.none,
                      contentPadding: const EdgeInsets.symmetric(vertical: 14),
                      prefixIconConstraints: const BoxConstraints(
                        minWidth: 48,
                        minHeight: 48,
                      ),
                      prefixIcon: IconButton(
                        tooltip: showEmoji ? 'Keyboard' : 'Emoji',
                        onPressed: _toggleEmojiPanel,
                        icon: AnimatedSwitcher(
                          duration: const Duration(milliseconds: 150),
                          child: Icon(
                            showEmoji
                                ? Icons.keyboard_rounded
                                : Icons.emoji_emotions_outlined,
                            key: ValueKey(showEmoji),
                            color: showEmoji
                                ? AppColors.blue
                                : scheme.onSurfaceVariant,
                          ),
                        ),
                      ),
                      suffixIconConstraints: const BoxConstraints(
                        minWidth: 48,
                        minHeight: 48,
                      ),
                      suffixIcon: IconButton(
                        tooltip: 'Photo or file',
                        onPressed: sending ? null : _pickAttachment,
                        icon: Icon(
                          Icons.attach_file_rounded,
                          color: scheme.onSurfaceVariant,
                        ),
                      ),
                    ),
                  ),
                ),
              ),
              const SizedBox(width: 9),
              SizedBox(
                width: 52,
                height: 52,
                child: IconButton.filled(
                  tooltip: textController.text.trim().isEmpty
                      ? 'Voice message'
                      : 'Send message',
                  onPressed: sending
                      ? null
                      : (textController.text.trim().isEmpty
                            ? _toggleRecording
                            : _sendText),
                  style: IconButton.styleFrom(
                    backgroundColor: AppColors.blue,
                    foregroundColor: Colors.white,
                    disabledBackgroundColor: AppColors.blue.withValues(alpha: .35),
                  ),
                  icon: AnimatedSwitcher(
                    duration: const Duration(milliseconds: 150),
                    child: Icon(
                      textController.text.trim().isEmpty
                          ? (recording ? Icons.stop_rounded : Icons.mic_rounded)
                          : Icons.send_rounded,
                      key: ValueKey('${textController.text.trim().isEmpty}:$recording'),
                      size: 24,
                    ),
                  ),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  void _toggleEmojiPanel() {
    final next = !showEmoji;
    FocusManager.instance.primaryFocus?.unfocus();
    setState(() => showEmoji = next);
    if (next) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) _toBottom();
      });
    }
  }

'''
text = text[:composer_start] + composer + text[composer_end:]

emoji_start = text.find('  Widget _emojiPanel() {')
emoji_end = text.find('  Future<void> _pickAttachment()', emoji_start)
if emoji_start < 0 or emoji_end < 0:
    raise RuntimeError('v3.8 emoji panel boundary missing')

emoji_panel = r'''  Widget _emojiPanel() {
    final groups = <String, List<String>>{
      'Recent': recentEmojis,
      'Smileys': const [
        '😀','😃','😄','😁','😆','😅','😂','🤣','😊','😇','🙂','🙃','😉','😍','🥰','😘',
        '😋','😜','🤪','🤨','🧐','🤓','😎','🤩','🥳','😏','😒','😞','😔','😟','😕','🙁',
        '🥺','😢','😭','😤','😠','😡','🤬','🤯','😳','🥵','🥶','😱','😨','😰','😥','🤗',
        '🤔','🫡','🤭','🫢','🫣','🤫','😶','😐','😑','😬','🙄','😮','🥱','😴','🤤','😵'
      ],
      'People': const [
        '👋','🤚','🖐️','✋','🖖','👌','🤌','🤏','✌️','🤞','🫰','🤟','🤘','🤙','👈','👉',
        '👆','👇','☝️','👍','👎','✊','👊','🤛','🤜','👏','🙌','🫶','👐','🤲','🤝','🙏',
        '💪','🦾','🫂','👀','👁️','👄','🧠','👶','🧒','👦','👧','🧑','👨','👩','🧔','👵'
      ],
      'Animals': const [
        '🐶','🐱','🐭','🐹','🐰','🦊','🐻','🐼','🐻‍❄️','🐨','🐯','🦁','🐮','🐷','🐸','🐵',
        '🐔','🐧','🐦','🐤','🦆','🦅','🦉','🦇','🐺','🐗','🐴','🦄','🐝','🦋','🐌','🐞',
        '🐢','🐍','🦎','🦂','🐙','🦑','🦀','🐠','🐟','🐬','🐳','🦈','🐊','🐘','🦒','🦓'
      ],
      'Food': const [
        '🍏','🍎','🍐','🍊','🍋','🍌','🍉','🍇','🍓','🫐','🍈','🍒','🍑','🥭','🍍','🥥',
        '🥝','🍅','🥑','🥦','🥕','🌽','🌶️','🥒','🥬','🍞','🥐','🥨','🧀','🥚','🍳','🥞',
        '🍔','🍟','🍕','🌭','🥪','🌮','🍜','🍝','🍣','🍚','🍰','🎂','🍫','🍿','☕','🧃'
      ],
      'Activities': const [
        '⚽','🏀','🏈','⚾','🥎','🎾','🏐','🏉','🥏','🎱','🏓','🏸','🥊','🥋','⛳','⛸️',
        '🎣','🤿','🎿','🛷','🏋️','🤸','⛹️','🏊','🚴','🏆','🥇','🥈','🥉','🎮','🎲','♟️',
        '🎯','🎳','🎨','🎬','🎤','🎧','🎹','🥁','🎸','🎺','📚','✏️','🧪','🔬','💻','🧩'
      ],
      'Objects': const [
        '⌚','📱','💻','⌨️','🖥️','🖨️','📷','📹','🎥','📞','☎️','📺','⏰','💡','🔦','📚',
        '📖','📝','📌','📎','📏','✂️','🔒','🔑','🔨','🛠️','🧰','🧲','💊','🩹','🧴','🎁',
        '💌','📩','📦','📅','📊','📈','📉','🗂️','📁','🗑️','🛒','🚪','🪑','🛏️','🧸','🪄'
      ],
      'Symbols': const [
        '❤️','🧡','💛','💚','💙','💜','🖤','🤍','🤎','💔','❣️','💕','💞','💓','💗','💖',
        '💘','💝','💟','☮️','✝️','☪️','🕉️','☸️','✡️','🔯','🕎','☯️','☦️','🛐','⛎','♈',
        '✅','❌','❗','❓','‼️','⁉️','💯','🔥','✨','⭐','🌟','💫','⚡','🎉','🎊','🔔'
      ],
      'Flags': const [
        '🇵🇰','🇦🇪','🇦🇺','🇬🇧','🇺🇸','🇨🇦','🇸🇦','🇹🇷','🇶🇦','🇯🇵','🇰🇷','🇨🇳','🇩🇪','🇫🇷','🇮🇹','🇪🇸',
        '🇮🇳','🇧🇩','🇱🇰','🇳🇿','🇲🇾','🇸🇬','🇮🇩','🇿🇦','🇳🇴','🇸🇪','🇨🇭','🇳🇱','🇧🇪','🇧🇷','🇦🇷','🇲🇽'
      ],
    };
    final activeCategory = emojiCategory == 'Recent' && recentEmojis.isEmpty
        ? 'Smileys'
        : emojiCategory;
    final items = groups[activeCategory] ?? groups['Smileys']!;
    final scheme = Theme.of(context).colorScheme;
    final compactHeight = MediaQuery.sizeOf(context).height < 650 ? 210.0 : 246.0;
    final categories = groups.keys.toList();

    IconData categoryIcon(String name) => switch (name) {
          'Recent' => Icons.schedule_rounded,
          'People' => Icons.back_hand_outlined,
          'Animals' => Icons.pets_outlined,
          'Food' => Icons.restaurant_outlined,
          'Activities' => Icons.sports_soccer_outlined,
          'Objects' => Icons.lightbulb_outline_rounded,
          'Symbols' => Icons.favorite_border_rounded,
          'Flags' => Icons.flag_outlined,
          _ => Icons.emoji_emotions_outlined,
        };

    return AnimatedContainer(
      duration: const Duration(milliseconds: 180),
      height: compactHeight,
      decoration: BoxDecoration(
        color: scheme.surface,
        border: Border(
          top: BorderSide(color: scheme.outlineVariant.withValues(alpha: .35)),
        ),
      ),
      child: Column(
        children: [
          SizedBox(
            height: 45,
            child: ListView.separated(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 5),
              scrollDirection: Axis.horizontal,
              itemCount: categories.length,
              separatorBuilder: (_, _) => const SizedBox(width: 3),
              itemBuilder: (_, i) {
                final name = categories[i];
                final selected = name == activeCategory;
                return Tooltip(
                  message: name,
                  child: InkWell(
                    borderRadius: BorderRadius.circular(13),
                    onTap: () => setState(() => emojiCategory = name),
                    child: AnimatedContainer(
                      duration: const Duration(milliseconds: 140),
                      width: 39,
                      alignment: Alignment.center,
                      decoration: BoxDecoration(
                        color: selected
                            ? AppColors.blue.withValues(alpha: .12)
                            : Colors.transparent,
                        borderRadius: BorderRadius.circular(13),
                      ),
                      child: Icon(
                        categoryIcon(name),
                        size: 20,
                        color: selected ? AppColors.blue : scheme.onSurfaceVariant,
                      ),
                    ),
                  ),
                );
              },
            ),
          ),
          Divider(height: 1, color: scheme.outlineVariant.withValues(alpha: .35)),
          Expanded(
            child: items.isEmpty
                ? Center(
                    child: Text(
                      'Your recently used emojis will appear here.',
                      style: TextStyle(color: scheme.onSurfaceVariant, fontSize: 12.5),
                    ),
                  )
                : GridView.builder(
                    padding: const EdgeInsets.fromLTRB(8, 8, 8, 10),
                    gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                      crossAxisCount: 8,
                      mainAxisSpacing: 2,
                      crossAxisSpacing: 2,
                    ),
                    itemCount: items.length,
                    itemBuilder: (_, i) => InkWell(
                      borderRadius: BorderRadius.circular(10),
                      onTap: () => _insertEmoji(items[i]),
                      child: Center(
                        child: Text(items[i], style: const TextStyle(fontSize: 25)),
                      ),
                    ),
                  ),
          ),
        ],
      ),
    );
  }

'''
text = text[:emoji_start] + emoji_panel + text[emoji_end:]
w(path, text)


# ---------------------------------------------------------------------------
# 2) Consolidated security endpoint with graceful legacy-server fallback.
# ---------------------------------------------------------------------------
path = 'flutter/lib/core/api_client.dart'
text = r(path)
marker = "  Future<Map<String, dynamic>> privacySettings() =>\n      _request({'action': 'privacy_get'});\n"
insert = "  Future<Map<String, dynamic>> securitySnapshot() =>\n      _request({'action': 'security_snapshot'});\n\n" + marker
text = replace_once(text, marker, insert, 'ApiClient security snapshot')
w(path, text)

path = 'flutter/lib/screens/security_screen.dart'
text = r(path)
load_start = text.find('  Future<void> _load() async {')
load_end = text.find('\n\n  @override\n  Widget build', load_start)
if load_start < 0 or load_end < 0:
    raise RuntimeError('v3.8 security load boundary missing')
load_fn = r'''  Future<void> _load() async {
    if (mounted) {
      setState(() {
        loading = true;
        error = null;
      });
    }
    try {
      final api = AppScope.of(context).api;
      try {
        final snapshot = await api.securitySnapshot();
        final rawSettings = snapshot['settings'];
        final rawSessions = snapshot['sessions'];
        settings = rawSettings is Map
            ? rawSettings.cast<String, dynamic>()
            : <String, dynamic>{};
        sessions = rawSessions is List
            ? rawSessions
                .whereType<Map>()
                .map((e) => e.cast<String, dynamic>())
                .toList()
            : <Map<String, dynamic>>[];
      } catch (e) {
        final firstMessage = apiMessage(e).toLowerCase();
        if (!firstMessage.contains('unknown api action')) rethrow;
        final result = await Future.wait<Object>([
          api.privacySettings(),
          api.mobileSessions(),
        ]);
        settings = result[0] as Map<String, dynamic>;
        sessions = result[1] as List<Map<String, dynamic>>;
      }
    } catch (e) {
      final message = apiMessage(e);
      error = message.toLowerCase().contains('unknown api action')
          ? 'The website API is older than this app. Upload the TaleemPK v3.8 server update to public_html/api/ and try again.'
          : message;
    }
    if (mounted) setState(() => loading = false);
  }'''
text = text[:load_start] + load_fn + text[load_end:]

text = replace_once(
    text,
    "                        _securityNote(),\n",
    "                        _securityNote(),\n                        const SizedBox(height: 16),\n                        _signOutCard(),\n",
    'security sign-out card placement',
)
choice_marker = '  Widget _choice({\n'
signout_widgets = r'''  Widget _signOutCard() => Card(
        child: ListTile(
          contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
          leading: Container(
            width: 42,
            height: 42,
            decoration: BoxDecoration(
              color: AppColors.danger.withValues(alpha: .09),
              borderRadius: BorderRadius.circular(13),
            ),
            child: const Icon(Icons.logout_rounded, color: AppColors.danger),
          ),
          title: const Text(
            'Sign out of this device',
            style: TextStyle(fontWeight: FontWeight.w800),
          ),
          subtitle: const Text('Your account stays signed in on devices you choose to keep.'),
          trailing: const Icon(Icons.chevron_right_rounded),
          onTap: saving ? null : _signOut,
        ),
      );

  Future<void> _signOut() async {
    final yes = await showDialog<bool>(
          context: context,
          builder: (dialog) => AlertDialog(
            icon: const Icon(Icons.logout_rounded, color: AppColors.danger),
            title: const Text('Sign out?'),
            content: const Text('You will need to enter your password again on this device.'),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(dialog, false),
                child: const Text('Cancel'),
              ),
              FilledButton(
                onPressed: () => Navigator.pop(dialog, true),
                child: const Text('Sign out'),
              ),
            ],
          ),
        ) ??
        false;
    if (!yes || !mounted) return;
    setState(() => saving = true);
    await AppScope.of(context).logout();
  }

'''
if choice_marker not in text:
    raise RuntimeError('v3.8 security choice marker missing')
text = text.replace(choice_marker, signout_widgets + choice_marker, 1)
w(path, text)

# Logout should always finish locally even when the network/server logout call
# cannot complete.
path = 'flutter/lib/core/app_state.dart'
text = r(path)
old_logout = "  Future<void> logout() async {\n    await api.logout();\n    bootstrap = null;\n    status = AppStatus.signedOut;\n    notifyListeners();\n  }"
new_logout = "  Future<void> logout() async {\n    try {\n      await api.logout();\n    } catch (_) {\n      await api.clearToken();\n    }\n    bootstrap = null;\n    error = null;\n    status = AppStatus.signedOut;\n    notifyListeners();\n  }"
text = replace_once(text, old_logout, new_logout, 'reliable local logout')
w(path, text)

# Also expose a clear sign-out action directly on the user's profile header.
path = 'flutter/lib/screens/profile_screen.dart'
text = r(path)
public_menu = "          if (profile?.isMe == false)\n            PopupMenuButton<String>("
profile_logout = r'''          if (profile?.isMe == true)
            IconButton(
              tooltip: 'Sign out',
              onPressed: actionBusy ? null : _confirmLogout,
              icon: const Icon(Icons.logout_rounded),
            ),
          if (profile?.isMe == false)
            PopupMenuButton<String>('''
text = replace_once(text, public_menu, profile_logout, 'profile sign-out action')
profile_menu_marker = '  Future<void> _profileMenu(String value) async {\n'
profile_logout_helper = r'''  Future<void> _confirmLogout() async {
    final yes = await showDialog<bool>(
          context: context,
          builder: (dialog) => AlertDialog(
            icon: const Icon(Icons.logout_rounded, color: AppColors.danger),
            title: const Text('Sign out of TaleemPK?'),
            content: const Text('Your account and saved profile stay safe. You can sign in again at any time.'),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(dialog, false),
                child: const Text('Cancel'),
              ),
              FilledButton(
                onPressed: () => Navigator.pop(dialog, true),
                child: const Text('Sign out'),
              ),
            ],
          ),
        ) ??
        false;
    if (!yes || !mounted) return;
    setState(() => actionBusy = true);
    await AppScope.of(context).logout();
  }

'''
if profile_menu_marker not in text:
    raise RuntimeError('v3.8 profile menu marker missing')
text = text.replace(profile_menu_marker, profile_logout_helper + profile_menu_marker, 1)
w(path, text)


# ---------------------------------------------------------------------------
# 3) Verification application polish without changing backend field contracts.
# ---------------------------------------------------------------------------
path = 'flutter/lib/screens/verification_screen.dart'
text = r(path)
text = replace_once(
    text,
    "      isScrollControlled: true,\n      useSafeArea: true,",
    "      isScrollControlled: true,\n      useSafeArea: true,\n      showDragHandle: true,",
    'verification sheet drag handle',
)
replacements = {
    "Text('Verification application'": "Text('Verify your TaleemPK profile'",
    "labelText: 'Verification type'": "labelText: 'Account role'",
    "labelText: 'CNIC / B-Form number *'": "labelText: 'CNIC / B-Form / Passport number *'",
    "labelText: 'School / institute'": "labelText: 'School / college / university'",
    "labelText: 'Role / designation'": "labelText: 'Role / designation (if applicable)'",
    "labelText: 'Subjects / field'": "labelText: 'Subjects / field of study'",
    "labelText: 'Experience in years'": "labelText: 'Experience in years (if applicable)'",
    "labelText: 'Website'": "labelText: 'Website (optional)'",
    "labelText: 'Contact phone'": "labelText: 'Contact phone (optional)'",
    "labelText: 'Additional information'": "labelText: 'Anything reviewers should know'",
    "'CNIC, student card or passport photo page'": "'Government ID, B-Form, student card or passport photo page'",
}
for old, new in replacements.items():
    if old not in text:
        raise RuntimeError(f'v3.8 verification label missing: {old}')
    text = text.replace(old, new, 1)

intro_old = "                const SizedBox(height: 16),\n                DropdownButtonFormField<String>("
intro_new = r'''                const SizedBox(height: 8),
                Container(
                  padding: const EdgeInsets.all(13),
                  decoration: BoxDecoration(
                    color: AppColors.blue.withValues(alpha: .07),
                    borderRadius: BorderRadius.circular(16),
                    border: Border.all(color: AppColors.blue.withValues(alpha: .14)),
                  ),
                  child: const Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Icon(Icons.shield_outlined, color: AppColors.blue, size: 21),
                      SizedBox(width: 10),
                      Expanded(
                        child: Text(
                          'Use accurate details that match your documents. Your identity files are used only for the verification review.',
                          style: TextStyle(height: 1.35, fontSize: 12.5),
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 16),
                Text('YOUR DETAILS', style: TextStyle(fontSize: 11, fontWeight: FontWeight.w900, letterSpacing: .8, color: AppColors.muted)),
                const SizedBox(height: 9),
                DropdownButtonFormField<String>('''
text = replace_once(text, intro_old, intro_new, 'verification intro grouping')

# Add contextual role guidance immediately below the role selector.
role_tail = "                  onChanged: submitting ? null : (v) => setModal(() => kind = v ?? kind),\n                ),\n                const SizedBox(height: 10),"
role_new = r'''                  onChanged: submitting ? null : (v) => setModal(() => kind = v ?? kind),
                ),
                const SizedBox(height: 8),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 9),
                  decoration: BoxDecoration(
                    color: Theme.of(sheet).colorScheme.surfaceContainerHighest.withValues(alpha: .45),
                    borderRadius: BorderRadius.circular(13),
                  ),
                  child: Row(
                    children: [
                      const Icon(Icons.info_outline_rounded, size: 18, color: AppColors.blue),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          kind == 'student'
                              ? 'Student verification checks identity and current education evidence.'
                              : kind == 'teacher'
                                  ? 'Teacher verification also checks your role, subjects and institution evidence.'
                                  : 'Institute verification checks registration, official identity and organization evidence.',
                          style: const TextStyle(fontSize: 11.5, height: 1.3, color: AppColors.muted),
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 12),'''
text = replace_once(text, role_tail, role_new, 'verification role guidance')

# Visually separate document upload controls from identity fields.
doc_anchor = "                _docPicker(\n                  sheet,\n                  title: 'Identity document *',"
doc_replacement = r'''                const SizedBox(height: 8),
                Text('DOCUMENTS', style: TextStyle(fontSize: 11, fontWeight: FontWeight.w900, letterSpacing: .8, color: AppColors.muted)),
                const SizedBox(height: 9),
                _docPicker(
                  sheet,
                  title: 'Identity document *','''
text = replace_once(text, doc_anchor, doc_replacement, 'verification documents grouping')
w(path, text)


# ---------------------------------------------------------------------------
# 4) Server: one security snapshot action + updated native sign-in identity.
# ---------------------------------------------------------------------------
security_action = r'''if ($action === 'security_snapshot') {
    $currentHash = hash('sha256', mobile_bearer());
    $rows = fetch_all(
        'SELECT token_hash,device_name,created_at,last_seen,expires_at FROM mobile_sessions WHERE user_id=? AND expires_at>NOW() ORDER BY created_at DESC LIMIT 20',
        [$uid]
    );
    $sessions = array_map(static function(array $row) use ($currentHash): array {
        return [
            'session_id' => (string) $row['token_hash'],
            'device' => (string) ($row['device_name'] ?: 'Mobile device'),
            'created_at' => (string) ($row['created_at'] ?? ''),
            'last_seen' => (string) ($row['last_seen'] ?? $row['created_at'] ?? ''),
            'expires_at' => (string) ($row['expires_at'] ?? ''),
            'current' => hash_equals($currentHash, (string) $row['token_hash']),
        ];
    }, $rows);
    mobile_out([
        'settings' => mobile_privacy_snapshot($uid),
        'sessions' => $sessions,
        'api_version' => '3.8',
    ]);
}

'''
for path in ['backend/api/mobile.php', 'flutter/backend/api/mobile.php']:
    text = r(path)
    privacy_marker = "if ($action === 'privacy_get') {\n"
    if "if ($action === 'security_snapshot')" not in text:
        if privacy_marker not in text:
            raise RuntimeError(f'v3.8 privacy marker missing in {path}')
        text = text.replace(privacy_marker, security_action + privacy_marker, 1)
    text = text.replace('TaleemPKApp/3.7', 'TaleemPKApp/3.8')
    w(path, text)

# Release version.
path = 'flutter/pubspec.yaml'
text = r(path)
text = re.sub(r'^version:\s*[^\n]+', 'version: 3.8.0+380', text, count=1, flags=re.M)
w(path, text)

# Final generated-source checks.
chat = r('flutter/lib/screens/chat_screen.dart')
api = r('flutter/lib/core/api_client.dart')
security = r('flutter/lib/screens/security_screen.dart')
profile = r('flutter/lib/screens/profile_screen.dart')
verification = r('flutter/lib/screens/verification_screen.dart')
app_state = r('flutter/lib/core/app_state.dart')
mobile = r('backend/api/mobile.php')
pubspec = r('flutter/pubspec.yaml')
assert "hintText: 'Message...'" in chat
assert 'Icons.attach_file_rounded' in chat
assert 'FocusManager.instance.primaryFocus?.unfocus()' in chat
assert 'height: compactHeight' in chat and 'crossAxisCount: 8' in chat
assert '_mentionSuggestions();' in chat and '_insertMention(member)' in chat
assert 'securitySnapshot()' in api
assert "'action': 'security_snapshot'" in api
assert 'The website API is older than this app.' in security
assert 'Sign out of this device' in security
assert "tooltip: 'Sign out'" in profile
assert 'try {' in app_state and 'await api.clearToken();' in app_state
assert 'Verify your TaleemPK profile' in verification
assert 'CNIC / B-Form / Passport number *' in verification
assert 'DOCUMENTS' in verification and 'YOUR DETAILS' in verification
assert "if ($action === 'security_snapshot')" in mobile
assert "'api_version' => '3.8'" in mobile
assert 'TaleemPKApp/3.8' in mobile
assert 'version: 3.8.0+380' in pubspec
print('TaleemPK v3.8 messenger/security/verification polish applied successfully')
