from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return (ROOT / path).read_text(encoding='utf-8')


def write(path, text):
    p = ROOT / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding='utf-8')


def once(text, old, new, label):
    if old not in text:
        raise RuntimeError(f'v3.6 missing target: {label}')
    return text.replace(old, new, 1)


def replace_function(text, signature, replacement, label):
    start = text.find(signature)
    if start < 0:
        raise RuntimeError(f'v3.6 missing function: {label}')
    brace = text.find('{', start)
    if brace < 0:
        raise RuntimeError(f'v3.6 malformed function: {label}')
    depth = 0
    quote = None
    escape = False
    end = None
    for i in range(brace, len(text)):
        ch = text[i]
        if quote is not None:
            if escape:
                escape = False
            elif ch == '\\':
                escape = True
            elif ch == quote:
                quote = None
            continue
        if ch in ('"', "'"):
            quote = ch
            continue
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    if end is None:
        raise RuntimeError(f'v3.6 unterminated function: {label}')
    return text[:start] + replacement + text[end:]


# ---------------------------------------------------------------------------
# Chat: native public profile instead of opening the website.
# ---------------------------------------------------------------------------
path = 'flutter/lib/screens/chat_screen.dart'
text = read(path)
if "import 'profile_screen.dart';" not in text:
    text = once(text, "import 'call_screen.dart';\n", "import 'call_screen.dart';\nimport 'profile_screen.dart';\n", 'profile screen import')
old = """  Future<void> _openProfile() async {
    final username = widget.conversation.otherUsername;
    if (username.isEmpty) return;
    final uri = Uri.parse(
      'https://taleempk.online/profile.php?u=${Uri.encodeQueryComponent(username)}',
    );
    if (!await launchUrl(uri, mode: LaunchMode.externalApplication) && mounted) {
      showMessage(context, 'Profile could not be opened.');
    }
  }
"""
new = """  Future<void> _openProfile() async {
    if (!mounted || widget.conversation.isGroup) return;
    final username = widget.conversation.otherUsername.trim();
    final userId = widget.conversation.otherId;
    if (username.isEmpty && userId <= 0) {
      showMessage(context, 'This profile is not available.');
      return;
    }
    await Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => PublicProfileScreen(
          username: username,
          userId: userId,
        ),
      ),
    );
  }
"""
text = once(text, old, new, 'native view profile')
write(path, text)


# ---------------------------------------------------------------------------
# Profile editor: Telegram-inspired grouped, compact and clear fields.
# ---------------------------------------------------------------------------
path = 'flutter/lib/screens/profile_screen.dart'
text = read(path)
new_edit = r'''  Future<void> _editProfile(ProfileData p) async {
    final name = TextEditingController(text: p.name);
    final headline = TextEditingController(text: p.headline);
    final bio = TextEditingController(text: p.bio);
    final city = TextEditingController(text: p.city);
    final phone = TextEditingController(text: p.phone);
    final subjects = TextEditingController(text: p.subjects);
    final qualification = TextEditingController(text: p.qualification);
    final experience = TextEditingController(text: p.experience > 0 ? '${p.experience}' : '');
    final institute = TextEditingController(text: p.institute);
    final degree = TextEditingController(text: p.degree);
    final department = TextEditingController(text: p.department);
    final semester = TextEditingController(text: p.semester);
    final teaches = TextEditingController(text: p.teaches);
    final website = TextEditingController(text: p.website);
    var level = p.level;
    var accepting = p.acceptingStudents;
    String? avatarPath, coverPath;
    bool saving = false;

    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      backgroundColor: Colors.transparent,
      builder: (sheet) => StatefulBuilder(
        builder: (sheet, setModal) {
          InputDecoration fieldDecoration(String label, IconData icon, {String? hint}) => InputDecoration(
                labelText: label,
                hintText: hint,
                prefixIcon: Icon(icon, size: 20),
                filled: true,
                fillColor: Theme.of(sheet).colorScheme.surfaceContainerLowest,
                contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 14),
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(14),
                  borderSide: BorderSide(color: Theme.of(sheet).colorScheme.outlineVariant),
                ),
                enabledBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(14),
                  borderSide: BorderSide(color: Theme.of(sheet).colorScheme.outlineVariant.withValues(alpha: .75)),
                ),
              );

          Widget section(String title, List<Widget> children) => Container(
                margin: const EdgeInsets.only(bottom: 14),
                padding: const EdgeInsets.fromLTRB(12, 10, 12, 12),
                decoration: BoxDecoration(
                  color: Theme.of(sheet).colorScheme.surface,
                  borderRadius: BorderRadius.circular(18),
                  border: Border.all(color: Theme.of(sheet).colorScheme.outlineVariant.withValues(alpha: .6)),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Padding(
                      padding: const EdgeInsets.fromLTRB(2, 2, 2, 10),
                      child: Text(
                        title,
                        style: TextStyle(
                          color: Theme.of(sheet).colorScheme.primary,
                          fontSize: 12.5,
                          fontWeight: FontWeight.w900,
                          letterSpacing: .2,
                        ),
                      ),
                    ),
                    ...children,
                  ],
                ),
              );

          Widget gap() => const SizedBox(height: 9);

          return DraggableScrollableSheet(
            initialChildSize: .96,
            minChildSize: .72,
            maxChildSize: .98,
            expand: false,
            builder: (_, controller) => Material(
              color: Theme.of(sheet).scaffoldBackgroundColor,
              borderRadius: const BorderRadius.vertical(top: Radius.circular(26)),
              clipBehavior: Clip.antiAlias,
              child: Column(
                children: [
                  Container(
                    padding: const EdgeInsets.fromLTRB(8, 6, 8, 7),
                    decoration: BoxDecoration(
                      color: Theme.of(sheet).colorScheme.surface,
                      border: Border(bottom: BorderSide(color: Theme.of(sheet).dividerColor.withValues(alpha: .55))),
                    ),
                    child: Row(
                      children: [
                        IconButton(
                          tooltip: 'Close',
                          onPressed: saving ? null : () => Navigator.pop(sheet),
                          icon: const Icon(Icons.close_rounded),
                        ),
                        const SizedBox(width: 4),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text('Edit profile', style: Theme.of(sheet).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w900)),
                              Text('Keep your learning identity up to date', style: TextStyle(fontSize: 11.5, color: Theme.of(sheet).colorScheme.onSurfaceVariant)),
                            ],
                          ),
                        ),
                        FilledButton(
                          onPressed: saving
                              ? null
                              : () async {
                                  if (name.text.trim().length < 3) {
                                    showMessage(sheet, 'Enter your full name.');
                                    return;
                                  }
                                  setModal(() => saving = true);
                                  try {
                                    await social.updateProfile(
                                      fields: {
                                        'name': name.text.trim(),
                                        'headline': headline.text.trim(),
                                        'bio': bio.text.trim(),
                                        'city': city.text.trim(),
                                        'phone': phone.text.trim(),
                                        'level': level,
                                        'institute': institute.text.trim(),
                                        'degree': degree.text.trim(),
                                        'department': department.text.trim(),
                                        'semester': semester.text.trim(),
                                        'subjects': subjects.text.trim(),
                                        'qualification': qualification.text.trim(),
                                        'experience': experience.text.trim(),
                                        'teaches': teaches.text.trim(),
                                        'website': website.text.trim(),
                                        'accepting_students': accepting ? '1' : '0',
                                      },
                                      avatarPath: avatarPath,
                                      coverPath: coverPath,
                                    );
                                    await AppScope.of(context).refreshSession();
                                    if (sheet.mounted) Navigator.pop(sheet);
                                    await _load(refresh: true);
                                  } catch (e) {
                                    if (sheet.mounted) {
                                      setModal(() => saving = false);
                                      showMessage(sheet, apiMessage(e));
                                    }
                                  }
                                },
                          style: FilledButton.styleFrom(
                            minimumSize: const Size(72, 40),
                            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                          ),
                          child: saving
                              ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2))
                              : const Text('Save'),
                        ),
                      ],
                    ),
                  ),
                  Expanded(
                    child: ListView(
                      controller: controller,
                      keyboardDismissBehavior: ScrollViewKeyboardDismissBehavior.onDrag,
                      padding: EdgeInsets.fromLTRB(14, 14, 14, MediaQuery.viewInsetsOf(sheet).bottom + 24),
                      children: [
                        section('PROFILE PHOTO & COVER', [
                          Row(
                            children: [
                              Expanded(
                                child: OutlinedButton.icon(
                                  style: OutlinedButton.styleFrom(minimumSize: const Size(0, 46), shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14))),
                                  onPressed: saving ? null : () async {
                                    final image = await ImagePicker().pickImage(source: ImageSource.gallery, imageQuality: 90, maxWidth: 1600);
                                    if (image != null && sheet.mounted) setModal(() => avatarPath = image.path);
                                  },
                                  icon: const Icon(Icons.account_circle_outlined, size: 19),
                                  label: Text(avatarPath == null ? 'Profile photo' : 'Photo selected'),
                                ),
                              ),
                              const SizedBox(width: 8),
                              Expanded(
                                child: OutlinedButton.icon(
                                  style: OutlinedButton.styleFrom(minimumSize: const Size(0, 46), shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14))),
                                  onPressed: saving ? null : () async {
                                    final image = await ImagePicker().pickImage(source: ImageSource.gallery, imageQuality: 90, maxWidth: 2200);
                                    if (image != null && sheet.mounted) setModal(() => coverPath = image.path);
                                  },
                                  icon: const Icon(Icons.panorama_outlined, size: 19),
                                  label: Text(coverPath == null ? 'Cover photo' : 'Cover selected'),
                                ),
                              ),
                            ],
                          ),
                        ]),
                        section('BASIC INFORMATION', [
                          TextField(controller: name, textCapitalization: TextCapitalization.words, decoration: fieldDecoration('Full name', Icons.person_outline_rounded)),
                          gap(),
                          TextField(controller: headline, maxLength: 160, decoration: fieldDecoration('Headline', Icons.short_text_rounded, hint: 'e.g. Computer Science Student')),
                          gap(),
                          TextField(controller: bio, minLines: 3, maxLines: 5, maxLength: 480, decoration: fieldDecoration('About you', Icons.notes_rounded, hint: 'Tell people about yourself')),
                          gap(),
                          TextField(controller: city, textCapitalization: TextCapitalization.words, decoration: fieldDecoration('City', Icons.location_on_outlined)),
                          gap(),
                          TextField(controller: phone, keyboardType: TextInputType.phone, decoration: fieldDecoration('Phone', Icons.phone_outlined, hint: 'Optional')),
                        ]),
                        section('EDUCATION', [
                          DropdownButtonFormField<String>(
                            initialValue: ['', 'school', 'college', 'university'].contains(level) ? level : '',
                            decoration: fieldDecoration('Education level', Icons.school_outlined),
                            items: const [
                              DropdownMenuItem(value: '', child: Text('Not specified')),
                              DropdownMenuItem(value: 'school', child: Text('School')),
                              DropdownMenuItem(value: 'college', child: Text('College')),
                              DropdownMenuItem(value: 'university', child: Text('University')),
                            ],
                            onChanged: saving ? null : (v) => setModal(() => level = v ?? ''),
                          ),
                          gap(),
                          TextField(controller: institute, textCapitalization: TextCapitalization.words, decoration: fieldDecoration('Institute', Icons.account_balance_outlined)),
                          gap(),
                          TextField(controller: degree, decoration: fieldDecoration('Degree / class', Icons.workspace_premium_outlined)),
                          gap(),
                          TextField(controller: department, decoration: fieldDecoration('Department', Icons.apartment_outlined)),
                          gap(),
                          TextField(controller: semester, decoration: fieldDecoration('Semester', Icons.calendar_view_month_outlined)),
                          gap(),
                          TextField(controller: subjects, decoration: fieldDecoration('Subjects', Icons.menu_book_outlined)),
                        ]),
                        section('EXPERIENCE & LINKS', [
                          TextField(controller: qualification, decoration: fieldDecoration('Qualification', Icons.verified_outlined)),
                          gap(),
                          TextField(controller: experience, keyboardType: TextInputType.number, decoration: fieldDecoration('Experience (years)', Icons.timeline_rounded)),
                          gap(),
                          TextField(controller: teaches, decoration: fieldDecoration('Teaches / specialization', Icons.psychology_outlined)),
                          gap(),
                          TextField(controller: website, keyboardType: TextInputType.url, decoration: fieldDecoration('Website', Icons.language_rounded, hint: 'https://...')),
                          if (p.role == 'teacher' || p.role == 'institute') ...[
                            gap(),
                            SwitchListTile.adaptive(
                              contentPadding: const EdgeInsets.symmetric(horizontal: 2),
                              value: accepting,
                              onChanged: saving ? null : (v) => setModal(() => accepting = v),
                              title: const Text('Currently taking students', style: TextStyle(fontWeight: FontWeight.w700)),
                              subtitle: const Text('Show learners that you are accepting new students.'),
                            ),
                          ],
                        ]),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          );
        },
      ),
    );

    for (final c in [name, headline, bio, city, phone, subjects, qualification, experience, institute, degree, department, semester, teaches, website]) {
      c.dispose();
    }
  }'''
text = replace_function(text, '  Future<void> _editProfile(ProfileData p) async {', new_edit, 'profile editor')
write(path, text)


# ---------------------------------------------------------------------------
# Home shell: professional bottom navigation + lifecycle-aware polling.
# ---------------------------------------------------------------------------
path = 'flutter/lib/screens/home_shell.dart'
text = read(path)
text = once(text, 'class _HomeShellState extends State<HomeShell> {', 'class _HomeShellState extends State<HomeShell> with WidgetsBindingObserver {', 'lifecycle observer')
text = once(text, """    super.initState();
    callWatch = Timer.periodic(
""", """    super.initState();
    WidgetsBinding.instance.addObserver(this);
    callWatch = Timer.periodic(
""", 'register lifecycle observer')
text = once(text, """  @override
  void dispose() {
    callWatch?.cancel();
    notificationWatch?.cancel();
    super.dispose();
  }
""", """  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) {
      callWatch?.cancel();
      callWatch = Timer.periodic(const Duration(seconds: 4), (_) => _watchIncomingCall());
      notificationWatch?.cancel();
      notificationWatch = Timer.periodic(const Duration(seconds: 6), (_) => _watchNotifications());
      _watchIncomingCall();
      _watchNotifications(seedOnly: true);
    } else if (state == AppLifecycleState.inactive ||
        state == AppLifecycleState.paused ||
        state == AppLifecycleState.detached ||
        state == AppLifecycleState.hidden) {
      callWatch?.cancel();
      notificationWatch?.cancel();
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    callWatch?.cancel();
    notificationWatch?.cancel();
    super.dispose();
  }
""", 'lifecycle polling')
old_nav_start = text.find('        bottomNavigationBar: NavigationBar(')
old_nav_end = text.find('        ),\n      ),\n    );', old_nav_start)
if old_nav_start < 0 or old_nav_end < 0:
    raise RuntimeError('v3.6 bottom navigation block not found')
old_nav_end += len('        ),\n')
new_nav = r'''        bottomNavigationBar: SafeArea(
          top: false,
          child: Container(
            margin: const EdgeInsets.fromLTRB(10, 0, 10, 8),
            decoration: BoxDecoration(
              color: Theme.of(context).colorScheme.surface,
              borderRadius: BorderRadius.circular(22),
              border: Border.all(color: Theme.of(context).colorScheme.outlineVariant.withValues(alpha: .55)),
              boxShadow: const [BoxShadow(color: Color(0x18000000), blurRadius: 18, offset: Offset(0, 7))],
            ),
            clipBehavior: Clip.antiAlias,
            child: NavigationBar(
              height: 68,
              elevation: 0,
              backgroundColor: Colors.transparent,
              indicatorShape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
              selectedIndex: index,
              onDestinationSelected: (value) => setState(() => index = value),
              destinations: [
                NavigationDestination(
                  icon: Badge(
                    isLabelVisible: unreadActivity > 0,
                    label: Text(unreadActivity > 99 ? '99+' : '$unreadActivity'),
                    child: const Icon(Icons.home_outlined),
                  ),
                  selectedIcon: Badge(
                    isLabelVisible: unreadActivity > 0,
                    label: Text(unreadActivity > 99 ? '99+' : '$unreadActivity'),
                    child: const Icon(Icons.home_rounded),
                  ),
                  label: 'Home',
                ),
                const NavigationDestination(
                  icon: Icon(Icons.dynamic_feed_outlined),
                  selectedIcon: Icon(Icons.dynamic_feed_rounded),
                  label: 'Feed',
                ),
                NavigationDestination(
                  icon: Badge(
                    isLabelVisible: unreadChats > 0,
                    label: Text(unreadChats > 99 ? '99+' : '$unreadChats'),
                    child: const Icon(Icons.chat_bubble_outline_rounded),
                  ),
                  selectedIcon: Badge(
                    isLabelVisible: unreadChats > 0,
                    label: Text(unreadChats > 99 ? '99+' : '$unreadChats'),
                    child: const Icon(Icons.chat_bubble_rounded),
                  ),
                  label: 'Chat',
                ),
                NavigationDestination(
                  icon: UserAvatar(url: user.avatar, name: user.name, radius: 12),
                  selectedIcon: Container(
                    padding: const EdgeInsets.all(2),
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      border: Border.all(color: Theme.of(context).colorScheme.primary, width: 2),
                    ),
                    child: UserAvatar(url: user.avatar, name: user.name, radius: 12),
                  ),
                  label: 'Profile',
                ),
              ],
            ),
          ),
        ),
'''
text = text[:old_nav_start] + new_nav + text[old_nav_end:]
write(path, text)


# ---------------------------------------------------------------------------
# Home dashboard: cleaner hierarchy, hero, quick actions and cards.
# ---------------------------------------------------------------------------
path = 'flutter/lib/screens/home_screen.dart'
text = read(path)
new_home_build = r'''  @override
  Widget build(BuildContext context) {
    final state = AppScope.of(context), data = state.bootstrap!, user = data.user;
    final shortcuts = data.shortcuts.where((s) => !['feed.php', 'chat.php'].contains(s.route)).toList();
    return Scaffold(
      appBar: PremiumAppBar(
        title: 'Hello, ${user.name.split(' ').first}',
        subtitle: 'Your learning space is ready',
        actions: [
          IconButton.filledTonal(
            tooltip: 'Notifications',
            onPressed: () => Navigator.push(
              context,
              MaterialPageRoute(builder: (_) => const ModuleScreen(module: 'notifications')),
            ),
            icon: const Badge(child: Icon(Icons.notifications_none_rounded, size: 21)),
          ),
          const SizedBox(width: 10),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: state.refreshSession,
        child: ListView(
          physics: const AlwaysScrollableScrollPhysics(parent: BouncingScrollPhysics()),
          padding: const EdgeInsets.fromLTRB(16, 8, 16, 30),
          children: [
            _hero(context, user),
            const SizedBox(height: 16),
            Row(
              children: [
                Expanded(child: _miniAction(context, Icons.quiz_outlined, 'Practice', 'Quick quiz', 'quizzes')),
                const SizedBox(width: 10),
                Expanded(child: _miniAction(context, Icons.event_note_outlined, 'Plan', 'Study planner', 'planner')),
              ],
            ),
            const SizedBox(height: 22),
            Row(
              children: [
                Expanded(
                  child: Text('Explore TaleemPK', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w900, color: Theme.of(context).colorScheme.onSurface)),
                ),
                Text('${shortcuts.length} tools', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w700, color: Theme.of(context).colorScheme.onSurfaceVariant)),
              ],
            ),
            const SizedBox(height: 11),
            for (final s in shortcuts)
              Padding(
                padding: const EdgeInsets.only(bottom: 9),
                child: _shortcut(context, s),
              ),
            const SizedBox(height: 6),
            _learningPromise(context),
          ],
        ),
      ),
    );
  }

  Widget _miniAction(BuildContext context, IconData icon, String title, String subtitle, String module) => Material(
        color: Theme.of(context).colorScheme.surface,
        borderRadius: BorderRadius.circular(18),
        child: InkWell(
          borderRadius: BorderRadius.circular(18),
          onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => ModuleScreen(module: module))),
          child: Container(
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(18),
              border: Border.all(color: Theme.of(context).colorScheme.outlineVariant.withValues(alpha: .6)),
            ),
            child: Row(
              children: [
                Container(
                  width: 40,
                  height: 40,
                  decoration: BoxDecoration(color: Theme.of(context).colorScheme.primary.withValues(alpha: .10), borderRadius: BorderRadius.circular(13)),
                  child: Icon(icon, color: Theme.of(context).colorScheme.primary, size: 21),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(title, style: const TextStyle(fontWeight: FontWeight.w900, fontSize: 13.5)),
                      const SizedBox(height: 2),
                      Text(subtitle, maxLines: 1, overflow: TextOverflow.ellipsis, style: TextStyle(fontSize: 10.5, color: Theme.of(context).colorScheme.onSurfaceVariant)),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
      );'''
text = replace_function(text, '  @override\n  Widget build(BuildContext context) {', new_home_build, 'home build')
# More premium hero without adding new data dependencies.
old_hero = """  Widget _hero(BuildContext context, User user) => Container(
    padding: const EdgeInsets.all(22),
"""
new_hero = """  Widget _hero(BuildContext context, User user) => Container(
    padding: const EdgeInsets.fromLTRB(20, 20, 18, 20),
"""
text = once(text, old_hero, new_hero, 'home hero padding')
text = once(text, '      borderRadius: BorderRadius.circular(26),', '      borderRadius: BorderRadius.circular(24),', 'home hero radius')
write(path, text)


# ---------------------------------------------------------------------------
# Splash/loading: quieter premium hierarchy and clearer loading status.
# ---------------------------------------------------------------------------
path = 'flutter/lib/main.dart'
text = read(path)
new_splash_build = r'''  @override
  Widget build(BuildContext context) => Scaffold(
    body: Container(
      decoration: const BoxDecoration(
        gradient: LinearGradient(
          colors: [Color(0xFF07152F), Color(0xFF142B63), Color(0xFF3E2D92)],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
      ),
      child: Stack(
        children: [
          Positioned(top: -120, right: -85, child: _orb(270, const Color(0x263AD7F0))),
          Positioned(bottom: -130, left: -100, child: _orb(300, const Color(0x267D63FF))),
          Positioned.fill(
            child: SafeArea(
              child: Center(
                child: FadeTransition(
                  opacity: CurvedAnimation(parent: _controller, curve: Curves.easeOut),
                  child: ScaleTransition(
                    scale: Tween(begin: .92, end: 1.0).animate(CurvedAnimation(parent: _controller, curve: Curves.easeOutCubic)),
                    child: Container(
                      margin: const EdgeInsets.symmetric(horizontal: 34),
                      padding: const EdgeInsets.fromLTRB(26, 30, 26, 24),
                      decoration: BoxDecoration(
                        color: Colors.white.withValues(alpha: .07),
                        borderRadius: BorderRadius.circular(30),
                        border: Border.all(color: Colors.white.withValues(alpha: .12)),
                      ),
                      child: const Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          BrandMark(size: 78, light: true),
                          SizedBox(height: 20),
                          Text(
                            'Learn today. Lead tomorrow.',
                            textAlign: TextAlign.center,
                            style: TextStyle(color: Color(0xE6FFFFFF), fontSize: 15, fontWeight: FontWeight.w600, letterSpacing: .1),
                          ),
                          SizedBox(height: 8),
                          Text(
                            'Preparing your learning space',
                            style: TextStyle(color: Color(0x9FFFFFFF), fontSize: 12.5),
                          ),
                          SizedBox(height: 26),
                          SizedBox(
                            width: 150,
                            child: LinearProgressIndicator(
                              minHeight: 3,
                              borderRadius: BorderRadius.all(Radius.circular(99)),
                              backgroundColor: Color(0x30FFFFFF),
                              color: Colors.white,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
              ),
            ),
          ),
        ],
      ),
    ),
  );'''
text = replace_function(text, '  @override\n  Widget build(BuildContext context) => Scaffold(', new_splash_build, 'splash build')
write(path, text)


# Version bump.
path = 'flutter/pubspec.yaml'
text = read(path)
import re
text, count = re.subn(r'^version:\s*[^\n]+', 'version: 3.6.0+360', text, count=1, flags=re.M)
if count != 1:
    raise RuntimeError('v3.6 could not update pubspec version')
write(path, text)

print('TaleemPK v3.6 UI/navigation polish applied successfully')
