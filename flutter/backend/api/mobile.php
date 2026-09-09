<?php
/**
 * TaleemPK native Android API v1.5.
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

/* Health is intentionally browser-checkable; authenticated state reads stay
   POST so credentials and account actions never leak into intermediary logs. */
$publicGet = $_SERVER['REQUEST_METHOD'] === 'GET' && in_array($action, ['health', 'file'], true);
if ($_SERVER['REQUEST_METHOD'] !== 'POST' && !$publicGet) {
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

if ($action === 'forgot_password') {
    if (!api_burst_limit('mobile_forgot_password', 5)) {
        mobile_error('Too many reset requests. Wait a minute and try again.', 429);
    }
    $email = strtolower(trim((string) ($_POST['email'] ?? '')));
    if (!filter_var($email, FILTER_VALIDATE_EMAIL)) {
        mobile_error('Enter a valid email address.');
    }

    $user = fetch_one("SELECT id,name,email FROM users WHERE email=? AND status='active' LIMIT 1", [$email]);
    if ($user) {
        /*
         * Use the same website password-reset table and mailer when available.
         * The response stays deliberately generic so the mobile endpoint does
         * not disclose whether an account exists.
         */
        try {
            $plain = bin2hex(random_bytes(32));
            $hash = hash('sha256', $plain);
            if (table_exists('password_resets')) {
                q('DELETE FROM password_resets WHERE email=? OR expires_at<=NOW()', [$email]);
                insert_row('password_resets', [
                    'email' => $email,
                    'token_hash' => $hash,
                    'expires_at' => date('Y-m-d H:i:s', time() + 3600),
                ]);
                $link = url('reset-password.php?token=' . rawurlencode($plain) . '&email=' . rawurlencode($email));
                if (function_exists('send_email')) {
                    send_email(
                        $email,
                        'Reset your TaleemPK password',
                        '<p>Hello ' . e((string)$user['name']) . ',</p>' .
                        '<p>Use the secure link below to reset your TaleemPK password. The link expires in one hour.</p>' .
                        '<p><a href="' . e($link) . '">Reset password</a></p>' .
                        '<p>If you did not request this, you can ignore this email.</p>'
                    );
                }
            }
        } catch (Throwable $e) {
            /* Keep the public response generic; server logs can capture mail
               or legacy-schema failures without exposing account state. */
        }
    }
    mobile_out(['message'=>'If that email exists, a password reset link has been sent.']);
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
$nativeSharedHandlers = [
    'send'           => 'chat_send.php',
    'reaction'       => 'chat_reaction.php',
    'star'           => 'chat_star.php',
    'pin'            => 'chat_pin.php',
    'message_action' => 'chat_message.php',
    'manage_chat'    => 'chat_manage.php',
    'search_chat'    => 'chat_search.php',
    'create_post'    => 'post_create.php',
    'react_post'     => 'react.php',
    'create_comment' => 'comment_create.php',
];
if (isset($nativeSharedHandlers[$action])) {
    $_SESSION['uid'] = $uid;
    if (!defined('NATIVE_API_AUTHENTICATED')) { define('NATIVE_API_AUTHENTICATED', true); }
    require __DIR__ . '/' . $nativeSharedHandlers[$action];
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
                EXISTS(SELECT 1 FROM reactions r WHERE r.target_type='post' AND r.target_id=p.id
                        AND r.user_id=? AND r.type='like') liked,
                u.name,u.username,u.avatar,u.is_verified
           FROM posts p JOIN users u ON u.id=p.user_id
          WHERE p.status='active' AND p.visibility='public' AND p.group_id IS NULL
            AND u.status='active'
          ORDER BY p.is_pinned DESC,p.id DESC LIMIT $limit OFFSET $offset"
    , [$uid]);
    $posts = array_map(static fn(array $p): array => [
        'id'=>(int)$p['id'], 'author'=>$p['name'], 'username'=>$p['username'],
        'avatar'=>!empty($p['avatar']) ? upload_url($p['avatar']) : null,
        'type'=>$p['type'], 'content'=>(string)($p['content'] ?? ''),
        'created_at'=>time_ago($p['created_at']), 'likes'=>(int)$p['likes_count'],
        'comments'=>(int)$p['comments_count'], 'solved'=>(int)$p['is_solved']===1, 'liked'=>(bool)$p['liked'],
        'verified'=>(int)$p['is_verified']===1,
    ], $rows);
    mobile_out(['posts'=>$posts, 'page'=>$page]);
}

if ($action === 'feed_comments') {
    require_feature('feature_comments');
    $postId = (int)($_POST['post_id'] ?? 0);
    $post = fetch_one("SELECT id FROM posts WHERE id=? AND status='active' AND visibility='public' AND group_id IS NULL", [$postId]);
    if (!$post) mobile_error('That post is not available.', 404);
    $rows = fetch_all("SELECT c.id,c.content,c.created_at,c.user_id,u.name
                       FROM comments c JOIN users u ON u.id=c.user_id
                       WHERE c.post_id=? AND c.status='active'
                       ORDER BY c.id LIMIT 200", [$postId]);
    $comments = array_map(static fn(array $c): array => [
        'id'=>(int)$c['id'], 'author'=>(string)$c['name'], 'content'=>(string)$c['content'],
        'created_at'=>time_ago($c['created_at']), 'mine'=>(int)$c['user_id']===$uid,
    ], $rows);
    mobile_out(['comments'=>$comments]);
}

if ($action === 'module') {
    $key = strtolower(trim((string)($_POST['module'] ?? 'study')));
    $items = []; $title = 'Learning'; $subtitle = 'Your TaleemPK learning space';
    if ($key === 'study') {
        $title = 'Study dashboard'; $subtitle = 'Today’s plan and recent learning activity';
        $rows = fetch_all("SELECT id,title,subject,minutes,priority,status,task_date FROM study_tasks
                           WHERE user_id=? AND task_date BETWEEN DATE_SUB(CURDATE(),INTERVAL 7 DAY)
                           AND DATE_ADD(CURDATE(),INTERVAL 14 DAY)
                           ORDER BY task_date,FIELD(priority,'high','normal','low'),id LIMIT 60", [$uid]);
        foreach ($rows as $r) $items[] = ['id'=>(int)$r['id'],'title'=>$r['title'],
            'subtitle'=>trim((string)($r['subject'] ?: 'Study task')),
            'meta'=>$r['task_date'].' · '.(int)$r['minutes'].' min · '.ucfirst($r['priority']),
            'kind'=>'task','done'=>$r['status']==='done'];
    } elseif ($key === 'library') {
        require_feature('feature_library'); $title = 'Study library'; $subtitle = 'Books, notes, papers and assignments';
        $rows = fetch_all("SELECT id,title,type,subject,class_grade,downloads,rating_avg FROM resources
                            WHERE status='approved' ORDER BY is_featured DESC,id DESC LIMIT 60");
        foreach ($rows as $r) $items[] = ['id'=>(int)$r['id'],'title'=>$r['title'],
            'subtitle'=>ucwords(str_replace('_',' ',$r['type'])).($r['subject']?' · '.$r['subject']:''),
            'meta'=>($r['class_grade']?:'All levels').' · '.(int)$r['downloads'].' downloads · '.number_format((float)$r['rating_avg'],1).' ★',
            'kind'=>'resource','done'=>false];
    } elseif ($key === 'quizzes') {
        require_feature('feature_quizzes'); $title = 'Quizzes'; $subtitle = 'Practice and test your knowledge';
        $rows = fetch_all("SELECT q.id,q.title,q.subject,q.class_grade,q.time_limit,q.attempts_count,
                           (SELECT COUNT(*) FROM quiz_questions qq WHERE qq.quiz_id=q.id) questions
                           FROM quizzes q WHERE q.status='approved' AND q.is_public=1
                           ORDER BY q.attempts_count DESC,q.id DESC LIMIT 60");
        foreach ($rows as $r) $items[] = ['id'=>(int)$r['id'],'title'=>$r['title'],
            'subtitle'=>(string)($r['subject']?:'General knowledge'),
            'meta'=>(int)$r['questions'].' questions'.((int)$r['time_limit']?' · '.(int)$r['time_limit'].' min':'').' · '.(int)$r['attempts_count'].' attempts',
            'kind'=>'quiz','done'=>false];
    } elseif ($key === 'groups') {
        require_feature('feature_groups'); $title = 'Study groups'; $subtitle = 'Learn together by subject';
        $rows = fetch_all("SELECT g.id,g.name,g.subject,g.level,g.members_count,gm.role
                           FROM study_groups g LEFT JOIN group_members gm ON gm.group_id=g.id AND gm.user_id=? AND gm.status='approved'
                           WHERE g.status='active' AND (g.privacy='public' OR gm.id IS NOT NULL)
                           ORDER BY (gm.id IS NOT NULL) DESC,g.members_count DESC LIMIT 60", [$uid]);
        foreach ($rows as $r) $items[] = ['id'=>(int)$r['id'],'title'=>$r['name'],
            'subtitle'=>(string)($r['subject']?:ucfirst($r['level'])),
            'meta'=>(int)$r['members_count'].' members'.($r['role']?' · You are '.$r['role']:''),'kind'=>'group','done'=>false];
    } elseif ($key === 'planner') {
        require_feature('feature_planner'); $title = 'Study planner'; $subtitle = 'Daily goals and upcoming tasks';
        $rows = fetch_all("SELECT t.id,t.title,t.subject,t.task_date,t.minutes,t.priority,t.status,p.title plan_title
                           FROM study_tasks t JOIN study_plans p ON p.id=t.plan_id
                           WHERE t.user_id=? ORDER BY t.status='done',t.task_date,FIELD(t.priority,'high','normal','low') LIMIT 80", [$uid]);
        foreach ($rows as $r) $items[] = ['id'=>(int)$r['id'],'title'=>$r['title'],
            'subtitle'=>$r['plan_title'].($r['subject']?' · '.$r['subject']:''),
            'meta'=>$r['task_date'].' · '.(int)$r['minutes'].' min · '.ucfirst($r['priority']),
            'kind'=>'task','done'=>$r['status']==='done'];
    } elseif ($key === 'results') {
        $title = 'Results & boards'; $subtitle = 'Official boards and saved result alerts';
        $rows = fetch_all("SELECT b.id,b.name,b.short_name,b.type,
                           (SELECT COUNT(*) FROM result_alerts a WHERE a.board_id=b.id AND a.user_id=?) alerts
                           FROM boards b WHERE b.status='active' ORDER BY b.sort_order,b.name LIMIT 80", [$uid]);
        foreach ($rows as $r) $items[] = ['id'=>(int)$r['id'],'title'=>(string)($r['short_name']?:$r['name']),
            'subtitle'=>$r['name'],'meta'=>ucfirst($r['type']).' · '.(int)$r['alerts'].' saved alerts','kind'=>'board','done'=>false];
    } elseif ($key === 'notifications') {
        $title = 'Notifications'; $subtitle = 'Recent activity on your account';
        $rows = fetch_all("SELECT id,message,type,is_read,created_at FROM notifications WHERE user_id=? ORDER BY id DESC LIMIT 80", [$uid]);
        foreach ($rows as $r) $items[] = ['id'=>(int)$r['id'],'title'=>$r['message'],'subtitle'=>ucfirst($r['type']),
            'meta'=>time_ago($r['created_at']),'kind'=>'notification','done'=>(int)$r['is_read']===1];
    } elseif ($key === 'support') {
        $title = 'Help & support'; $subtitle = 'Your support requests and appeals';
        $rows = fetch_all("SELECT id,subject,topic,status,priority,ref,last_reply,created_at FROM tickets
                           WHERE user_id=? ORDER BY id DESC LIMIT 50", [$uid]);
        foreach ($rows as $r) $items[] = ['id'=>(int)$r['id'],'title'=>$r['subject'],'subtitle'=>'#'.$r['ref'].' · '.ucfirst($r['topic']),
            'meta'=>ucfirst($r['status']).' · '.ucfirst($r['priority']).' priority · '.time_ago($r['last_reply']?:$r['created_at']),
            'kind'=>'ticket','done'=>$r['status']==='closed'];
    } elseif ($key === 'profile' || $key === 'settings') {
        $title = $key === 'profile' ? 'Edit profile' : 'Privacy & security';
        $subtitle = $key === 'profile' ? 'Your public TaleemPK identity' : 'Account protection and privacy choices';
        $items = $key === 'profile' ? [
            ['id'=>1,'title'=>$u['name'],'subtitle'=>'@'.$u['username'],'meta'=>(string)($u['headline']?:$u['role']),'kind'=>'profile','done'=>(bool)$u['is_verified']],
            ['id'=>2,'title'=>'Location','subtitle'=>(string)($u['city']?:'Not added'),'meta'=>(string)$u['country'],'kind'=>'profile','done'=>false],
            ['id'=>3,'title'=>'About you','subtitle'=>(string)($u['bio']?:'Add a short introduction'),'meta'=>'Visible on your public profile','kind'=>'profile','done'=>!empty($u['bio'])],
        ] : [
            ['id'=>1,'title'=>'Two-step verification','subtitle'=>'Extra email code at sign in','meta'=>(int)$u['two_factor']===1?'Enabled':'Not enabled','kind'=>'setting','done'=>(int)$u['two_factor']===1],
            ['id'=>2,'title'=>'Profile privacy','subtitle'=>'Who can see your profile','meta'=>ucfirst($u['profile_privacy']),'kind'=>'setting','done'=>false],
            ['id'=>3,'title'=>'Online status','subtitle'=>'Show when you are active','meta'=>(int)$u['show_online']===1?'Visible':'Hidden','kind'=>'setting','done'=>(int)$u['show_online']===1],
        ];
    } else { mobile_error('That app section is not available.', 404); }
    mobile_out(['key'=>$key,'title'=>$title,'subtitle'=>$subtitle,'items'=>$items]);
}

if ($action === 'module_action') {
    $do = (string)($_POST['do'] ?? ''); $id = (int)($_POST['id'] ?? 0);
    if ($do === 'toggle_task') {
        $task = fetch_one('SELECT id,status FROM study_tasks WHERE id=? AND user_id=?', [$id,$uid]);
        if (!$task) mobile_error('That task is not available.', 404);
        $next = $task['status']==='done' ? 'pending' : 'done';
        q('UPDATE study_tasks SET status=?,completed_at=? WHERE id=?', [$next,$next==='done'?date('Y-m-d H:i:s'):null,$id]);
        mobile_out(['done'=>$next==='done']);
    }
    if ($do === 'toggle_online') {
        $next = (int)($u['show_online'] ?? 0) === 1 ? 0 : 1;
        update_row('users', ['show_online'=>$next], 'id=?', [$uid]);
        mobile_out(['enabled'=>$next===1]);
    }
    if ($do === 'cycle_privacy') {
        $levels = ['public','members','private'];
        $current = (string)($u['profile_privacy'] ?? 'public');
        $position = array_search($current, $levels, true);
        $next = $levels[(($position === false ? 0 : $position) + 1) % count($levels)];
        update_row('users', ['profile_privacy'=>$next], 'id=?', [$uid]);
        mobile_out(['privacy'=>$next]);
    }
    if ($do === 'read_notification') {
        q('UPDATE notifications SET is_read=1 WHERE id=? AND user_id=?', [$id,$uid]);
        mobile_out(['read'=>true]);
    }
    mobile_error('That action is not available.', 404);
}

if ($action === 'update_profile') {
    $name = mail_header_safe(trim((string)($_POST['name'] ?? '')));
    $city = mb_substr(trim((string)($_POST['city'] ?? '')), 0, 80);
    $headline = mb_substr(trim((string)($_POST['headline'] ?? '')), 0, 160);
    $bio = mb_substr(trim((string)($_POST['bio'] ?? '')), 0, 480);
    if (mb_strlen($name) < 3) mobile_error('Enter your full name.');
    update_row('users', [
        'name'=>$name, 'city'=>$city !== '' ? $city : null,
        'headline'=>$headline !== '' ? $headline : null,
        'bio'=>$bio !== '' ? $bio : null,
    ], 'id=?', [$uid]);
    log_activity($uid, 'mobile_profile_update', 'Updated profile in Android app');
    mobile_out(['message'=>'Profile updated.']);
}

if ($action === 'create_ticket') {
    if (!api_burst_limit('mobile_ticket', 4)) mobile_error('Too many support requests. Please wait a minute.', 429);
    $topics = ticket_topics();
    $topic = strtolower(trim((string)($_POST['topic'] ?? 'bug')));
    if (!isset($topics[$topic])) $topic = 'other';
    $subject = mb_substr(trim((string)($_POST['subject'] ?? '')), 0, 180);
    $body = mb_substr(trim((string)($_POST['body'] ?? '')), 0, 5000);
    if (mb_strlen($subject) < 5) mobile_error('Add a short subject for your request.');
    if (mb_strlen($body) < 10) mobile_error('Please describe the issue in a little more detail.');
    $priority = ticket_start_priority($topic, true);
    [$firstDue, $resolutionDue] = ticket_due_dates($priority);
    $ref = ticket_ref();
    $ticketId = insert_row('tickets', [
        'ref'=>$ref, 'user_id'=>$uid, 'topic'=>$topic, 'subject'=>$subject, 'body'=>$body,
        'device'=>mb_substr((string)($_SERVER['HTTP_USER_AGENT'] ?? 'TaleemPK Android'),0,180),
        'priority'=>$priority, 'first_response_due'=>$firstDue, 'resolution_due'=>$resolutionDue,
        'last_reply'=>date('Y-m-d H:i:s'),
    ]);
    log_activity($uid, 'mobile_support_ticket', 'Opened support ticket '.$ref);
    mobile_out(['id'=>$ticketId, 'ref'=>$ref, 'message'=>'Support request '.$ref.' created.'], 201);
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

if ($action === 'presence') {
    require_feature('feature_chat');
    $cid = (int)($_POST['conversation_id'] ?? 0);
    $member = fetch_one('SELECT id FROM conversation_members WHERE conversation_id=? AND user_id=?', [$cid,$uid]);
    if (!$member) mobile_error('That conversation is not yours.', 403);
    $kind = strtolower(trim((string)($_POST['kind'] ?? '')));
    if (!in_array($kind, ['text','voice'], true)) $kind = '';
    $sharesTyping = (int)($u['show_typing'] ?? 1) === 1;
    try {
        if ($sharesTyping && $kind !== '') {
            q('UPDATE conversation_members SET typing_at=NOW(),typing_kind=? WHERE conversation_id=? AND user_id=?', [$kind,$cid,$uid]);
        } else {
            q('UPDATE conversation_members SET typing_at=NULL WHERE conversation_id=? AND user_id=?', [$cid,$uid]);
        }
        $other = fetch_one("SELECT cm.typing_kind,u.name FROM conversation_members cm
                             JOIN users u ON u.id=cm.user_id
                            WHERE cm.conversation_id=? AND cm.user_id<>? AND cm.typing_at>=DATE_SUB(NOW(),INTERVAL 8 SECOND)
                            ORDER BY cm.typing_at DESC LIMIT 1", [$cid,$uid]);
    } catch (PDOException $e) {
        /* Graceful compatibility for a host where the schema migration has
           not run yet. Typing still works; voice is displayed as typing until
           the normal TaleemPK migrator adds typing_kind. */
        if ($sharesTyping && $kind !== '') {
            q('UPDATE conversation_members SET typing_at=NOW() WHERE conversation_id=? AND user_id=?', [$cid,$uid]);
        } else {
            q('UPDATE conversation_members SET typing_at=NULL WHERE conversation_id=? AND user_id=?', [$cid,$uid]);
        }
        $other = fetch_one("SELECT 'text' typing_kind,u.name FROM conversation_members cm
                             JOIN users u ON u.id=cm.user_id
                            WHERE cm.conversation_id=? AND cm.user_id<>? AND cm.typing_at>=DATE_SUB(NOW(),INTERVAL 8 SECOND)
                            ORDER BY cm.typing_at DESC LIMIT 1", [$cid,$uid]);
    }
    $readThrough = (int)fetch_col('SELECT COALESCE(MAX(last_read_id),0) FROM conversation_members WHERE conversation_id=? AND user_id<>?', [$cid,$uid]);
    mobile_out([
        'active'=>(bool)$other,
        'kind'=>$other ? (string)($other['typing_kind'] ?: 'text') : '',
        'name'=>$other ? (string)$other['name'] : '',
        'read_through'=>$readThrough,
    ]);
}

if ($action === 'messages') {
    require_feature('feature_chat');
    $cid = (int) ($_POST['conversation_id'] ?? 0);
    $afterId = max(0, (int)($_POST['after_id'] ?? 0));
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
            AND (?=0 OR m.id>?)
            AND NOT EXISTS(SELECT 1 FROM message_hides h WHERE h.message_id=m.id AND h.user_id=?)
          ORDER BY m.id DESC LIMIT 150', [$uid,$cid,$afterId,$afterId,$uid]
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
