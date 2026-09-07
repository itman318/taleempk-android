<?php
/**
 * TaleemPK native Android API v1.1.
 *
 * Browser sessions are never exported to a phone. A successful native sign-in
 * receives a random bearer token; the database stores only its SHA-256 digest.
 */
/* Mark native requests before the shared bootstrap runs. This gives current
   and future gates an unambiguous way to keep API responses machine-readable. */
if (!defined('NATIVE_API_REQUEST')) { define('NATIVE_API_REQUEST', true); }

/* Set JSON before loading the application. If a shared include terminates
   early, Android must never be handed an HTML content type. */
header('Content-Type: application/json; charset=utf-8');

try {
    require_once dirname(__DIR__) . '/includes/bootstrap.php';
    require_once dirname(__DIR__) . '/includes/chat_helpers.php';
} catch (Throwable $e) {
    while (ob_get_level() > 0) { @ob_end_clean(); }
    http_response_code(500);
    header('Content-Type: application/json; charset=utf-8');
    echo json_encode(['ok' => false, 'error' => 'The mobile service could not start. Please try again later.']);
    exit;
}

header('Cache-Control: no-store, private');
header('X-Content-Type-Options: nosniff');

$action = strtolower(trim((string) ($_POST['action'] ?? $_GET['action'] ?? '')));

/* File playback is the sole GET action. Every state-reading JSON request is
   POST as well, keeping credentials out of URLs and intermediary logs. */
if ($_SERVER['REQUEST_METHOD'] !== 'POST' && !($action === 'file' && $_SERVER['REQUEST_METHOD'] === 'GET')) {
    mobile_error('This endpoint only accepts POST.', 405);
}
if ($_SERVER['REQUEST_METHOD'] === 'POST' && post_body_was_too_large()) {
    mobile_error(post_too_large_message(), 413);
}

function mobile_out(array $data = [], int $status = 200): void
{
    http_response_code($status);
    header('Content-Type: application/json; charset=utf-8');
    echo json_encode(['ok' => $status < 400, 'data' => $data], JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE);
    exit;
}

function mobile_error(string $message, int $status = 400): void
{
    http_response_code($status);
    header('Content-Type: application/json; charset=utf-8');
    echo json_encode(['ok' => false, 'error' => $message], JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE);
    exit;
}

function mobile_bearer(): string
{
    $header = (string) ($_SERVER['HTTP_AUTHORIZATION'] ?? $_SERVER['REDIRECT_HTTP_AUTHORIZATION'] ?? '');
    if ($header === '' && function_exists('getallheaders')) {
        foreach ((array) getallheaders() as $k => $v) {
            if (strcasecmp((string) $k, 'Authorization') === 0) { $header = (string) $v; break; }
        }
    }
    return preg_match('/^Bearer\s+([a-f0-9]{64})$/i', trim($header), $m) ? strtolower($m[1]) : '';
}

function mobile_user(): array
{
    $token = mobile_bearer();
    if ($token === '') { mobile_error('Sign in to continue.', 401); }
    $row = fetch_one(
        "SELECT u.* FROM mobile_sessions s JOIN users u ON u.id=s.user_id
          WHERE s.token_hash=? AND s.expires_at>NOW() AND u.status='active' LIMIT 1",
        [hash('sha256', $token)]
    );
    if (!$row) { mobile_error('Your session has expired. Sign in again.', 401); }
    /* A chatty phone must not turn every API read into a database write. */
    q('UPDATE mobile_sessions SET last_seen=NOW()
        WHERE token_hash=? AND last_seen<DATE_SUB(NOW(), INTERVAL 5 MINUTE)', [hash('sha256', $token)]);
    return $row;
}

function mobile_public_user(array $u): array
{
    return [
        'id'       => (int) $u['id'],
        'name'     => (string) $u['name'],
        'username' => (string) $u['username'],
        'role'     => (string) $u['role'],
        'avatar'   => !empty($u['avatar']) ? upload_url((string) $u['avatar']) : null,
        'verified' => (int) ($u['is_verified'] ?? 0) === 1,
    ];
}

function mobile_issue_token(int $userId, string $device): string
{
    $plain = bin2hex(random_bytes(32));
    insert_row('mobile_sessions', [
        'token_hash' => hash('sha256', $plain),
        'user_id' => $userId,
        'device_name' => mb_substr(trim($device), 0, 100),
        'expires_at' => date('Y-m-d H:i:s', time() + 30 * 86400),
    ]);
    q('DELETE FROM mobile_sessions WHERE expires_at<=NOW()');
    /* Bound stolen/forgotten device sessions while retaining the ten newest. */
    q('DELETE FROM mobile_sessions WHERE user_id=? AND token_hash NOT IN
       (SELECT token_hash FROM (SELECT token_hash FROM mobile_sessions WHERE user_id=?
        ORDER BY created_at DESC LIMIT 10) newest)', [$userId, $userId]);
    return $plain;
}

function mobile_finish_login(array $u, string $device): void
{
    $signin = record_signin((int) $u['id']);
    alert_signin((int) $u['id'], $signin);
    login_rate_success((string) $u['email']);
    login_rate_success((string) $u['username']);
    q('UPDATE users SET last_seen=NOW(), last_ip=? WHERE id=?', [client_ip(), $u['id']]);
    award_daily_login((int) $u['id']);
    log_activity((int) $u['id'], 'mobile_login', 'Signed in on ' . mb_substr($device, 0, 80));
    mobile_out(['token' => mobile_issue_token((int) $u['id'], $device), 'user' => mobile_public_user($u)]);
}

/* Unauthenticated deployment probe. It exposes no account or infrastructure
   data and lets the Android client/support distinguish a healthy API from a
   misplaced or partially uploaded file. */
if ($action === 'health') {
    mobile_out(['service' => 'TaleemPK mobile API', 'version' => defined('APP_VERSION') ? APP_VERSION : 'unknown']);
}

if ($action === 'login') {
    if (!api_burst_limit('mobile_login', 10)) { mobile_error('Too many attempts. Wait a minute.', 429); }
    $identifier = strtolower(trim((string) ($_POST['identifier'] ?? '')));
    $password = (string) ($_POST['password'] ?? '');
    $device = trim((string) ($_POST['device'] ?? 'Android device'));
    if ($identifier === '' || $password === '') { mobile_error('Enter your email or username and password.'); }

    $blocked = max(login_rate_blocked($identifier), login_spray_blocked());
    if ($blocked > time()) { mobile_error('Too many attempts. Try again later.', 429); }
    $u = fetch_one('SELECT * FROM users WHERE email=? OR username=? LIMIT 1', [$identifier, $identifier]);
    if (!$u || !password_verify($password, (string) $u['password_hash'])) {
        login_rate_fail($identifier); login_spray_fail();
        if ($u) { log_activity((int) $u['id'], 'login_failed', 'Wrong password in Android app'); }
        mobile_error('That email or password is not right.', 401);
    }
    if ($u['status'] !== 'active') { mobile_error((string) ($u['status_reason'] ?: 'This account is not active.'), 403); }
    if ((int) $u['email_verified'] !== 1) { mobile_error('Verify your email before signing in to the app.', 403); }

    $forced = in_array($u['role'], ['admin', 'moderator'], true) && (int) setting('admin_force_tfa', 1) === 1;
    if ((int) $u['two_factor'] === 1 || $forced) {
        $plain = bin2hex(random_bytes(32));
        insert_row('mobile_login_challenges', [
            'challenge_hash' => hash('sha256', $plain), 'user_id' => (int) $u['id'],
            'device_name' => mb_substr($device, 0, 100),
            'expires_at' => date('Y-m-d H:i:s', time() + 600),
        ]);
        q('DELETE FROM mobile_login_challenges WHERE expires_at<=NOW()');
        if (!tfa_send_code((int) $u['id'])) { mobile_error('The verification email could not be sent.', 503); }
        mobile_out(['needs_2fa' => true, 'challenge' => $plain]);
    }
    mobile_finish_login($u, $device);
}

if ($action === 'verify_2fa') {
    if (!api_burst_limit('mobile_2fa', 10)) { mobile_error('Too many attempts. Wait a minute.', 429); }
    $plain = strtolower(trim((string) ($_POST['challenge'] ?? '')));
    $code = trim((string) ($_POST['code'] ?? ''));
    if (!preg_match('/^[a-f0-9]{64}$/', $plain) || !preg_match('/^[0-9]{6}$/', $code)) {
        mobile_error('Enter the six-digit code.');
    }
    $challenge = fetch_one(
        'SELECT * FROM mobile_login_challenges WHERE challenge_hash=? AND expires_at>NOW() LIMIT 1',
        [hash('sha256', $plain)]
    );
    if (!$challenge || !tfa_check_code((int) $challenge['user_id'], $code)) {
        mobile_error('That code is incorrect or has expired.', 401);
    }
    delete_row('mobile_login_challenges', 'challenge_hash=?', [$challenge['challenge_hash']]);
    $u = fetch_one("SELECT * FROM users WHERE id=? AND status='active'", [$challenge['user_id']]);
    if (!$u) { mobile_error('This account is not available.', 403); }
    mobile_finish_login($u, (string) $challenge['device_name']);
}

if ($action === 'logout') {
    $u = mobile_user();
    delete_row('mobile_sessions', 'token_hash=?', [hash('sha256', mobile_bearer())]);
    log_activity((int) $u['id'], 'mobile_logout', 'Signed out of Android app');
    mobile_out();
}

$u = mobile_user();
$uid = (int) $u['id'];

if ($action === 'bootstrap') {
    $stats = [
        'members' => (int) fetch_col("SELECT COUNT(*) FROM users WHERE status='active'"),
        'active_today' => (int) fetch_col("SELECT COUNT(*) FROM users WHERE status='active' AND last_seen>=CURDATE()"),
        'messages_today' => table_exists('messages') ? (int) fetch_col('SELECT COUNT(*) FROM messages WHERE created_at>=CURDATE()') : 0,
        'quiz_attempts' => table_exists('quiz_attempts') ? (int) fetch_col('SELECT COUNT(*) FROM quiz_attempts WHERE started_at>=CURDATE()') : 0,
    ];
    $shortcuts = [
        ['title'=>'Study dashboard','subtitle'=>'Your plan, progress and next steps','route'=>'study.php','icon'=>'study'],
        ['title'=>'Community feed','subtitle'=>'Questions, answers and announcements','route'=>'feed.php','icon'=>'feed'],
        ['title'=>'Study library','subtitle'=>'Notes, files and learning resources','route'=>'library.php','icon'=>'library'],
        ['title'=>'Quizzes','subtitle'=>'Practice and test your knowledge','route'=>'quiz.php','icon'=>'quiz'],
        ['title'=>'Messages','subtitle'=>'Private and group conversations','route'=>'chat.php','icon'=>'chat'],
        ['title'=>'Study groups','subtitle'=>'Learn together by subject','route'=>'groups.php','icon'=>'groups'],
        ['title'=>'Planner','subtitle'=>'Organise tasks and deadlines','route'=>'planner.php','icon'=>'planner'],
        ['title'=>'Results','subtitle'=>'Check academic results and alerts','route'=>'results.php','icon'=>'results'],
    ];
    mobile_out(['user'=>mobile_public_user($u), 'stats'=>$stats, 'shortcuts'=>$shortcuts]);
}

if ($action === 'feed') {
    require_feature('feature_feed');
    $page = max(1, min(1000, (int) ($_POST['page'] ?? 1)));
    $limit = 20; $offset = ($page - 1) * $limit;
    $rows = fetch_all(
        "SELECT p.id,p.type,p.content,p.created_at,p.likes_count,p.comments_count,p.is_solved,
                u.name,u.username,u.avatar
           FROM posts p JOIN users u ON u.id=p.user_id
          WHERE p.status='active' AND p.visibility='public' AND p.group_id IS NULL
            AND u.status='active'
          ORDER BY p.is_pinned DESC,p.id DESC LIMIT $limit OFFSET $offset"
    );
    $posts = array_map(static fn(array $p): array => [
        'id'=>(int)$p['id'], 'author'=>$p['name'], 'username'=>$p['username'],
        'avatar'=>!empty($p['avatar']) ? upload_url($p['avatar']) : null,
        'type'=>$p['type'], 'content'=>(string)($p['content'] ?? ''),
        'created_at'=>time_ago($p['created_at']), 'likes'=>(int)$p['likes_count'],
        'comments'=>(int)$p['comments_count'], 'solved'=>(int)$p['is_solved']===1,
    ], $rows);
    mobile_out(['posts'=>$posts, 'page'=>$page]);
}

if ($action === 'conversations') {
    require_feature('feature_chat');
    $rows = fetch_all(
        "SELECT c.id,c.type,c.title,c.avatar,c.last_message,c.last_activity,cm.unread_count,
                (SELECT u2.name FROM conversation_members cm2 JOIN users u2 ON u2.id=cm2.user_id
                  WHERE cm2.conversation_id=c.id AND cm2.user_id<>? LIMIT 1) other_name,
                (SELECT u2.avatar FROM conversation_members cm2 JOIN users u2 ON u2.id=cm2.user_id
                  WHERE cm2.conversation_id=c.id AND cm2.user_id<>? LIMIT 1) other_avatar
           FROM conversation_members cm JOIN conversations c ON c.id=cm.conversation_id
          WHERE cm.user_id=? AND cm.is_archived=0 ORDER BY c.last_activity DESC LIMIT 100",
        [$uid,$uid,$uid]
    );
    $items = array_map(static function(array $c): array {
        $group = $c['type']==='group';
        $avatar = $group ? $c['avatar'] : $c['other_avatar'];
        return [
            'id'=>(int)$c['id'], 'title'=>$group ? ($c['title'] ?: 'Study group') : ($c['other_name'] ?: 'Conversation'),
            'avatar'=>$avatar ? upload_url($avatar) : null, 'last_message'=>(string)($c['last_message'] ?? ''),
            'last_activity'=>time_ago($c['last_activity']), 'unread'=>(int)$c['unread_count'], 'is_group'=>$group,
        ];
    }, $rows);
    mobile_out(['conversations'=>$items]);
}

if ($action === 'messages') {
    require_feature('feature_chat');
    $cid = (int) ($_POST['conversation_id'] ?? 0);
    $member = fetch_one('SELECT id FROM conversation_members WHERE conversation_id=? AND user_id=?', [$cid,$uid]);
    if (!$member) { mobile_error('That conversation is not yours.', 403); }
    $rows = fetch_all(
        'SELECT m.*,u.name sender FROM messages m JOIN users u ON u.id=m.sender_id
          WHERE m.conversation_id=? ORDER BY m.id DESC LIMIT 100', [$cid]
    );
    $newest = $rows ? (int) $rows[0]['id'] : 0;
    if ($newest) {
        q('UPDATE conversation_members SET last_read_id=GREATEST(last_read_id,?),unread_count=0 WHERE conversation_id=? AND user_id=?', [$newest,$cid,$uid]);
    }
    $otherReadThrough = (int) fetch_col(
        'SELECT COALESCE(MAX(last_read_id),0) FROM conversation_members WHERE conversation_id=? AND user_id<>?',
        [$cid,$uid]
    );
    $items = array_reverse(array_map(static function(array $m) use ($uid, $otherReadThrough): array {
        $mine = (int)$m['sender_id']===$uid;
        $read = $mine && $otherReadThrough >= (int) $m['id'];
        $deleted = $m['status']==='deleted';
        return [
            'id'=>(int)$m['id'], 'sender_id'=>(int)$m['sender_id'], 'sender'=>$m['sender'],
            'content'=>$deleted ? 'This message was deleted.' : (string)($m['content'] ?? ''),
            'time'=>date('g:i A', strtotime($m['created_at'])), 'mine'=>$mine,
            'voice_seconds'=>$deleted ? 0 : (int)($m['voice_seconds'] ?? 0),
            'attachment_url'=>!$deleted && !empty($m['attachment']) ? url('api/mobile.php?action=file&id='.(int)$m['id']) : null,
            'attachment_name'=>$deleted ? null : ($m['attachment_name'] ?? null), 'read'=>$read,
        ];
    }, $rows));
    mobile_out(['messages'=>$items]);
}

if ($action === 'file') {
    $id = max(0, (int) ($_GET['id'] ?? 0));
    $m = fetch_one("SELECT m.attachment,m.attachment_name,m.attachment_type,m.conversation_id
                      FROM messages m JOIN conversation_members cm ON cm.conversation_id=m.conversation_id
                     WHERE m.id=? AND m.status='sent' AND cm.user_id=? LIMIT 1", [$id,$uid]);
    if (!$m || empty($m['attachment'])) { http_response_code(404); exit; }
    $base = realpath(UPLOAD_PATH . '/chat');
    $file = realpath(UPLOAD_PATH . '/' . ltrim((string)$m['attachment'],'/'));
    if (!$base || !$file || strpos($file,$base.DIRECTORY_SEPARATOR)!==0 || !is_file($file)) { http_response_code(404); exit; }
    $name = preg_replace('/[^A-Za-z0-9._ -]/','_', (string)($m['attachment_name'] ?: basename($file)));
    $mimeMap = [
        'm4a'=>'audio/mp4', 'mp4'=>'audio/mp4', 'mp3'=>'audio/mpeg', 'ogg'=>'audio/ogg', 'webm'=>'audio/webm',
        'jpg'=>'image/jpeg', 'jpeg'=>'image/jpeg', 'png'=>'image/png', 'gif'=>'image/gif', 'webp'=>'image/webp',
        'pdf'=>'application/pdf', 'txt'=>'text/plain', 'doc'=>'application/msword',
        'docx'=>'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    ];
    $type = strtolower((string) ($m['attachment_type'] ?? ''));
    header('Content-Type: ' . ($mimeMap[$type] ?? 'application/octet-stream'));
    header('Content-Length: '.filesize($file));
    header('Content-Disposition: inline; filename="'.$name.'"');
    header('Cache-Control: private, max-age=300');
    readfile($file); exit;
}

if ($action === 'send') {
    require_feature('feature_chat');
    $_SESSION['uid'] = $uid;
    define('NATIVE_API_AUTHENTICATED', true);
    require __DIR__ . '/chat_send.php';
}

mobile_error('Unknown API action.', 404);
