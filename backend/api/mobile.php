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

if ($action === 'register') {
    if (!api_burst_limit('mobile_register', 3)) {
        mobile_error('Too many accounts were created from this connection. Wait a minute and try again.', 429);
    }
    if ((int) setting('allow_registration', 1) !== 1) {
        mobile_error('New registrations are temporarily closed.', 403);
    }
    if (ip_is_banned()) {
        mobile_error('Registration is not available from this connection.', 403);
    }

    $role = strtolower(trim((string) ($_POST['role'] ?? 'student')));
    $name = mail_header_safe(trim((string) ($_POST['name'] ?? '')));
    $username = strtolower(trim((string) ($_POST['username'] ?? '')));
    $email = strtolower(trim((string) ($_POST['email'] ?? '')));
    $phone = trim((string) ($_POST['phone'] ?? ''));
    $dobInput = trim((string) ($_POST['dob'] ?? ''));
    $password = (string) ($_POST['password'] ?? '');

    if (!in_array($role, ['student', 'teacher', 'institute'], true)) { $role = 'student'; }
    if (mb_strlen($name) < 3) { mobile_error('Enter your full name.'); }
    if (!preg_match('/^[a-zA-Z0-9_]{3,30}$/', $username)) {
        mobile_error('Username must contain 3 to 30 letters, numbers or underscores.');
    }
    if ((int) fetch_col('SELECT COUNT(*) FROM users WHERE username=?', [$username]) > 0) {
        mobile_error('That username is already taken.', 409);
    }
    if (!filter_var($email, FILTER_VALIDATE_EMAIL)) { mobile_error('Enter a valid email address.'); }
    if ((int) fetch_col('SELECT COUNT(*) FROM users WHERE email=?', [$email]) > 0) {
        mobile_error('An account already uses this email address.', 409);
    }
    [$passwordOk, $passwordReason] = password_quality($password, [
        'name' => $name, 'username' => $username, 'email' => $email,
    ]);
    if (!$passwordOk) { mobile_error($passwordReason); }

    $phoneE164 = null;
    if (phone_enabled() && $phone !== '') {
        $phoneE164 = phone_normalize($phone);
        if ($phoneE164 === '') { mobile_error('Enter a valid phone number, for example 03001234567.'); }
        if (phone_taken($phoneE164)) { mobile_error('That phone number is already confirmed on another account.', 409); }
    } elseif (phone_enabled() && (int) setting('phone_required', 0) === 1) {
        mobile_error('Enter your phone number.');
    }

    $dob = parse_dmy_date($dobInput);
    if (!$dob) { mobile_error('Enter a valid date of birth as DD-MM-YYYY.'); }
    $born = DateTime::createFromFormat('!Y-m-d', $dob);
    $today = new DateTime('today');
    if (!$born || $born > $today) { mobile_error('Enter a valid date of birth.'); }
    $age = $today->diff($born)->y;
    if ($age < (int) setting('min_age', 13)) {
        mobile_error('You do not meet the minimum age required to join.', 403);
    }

    $isMinor = $age < 18;
    $safeDefaults = $isMinor ? [
        'allow_dm' => 'following', 'allow_comments' => 'followers',
        'profile_privacy' => 'members', 'searchable' => 0,
        'show_online' => 0, 'allow_calls' => 'following',
    ] : [];
    $needsReview = ($role === 'teacher' && (int) setting('teacher_needs_review', 1) === 1)
        || ($role === 'institute' && (int) setting('institute_needs_review', 1) === 1);
    $verifyEmail = (int) setting('require_email_verify', 1) === 1;

    $userId = insert_row('users', $safeDefaults + [
        'role' => $role, 'name' => $name, 'username' => $username, 'email' => $email,
        'phone' => $phone !== '' ? $phone : null, 'phone_e164' => $phoneE164 ?: null,
        'dob' => $dob, 'password_hash' => password_hash($password, PASSWORD_DEFAULT),
        'status' => $needsReview ? 'pending' : 'active',
        'status_reason' => $needsReview ? 'Waiting for an admin to review this account.' : null,
        'email_verified' => $verifyEmail ? 0 : 1,
    ]);
    insert_row('profiles', ['user_id' => $userId]);
    log_activity($userId, 'mobile_register', 'New ' . $role . ' account from Android app');

    if ($verifyEmail) {
        send_verify_code(['id' => $userId, 'name' => $name, 'email' => $email, 'verify_sent_at' => null], true);
    } else {
        [$subject, $html] = mail_msg_welcome($name, url('feed.php'), url('library.php'), url('edit-profile.php'));
        queue_mail($email, $subject, $html, $name, 'account');
    }

    $message = $needsReview
        ? 'Account created. Our team will review it and email you when it is ready.'
        : ($verifyEmail
            ? 'Account created. Check your email to verify it, then sign in.'
            : 'Account created successfully. You can now sign in.');
    mobile_out(['message' => $message, 'needs_review' => $needsReview, 'needs_email_verification' => $verifyEmail], 201);
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

/* Reuse the mature website chat handlers behind bearer authentication. Each
   handler still performs its own membership, feature, verification and abuse
   checks; only the browser-only CSRF check is bypassed for this authenticated
   first-party client. Keeping one mutation path also keeps Android and web
   behaviour identical. */
$nativeChatHandlers = [
    'send'           => 'chat_send.php',
    'reaction'       => 'chat_reaction.php',
    'star'           => 'chat_star.php',
    'pin'            => 'chat_pin.php',
    'message_action' => 'chat_message.php',
    'manage_chat'    => 'chat_manage.php',
    'search_chat'    => 'chat_search.php',
];
if (isset($nativeChatHandlers[$action])) {
    require_feature('feature_chat');
    $_SESSION['uid'] = $uid;
    if (!defined('NATIVE_API_AUTHENTICATED')) { define('NATIVE_API_AUTHENTICATED', true); }
    require __DIR__ . '/' . $nativeChatHandlers[$action];
}

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
        "SELECT c.id,c.type,c.title,c.avatar,c.last_message,c.last_activity,cm.unread_count,cm.is_muted,
                (SELECT u2.name FROM conversation_members cm2 JOIN users u2 ON u2.id=cm2.user_id
                  WHERE cm2.conversation_id=c.id AND cm2.user_id<>? LIMIT 1) other_name,
                (SELECT u2.avatar FROM conversation_members cm2 JOIN users u2 ON u2.id=cm2.user_id
                  WHERE cm2.conversation_id=c.id AND cm2.user_id<>? LIMIT 1) other_avatar,
                (SELECT u2.last_seen FROM conversation_members cm2 JOIN users u2 ON u2.id=cm2.user_id
                  WHERE cm2.conversation_id=c.id AND cm2.user_id<>? LIMIT 1) other_last_seen,
                (SELECT u2.show_online FROM conversation_members cm2 JOIN users u2 ON u2.id=cm2.user_id
                  WHERE cm2.conversation_id=c.id AND cm2.user_id<>? LIMIT 1) other_show_online
           FROM conversation_members cm JOIN conversations c ON c.id=cm.conversation_id
          WHERE cm.user_id=? AND cm.is_archived=0 ORDER BY c.last_activity DESC LIMIT 100",
        [$uid,$uid,$uid,$uid,$uid]
    );
    $items = array_map(static function(array $c): array {
        $group = $c['type']==='group';
        $avatar = $group ? $c['avatar'] : $c['other_avatar'];
        $online = !$group && (int)($c['other_show_online'] ?? 0) === 1
            && !empty($c['other_last_seen']) && strtotime((string)$c['other_last_seen']) >= time() - 120;
        $status = $group ? 'Study group' : ($online ? 'Online now'
            : (!empty($c['other_last_seen']) && (int)($c['other_show_online'] ?? 0) === 1
                ? 'Last seen ' . time_ago($c['other_last_seen']) : 'Private conversation'));
        return [
            'id'=>(int)$c['id'], 'title'=>$group ? ($c['title'] ?: 'Study group') : ($c['other_name'] ?: 'Conversation'),
            'avatar'=>$avatar ? upload_url($avatar) : null, 'last_message'=>(string)($c['last_message'] ?? ''),
            'last_activity'=>time_ago($c['last_activity']), 'unread'=>(int)$c['unread_count'], 'is_group'=>$group,
            'online'=>$online, 'status_text'=>$status, 'muted'=>(int)$c['is_muted']===1,
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
        'SELECT m.*,u.name sender,ru.name reply_sender,rm.content reply_content,
                rm.status reply_status,rm.voice_seconds reply_voice_seconds,rm.attachment_name reply_attachment_name,
                EXISTS(SELECT 1 FROM message_stars s WHERE s.message_id=m.id AND s.user_id=?) starred
           FROM messages m JOIN users u ON u.id=m.sender_id
           LEFT JOIN messages rm ON rm.id=m.reply_to_id
           LEFT JOIN users ru ON ru.id=rm.sender_id
          WHERE m.conversation_id=?
            AND NOT EXISTS(SELECT 1 FROM message_hides h WHERE h.message_id=m.id AND h.user_id=?)
          ORDER BY m.id DESC LIMIT 150', [$uid,$cid,$uid]
    );
    $newest = $rows ? (int) $rows[0]['id'] : 0;
    if ($newest) {
        q('UPDATE conversation_members SET last_read_id=GREATEST(last_read_id,?),unread_count=0 WHERE conversation_id=? AND user_id=?', [$newest,$cid,$uid]);
    }
    $otherReadThrough = (int) fetch_col(
        'SELECT COALESCE(MAX(last_read_id),0) FROM conversation_members WHERE conversation_id=? AND user_id<>?',
        [$cid,$uid]
    );
    $reactionMap = [];
    $messageIds = array_map(static fn(array $m): int => (int)$m['id'], $rows);
    if ($messageIds) {
        $ph = implode(',', array_fill(0, count($messageIds), '?'));
        $reactionRows = fetch_all("SELECT message_id,emoji,COUNT(*) n,MAX(user_id=?) mine
                                     FROM message_reactions WHERE message_id IN ($ph)
                                    GROUP BY message_id,emoji ORDER BY MIN(id)", array_merge([$uid], $messageIds));
        foreach ($reactionRows as $reaction) {
            $reactionMap[(int)$reaction['message_id']][] = [
                'emoji'=>(string)$reaction['emoji'], 'count'=>(int)$reaction['n'], 'mine'=>(bool)$reaction['mine'],
            ];
        }
    }
    $items = array_reverse(array_map(static function(array $m) use ($uid, $otherReadThrough, $reactionMap): array {
        $mine = (int)$m['sender_id']===$uid;
        $read = $mine && $otherReadThrough >= (int) $m['id'];
        $deleted = $m['status']==='deleted';
        $created = strtotime((string)$m['created_at']);
        $dateLabel = date('Y-m-d', $created) === date('Y-m-d') ? 'Today'
            : (date('Y-m-d', $created) === date('Y-m-d', strtotime('-1 day')) ? 'Yesterday' : date('M j, Y', $created));
        $reply = null;
        if (!$deleted && !empty($m['reply_to_id'])) {
            $replyText = $m['reply_status']==='deleted' ? 'Message deleted'
                : trim((string)($m['reply_content'] ?? ''));
            if ($replyText === '') {
                $replyText = (int)($m['reply_voice_seconds'] ?? 0) > 0 ? 'Voice message'
                    : (!empty($m['reply_attachment_name']) ? (string)$m['reply_attachment_name'] : 'Attachment');
            }
            $reply = ['id'=>(int)$m['reply_to_id'], 'sender'=>(string)($m['reply_sender'] ?: 'Message'),
                'text'=>mb_substr($replyText, 0, 120)];
        }
        return [
            'id'=>(int)$m['id'], 'sender_id'=>(int)$m['sender_id'], 'sender'=>$m['sender'],
            'content'=>$deleted ? 'This message was deleted.' : (string)($m['content'] ?? ''),
            'time'=>date('g:i A', strtotime($m['created_at'])), 'mine'=>$mine,
            'date_label'=>$dateLabel, 'deleted'=>$deleted, 'edited'=>!empty($m['edited_at']),
            'forwarded'=>!empty($m['forwarded_from']), 'starred'=>(bool)$m['starred'],
            'pinned'=>(int)($m['is_pinned'] ?? 0)===1,
            'can_edit'=>$mine && !$deleted && within_edit_window((string)$m['created_at']),
            'voice_seconds'=>$deleted ? 0 : (int)($m['voice_seconds'] ?? 0),
            'attachment_url'=>!$deleted && !empty($m['attachment']) ? url('api/mobile.php?action=file&id='.(int)$m['id']) : null,
            'attachment_name'=>$deleted ? null : ($m['attachment_name'] ?? null),
            'attachment_type'=>$deleted ? null : ($m['attachment_type'] ?? null), 'read'=>$read,
            'reply'=>$reply, 'reactions'=>$reactionMap[(int)$m['id']] ?? [],
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

mobile_error('Unknown API action.', 404);
