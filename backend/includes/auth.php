<?php
/**
 * StudyHub - Session and access control.
 * Include order:  config/db.php -> includes/functions.php -> includes/auth.php
 */

if (session_status() === PHP_SESSION_NONE) {
    session_name(SESSION_NAME);
    session_set_cookie_params([
        'lifetime' => 0,
        'path'     => '/',
        'httponly' => true,
        'samesite' => 'Lax',
        'secure'   => request_is_https(),
    ]);
    session_start();
}

/* ---------------- current user ---------------- */

function current_user(): ?array
{
    static $user = null;
    static $loaded = false;
    static $loadedForUid = null;

    /* Bootstrap can read the guest identity before mobile.php validates a
       bearer token and attaches its user ID. Cache by that ID, not just by
       whether a lookup happened: a cached guest must not survive sign-in,
       and a cached account must not survive logout or an account switch. */
    $sessionUid = (int) ($_SESSION['uid'] ?? 0);

    if ($loaded && $loadedForUid === $sessionUid) {
        return $user;
    }
    $loaded = true;
    $loadedForUid = $sessionUid;
    $user = null;

    if ($sessionUid <= 0) {
        return null;
    }

    $user = fetch_one(
        'SELECT u.*, p.level, p.class_grade, p.institute_id, p.board_id, p.degree, p.department
         FROM users u LEFT JOIN profiles p ON p.user_id = u.id
         WHERE u.id = ? LIMIT 1',
        [$sessionUid]
    );

    if (!$user) {
        logout_user();
        return null;
    }

    // A banned or suspended account is dropped immediately.
    if ($user['status'] === 'banned') {
        $reason = $user['status_reason'] ?: 'This account was banned for breaking the community rules.';
        logout_user();
        $_SESSION['flash'][] = ['type' => 'error', 'message' => $reason];
        $user = null;
        return null;
    }
    if ($user['status'] === 'suspended') {
        if ($user['suspended_until'] && strtotime($user['suspended_until']) < time()) {
            q("UPDATE users SET status='active', suspended_until=NULL, status_reason=NULL WHERE id=?", [$user['id']]);
            $user['status'] = 'active';
        } else {
            $until = $user['suspended_until'] ? ' until ' . date('j M Y', strtotime($user['suspended_until'])) : '';
            logout_user();
            $_SESSION['flash'][] = ['type' => 'error', 'message' => 'This account is suspended' . $until . '.'];
            $user = null;
            return null;
        }
    }

    touch_last_seen((int) $user['id']);
    return $user;
}

function touch_last_seen(int $userId): void
{
    if (!empty($_SESSION['seen_at']) && (time() - (int) $_SESSION['seen_at']) < 60) {
        return;
    }
    $_SESSION['seen_at'] = time();
    q('UPDATE users SET last_seen = NOW(), last_ip = ?, admin_seen_at = NOW() WHERE id = ?',
      [client_ip(), $userId]);
}

function uid(): int
{
    $u = current_user();
    return $u ? (int) $u['id'] : 0;
}

function logged_in(): bool
{
    return current_user() !== null;
}

function user_role(): string
{
    $u = current_user();
    return $u ? (string) $u['role'] : 'guest';
}

/**
 * Let go of the session file.
 *
 * PHP's file session handler holds an EXCLUSIVE lock from session_start() until
 * the request ends. Every request from one person therefore runs strictly one
 * after another, however many the browser has in flight — and the chat polls
 * every three seconds. So a poll that takes half a second on a busy shared host
 * blocks that user's next page load, which blocks the one after it, and the
 * queue occupies a PHP process each. cPanel kills the account's processes when
 * the queue outgrows the entry-process limit: the whole site returns 500 for a
 * few minutes and then recovers on its own once the burst drains.
 *
 * A polling endpoint reads the session to learn who is asking and never writes
 * to it again. Handing the lock back at that point costs nothing and takes the
 * queue apart. Call it AFTER the last write to $_SESSION — anything written
 * after this is silently discarded.
 */
function session_release(): void
{
    if (session_status() === PHP_SESSION_ACTIVE) {
        session_write_close();
    }
}

function is_admin(): bool
{
    return user_role() === 'admin';
}

/**
 * A moderator is not a small admin.
 *
 * is_admin() deliberately stays false for them. It is asked in seventy places
 * that mean "the owner" — maintenance mode, rate-limit exemptions, reading
 * other people's private posts — and widening it would have handed all of that
 * to every moderator in one line. What a moderator may do is asked separately,
 * through mod_can(), and every answer comes from the permissions the admin
 * ticked for that account.
 */
function is_moderator(): bool
{
    return user_role() === 'moderator';
}

/** Anyone who may open the admin area at all. What they see there is theirs. */
function is_staff(): bool
{
    return in_array(user_role(), ['admin', 'moderator'], true);
}

function is_teacher(): bool
{
    return user_role() === 'teacher';
}

/* ---------------- login / logout ---------------- */

function login_user(int $userId, bool $remember = false): void
{
    session_regenerate_id(true);
    $_SESSION['uid']     = $userId;
    $_SESSION['seen_at'] = 0;
    /* When THIS session began. The admin idle timeout needs it: without it, a
       stale admin_seen_at from a session that ended yesterday looks exactly
       like thirty minutes of idling in the session that started a second ago. */
    $_SESSION['started'] = time();

    if ($remember) {
        session_start_device($userId);
    }

    q('UPDATE users SET last_seen = NOW(), last_ip = ?, admin_seen_at = NOW() WHERE id = ?',
      [client_ip(), $userId]);
    log_activity($userId, 'login', 'Signed in');
    award_daily_login($userId);
}

function award_daily_login(int $userId): void
{
    $today = fetch_col(
        "SELECT COUNT(*) FROM point_logs
         WHERE user_id = ? AND action = 'daily_login' AND DATE(created_at) = CURDATE()",
        [$userId]
    );
    if ((int) $today === 0) {
        add_points($userId, 'daily_login');
    }
}

function logout_user(): void
{
    $id = $_SESSION['uid'] ?? null;
    if ($id) {
        log_activity((int) $id, 'logout', 'Signed out');
    }
    session_forget_device();

    $flash = $_SESSION['flash'] ?? [];
    $_SESSION = [];
    $_SESSION['flash'] = $flash;
}

/* ---------------- guards ---------------- */

function require_login(string $why = ''): void
{
    if (logged_in()) {
        return;
    }
    if (is_ajax()) {
        json_out(['ok' => false, 'error' => 'Sign in to continue.', 'login' => true], 401);
    }
    $_SESSION['after_login'] = safe_return_path();
    if ($why !== '') {
        flash('info', $why);
    }
    redirect('login.php');
}

function require_role(string ...$roles): void
{
    require_login();
    if (!in_array(user_role(), $roles, true)) {
        if (is_ajax()) {
            json_out(['ok' => false, 'error' => 'You do not have access to this.'], 403);
        }
        http_response_code(403);
        flash('error', 'You do not have access to that page.');
        redirect('index.php');
    }
}

function require_admin(): void
{
    require_role('admin');
}

/** The admin area's front door. Which rooms open is decided per permission. */
function require_staff(): void
{
    require_role('admin', 'moderator');
}

function require_verified(): void
{
    require_login();
    $u = current_user();
    if ((int) setting('require_email_verify', 1) === 1 && (int) $u['email_verified'] === 0) {
        flash('info', 'Verify your email address to use this feature. Check your inbox for the link.');
        redirect('verify.php');
    }
}

/* ---------------- relationship checks ---------------- */

/**
 * Is there a block in either direction?
 *
 * Right for "may these two interact" — messaging, replying, following — which
 * is what most callers want. It is the WRONG question for "who blocked whom",
 * and the profile page was asking it that way: when somebody blocked YOU, your
 * view of their profile said "You blocked this person" and offered an Unblock
 * button that would have created a block from your side. Use i_blocked() or
 * blocked_me() whenever the direction matters.
 */
/**
 * Is either of these two blocking the other?
 *
 * Cached for the request. This is asked in loops — once per group member when
 * a message is sent, once per row when a member list is rendered — and it was a
 * query every time, for an answer that cannot change while a single request is
 * running.
 *
 * Keyed on the ordered pair so that is_blocked(a,b) and is_blocked(b,a) share
 * an entry: the question is symmetric and answering it twice would defeat the
 * point of caching it at all.
 */
function is_blocked(int $a, int $b): bool
{
    static $cache = [];
    if ($a < 1 || $b < 1) { return false; }

    $key = $a < $b ? "$a:$b" : "$b:$a";
    if (isset($cache[$key])) { return $cache[$key]; }

    return $cache[$key] = (int) fetch_col(
        'SELECT COUNT(*) FROM blocks
         WHERE (user_id = ? AND blocked_id = ?) OR (user_id = ? AND blocked_id = ?)',
        [$a, $b, $b, $a]
    ) > 0;
}

/** Did $me block $them? */
function i_blocked(int $me, int $them): bool
{
    if ($me < 1 || $them < 1) { return false; }
    return (int) fetch_col('SELECT COUNT(*) FROM blocks WHERE user_id = ? AND blocked_id = ?',
                           [$me, $them]) > 0;
}

/** Did $them block $me? */
function blocked_me(int $me, int $them): bool
{
    if ($me < 1 || $them < 1) { return false; }
    return (int) fetch_col('SELECT COUNT(*) FROM blocks WHERE user_id = ? AND blocked_id = ?',
                           [$them, $me]) > 0;
}

function is_following(int $followerId, int $followingId): bool
{
    return (int) fetch_col(
        'SELECT COUNT(*) FROM follows WHERE follower_id = ? AND following_id = ?',
        [$followerId, $followingId]
    ) > 0;
}

function can_message(int $fromId, int $toId): bool
{
    if ($fromId === $toId || is_blocked($fromId, $toId)) {
        return false;
    }
    $pref = fetch_col('SELECT allow_dm FROM users WHERE id = ?', [$toId]);
    if ($pref === 'nobody') {
        return false;
    }
    if ($pref === 'following') {
        return is_following($toId, $fromId);
    }
    return true;
}

function can_edit(?array $owner, $ownerId): bool
{
    if (is_admin()) {
        return true;
    }
    $id = is_array($owner) ? (int) ($owner['user_id'] ?? 0) : (int) $ownerId;
    return $id > 0 && $id === uid();
}

function unread_notifications(): int
{
    if (!logged_in()) {
        return 0;
    }
    return (int) fetch_col(
        'SELECT COUNT(*) FROM notifications WHERE user_id = ? AND is_read = 0',
        [uid()]
    );
}

function unread_messages(): int
{
    if (!logged_in()) {
        return 0;
    }
    return (int) fetch_col(
        'SELECT COALESCE(SUM(unread_count),0) FROM conversation_members WHERE user_id = ?',
        [uid()]
    );
}

/**
 * The saved-session restore and the maintenance gate both need security.php,
 * which is loaded after this file. bootstrap.php calls this once everything
 * is in place.
 */
function boot_gate(): void
{
    /* Cron and any other command-line run has no visitor, no address to block
       and no maintenance page to show. Gating it meant that switching
       maintenance mode on silently stopped every email on the site — including
       confirmation links and result alerts. */
    if (PHP_SAPI === 'cli') {
        return;
    }

    send_security_headers();
    session_restore();

    /* Sign-in and setup stay reachable from a blocked address, or an admin
       whose own address got caught would have no way back in. */
    $self = basename((string) ($_SERVER['SCRIPT_NAME'] ?? ''));
    $alwaysOpen = ['login.php', 'install.php', 'logout.php', 'forgot.php', 'reset.php'];

    if (!in_array($self, $alwaysOpen, true) && ip_is_banned() && !is_staff()) {
        http_response_code(403);
        echo '<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">';
        echo '<title>Blocked</title><div style="font-family:system-ui;max-width:420px;margin:18vh auto;'
           . 'padding:24px;text-align:center"><h1 style="font-size:20px">This address is blocked</h1>'
           . '<p>If you think that is a mistake, <a href="' . url('support.php') . '">write to us</a> — you do not need an account.</p></div>';
        exit;
    }

    if ((int) setting('maintenance_mode', 0) === 1 && !is_staff()) {
        /* Signing out has to keep working, or a member caught by maintenance
           mode is stuck signed in with no way to leave. */
        /* unsubscribe.php is here for the same reason cron_mail.php is: Gmail
           POSTs to it on its own schedule, and a 503 to a one-click
           unsubscribe is a promise that failed. The person who thinks they
           opted out and keeps getting mail reports it as spam. */
        $selfName = basename((string) ($_SERVER['SCRIPT_NAME'] ?? ''));
        if (!in_array($selfName, ['login.php', 'logout.php', 'cron_mail.php', 'unsubscribe.php'], true)) {

            /* An optional, honest ETA rather than a fixed guess. Only used when
               it parses and is still in the future — a stale or malformed value
               falls back to the plain message exactly as if it were blank,
               rather than showing a countdown to the past. */
            $untilRaw = trim((string) setting('maintenance_until', ''));
            $untilTs  = $untilRaw !== '' ? strtotime($untilRaw) : false;
            if ($untilTs !== false && $untilTs <= time()) { $untilTs = false; }

            http_response_code(503);
            header('Retry-After: ' . ($untilTs ? max(30, $untilTs - time()) : 600));

            /* An endpoint under /api/ answers with JSON, and handing it this
               page instead produces "unreadable response" on the screen rather
               than "the site is down for a few minutes". The path decides,
               exactly as it does in the error handlers. */
            if (strpos((string) ($_SERVER['SCRIPT_NAME'] ?? ''), '/api/') !== false) {
                header('Content-Type: application/json; charset=utf-8');
                echo json_encode(['ok' => false, 'maintenance' => true,
                    'error' => 'The site is down for a short update. Try again in a few minutes.']);
                exit;
            }

            /* This page is the whole site for as long as maintenance is on,
               so it is built like a page and not like an error string.

               It cannot use header.php: that loads the nav, the feed rail and
               the session furniture, all of which is what maintenance mode is
               keeping people out of. So the whole page is inline, and it has
               to be — deliberately, not by neglect. */
            $msg = trim((string) setting('maintenance_message', ''));
            /* Replace the earlier generic default as well as a blank setting.
               Existing installations keep their saved setting, so changing only
               the migration default would leave the old wording visible. */
            $legacyMsg = 'We are doing a quick update. Back in a few minutes.';
            if ($msg === '' || $msg === $legacyMsg) {
                $msg = 'Scheduled maintenance is in progress. We are applying updates to keep '
                     . e(site_name()) . ' secure, fast and reliable. Your account, posts, files, '
                     . 'results and messages are unaffected and will be exactly as you left them.';
            } else {
                $msg = e($msg);
            }

            /* NO contact address on this page, deliberately.
               It used to print mail_from()['reply'] as a mailto: link. This is
               the one page on the site that is served to EVERY unauthenticated
               request while maintenance is on — including crawlers and address
               harvesters — and a mailto: in plain markup is the easiest address
               on the internet to scrape. The support inbox is the same address
               that receives password resets and ticket replies, so filling it
               with spam is not a cosmetic problem.
               Somebody who genuinely needs us can write from support.php once
               the site is back, and the reply-to on every mail we have ever
               sent them already carries the address. */
            $started = trim((string) setting('maintenance_started', ''));
            $startTs = $started !== '' ? strtotime($started) : false;

            echo '<!doctype html><html lang="en"><head><meta charset="utf-8">';
            echo '<meta name="viewport" content="width=device-width,initial-scale=1">';
            echo '<meta name="color-scheme" content="light">';
            /* Search engines must not index a temporary page as if it were the
               site. 503 already tells a well-behaved crawler to come back, and
               this says it a second way. */
            echo '<meta name="robots" content="noindex,nofollow">';
            echo '<title>' . e(site_name()) . ' — scheduled maintenance</title>';
            echo '<style>'
               . ':root{--ink:#16213A;--ink-soft:#33405C;--paper:#F4F6FA;--line:#E3E8F0;'
               . '--marker:#D6F45B;--muted:#5A6782;--ok:#1E9E6A}'
               . '*{box-sizing:border-box}'
               . 'body{margin:0;min-height:100vh;display:grid;place-items:center;padding:20px;'
               . 'background:'
               . 'radial-gradient(58% 42% at 12% 6%,rgba(214,244,91,.16) 0,transparent 62%),'
               . 'radial-gradient(120% 62% at 50% 0,#22314F 0,#16213A 62%);'
               . "font-family:system-ui,-apple-system,'Segoe UI',Roboto,sans-serif;color:#fff;"
               . '-webkit-font-smoothing:antialiased}'
               . '.wrap{width:100%;max-width:460px}'
               . '.namebar{display:flex;align-items:center;justify-content:center;gap:8px;'
               . 'margin:0 0 14px;font-size:13px;font-weight:700;letter-spacing:.04em;'
               . 'color:rgba(255,255,255,.82);text-transform:uppercase}'
               /* A card with a rule across the top, the way a notice from an
                  institution is laid out. */
               . '.card{position:relative;overflow:hidden;background:#fff;color:var(--ink);'
               . 'border-radius:20px;padding:34px 26px 28px;'
               . 'box-shadow:0 24px 60px rgba(8,14,28,.38)}'
               . '.card:before{content:"";position:absolute;inset:0 0 auto;height:3px;'
               . 'background:linear-gradient(90deg,var(--ink) 0,var(--ink) 45%,var(--marker) 100%)}'
               . '.mark{width:52px;height:52px;margin:0 auto 16px;'
               . 'filter:drop-shadow(0 6px 14px rgba(22,33,58,.25))}'
               . '.mark svg{width:100%;height:100%}'
               . '.badge{display:flex;align-items:center;justify-content:center;gap:7px;'
               . 'padding:6px 13px;border-radius:999px;background:var(--paper);color:var(--muted);'
               . 'font-size:11px;font-weight:800;letter-spacing:.09em;text-transform:uppercase;'
               . 'width:max-content;margin:0 auto 16px}'
               . '.badge i{width:6px;height:6px;border-radius:50%;background:var(--marker);'
               . 'box-shadow:0 0 0 3px rgba(214,244,91,.35);animation:p 1.6s infinite}'
               . '@keyframes p{0%,100%{opacity:1}50%{opacity:.35}}'
               . 'h1{margin:0 0 10px;text-align:center;font-size:21px;line-height:1.25;'
               . "letter-spacing:-.01em;font-family:Georgia,'Times New Roman',serif}"
               . 'p.lead{margin:0 0 20px;text-align:center;font-size:14.5px;line-height:1.65;'
               . 'color:var(--muted)}'
               /* The status of the work itself, as a record rather than a
                  sentence: what is happening, when it began, when it ends. */
               . '.rec{display:grid;gap:1px;background:var(--line);border:1px solid var(--line);'
               . 'border-radius:12px;overflow:hidden;margin:0 0 18px}'
               . '.rec>div{background:#fff;padding:11px 14px;display:flex;'
               . 'align-items:baseline;justify-content:space-between;gap:12px}'
               . '.rec dt{font-size:10.5px;font-weight:800;letter-spacing:.09em;'
               . 'text-transform:uppercase;color:var(--muted);margin:0}'
               . '.rec dd{margin:0;font-size:13.5px;font-weight:700;color:var(--ink);'
               . 'text-align:right;font-variant-numeric:tabular-nums}'
               . '.rec dd.live{color:var(--ok)}'
               . '.eta{margin:0 0 18px;padding:15px 16px;background:var(--paper);border-radius:12px;'
               . 'border:1px solid var(--line);text-align:center}'
               . '.eta .lbl{font-size:10.5px;letter-spacing:.09em;text-transform:uppercase;'
               . 'color:var(--muted);font-weight:800;margin:0 0 5px}'
               . '.eta .clock{font-variant-numeric:tabular-nums;font-size:28px;font-weight:800;'
               . 'color:var(--ink);letter-spacing:.01em;line-height:1.1}'
               . '.eta .at{font-size:12.5px;color:var(--muted);margin-top:4px}'
               . '.dots{display:flex;gap:5px;justify-content:center;margin:0 0 20px}'
               . '.dots i{width:6px;height:6px;border-radius:50%;background:var(--line);'
               . 'animation:b 1.4s infinite}'
               . '.dots i:nth-child(2){animation-delay:.2s}.dots i:nth-child(3){animation-delay:.4s}'
               . '@keyframes b{0%,60%,100%{background:var(--line)}30%{background:var(--marker)}}'
               . '@media (prefers-reduced-motion:reduce){.dots i,.badge i{animation:none}}'
               /* Three assurances, because the question underneath "how long"
                  is always "is my work still there". */
               . '.assure{list-style:none;margin:0 0 20px;padding:0;display:grid;gap:8px}'
               . '.assure li{display:flex;align-items:flex-start;gap:9px;font-size:13px;'
               . 'line-height:1.5;color:var(--ink-soft)}'
               . '.assure li:before{content:"\\2713";flex:none;width:17px;height:17px;margin-top:1px;'
               . 'border-radius:50%;background:var(--marker);color:var(--ink);font-size:10px;'
               . 'font-weight:800;display:flex;align-items:center;justify-content:center}'
               . '.btn{display:block;text-align:center;padding:13px 26px;border-radius:11px;'
               . 'background:var(--ink);color:#fff;text-decoration:none;font-size:14.5px;'
               . 'font-weight:700}'
               . '.foot{margin:18px 0 0;text-align:center;font-size:12.5px;color:var(--muted);'
               . 'line-height:1.7;border-top:1px solid var(--line);padding-top:16px}'
               . '.foot a{color:var(--ink-soft)}'
               . '</style></head><body><div class="wrap">';
            echo '<p class="namebar">' . e(site_name()) . '</p>';
            echo '<div class="card">';
            echo '<div class="mark">' . logo_mark(52) . '</div>';
            echo '<div class="badge"><i></i>Maintenance in progress</div>';
            echo '<h1>' . e(site_name()) . ' is temporarily unavailable</h1>';
            echo '<p class="lead">' . $msg . '</p>';

            echo '<dl class="rec">';
            echo '<div><dt>Status</dt><dd class="live">Update in progress</dd></div>';
            if ($startTs) {
                echo '<div><dt>Began</dt><dd>' . e(date('j M, g:i A', $startTs)) . '</dd></div>';
            }
            echo '<div><dt>Expected back</dt><dd>'
               . ($untilTs ? e(date('j M, g:i A', $untilTs)) : 'Shortly') . '</dd></div>';
            echo '</dl>';

            if ($untilTs) {
                /* A live number rather than a static "back at X" is the
                   difference between a page that looks maintained and one that
                   looks abandoned mid-sentence.

                   Counted from a REMAINING figure worked out on the server, not
                   from a server timestamp compared against the browser's clock.
                   The old version did the latter, so a device whose clock ran
                   ahead saw the countdown already finished, reloaded, got this
                   page again and reloaded again — an endless refresh, for the
                   people least able to work out why. The reload is also capped
                   and delayed, so the worst case is a few polite retries
                   instead of a loop. */
                echo '<div class="eta">'
                   . '<div class="lbl">Estimated time remaining</div>'
                   . '<div class="clock" id="shCountdown">&mdash;</div>'
                   . '<div class="at">around ' . e(date('j M, g:i A', $untilTs)) . '</div>'
                   . '</div>';
                echo '<script nonce="' . e(csp_nonce()) . '">(function(){'
                   . 'var left=' . (int) max(0, $untilTs - time()) . ','
                   . 'el=document.getElementById("shCountdown"),done=false;'
                   . 'function tick(){'
                   . 'if(left<=0){if(done)return;done=true;'
                   . 'el.textContent="Checking\\u2026";'
                   . 'var n=0;try{n=parseInt(sessionStorage.getItem("shMx")||"0",10)||0;}catch(e){}'
                   . 'if(n<5){try{sessionStorage.setItem("shMx",String(n+1));}catch(e){}'
                   . 'setTimeout(function(){location.reload();},15000);}'
                   . 'else{el.textContent="Any moment now";}return;}'
                   . 'var h=Math.floor(left/3600),m=Math.floor(left%3600/60),s=left%60;'
                   . 'el.textContent=(h>0?h+"h ":"")+String(m).padStart(2,"0")+"m "'
                   . '+String(s).padStart(2,"0")+"s";left--;'
                   . '}tick();setInterval(tick,1000);'
                   . '})();</script>';
            } else {
                echo '<div class="dots"><i></i><i></i><i></i></div>';
            }

            echo '<ul class="assure">'
               . '<li>Nothing you have saved is affected — posts, files, results and messages are intact.</li>'
               . '<li>No action is required from you. The site returns on its own.</li>'
               . '<li>Sessions remain valid; you will not be signed out.</li>'
               . '</ul>';

            /* Something to do other than stare at it. Reloading is the only
               thing anybody wants from this page, and making them find the
               browser's own button is a small unkindness. */
            echo '<a class="btn" href="' . e(url('index.php')) . '">Check again</a>';
            echo '<p class="foot">Signed in already? <a href="' . e(url('logout.php')) . '">Sign out</a>.'
               . '<br>Nothing needs to be reported — the work is planned and this page updates itself.</p>';
            echo '</div></div></body></html>';
            exit;
        }
    }

    /* An unread moderator's notice stands in front of the site until it is
       acknowledged. Reading the rules, getting help and signing out are all
       deliberately still reachable — a notice that traps somebody with no way
       to appeal is a different thing from a notice. */
    $noticeOpen = ['notice.php', 'logout.php', 'support.php', 'page.php', 'ticket-file.php'];

    /* Not on an API call: those answer with JSON, and redirecting one produces a
       page where the caller expected an object. The restriction checks inside
       each endpoint are what stop the action there. */
    $isApi = strpos((string) ($_SERVER['SCRIPT_NAME'] ?? ''), '/api/') !== false;

    if (logged_in() && !$isApi && !in_array($self, $noticeOpen, true) && pending_warning()) {
        redirect('notice.php');
    }
}
