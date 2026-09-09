<?php
/**
 * Admin -> Health. Everything that is quietly wrong.
 *
 * Why this exists, plainly. This site is deployed by uploading a zip over the
 * live one. There is no staging copy, no version control, and no way back if
 * an upload goes badly. That has been survivable so far because there is
 * almost nobody using it — but the same setup with five hundred students on it
 * means a bad upload takes the site down and nothing says so.
 *
 * The specific thing that made this worth writing: error_reporting(0) sits in
 * the live config, and bootstrap.php's handler opens with
 * `if (!(error_reporting() & $severity)) return false;`. So PHP is silenced,
 * the site's own error log is silenced with it, and Admin -> Logs is
 * permanently empty. Every warning the site has ever raised has gone nowhere.
 * A page that has to be read to find that out is not much use, so this one
 * checks for it and says so at the top.
 *
 * Nothing here changes anything. It looks, and it reports.
 */

require_once dirname(__DIR__) . '/includes/bootstrap.php';
require_staff();
require_admin_permission('system');

/** One finding. 'bad' needs doing now, 'warn' soon, 'ok' is reassurance. */
function hc(string $level, string $title, string $detail, string $fix = ''): array
{
    return ['level' => $level, 'title' => $title, 'detail' => $detail, 'fix' => $fix];
}

$checks = [];

/* ---------- Can this site tell you when it breaks? ---------- */

$reporting = error_reporting();
if ($reporting === 0) {
    $checks[] = hc('bad', 'Errors are not being recorded',
        'error_reporting is 0, so PHP raises nothing and the site\'s own handler in '
      . 'bootstrap.php returns early on every warning. Admin → Logs will stay empty '
      . 'no matter what goes wrong.',
        'In config/config.php set error_reporting(E_ALL) and leave '
      . 'ini_set(\'display_errors\', \'0\'). Visitors still see nothing — display_errors '
      . 'is what decides that, not error_reporting.');
} else {
    $checks[] = hc('ok', 'Errors are being recorded', 'Warnings reach Admin → Logs.');
}

if (ini_get('display_errors') && !DEBUG_MODE) {
    $checks[] = hc('bad', 'PHP errors are visible to visitors',
        'display_errors is on with DEBUG_MODE off. An error message can expose file '
      . 'paths and query fragments to anybody who triggers it.',
        'Set ini_set(\'display_errors\', \'0\') in config/config.php.');
}

$errs = (int) fetch_col("SELECT COUNT(*) FROM app_errors WHERE created_at > DATE_SUB(NOW(), INTERVAL 24 HOUR)");
if ($errs > 50) {
    $checks[] = hc('warn', $errs . ' errors in the last day',
        'That is high enough that something is repeating rather than going wrong once.',
        'Admin → Logs, sorted by newest.');
}

/* ---------- Things that should not be on a live site ---------- */

if (is_file(dirname(__DIR__) . '/install.php')) {
    $checks[] = hc('warn', 'install.php is still on the server',
        'It refuses to run while config/config.php exists, so this is not an open door. '
      . 'But it has no reason to be there.',
        'Delete install.php over File Manager.');
} else {
    $checks[] = hc('ok', 'Installer removed', 'install.php is not on the server.');
}

$cfg = dirname(__DIR__) . '/config/config.php';
if (is_file($cfg) && is_writable($cfg)) {
    $checks[] = hc('warn', 'config.php is writable',
        'It holds the database password. Nothing needs to write to it after install.',
        'chmod it to 644, or 444 if your host allows.');
}

/* ---------- Is the schema what this code expects? ---------- */

/* db.php keeps the installed version in config/schema.lock, not in settings. */
$lockPath  = CONFIG_PATH . '/schema.lock';
$installed = is_file($lockPath) ? (int) trim((string) @file_get_contents($lockPath)) : 0;
$target    = max((int) SCHEMA_VERSION, (int) APP_SCHEMA_VERSION);

if ($installed !== $target) {
    $checks[] = hc('bad', 'Database is not on the expected version',
        'The code wants schema ' . $target . ' and config/schema.lock reports '
      . ($installed ?: 'nothing') . '. Tables or columns this build relies on may not exist yet.',
        'Load any page as an admin — the migrator runs on its own. If it stays behind, '
      . 'config/ is probably not writable, so the lock can never be saved and the migrator '
      . 're-runs on every single request.');
} else {
    $checks[] = hc('ok', 'Database schema is current', 'Version ' . $installed . '.');
}

/* ---------- Did the last upload actually land? ----------
   Files are uploaded by hand here, one folder at a time, and a partial upload
   is the failure that keeps happening: new PHP against an old stylesheet, or a
   page fixed in the zip but never copied across. The page cannot check every
   file, but it can check the handful that break loudly, by looking for a marker
   this build is known to contain. */
$fileMarks = [
    'chat.php'             => 'const playedQueue = new Set();',
    'assets/css/style.css' => '.voice-wave rect',
    'api/chat_poll.php'    => '$playsReady',
    'includes/render.php'  => 'function tick_shape',
    'includes/functions.php' => 'function admin_nav_items',
    'includes/auth.php'    => 'static $loadedForUid = null;',
    'api/mobile.php'       => "\$_SERVER['HTTP_X_REQUESTED_WITH'] = 'xmlhttprequest';",
    'includes/mobile_social.php' => "if (\$action === 'notifications')",
    'includes/api_boot.php' => "\$GLOBALS['native_api_endpoint']",
    '.htaccess'            => 'AddOutputFilterByType DEFLATE',
];
$stale = [];
foreach ($fileMarks as $rel => $needle) {
    $path = dirname(__DIR__) . '/' . $rel;
    if (!is_file($path) || strpos((string) @file_get_contents($path), $needle) === false) {
        $stale[] = $rel;
    }
}
if ($stale) {
    $checks[] = hc('bad', count($stale) . ' file' . (count($stale) === 1 ? '' : 's') . ' are older than this build',
        implode(', ', $stale) . ' do not contain what build ' . APP_VERSION . ' expects. '
      . 'That is a partial upload: some files from the zip were copied and these were not.',
        'Upload those files again from the zip, keeping the same folder structure.');
} else {
    $checks[] = hc('ok', 'All checked files match build ' . APP_VERSION,
        count($fileMarks) . ' key files verified.');
}

/* ---------- Did the site fall over recently? ----------
   A site that works, dies for a few minutes and then recovers on its own is
   almost never a code fault — code that is broken stays broken. It is the host
   killing the account's PHP processes because too many were alive at once.
   The 500s that result are logged, so the shape is visible here rather than
   having to be guessed at from a screenshot. */
$errWindow = fetch_all(
    "SELECT DATE_FORMAT(created_at, '%Y-%m-%d %H:%i') AS minute, COUNT(*) AS n
     FROM app_errors WHERE created_at >= DATE_SUB(NOW(), INTERVAL 24 HOUR)
     GROUP BY minute ORDER BY n DESC LIMIT 1");
$errTotal = (int) fetch_col(
    "SELECT COUNT(*) FROM app_errors WHERE created_at >= DATE_SUB(NOW(), INTERVAL 24 HOUR)");
if ($errWindow && (int) $errWindow[0]['n'] >= 10) {
    $checks[] = hc('warn', 'A burst of errors in the last day',
        (int) $errWindow[0]['n'] . ' in the single minute at ' . $errWindow[0]['minute']
      . ', ' . $errTotal . ' in 24 hours. Many errors in one minute followed by silence is the '
      . 'signature of the host killing processes, not of a broken page.',
        'Open Admin → Logs and read the top entry from that minute. If it names a resource '
      . 'limit rather than a file and line, ask the host to raise the entry-process limit.');
} elseif ($errTotal > 0) {
    $checks[] = hc('ok', 'Errors in the last day: ' . $errTotal,
        'Spread out rather than bunched, which points at individual pages rather than the host.');
}

/* Is the server compressing what it sends?
   style.css and app.js are 200 KB of text together and gzip to 48 KB. Whether
   that is happening is decided by .htaccess, which file managers hide by
   default — so it is the file most likely to be left behind in an upload, and
   the loss is invisible from inside the page. */
$gzOn = in_array('ob_gzhandler', @ob_list_handlers() ?: [], true)
     || (function_exists('apache_get_modules') && in_array('mod_deflate', (array) @apache_get_modules(), true))
     || strpos((string) ($_SERVER['HTTP_ACCEPT_ENCODING'] ?? ''), 'gzip') !== false;
if (!is_file(dirname(__DIR__) . '/.htaccess')) {
    $checks[] = hc('bad', 'The root .htaccess is missing',
        'Without it nothing is compressed and nothing is cached: about 200 KB of CSS and '
      . 'JavaScript are re-sent uncompressed on every first visit.',
        'Upload .htaccess from the build zip to the site root. File managers hide dotfiles — '
      . 'switch on "show hidden files" first.');
} elseif (!$gzOn) {
    $checks[] = hc('warn', 'Compression could not be confirmed',
        'The .htaccess is in place, but the server did not report gzip support.',
        'Ask the host whether mod_deflate is enabled.');
}

/* The lock file is not evidence. It is written the moment the migrator returns,
   whether or not every statement inside it succeeded — so it can report the
   newest version while a table from that version was never created. Nothing
   noticed until a page went looking for the table and answered with a 500.
   This asks the database instead of the lock. */
/* include, not require: migrator.php includes the same file, and a second
   require of an already-included path returns true rather than the array. */
$schemaDef = include INC_PATH . '/schema.php';
$expected  = is_array($schemaDef) ? array_keys($schemaDef) : [];
$present   = db_tables();

if (!$expected) {
    $checks[] = hc('warn', 'Could not read includes/schema.php',
        'The table list this build expects could not be loaded, so nothing was compared.');
} elseif (!$present) {
    /* Distinguished on purpose. "The list could not be read" and "the tables
       are gone" look identical if you only report the second, and the second
       is the one that starts a panic. */
    $checks[] = hc('warn', 'Could not read the database table list',
        'SHOW TABLES did not answer, so the tables could not be verified. This is a '
      . 'permissions problem on the database user, not missing data.',
        'Check that the database user in config/config.php has SHOW VIEW / basic schema rights.');
} else {
    $missing = [];
    foreach ($expected as $t) {
        if (!isset($present[strtolower($t)])) { $missing[] = $t; }
    }
    if ($missing) {
        $checks[] = hc('bad', count($missing) . ' table' . (count($missing) === 1 ? '' : 's') . ' missing from the database',
            'This build expects ' . implode(', ', array_slice($missing, 0, 8))
          . (count($missing) > 8 ? ' and ' . (count($missing) - 8) . ' more' : '')
          . '. Anything that reads them will fail rather than degrade.',
            'Delete config/schema.lock and load any page — the migrator re-runs from scratch and '
          . 'creates whatever is absent. Existing data is not touched.');
    } else {
        $checks[] = hc('ok', 'Every expected table exists',
            count($expected) . ' checked against the ' . count($present) . ' in the database.');
    }
}

if (!is_writable(CONFIG_PATH)) {
    $checks[] = hc('bad', 'config/ is not writable',
        'schema.lock cannot be saved, so the migrator re-runs its whole comparison on '
      . 'every request instead of once. On shared hosting that is a large amount of work '
      . 'repeated on every page load.',
        'chmod the config folder to 755.');
}

/* ---------- Is anything waiting for a human? ---------- */

$queues = [
    ['Posts waiting for review', (int) fetch_col("SELECT COUNT(*) FROM posts WHERE status='pending'"), 'posts.php?status=pending'],
    ['Open reports',             (int) fetch_col("SELECT COUNT(*) FROM reports WHERE status='open'"), 'reports.php'],
    ['Verification requests',    (int) fetch_col("SELECT COUNT(*) FROM verifications WHERE status='pending'"), 'verifications.php'],
    ['Library uploads',          (int) fetch_col("SELECT COUNT(*) FROM resources WHERE status='pending'"), 'resources.php'],
];
foreach ($queues as [$label, $n, $where]) {
    if ($n > 0) {
        $checks[] = hc($n > 20 ? 'warn' : 'info', $label . ': ' . $n,
            'Waiting on somebody. Students who post a picture cannot see it until this is cleared.',
            $where);
    }
}

/* ---------- Email ---------- */

$queued = (int) fetch_col("SELECT COUNT(*) FROM email_queue WHERE status='queued'");
$stuck  = (int) fetch_col("SELECT COUNT(*) FROM email_queue WHERE status='queued' AND attempts >= 3");
$lastRun = (string) setting('mail_last_run', '');

if ($lastRun === '') {
    $checks[] = hc($queued > 0 ? 'bad' : 'warn', 'The mail cron has never run',
        'Nothing has ever drained the queue, so sign-in codes and password resets are '
      . 'sitting in the database rather than arriving.'
      . ($queued > 0 ? ' There are ' . $queued . ' waiting right now.' : ''),
        'Add a cPanel cron job for cron_mail.php, every five minutes.');
} else {
    $checks[] = hc('ok', 'Mail cron is running', 'Last run: ' . $lastRun);
}
if ($stuck > 0) {
    $checks[] = hc('warn', $stuck . ' messages have given up',
        'Three failed attempts each. Usually the SMTP details or the host blocking the port.',
        'Admin → Email.');
}

/* ---------- Uploads ---------- */

$upDir = dirname(__DIR__) . '/uploads';
if (!is_writable($upDir)) {
    $checks[] = hc('bad', 'The uploads folder is not writable',
        'Nobody can attach a photo or a paper. Uploads will fail with a message that '
      . 'does not explain why.',
        'chmod uploads/ to 755 and check it is owned by the web user.');
}
foreach (['verify', 'payments', 'tickets'] as $sensitive) {
    $ht = $upDir . '/' . $sensitive . '/.htaccess';
    if (is_dir($upDir . '/' . $sensitive) && !is_file($ht)) {
        $checks[] = hc('bad', 'uploads/' . $sensitive . ' is unprotected',
            'That folder holds identity documents and payment receipts, and its .htaccess '
          . 'is missing — the files can be fetched by anybody who knows the address.',
            'Re-upload the .htaccess from the release zip.');
    }
}

/* ---------- Moderation settings that may have drifted ---------- */

if ((int) setting('filter_enabled', 1) !== 1) {
    $checks[] = hc('warn', 'The language filter is off',
        'Posts, replies and messages are not being checked for abuse.',
        'settings.php');
}
if ((int) setting('media_review', 1) !== 1) {
    $checks[] = hc('warn', 'Pictures from new accounts are not reviewed',
        'Anybody who signs up can publish an image straight to the feed. On a site used '
      . 'by schoolchildren this is the check that matters most.',
        'settings.php');
}
if ((int) setting('require_email_verify', 1) !== 1) {
    $checks[] = hc('warn', 'Email confirmation is off',
        'Accounts can be made with an address nobody owns, which removes the floor under '
      . 'every other trust rule.',
        'settings.php');
}

/* ---------- Is anybody here? ---------- */

$users = (int) fetch_col('SELECT COUNT(*) FROM users WHERE deleted_at IS NULL');
$posts = (int) fetch_col("SELECT COUNT(*) FROM posts WHERE status='active'");
$week  = (int) fetch_col("SELECT COUNT(*) FROM posts WHERE status='active' AND created_at > DATE_SUB(NOW(), INTERVAL 7 DAY)");
$unans = (int) fetch_col("SELECT COUNT(*) FROM posts WHERE status='active' AND type='question' AND comments_count=0");

if ($unans > 0 && $users < 50) {
    $checks[] = hc('warn', $unans . ' question' . ($unans === 1 ? '' : 's') . ' with no answer',
        'On a site this size an unanswered question usually stays unanswered, and the '
      . 'student who asked does not come back to ask a second one. This is the number '
      . 'worth watching before any other.',
        '');
}

$order = ['bad' => 0, 'warn' => 1, 'info' => 2, 'ok' => 3];
usort($checks, fn($a, $b) => $order[$a['level']] <=> $order[$b['level']]);

$bad  = count(array_filter($checks, fn($c) => $c['level'] === 'bad'));
$warn = count(array_filter($checks, fn($c) => $c['level'] === 'warn'));

$page_title = 'Health';
require INC_PATH . '/admin_header.php';
?>

<div class="card">
  <h2 style="margin-top:0">Health</h2>
  <p class="small muted">Read-only. Nothing on this page changes anything.</p>

  <p class="hc-summary hc-<?= $bad ? 'bad' : ($warn ? 'warn' : 'ok') ?>">
    <?php if ($bad): ?>
      <strong><?= $bad ?></strong> thing<?= $bad === 1 ? '' : 's' ?> need attention now<?php
        if ($warn): ?>, and <?= $warn ?> worth looking at<?php endif; ?>.
    <?php elseif ($warn): ?>
      Nothing urgent. <strong><?= $warn ?></strong> worth looking at.
    <?php else: ?>
      Everything checks out.
    <?php endif; ?>
  </p>
</div>

<?php foreach ($checks as $c): ?>
  <div class="card hc-item hc-<?= $c['level'] ?>">
    <div class="hc-title"><?= e($c['title']) ?></div>
    <p class="small" style="margin:6px 0 0"><?= e($c['detail']) ?></p>
    <?php if ($c['fix'] !== ''): ?>
      <p class="small muted" style="margin:8px 0 0">
        <?php if (str_ends_with($c['fix'], '.php') || str_contains($c['fix'], '.php?')): ?>
          <a href="<?= e($c['fix']) ?>">Open it</a>
        <?php else: ?>
          <strong>Fix:</strong> <?= e($c['fix']) ?>
        <?php endif; ?>
      </p>
    <?php endif; ?>
  </div>
<?php endforeach; ?>

<?php
/* Voice calls are the one feature that can be switched on, look correctly
   configured, and still fail for most of the people using it — because
   whether two phones can reach each other has nothing to do with this server.
   Without these numbers there is no way to find that out except by being told,
   and the people it fails for mostly do not report it; they stop trying.

   The number that matters is the connection rate. Anything under about 80%
   means calls are being attempted and not connecting, and on Pakistani mobile
   networks that almost always means one thing: STUN alone is not enough and a
   TURN relay is needed. That diagnosis is written out below rather than left
   for somebody to work out from a percentage. */
if (table_exists('calls') && (int) setting('chat_calls', 1) === 1):
    $cs = fetch_one("SELECT
            COUNT(*) AS total,
            SUM(status = 'ended')    AS ended,
            SUM(status = 'missed')   AS missed,
            SUM(status = 'declined') AS declined,
            SUM(status = 'failed' OR end_reason = 'failed') AS failed,
            SUM(seconds) AS secs,
            SUM(answered_at IS NOT NULL) AS answered
        FROM calls WHERE created_at > DATE_SUB(NOW(), INTERVAL 7 DAY)")
        ?: ['total' => 0];

    $total    = (int) ($cs['total'] ?? 0);
    $answered = (int) ($cs['answered'] ?? 0);
    $failed   = (int) ($cs['failed'] ?? 0);
    /* Out of the calls somebody actually picked up — a missed call is not a
       connection failure, it is a person who did not answer. */
    $rate = $answered > 0 ? round((($answered - $failed) / $answered) * 100) : null;
?>
<div class="card">
  <div class="hc-title">Voice calls, last 7 days</div>
  <?php if ($total === 0): ?>
    <p class="small muted" style="margin:6px 0 0">No calls yet.</p>
  <?php else: ?>
    <p class="small muted" style="margin:6px 0 0">
      <?= number_format($total) ?> started ·
      <?= number_format($answered) ?> answered ·
      <?= number_format((int) ($cs['missed'] ?? 0)) ?> missed ·
      <?= number_format((int) ($cs['declined'] ?? 0)) ?> declined ·
      <?= number_format($failed) ?> failed to connect
      <?php if ((int) ($cs['secs'] ?? 0) > 0): ?>
        · <?= number_format((int) ($cs['secs'] ?? 0) / 60, 1) ?> minutes of talking
      <?php endif; ?>
    </p>
    <?php if ($rate !== null): ?>
      <p class="small" style="margin:8px 0 0;font-weight:700;color:<?= $rate >= 80 ? 'var(--live)' : 'var(--redpen)' ?>">
        <?= $rate ?>% of answered calls connected
      </p>
      <?php if ($rate < 80 && $answered >= 5): ?>
        <p class="small muted" style="margin:6px 0 0">
          Calls are being answered and then failing. That is almost never this server — it is two phones
          that cannot find a route to each other. Public STUN gets through most home and office Wi-Fi and
          not through the carrier-grade NAT most Pakistani mobile networks sit behind. Add a TURN relay
          under <a href="<?= url('admin/settings.php') ?>#chat">Settings → Chat → call_ice_servers</a>,
          one per line: <span class="mono">turn:host:3478?transport=udp|user|pass</span>
        </p>
      <?php endif; ?>
    <?php endif; ?>
  <?php endif; ?>
</div>
<?php endif; ?>

<?php
/* Disk. Shared hosting gives a quota and no warning before it is reached, and
   the first symptom is uploads silently failing — which looks like a bug in
   the site rather than a full disk. Voice notes make this sharper: they arrive
   constantly, nobody deletes them, and at the bitrate they are recorded at a
   busy week is a few hundred megabytes.

   Walking the folder is slow enough to matter on a page somebody refreshes, so
   the answer is cached for an hour. It does not need to be to the minute. */
$storage = cache_remember('admin_upload_bytes', 3600, static function (): array {
    $dir = dirname(__DIR__) . '/uploads';
    if (!is_dir($dir)) { return ['bytes' => 0, 'files' => 0]; }
    $bytes = 0; $files = 0;
    try {
        $it = new RecursiveIteratorIterator(
            new RecursiveDirectoryIterator($dir, FilesystemIterator::SKIP_DOTS),
            RecursiveIteratorIterator::LEAVES_ONLY
        );
        foreach ($it as $f) {
            if ($f->isFile()) { $bytes += $f->getSize(); $files++; }
        }
    } catch (Throwable $e) { /* unreadable subfolder: report what we counted */ }
    return ['bytes' => $bytes, 'files' => $files];
});
?>
<div class="card">
  <div class="hc-title">Storage</div>
  <p class="small muted" style="margin:6px 0 0">
    <?= number_format($storage['bytes'] / 1048576, 1) ?> MB in
    <?= number_format((int) $storage['files']) ?> uploaded files
    <?php $free = @disk_free_space(dirname(__DIR__)); if ($free): ?>
      · <?= number_format($free / 1073741824, 1) ?> GB free on the disk
    <?php endif; ?>
  </p>
  <p class="small muted" style="margin:6px 0 0">Counted once an hour, not on every load.</p>
</div>

<div class="card">
  <div class="hc-title">Where the site is</div>
  <p class="small muted" style="margin:6px 0 0">
    <?= number_format($users) ?> members ·
    <?= number_format($posts) ?> posts ·
    <?= number_format($week) ?> in the last week ·
    build <?= e(APP_VERSION) ?> ·
    PHP <?= e(PHP_VERSION) ?>
  </p>
</div>

<?php require INC_PATH . '/admin_footer.php'; ?>
