from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def r(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def w(path: str, text: str) -> None:
    p = ROOT / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding='utf-8')


def once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f'v4.5 missing target: {label}')
    return text.replace(old, new, 1)


def replace_between(text: str, start: str, end: str, replacement: str, label: str) -> str:
    s = text.find(start)
    if s < 0:
        raise RuntimeError(f'v4.5 missing start: {label}')
    e = text.find(end, s)
    if e < 0:
        raise RuntimeError(f'v4.5 missing end: {label}')
    return text[:s] + replacement + text[e:]


def block_bounds(text: str, signature: str):
    start = text.find(signature)
    if start < 0:
        raise RuntimeError(f'v4.5 missing block: {signature}')
    brace = text.find('{', start)
    if brace < 0:
        raise RuntimeError(f'v4.5 malformed block: {signature}')
    depth = 0
    quote = None
    escape = False
    line_comment = False
    block_comment = False
    i = brace
    while i < len(text):
        ch = text[i]
        nxt = text[i + 1] if i + 1 < len(text) else ''
        if line_comment:
            if ch == '\n':
                line_comment = False
            i += 1
            continue
        if block_comment:
            if ch == '*' and nxt == '/':
                block_comment = False
                i += 2
                continue
            i += 1
            continue
        if quote is not None:
            if escape:
                escape = False
            elif ch == '\\':
                escape = True
            elif ch == quote:
                quote = None
            i += 1
            continue
        if ch == '/' and nxt == '/':
            line_comment = True
            i += 2
            continue
        if ch == '/' and nxt == '*':
            block_comment = True
            i += 2
            continue
        if ch in ('\"', "'"):
            quote = ch
            i += 1
            continue
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                return start, i + 1
        i += 1
    raise RuntimeError(f'v4.5 unterminated block: {signature}')


def replace_block(text: str, signature: str, replacement: str) -> str:
    s, e = block_bounds(text, signature)
    return text[:s] + replacement + text[e:]


# ---------------------------------------------------------------------------
# 1) Social API: follower/following lists with server-enforced privacy.
# ---------------------------------------------------------------------------
path = 'flutter/lib/core/social_api.dart'
text = r(path)
if 'profileConnections(' not in text:
    marker = '  Future<bool> toggleFollow(int userId) async {'
    method = r'''  Future<Map<String, dynamic>> profileConnections(
    int userId,
    String kind, {
    int before = 0,
    int limit = 30,
  }) => _request({
        'action': 'profile_connections',
        'user_id': '$userId',
        'kind': kind,
        'before': '$before',
        'limit': '${limit.clamp(12, 50)}',
      });

'''
    text = once(text, marker, method + marker, 'social profile connections method')
w(path, text)


# ---------------------------------------------------------------------------
# 2) Profile: premium identity header, tappable follower/following stats, and
# a native paginated people list. Hidden connections remain hidden server-side.
# ---------------------------------------------------------------------------
path = 'flutter/lib/screens/profile_screen.dart'
text = r(path)
header_start = '  Widget _header(ProfileData p) => Column('
chip_marker = '\n\n  Widget _chip('
header = r'''  Widget _header(ProfileData p) => Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          SizedBox(
            height: 178,
            child: Stack(
              clipBehavior: Clip.none,
              children: [
                Positioned.fill(
                  bottom: 42,
                  child: Container(
                    decoration: BoxDecoration(
                      gradient: const LinearGradient(
                        colors: [AppColors.navy, Color(0xFF3157E8), Color(0xFF7657EF)],
                        begin: Alignment.topLeft,
                        end: Alignment.bottomRight,
                      ),
                      image: p.cover != null
                          ? DecorationImage(
                              image: CachedNetworkImageProvider(p.cover!),
                              fit: BoxFit.cover,
                            )
                          : null,
                    ),
                    child: DecoratedBox(
                      decoration: BoxDecoration(
                        gradient: LinearGradient(
                          colors: [
                            Colors.black.withValues(alpha: .06),
                            Colors.black.withValues(alpha: .20),
                          ],
                          begin: Alignment.topCenter,
                          end: Alignment.bottomCenter,
                        ),
                      ),
                    ),
                  ),
                ),
                Positioned(
                  left: 20,
                  bottom: 2,
                  child: Container(
                    padding: const EdgeInsets.all(4),
                    decoration: BoxDecoration(
                      color: Theme.of(context).scaffoldBackgroundColor,
                      shape: BoxShape.circle,
                      boxShadow: const [
                        BoxShadow(
                          color: Color(0x1A071426),
                          blurRadius: 18,
                          offset: Offset(0, 7),
                        ),
                      ],
                    ),
                    child: UserAvatar(url: p.avatar, name: p.name, radius: 45),
                  ),
                ),
                if (p.verified)
                  Positioned(
                    left: 91,
                    bottom: 9,
                    child: Container(
                      padding: const EdgeInsets.all(5),
                      decoration: BoxDecoration(
                        color: AppColors.blue,
                        shape: BoxShape.circle,
                        border: Border.all(
                          color: Theme.of(context).scaffoldBackgroundColor,
                          width: 2.5,
                        ),
                      ),
                      child: const Icon(Icons.verified_rounded, color: Colors.white, size: 17),
                    ),
                  ),
              ],
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 6, 20, 0),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Text(
                        p.name,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(
                          fontSize: 24,
                          fontWeight: FontWeight.w900,
                          letterSpacing: -.55,
                        ),
                      ),
                    ),
                    if (p.verified) ...[
                      const SizedBox(width: 6),
                      const Icon(Icons.verified_rounded, color: AppColors.blue, size: 20),
                    ],
                  ],
                ),
                const SizedBox(height: 2),
                Text(
                  '@${p.username}',
                  style: TextStyle(
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                const SizedBox(height: 10),
                Wrap(
                  spacing: 7,
                  runSpacing: 7,
                  children: [
                    _chip(p.role.toUpperCase(), AppColors.blue),
                    if (p.level.isNotEmpty) _chip(p.level, AppColors.violet),
                    if (p.classGrade.isNotEmpty) _chip(p.classGrade, AppColors.violet),
                    if (p.city.isNotEmpty) _chip(p.city, AppColors.success),
                    if (p.followsYou) _chip('Follows you', AppColors.success),
                  ],
                ),
              ],
            ),
          ),
          Container(
            margin: const EdgeInsets.fromLTRB(18, 16, 18, 0),
            padding: const EdgeInsets.symmetric(vertical: 8),
            decoration: BoxDecoration(
              color: Theme.of(context).colorScheme.surface,
              borderRadius: BorderRadius.circular(20),
              border: Border.all(
                color: Theme.of(context).colorScheme.outlineVariant.withValues(alpha: .55),
              ),
              boxShadow: const [
                BoxShadow(
                  color: Color(0x08071426),
                  blurRadius: 18,
                  offset: Offset(0, 6),
                ),
              ],
            ),
            child: Row(
              children: [
                _stat('${p.posts}', 'Posts'),
                _stat(
                  '${p.followers}',
                  'Followers',
                  onTap: () => _openConnections(p, 'followers'),
                ),
                _stat(
                  '${p.following}',
                  'Following',
                  onTap: () => _openConnections(p, 'following'),
                ),
                if ((p.role == 'teacher' || p.role == 'institute') && p.ratings > 0)
                  _stat(p.rating.toStringAsFixed(1), '★ ${p.ratings}'),
              ],
            ),
          ),
        ],
      );

  Widget _stat(
    String value,
    String label, {
    VoidCallback? onTap,
  }) => Expanded(
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(15),
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 8),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  value,
                  style: const TextStyle(fontWeight: FontWeight.w900, fontSize: 18),
                ),
                const SizedBox(height: 2),
                Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Flexible(
                      child: Text(
                        label,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(
                          color: AppColors.muted,
                          fontSize: 11.5,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ),
                    if (onTap != null) ...[
                      const SizedBox(width: 1),
                      const Icon(Icons.chevron_right_rounded, size: 14, color: AppColors.muted),
                    ],
                  ],
                ),
              ],
            ),
          ),
        ),
      );

  Future<void> _openConnections(ProfileData p, String kind) async {
    if (!mounted) return;
    await Navigator.of(context).push(
      premiumRoute<void>(
        builder: (_) => _ProfileConnectionsScreen(
          userId: p.id,
          ownerName: p.name,
          kind: kind,
        ),
      ),
    );
  }'''
text = replace_between(text, header_start, chip_marker, header, 'profile header/stat block')

if 'class _ProfileConnectionsScreen extends StatefulWidget' not in text:
    connections_screen = r'''

class _ProfileConnectionsScreen extends StatefulWidget {
  const _ProfileConnectionsScreen({
    required this.userId,
    required this.ownerName,
    required this.kind,
  });

  final int userId;
  final String ownerName;
  final String kind;

  @override
  State<_ProfileConnectionsScreen> createState() => _ProfileConnectionsScreenState();
}

class _ProfileConnectionsScreenState extends State<_ProfileConnectionsScreen> {
  final List<Map<String, dynamic>> people = <Map<String, dynamic>>[];
  bool loading = true;
  bool loadingMore = false;
  bool hasMore = false;
  bool visible = true;
  int before = 0;
  String? error;

  SocialApi get social => SocialApi(AppScope.of(context).api);

  @override
  void initState() {
    super.initState();
    _load(reset: true);
  }

  Future<void> _load({bool reset = false}) async {
    if (reset) {
      if (mounted) {
        setState(() {
          loading = true;
          error = null;
          before = 0;
          hasMore = false;
          visible = true;
          people.clear();
        });
      }
    } else {
      if (loadingMore || !hasMore) return;
      setState(() => loadingMore = true);
    }

    try {
      final data = await social.profileConnections(
        widget.userId,
        widget.kind,
        before: reset ? 0 : before,
      );
      if (!mounted) return;
      final next = smList(data['people']).map((e) => smMap(e)).toList();
      final seen = people.map((e) => smInt(e['id'])).toSet();
      setState(() {
        visible = !data.containsKey('visible') || smBool(data['visible']);
        if (reset) people.clear();
        for (final person in next) {
          final id = smInt(person['id']);
          if (id > 0 && !seen.contains(id)) {
            people.add(person);
            seen.add(id);
          }
        }
        hasMore = smBool(data['has_more']);
        before = smInt(data['next_before']);
        loading = false;
        loadingMore = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        error = apiMessage(e);
        loading = false;
        loadingMore = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final followers = widget.kind == 'followers';
    return Scaffold(
      appBar: PremiumAppBar(
        title: followers ? 'Followers' : 'Following',
        subtitle: widget.ownerName,
      ),
      body: loading
          ? const Center(child: CircularProgressIndicator())
          : error != null
              ? ErrorView(message: error!, retry: () => _load(reset: true))
              : !visible
                  ? const EmptyView(
                      icon: Icons.lock_outline_rounded,
                      title: 'Connections are private',
                      message: 'This member has chosen not to show their followers and following lists.',
                    )
                  : people.isEmpty
                      ? EmptyView(
                          icon: followers ? Icons.people_outline_rounded : Icons.person_search_rounded,
                          title: followers ? 'No followers yet' : 'Not following anyone yet',
                          message: followers
                              ? 'New followers will appear here.'
                              : 'People followed by this member will appear here.',
                        )
                      : RefreshIndicator(
                          onRefresh: () => _load(reset: true),
                          child: ListView.separated(
                            physics: const AlwaysScrollableScrollPhysics(),
                            padding: const EdgeInsets.fromLTRB(14, 12, 14, 28),
                            itemCount: people.length + (hasMore ? 1 : 0),
                            separatorBuilder: (_, __) => const SizedBox(height: 8),
                            itemBuilder: (context, index) {
                              if (index >= people.length) {
                                if (!loadingMore) {
                                  WidgetsBinding.instance.addPostFrameCallback((_) => _load());
                                }
                                return const Padding(
                                  padding: EdgeInsets.all(16),
                                  child: Center(child: CircularProgressIndicator(strokeWidth: 2.2)),
                                );
                              }
                              final person = people[index];
                              final id = smInt(person['id']);
                              final name = '${person['name'] ?? 'TaleemPK member'}';
                              final username = '${person['username'] ?? ''}';
                              final role = '${person['role'] ?? 'student'}';
                              final avatar = smNullable(person['avatar']);
                              final verified = smBool(person['verified']);
                              return Material(
                                color: Theme.of(context).colorScheme.surface,
                                borderRadius: BorderRadius.circular(18),
                                child: InkWell(
                                  borderRadius: BorderRadius.circular(18),
                                  onTap: id <= 0
                                      ? null
                                      : () => Navigator.of(context).push(
                                            premiumRoute<void>(
                                              builder: (_) => PublicProfileScreen(userId: id),
                                            ),
                                          ),
                                  child: Padding(
                                    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 11),
                                    child: Row(
                                      children: [
                                        UserAvatar(url: avatar, name: name, radius: 23),
                                        const SizedBox(width: 12),
                                        Expanded(
                                          child: Column(
                                            crossAxisAlignment: CrossAxisAlignment.start,
                                            children: [
                                              Row(
                                                children: [
                                                  Flexible(
                                                    child: Text(
                                                      name,
                                                      maxLines: 1,
                                                      overflow: TextOverflow.ellipsis,
                                                      style: const TextStyle(fontWeight: FontWeight.w800),
                                                    ),
                                                  ),
                                                  if (verified) ...[
                                                    const SizedBox(width: 4),
                                                    const Icon(Icons.verified_rounded, size: 16, color: AppColors.blue),
                                                  ],
                                                ],
                                              ),
                                              const SizedBox(height: 2),
                                              Text(
                                                [if (username.isNotEmpty) '@$username', role].join(' · '),
                                                maxLines: 1,
                                                overflow: TextOverflow.ellipsis,
                                                style: const TextStyle(color: AppColors.muted, fontSize: 12.5),
                                              ),
                                            ],
                                          ),
                                        ),
                                        const Icon(Icons.chevron_right_rounded, color: AppColors.muted),
                                      ],
                                    ),
                                  ),
                                ),
                              );
                            },
                          ),
                        ),
    );
  }
}
'''
    text += connections_screen
w(path, text)


# ---------------------------------------------------------------------------
# 3) Privacy screen: dedicated connection-list visibility toggle.
# ---------------------------------------------------------------------------
path = 'flutter/lib/screens/security_screen.dart'
text = r(path)
if "value: _bool(s['show_connections'], true)" not in text:
    marker = "            SwitchListTile.adaptive(\n              contentPadding: EdgeInsets.zero,\n              value: _bool(s['show_receipts'], true),"
    connection_toggle = r'''            SwitchListTile.adaptive(
              contentPadding: EdgeInsets.zero,
              value: _bool(s['show_connections'], true),
              onChanged: saving ? null : (v) => _savePrivacy('show_connections', v ? '1' : '0'),
              title: const Text('Show followers & following'),
              subtitle: const Text('Allow other members to open your followers and following lists.'),
            ),
'''
    text = once(text, marker, connection_toggle + marker, 'connections privacy switch')
w(path, text)


# ---------------------------------------------------------------------------
# 4) Main API privacy setting: keep it separate from the users table so this
# feature deploys safely on existing TaleemPK databases without a migration.
# ---------------------------------------------------------------------------
privacy_snapshot = r'''function mobile_privacy_snapshot(int $uid): array
{
    $row = fetch_one('SELECT profile_privacy,show_online,searchable,allow_dm,allow_comments,allow_calls,show_receipts,show_typing FROM users WHERE id=? LIMIT 1', [$uid]);
    if (!$row) { mobile_error('This account is not available.', 404); }
    mobile_connections_privacy_table();
    $connections = fetch_one('SELECT show_connections FROM mobile_profile_privacy WHERE user_id=? LIMIT 1', [$uid]);
    return [
        'profile_privacy' => (string) ($row['profile_privacy'] ?? 'public'),
        'show_online' => (int) ($row['show_online'] ?? 1) === 1,
        'searchable' => (int) ($row['searchable'] ?? 1) === 1,
        'allow_dm' => (string) ($row['allow_dm'] ?? 'everyone'),
        'allow_comments' => (string) ($row['allow_comments'] ?? 'everyone'),
        'allow_calls' => (string) ($row['allow_calls'] ?? 'everyone'),
        'show_receipts' => (int) ($row['show_receipts'] ?? 1) === 1,
        'show_typing' => (int) ($row['show_typing'] ?? 1) === 1,
        'show_connections' => !$connections || (int) ($connections['show_connections'] ?? 1) === 1,
    ];
}'''
privacy_update = r'''if ($action === 'privacy_update') {
    $key = strtolower(trim((string) ($_POST['key'] ?? '')));
    $value = strtolower(trim((string) ($_POST['value'] ?? '')));
    $choices = [
        'profile_privacy' => ['public','members','private'],
        'allow_dm' => ['everyone','following','nobody'],
        'allow_comments' => ['everyone','followers','nobody'],
        'allow_calls' => ['everyone','following','nobody'],
    ];
    $booleans = ['show_online','searchable','show_receipts','show_typing'];
    if ($key === 'show_connections') {
        if (!in_array($value, ['0','1'], true)) { mobile_error('That privacy option is not valid.'); }
        mobile_connections_privacy_table();
        q('INSERT INTO mobile_profile_privacy(user_id,show_connections) VALUES(?,?) ON DUPLICATE KEY UPDATE show_connections=VALUES(show_connections),updated_at=CURRENT_TIMESTAMP', [$uid,(int)$value]);
    } elseif (isset($choices[$key])) {
        if (!in_array($value, $choices[$key], true)) { mobile_error('That privacy option is not valid.'); }
        q("UPDATE users SET {$key}=? WHERE id=?", [$value,$uid]);
    } elseif (in_array($key, $booleans, true)) {
        if (!in_array($value, ['0','1'], true)) { mobile_error('That privacy option is not valid.'); }
        q("UPDATE users SET {$key}=? WHERE id=?", [(int)$value,$uid]);
    } else {
        mobile_error('That privacy setting is not supported.');
    }
    log_activity($uid, 'privacy_update', 'Updated ' . $key . ' from Android app');
    mobile_out(mobile_privacy_snapshot($uid));
}'''
for path in ['backend/api/mobile.php', 'flutter/backend/api/mobile.php']:
    text = r(path)
    if 'function mobile_connections_privacy_table()' not in text:
        marker = 'function mobile_privacy_snapshot(int $uid): array'
        helper = r'''function mobile_connections_privacy_table(): void
{
    q("CREATE TABLE IF NOT EXISTS mobile_profile_privacy (
        user_id BIGINT UNSIGNED NOT NULL PRIMARY KEY,
        show_connections TINYINT(1) NOT NULL DEFAULT 1,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4");
}

'''
        text = once(text, marker, helper + marker, f'privacy helper in {path}')
    text = replace_block(text, 'function mobile_privacy_snapshot(int $uid): array', privacy_snapshot)
    text = replace_between(
        text,
        "if ($action === 'privacy_update') {",
        "\n\nif ($action === 'sessions') {",
        privacy_update,
        f'privacy update block in {path}',
    )
    w(path, text)


# ---------------------------------------------------------------------------
# 5) Social server: private-by-choice follower/following lists with pagination.
# ---------------------------------------------------------------------------
connections_action = r'''if($action==='profile_connections'){
    $targetId=max(1,(int)($_POST['user_id']??0));
    $kind=strtolower(trim((string)($_POST['kind']??'followers')));
    if(!in_array($kind,['followers','following'],true))$kind='followers';
    $before=max(0,(int)($_POST['before']??0));
    $limit=max(12,min(50,(int)($_POST['limit']??30)));
    $target=fetch_one("SELECT id,name,profile_privacy,status FROM users WHERE id=? LIMIT 1",[$targetId]);
    if(!$target||(string)$target['status']!=='active')mobile_error('That account is not available.',404);
    $isMe=$targetId===$uid;
    $blocked=!$isMe&&(bool)fetch_one('SELECT id FROM blocks WHERE (user_id=? AND blocked_id=?) OR (user_id=? AND blocked_id=?) LIMIT 1',[$uid,$targetId,$targetId,$uid]);
    mobile_social_connections_table();
    $privacy=fetch_one('SELECT show_connections FROM mobile_profile_privacy WHERE user_id=? LIMIT 1',[$targetId]);
    $shares=!$privacy||(int)($privacy['show_connections']??1)===1;
    $profilePrivate=(string)($target['profile_privacy']??'public')==='private'&&!$isMe&&!is_admin();
    $visible=!$blocked&&!$profilePrivate&&($isMe||is_admin()||$shares);
    if(!$visible)mobile_out(['visible'=>false,'people'=>[],'has_more'=>false,'next_before'=>0]);

    $params=[$targetId];
    if($kind==='followers'){
        $where='f.following_id=?';
        if($before>0){$where.=' AND f.id<?';$params[]=$before;}
        $sql="SELECT f.id relation_id,u.id,u.name,u.username,u.avatar,u.role,u.is_verified
                FROM follows f JOIN users u ON u.id=f.follower_id
               WHERE {$where} AND u.status='active'
               ORDER BY f.id DESC LIMIT ".($limit+1);
    }else{
        $where='f.follower_id=?';
        if($before>0){$where.=' AND f.id<?';$params[]=$before;}
        $sql="SELECT f.id relation_id,u.id,u.name,u.username,u.avatar,u.role,u.is_verified
                FROM follows f JOIN users u ON u.id=f.following_id
               WHERE {$where} AND u.status='active'
               ORDER BY f.id DESC LIMIT ".($limit+1);
    }
    $rows=fetch_all($sql,$params);
    $more=count($rows)>$limit;if($more)array_pop($rows);
    $people=array_map(static function(array $row):array{
        return [
            'id'=>(int)$row['id'],
            'name'=>(string)$row['name'],
            'username'=>(string)$row['username'],
            'avatar'=>!empty($row['avatar'])?upload_url((string)$row['avatar']):null,
            'role'=>(string)($row['role']??'student'),
            'verified'=>(int)($row['is_verified']??0)===1,
        ];
    },$rows);
    $next=$rows?min(array_map(static fn(array $row):int=>(int)$row['relation_id'],$rows)):0;
    mobile_out(['visible'=>true,'people'=>$people,'has_more'=>$more,'next_before'=>$next]);
}

'''
for path in ['backend/api/mobile_social_v31.php', 'flutter/backend/api/mobile_social_v31.php']:
    text = r(path)
    if 'function mobile_social_connections_table()' not in text:
        marker = "if($_SERVER['REQUEST_METHOD']!=='POST') mobile_error('This endpoint only accepts POST.',405);"
        helper = r'''function mobile_social_connections_table(): void {
    q("CREATE TABLE IF NOT EXISTS mobile_profile_privacy (
        user_id BIGINT UNSIGNED NOT NULL PRIMARY KEY,
        show_connections TINYINT(1) NOT NULL DEFAULT 1,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4");
}

'''
        text = once(text, marker, helper + marker, f'social privacy helper in {path}')
    if "if($action==='profile_connections')" not in text:
        marker = "if($action==='profile_follow'){"
        text = once(text, marker, connections_action + marker, f'connections action in {path}')
    w(path, text)


# ---------------------------------------------------------------------------
# 6) Chat attachment sheet: replace the oversized Standard/Once segmented UI
# with a compact privacy control and clean, premium attachment cards.
# ---------------------------------------------------------------------------
path = 'flutter/lib/screens/chat_screen.dart'
text = r(path)
picker = r'''  Future<void> _pickAttachment() async {
    if (_chatBlocked || sending) return;
    var viewOnce = false;
    await showModalBottomSheet<void>(
      context: context,
      useSafeArea: true,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (sheet) => StatefulBuilder(
        builder: (sheet, setModal) {
          final scheme = Theme.of(sheet).colorScheme;

          Widget option({
            required IconData icon,
            required Color color,
            required String title,
            required String subtitle,
            required VoidCallback onTap,
          }) => Container(
                margin: const EdgeInsets.only(bottom: 9),
                decoration: BoxDecoration(
                  color: scheme.surface,
                  borderRadius: BorderRadius.circular(18),
                  border: Border.all(color: scheme.outlineVariant.withValues(alpha: .55)),
                ),
                child: Material(
                  color: Colors.transparent,
                  child: InkWell(
                    borderRadius: BorderRadius.circular(18),
                    onTap: onTap,
                    child: Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 13, vertical: 12),
                      child: Row(
                        children: [
                          Container(
                            width: 44,
                            height: 44,
                            decoration: BoxDecoration(
                              color: color.withValues(alpha: .10),
                              borderRadius: BorderRadius.circular(14),
                            ),
                            child: Icon(icon, color: color, size: 23),
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(title, style: const TextStyle(fontSize: 15.5, fontWeight: FontWeight.w800)),
                                const SizedBox(height: 2),
                                Text(
                                  subtitle,
                                  maxLines: 2,
                                  overflow: TextOverflow.ellipsis,
                                  style: TextStyle(fontSize: 12.2, height: 1.25, color: scheme.onSurfaceVariant),
                                ),
                              ],
                            ),
                          ),
                          const SizedBox(width: 6),
                          Icon(Icons.chevron_right_rounded, color: scheme.onSurfaceVariant),
                        ],
                      ),
                    ),
                  ),
                ),
              );

          return Material(
            color: Theme.of(sheet).scaffoldBackgroundColor,
            borderRadius: const BorderRadius.vertical(top: Radius.circular(28)),
            clipBehavior: Clip.antiAlias,
            child: Padding(
              padding: EdgeInsets.fromLTRB(
                16,
                8,
                16,
                MediaQuery.viewInsetsOf(sheet).bottom + 16,
              ),
              child: SingleChildScrollView(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Center(
                      child: Container(
                        width: 42,
                        height: 4,
                        decoration: BoxDecoration(
                          color: scheme.onSurfaceVariant.withValues(alpha: .32),
                          borderRadius: BorderRadius.circular(99),
                        ),
                      ),
                    ),
                    const SizedBox(height: 14),
                    Row(
                      children: [
                        Container(
                          width: 42,
                          height: 42,
                          decoration: BoxDecoration(
                            gradient: const LinearGradient(colors: [AppColors.blue, AppColors.violet]),
                            borderRadius: BorderRadius.circular(14),
                          ),
                          child: const Icon(Icons.attach_file_rounded, color: Colors.white),
                        ),
                        const SizedBox(width: 11),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text('Send attachment', style: Theme.of(sheet).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w900)),
                              Text('Choose what you want to share', style: TextStyle(fontSize: 12.5, color: scheme.onSurfaceVariant)),
                            ],
                          ),
                        ),
                        IconButton(
                          tooltip: 'Close',
                          onPressed: () => Navigator.pop(sheet),
                          icon: const Icon(Icons.close_rounded),
                        ),
                      ],
                    ),
                    const SizedBox(height: 13),
                    if (!widget.conversation.isGroup)
                      Container(
                        margin: const EdgeInsets.only(bottom: 12),
                        padding: const EdgeInsets.fromLTRB(12, 9, 8, 9),
                        decoration: BoxDecoration(
                          color: viewOnce
                              ? AppColors.violet.withValues(alpha: .08)
                              : scheme.surface,
                          borderRadius: BorderRadius.circular(17),
                          border: Border.all(
                            color: viewOnce
                                ? AppColors.violet.withValues(alpha: .28)
                                : scheme.outlineVariant.withValues(alpha: .55),
                          ),
                        ),
                        child: Row(
                          children: [
                            Container(
                              width: 36,
                              height: 36,
                              decoration: BoxDecoration(
                                color: AppColors.violet.withValues(alpha: .10),
                                borderRadius: BorderRadius.circular(12),
                              ),
                              child: Icon(
                                viewOnce ? Icons.looks_one_rounded : Icons.visibility_outlined,
                                color: AppColors.violet,
                                size: 21,
                              ),
                            ),
                            const SizedBox(width: 10),
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    'View once',
                                    style: TextStyle(fontWeight: FontWeight.w800, color: viewOnce ? AppColors.violet : null),
                                  ),
                                  Text(
                                    viewOnce
                                        ? 'The photo can be opened only once.'
                                        : 'Turn on only when you need one-time media.',
                                    style: TextStyle(fontSize: 11.5, color: scheme.onSurfaceVariant),
                                  ),
                                ],
                              ),
                            ),
                            Switch.adaptive(
                              value: viewOnce,
                              onChanged: (value) => setModal(() => viewOnce = value),
                            ),
                          ],
                        ),
                      )
                    else
                      Container(
                        margin: const EdgeInsets.only(bottom: 12),
                        padding: const EdgeInsets.all(11),
                        decoration: BoxDecoration(
                          color: scheme.surfaceContainerHighest.withValues(alpha: .42),
                          borderRadius: BorderRadius.circular(15),
                        ),
                        child: Row(
                          children: [
                            Icon(Icons.info_outline_rounded, size: 18, color: scheme.onSurfaceVariant),
                            const SizedBox(width: 8),
                            Expanded(
                              child: Text(
                                'View once is available in direct chats only.',
                                style: TextStyle(fontSize: 11.8, color: scheme.onSurfaceVariant),
                              ),
                            ),
                          ],
                        ),
                      ),
                    option(
                      icon: Icons.photo_library_outlined,
                      color: AppColors.blue,
                      title: viewOnce ? 'Choose one photo' : 'Photos & images',
                      subtitle: viewOnce
                          ? 'Select a photo and send it as one-time media.'
                          : 'Select one or multiple photos and send directly.',
                      onTap: () async {
                        Navigator.pop(sheet);
                        if (viewOnce) {
                          final image = await ImagePicker().pickImage(
                            source: ImageSource.gallery,
                            imageQuality: 92,
                            maxWidth: 2600,
                            maxHeight: 2600,
                          );
                          if (image != null && mounted) {
                            await _uploadManyImages([image.path], viewOnce: true);
                          }
                        } else {
                          final images = await ImagePicker().pickMultiImage(
                            imageQuality: 92,
                            maxWidth: 2600,
                            maxHeight: 2600,
                          );
                          if (images.isNotEmpty && mounted) {
                            await _uploadManyImages(images.map((e) => e.path).toList());
                          }
                        }
                      },
                    ),
                    option(
                      icon: Icons.photo_camera_outlined,
                      color: AppColors.success,
                      title: 'Camera',
                      subtitle: viewOnce ? 'Capture and send once.' : 'Capture a new photo and send directly.',
                      onTap: () async {
                        Navigator.pop(sheet);
                        final image = await ImagePicker().pickImage(
                          source: ImageSource.camera,
                          imageQuality: 92,
                          maxWidth: 2600,
                          maxHeight: 2600,
                        );
                        if (image != null && mounted) {
                          await _uploadManyImages([image.path], viewOnce: viewOnce);
                        }
                      },
                    ),
                    if (!viewOnce)
                      option(
                        icon: Icons.tune_rounded,
                        color: AppColors.violet,
                        title: 'Edit before sending',
                        subtitle: 'Crop, rotate, draw, hide details or review multiple photos.',
                        onTap: () async {
                          Navigator.pop(sheet);
                          final images = await ImagePicker().pickMultiImage(
                            imageQuality: 92,
                            maxWidth: 2600,
                            maxHeight: 2600,
                          );
                          if (images.isNotEmpty && mounted) {
                            await _reviewImages(images.map((e) => e.path).toList());
                          }
                        },
                      ),
                    if (!viewOnce)
                      option(
                        icon: Icons.description_outlined,
                        color: AppColors.violet,
                        title: 'Document or file',
                        subtitle: 'Share a PDF, document or another supported file.',
                        onTap: () async {
                          Navigator.pop(sheet);
                          final file = await FilePicker.pickFile();
                          final filePath = file?.path;
                          if (filePath != null && mounted) await _upload(filePath);
                        },
                      ),
                  ],
                ),
              ),
            ),
          );
        },
      ),
    );
  }'''
text = replace_block(text, '  Future<void> _pickAttachment() async {', picker)
w(path, text)


# ---------------------------------------------------------------------------
# 7) Global visual polish: consistent buttons, sheets, dialogs and list tiles.
# ---------------------------------------------------------------------------
path = 'flutter/lib/core/theme.dart'
text = r(path)
if 'bottomSheetTheme: BottomSheetThemeData(' not in text:
    light_marker = '    snackBarTheme: SnackBarThemeData(\n      behavior: SnackBarBehavior.floating,\n      backgroundColor: AppColors.navy,'
    light_polish = r'''    bottomSheetTheme: const BottomSheetThemeData(
      backgroundColor: Colors.white,
      modalBackgroundColor: Colors.white,
      surfaceTintColor: Colors.transparent,
      showDragHandle: false,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(28)),
      ),
    ),
    dialogTheme: DialogThemeData(
      backgroundColor: Colors.white,
      surfaceTintColor: Colors.transparent,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(24)),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        minimumSize: const Size(0, 48),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(15)),
        side: const BorderSide(color: Color(0x243157E8)),
        textStyle: const TextStyle(fontWeight: FontWeight.w700),
      ),
    ),
    listTileTheme: const ListTileThemeData(
      minVerticalPadding: 8,
      iconColor: AppColors.blue,
    ),
'''
    text = once(text, light_marker, light_polish + light_marker, 'light theme polish')

    dark_marker = "    snackBarTheme: SnackBarThemeData(\n      behavior: SnackBarBehavior.floating,\n      backgroundColor: const Color(0xFF1A2740),"
    dark_polish = r'''    bottomSheetTheme: const BottomSheetThemeData(
      backgroundColor: Color(0xFF0D1728),
      modalBackgroundColor: Color(0xFF0D1728),
      surfaceTintColor: Colors.transparent,
      showDragHandle: false,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(28)),
      ),
    ),
    dialogTheme: DialogThemeData(
      backgroundColor: const Color(0xFF10192A),
      surfaceTintColor: Colors.transparent,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(24)),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        minimumSize: const Size(0, 48),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(15)),
        side: const BorderSide(color: Color(0x408EA2FF)),
        textStyle: const TextStyle(fontWeight: FontWeight.w700),
      ),
    ),
    listTileTheme: const ListTileThemeData(
      minVerticalPadding: 8,
      iconColor: Color(0xFF8EA2FF),
      textColor: Color(0xFFE7ECF8),
    ),
'''
    text = once(text, dark_marker, dark_polish + dark_marker, 'dark theme polish')
w(path, text)


# ---------------------------------------------------------------------------
# 8) Release version.
# ---------------------------------------------------------------------------
path = 'flutter/pubspec.yaml'
text = r(path)
import re
text, count = re.subn(r'^version:\s*[^\n]+', 'version: 4.5.0+450', text, count=1, flags=re.M)
if count != 1:
    raise RuntimeError('v4.5 pubspec version marker missing')
w(path, text)


# Assertions keep this transform self-diagnosing before Flutter analyze.
profile = r('flutter/lib/screens/profile_screen.dart')
chat = r('flutter/lib/screens/chat_screen.dart')
security = r('flutter/lib/screens/security_screen.dart')
social_api = r('flutter/lib/core/social_api.dart')
mobile = r('backend/api/mobile.php')
social_server = r('backend/api/mobile_social_v31.php')
theme = r('flutter/lib/core/theme.dart')
pubspec = r('flutter/pubspec.yaml')
assert 'class _ProfileConnectionsScreen extends StatefulWidget' in profile
assert "_openConnections(p, 'followers')" in profile and "_openConnections(p, 'following')" in profile
assert 'profileConnections(' in social_api
assert "value: _bool(s['show_connections'], true)" in security
assert 'mobile_profile_privacy' in mobile and "if ($key === 'show_connections')" in mobile
assert "if($action==='profile_connections')" in social_server
assert "Text('View once'" in chat and "title: 'Photos & images'" in chat
assert 'bottomSheetTheme: const BottomSheetThemeData(' in theme
assert 'version: 4.5.0+450' in pubspec
print('TaleemPK v4.5 profile, connections, attachment and app polish applied successfully')
