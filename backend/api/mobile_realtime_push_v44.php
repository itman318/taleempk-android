<?php
/** TaleemPK v4.4 realtime WebSocket + Firebase Cloud Messaging helpers. */

function mobile_v44_cfg(string $env, string $settingKey = ''): string
{
    $value = getenv($env);
    if ($value !== false && trim((string)$value) !== '') return trim((string)$value);
    if ($settingKey !== '' && function_exists('setting')) {
        return trim((string) setting($settingKey, ''));
    }
    return '';
}

function mobile_v44_b64url(string $raw): string
{
    return rtrim(strtr(base64_encode($raw), '+/', '-_'), '=');
}

function mobile_v44_push_tables(): void
{
    static $ready = false;
    if ($ready) return;
    q("CREATE TABLE IF NOT EXISTS mobile_push_tokens (
        id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
        user_id BIGINT UNSIGNED NOT NULL,
        session_hash CHAR(64) NOT NULL,
        token VARCHAR(255) NOT NULL,
        platform VARCHAR(20) NOT NULL DEFAULT 'android',
        device_name VARCHAR(120) NULL,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        UNIQUE KEY uq_mobile_push_token (token),
        KEY idx_mobile_push_user (user_id),
        KEY idx_mobile_push_session (session_hash)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4");
    q("CREATE TABLE IF NOT EXISTS mobile_push_receipts (
        message_id BIGINT UNSIGNED NOT NULL,
        user_id BIGINT UNSIGNED NOT NULL,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (message_id,user_id),
        KEY idx_mobile_push_receipt_created (created_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4");
    $ready = true;
}

function mobile_v44_fcm_public_config(): array
{
    $project = mobile_v44_cfg('FIREBASE_PROJECT_ID', 'firebase_project_id');
    $appId = mobile_v44_cfg('FIREBASE_ANDROID_APP_ID', 'firebase_android_app_id');
    $sender = mobile_v44_cfg('FIREBASE_SENDER_ID', 'firebase_sender_id');
    $apiKey = mobile_v44_cfg('FIREBASE_API_KEY', 'firebase_api_key');
    return [
        'enabled' => $project !== '' && $appId !== '' && $sender !== '' && $apiKey !== '',
        'project_id' => $project,
        'app_id' => $appId,
        'sender_id' => $sender,
        'api_key' => $apiKey,
    ];
}

function mobile_v44_fcm_private_config(): array
{
    $project = mobile_v44_cfg('FIREBASE_PROJECT_ID', 'firebase_project_id');
    $email = mobile_v44_cfg('FIREBASE_CLIENT_EMAIL', 'firebase_client_email');
    $key = mobile_v44_cfg('FIREBASE_PRIVATE_KEY', 'firebase_private_key');
    $key = str_replace('\\n', "\n", $key);
    return [
        'enabled' => $project !== '' && $email !== '' && $key !== '',
        'project_id' => $project,
        'client_email' => $email,
        'private_key' => $key,
    ];
}

function mobile_v44_http_post(string $url, array $headers, string $body, int $timeout = 8): array
{
    if (!function_exists('curl_init')) return [0, ''];
    $ch = curl_init($url);
    curl_setopt_array($ch, [
        CURLOPT_POST => true,
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_HTTPHEADER => $headers,
        CURLOPT_POSTFIELDS => $body,
        CURLOPT_CONNECTTIMEOUT => 4,
        CURLOPT_TIMEOUT => $timeout,
    ]);
    $raw = curl_exec($ch);
    $status = (int) curl_getinfo($ch, CURLINFO_HTTP_CODE);
    curl_close($ch);
    return [$status, is_string($raw) ? $raw : ''];
}

function mobile_v44_fcm_access_token(): string
{
    $cfg = mobile_v44_fcm_private_config();
    if (!$cfg['enabled'] || !function_exists('openssl_sign')) return '';

    $cacheKey = hash('sha256', $cfg['project_id'] . '|' . $cfg['client_email']);
    $cacheFile = rtrim(sys_get_temp_dir(), DIRECTORY_SEPARATOR) . DIRECTORY_SEPARATOR . 'taleempk_fcm_' . $cacheKey . '.json';
    if (is_file($cacheFile)) {
        $cached = json_decode((string) @file_get_contents($cacheFile), true);
        if (is_array($cached) && !empty($cached['token']) && (int)($cached['exp'] ?? 0) > time() + 90) {
            return (string) $cached['token'];
        }
    }

    $now = time();
    $header = mobile_v44_b64url(json_encode(['alg'=>'RS256','typ'=>'JWT'], JSON_UNESCAPED_SLASHES));
    $claims = mobile_v44_b64url(json_encode([
        'iss' => $cfg['client_email'],
        'scope' => 'https://www.googleapis.com/auth/firebase.messaging',
        'aud' => 'https://oauth2.googleapis.com/token',
        'iat' => $now,
        'exp' => $now + 3600,
    ], JSON_UNESCAPED_SLASHES));
    $unsigned = $header . '.' . $claims;
    $signature = '';
    $private = openssl_pkey_get_private($cfg['private_key']);
    if (!$private || !openssl_sign($unsigned, $signature, $private, OPENSSL_ALGO_SHA256)) return '';
    $jwt = $unsigned . '.' . mobile_v44_b64url($signature);

    [$status, $raw] = mobile_v44_http_post(
        'https://oauth2.googleapis.com/token',
        ['Content-Type: application/x-www-form-urlencoded'],
        http_build_query([
            'grant_type' => 'urn:ietf:params:oauth:grant-type:jwt-bearer',
            'assertion' => $jwt,
        ]),
        8
    );
    if ($status < 200 || $status >= 300) return '';
    $data = json_decode($raw, true);
    $token = is_array($data) ? trim((string)($data['access_token'] ?? '')) : '';
    if ($token !== '') {
        @file_put_contents($cacheFile, json_encode([
            'token' => $token,
            'exp' => $now + max(300, (int)($data['expires_in'] ?? 3600)),
        ]), LOCK_EX);
    }
    return $token;
}

function mobile_v44_fcm_send_token(string $token, string $title, string $body, array $data): bool
{
    $cfg = mobile_v44_fcm_private_config();
    if (!$cfg['enabled']) return false;
    $access = mobile_v44_fcm_access_token();
    if ($access === '') return false;

    $payload = [
        'message' => [
            'token' => $token,
            'notification' => ['title' => $title, 'body' => $body],
            'data' => array_map(static fn($v): string => (string)$v, $data),
            'android' => [
                'priority' => 'high',
                'notification' => ['sound' => 'default'],
            ],
        ],
    ];
    [$status, $raw] = mobile_v44_http_post(
        'https://fcm.googleapis.com/v1/projects/' . rawurlencode($cfg['project_id']) . '/messages:send',
        ['Authorization: Bearer ' . $access, 'Content-Type: application/json'],
        json_encode($payload, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE),
        8
    );
    if ($status >= 200 && $status < 300) return true;
    if ($status === 400 || $status === 404) {
        $upper = strtoupper($raw);
        if (str_contains($upper, 'UNREGISTERED') || str_contains($upper, 'REGISTRATION-TOKEN-NOT-REGISTERED')) {
            mobile_v44_push_tables();
            q('DELETE FROM mobile_push_tokens WHERE token=?', [$token]);
        }
    }
    return false;
}

function mobile_v44_fcm_send_user(int $userId, string $title, string $body, array $data): bool
{
    mobile_v44_push_tables();
    $rows = fetch_all(
        "SELECT t.token FROM mobile_push_tokens t
          WHERE t.user_id=?
            AND EXISTS(SELECT 1 FROM mobile_sessions s
                        WHERE s.token_hash=t.session_hash AND s.user_id=t.user_id AND s.expires_at>NOW())
          ORDER BY t.updated_at DESC LIMIT 8",
        [$userId]
    );
    $sent = false;
    foreach ($rows as $row) {
        $token = trim((string)($row['token'] ?? ''));
        if ($token !== '' && mobile_v44_fcm_send_token($token, $title, $body, $data)) $sent = true;
    }
    return $sent;
}

if ($action === 'realtime_config') {
    $url = mobile_v44_cfg('TALEEMPK_WS_URL', 'realtime_ws_url');
    $secret = mobile_v44_cfg('TALEEMPK_REALTIME_SECRET', 'realtime_secret');
    if ($url === '' || $secret === '') {
        mobile_out(['enabled'=>false, 'url'=>'', 'ticket'=>'']);
    }
    $rooms = array_map(
        static fn(array $row): int => (int)$row['conversation_id'],
        fetch_all('SELECT conversation_id FROM conversation_members WHERE user_id=? ORDER BY conversation_id DESC LIMIT 250', [$uid])
    );
    $payload = json_encode([
        'uid' => $uid,
        'exp' => time() + 600,
        'rooms' => array_values(array_unique($rooms)),
    ], JSON_UNESCAPED_SLASHES);
    $encoded = mobile_v44_b64url($payload);
    $signature = mobile_v44_b64url(hash_hmac('sha256', $encoded, $secret, true));
    mobile_out([
        'enabled'=>true,
        'url'=>$url,
        'ticket'=>$encoded . '.' . $signature,
        'expires_in'=>600,
    ]);
}

if ($action === 'push_config') {
    mobile_out(mobile_v44_fcm_public_config());
}

if ($action === 'register_push') {
    $token = trim((string)($_POST['token'] ?? ''));
    if ($token === '' || strlen($token) > 255) mobile_error('Invalid push token.');
    mobile_v44_push_tables();
    $sessionHash = hash('sha256', mobile_bearer());
    $platform = strtolower(trim((string)($_POST['platform'] ?? 'android')));
    if (!in_array($platform, ['android','ios'], true)) $platform = 'android';
    q("INSERT INTO mobile_push_tokens(user_id,session_hash,token,platform,device_name)
       VALUES(?,?,?,?,?)
       ON DUPLICATE KEY UPDATE user_id=VALUES(user_id),session_hash=VALUES(session_hash),
       platform=VALUES(platform),device_name=VALUES(device_name),updated_at=NOW()",
       [$uid,$sessionHash,$token,$platform,mb_substr((string)($_POST['device'] ?? ''),0,120)]);
    mobile_out(['registered'=>true]);
}

if ($action === 'unregister_push') {
    $token = trim((string)($_POST['token'] ?? ''));
    mobile_v44_push_tables();
    if ($token !== '') q('DELETE FROM mobile_push_tokens WHERE user_id=? AND token=?', [$uid,$token]);
    mobile_out(['registered'=>false]);
}

if ($action === 'push_chat') {
    $cfg = mobile_v44_fcm_private_config();
    if (!$cfg['enabled']) mobile_out(['enabled'=>false,'sent'=>0]);

    $cid = max(0, (int)($_POST['conversation_id'] ?? 0));
    if (!$cid || !fetch_one('SELECT id FROM conversation_members WHERE conversation_id=? AND user_id=? LIMIT 1', [$cid,$uid])) {
        mobile_error('That conversation is not yours.', 403);
    }
    $message = fetch_one(
        "SELECT m.id,m.content,m.enc,m.attachment_name,m.voice_seconds,c.type,c.title
           FROM messages m JOIN conversations c ON c.id=m.conversation_id
          WHERE m.conversation_id=? AND m.sender_id=? AND m.status='sent'
          ORDER BY m.id DESC LIMIT 1",
        [$cid,$uid]
    );
    if (!$message) mobile_out(['enabled'=>true,'sent'=>0]);

    $mid = (int)$message['id'];
    $senderName = trim((string)($u['name'] ?? 'TaleemPK'));
    $title = (string)($message['type'] ?? '') === 'group'
        ? trim((string)($message['title'] ?? 'TaleemPK group'))
        : $senderName;
    if ((int)($message['enc'] ?? 0) === 1) {
        $body = 'New encrypted message';
    } elseif ((int)($message['voice_seconds'] ?? 0) > 0) {
        $body = 'Voice message';
    } elseif (trim((string)($message['attachment_name'] ?? '')) !== '') {
        $body = 'Photo or attachment';
    } else {
        $body = trim(strip_tags((string)($message['content'] ?? '')));
        if ($body === '') $body = 'New message';
        $body = mb_substr($body, 0, 140);
    }

    mobile_v44_push_tables();
    q("DELETE FROM mobile_push_receipts WHERE created_at<DATE_SUB(NOW(),INTERVAL 7 DAY)");
    $recipients = fetch_all(
        "SELECT cm.user_id,COALESCE(cm.is_muted,0) is_muted
           FROM conversation_members cm JOIN users u2 ON u2.id=cm.user_id
          WHERE cm.conversation_id=? AND cm.user_id<>? AND u2.status='active'",
        [$cid,$uid]
    );
    $sent = 0;
    foreach ($recipients as $recipient) {
        $rid = (int)$recipient['user_id'];
        if ((int)$recipient['is_muted'] === 1) continue;
        if (fetch_one('SELECT message_id FROM mobile_push_receipts WHERE message_id=? AND user_id=? LIMIT 1', [$mid,$rid])) continue;
        if (mobile_v44_fcm_send_user($rid, $title, $body, [
            'event'=>'message',
            'conversation_id'=>(string)$cid,
            'message_id'=>(string)$mid,
        ])) {
            q('INSERT IGNORE INTO mobile_push_receipts(message_id,user_id) VALUES(?,?)', [$mid,$rid]);
            $sent++;
        }
    }
    mobile_out(['enabled'=>true,'sent'=>$sent,'message_id'=>$mid]);
}
