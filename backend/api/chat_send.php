<?php
require_once dirname(__DIR__) . '/includes/api_boot.php';
require_once dirname(__DIR__) . '/includes/push.php';
require_once dirname(__DIR__) . '/includes/chat_helpers.php'; require_feature('feature_chat');
require_login();
block_if_restricted('message');

/* Messaging had no ceiling of its own. One script could fill somebody's inbox
   faster than they could block it, and every message notifies. */
if (!api_burst_limit('chat_send', 30)) {
    json_out(['ok' => false, 'error' => 'You are sending very fast. Wait a moment.']);
}
require_verified_api();

if ((int) setting('chat_enabled', 1) === 0) {
    json_out(['ok' => false, 'error' => 'Chat is switched off right now.']);
}

/* An account minutes old sending messages is almost always a nuisance
   account. The setting existed and was seeded, but nothing ever read it. */
$minAgeDays = (int) setting('chat_min_account_age', 0);
if ($minAgeDays > 0 && !is_admin()) {
    $joined = strtotime((string) current_user()['created_at']);
    if ($joined && $joined > time() - $minAgeDays * 86400) {
        json_out(['ok' => false, 'error' => 'New accounts can start chatting after '
            . $minAgeDays . ' day' . ($minAgeDays === 1 ? '' : 's') . '.']);
    }
}

$cid     = (int) ($_POST['conversation_id'] ?? 0);
$content = trim((string) ($_POST['content'] ?? ''));

/* End-to-end encrypted messages arrive as an opaque base64 packet. The server
   cannot read them, so every step below that inspects text — the word filter,
   the link-preview scan, @mention parsing, the conversation-list excerpt —
   must be skipped rather than run against ciphertext. Skipping is not a
   weakening of those checks: there is genuinely nothing there to check, and
   running them anyway would produce a link preview of random base64 and an
   inbox excerpt of gibberish. Moderation of encrypted messages happens by
   report, where the reporter's own device supplies the plaintext. */
/* Two packet shapes now, because a group cannot use the pairwise format:
     "1.<iv>.<ct>"              a private thread, keyed by ECDH between the two
     "g1.<epoch>.<iv>.<ct>"     a group, keyed by the group key of that epoch

   The epoch is carried IN the packet so a message stays readable after the
   group re-keys — without it, one member leaving would make the whole history
   undecryptable. The server checks only the shape; it cannot check the
   contents, which is the point of the feature. */
$isEnc = ((int) ($_POST['enc'] ?? 0) === 1) && $content !== '';
if ($isEnc) {
    $privateShape = (bool) preg_match('~^1\.[A-Za-z0-9+/=]{12,}\.[A-Za-z0-9+/=]{8,}$~', $content);
    $groupShape   = (bool) preg_match('~^g1\.[0-9]{1,9}\.[A-Za-z0-9+/=]{12,}\.[A-Za-z0-9+/=]{8,}$~', $content);

    if (!$privateShape && !$groupShape) {
        json_out(['ok' => false, 'error' => 'That encrypted message is malformed.']);
    }
}

/* The token the composer makes up once per tap of Send. Checked before
   anything else is validated, so a resend of the same attempt — a slow
   connection the browser retried on its own, a double-tap fast enough to
   land before the button actually disabled — answers with the message
   that already exists rather than filtering, uploading and inserting a
   second time. Scoped to sender AND conversation: a token is only ever
   compared against this same person's own recent sends, so nothing about
   it lets one request affect another person's message.

   A build uploaded by hand before the migration ran has no client_token
   column; table_exists/column checks elsewhere in this codebase guard
   exactly that case, and the same caution applies here. */
$clientToken = mb_substr(trim((string) ($_POST['client_token'] ?? '')),0,40);
if ($clientToken !== '') {
    try {
        $dupe = fetch_one(
            'SELECT id FROM messages WHERE conversation_id = ? AND sender_id = ? AND client_token = ?
             ORDER BY id DESC LIMIT 1',
            [$cid, uid(), $clientToken]
        );
        if ($dupe) { json_out(['ok' => true, 'id' => (int) $dupe['id']]); }
    } catch (PDOException $e) { /* column not migrated yet on this install */ }
}

$member = fetch_one('SELECT id FROM conversation_members WHERE conversation_id = ? AND user_id = ?', [$cid, uid()]);
if (!$member) { json_out(['ok' => false, 'error' => 'That conversation is not yours.'], 403); }

$conv = fetch_one('SELECT type, title FROM conversations WHERE id = ?', [$cid]);
$conversationTitle = ($conv && $conv['type'] === 'group' && $conv['title'] !== '')
    ? '"' . $conv['title'] . '"' : '';

/* The packet shape has to match the thread, and this is the first point where
   both are known — $conv is loaded here, after the format check above.
   A group packet in a private thread, or the reverse, would be stored as
   something the other side has no way to open: a message that looks delivered
   and is simply unreadable, with nothing to say why. */
if ($isEnc) {
    $threadIsGroup = $conv && (string) $conv['type'] === 'group';
    if ($threadIsGroup !== $groupShape) {
        json_out(['ok' => false, 'error' => 'That encrypted message is malformed.']);
    }
}

/* is_muted comes back with the membership.
   It was fetched again, one query per recipient, in the notification loop at
   the bottom of this file — so a group of thirty ran thirty extra queries on
   every message sent, to read a column that was already in this table. The
   loop is the hottest path on the site. */
$others = fetch_all('SELECT user_id, is_muted FROM conversation_members
                     WHERE conversation_id = ? AND user_id <> ?', [$cid, uid()]);
foreach ($others as $o) {
    if (is_blocked(uid(), (int) $o['user_id'])) {
        json_out(['ok' => false, 'error' => 'You cannot send messages in this conversation.']);
    }
}

if ($content === '' && empty($_FILES['attachment']['name']) && empty($_FILES['voice']['name'])) {
    json_out(['ok' => false, 'error' => 'Write something first.']);
}
/* Ciphertext is roughly a third longer than its plaintext, so the limit has
   to allow for that or a message the composer accepted would be refused here. */
if (mb_strlen($content) > ($isEnc ? 6000 : 4000)) { json_out(['ok' => false, 'error' => 'Keep the message under 4000 characters.']); }
if (!$isEnc && bad_words($content)) { json_out(['ok' => false, 'error' => 'That message contains words this community does not allow.']); }

$att = null;
$voiceSeconds = 0;
$voiceWave = '';

/* An end-to-end encrypted attachment arrives as a featureless blob. None of
   the usual checks apply to it and running them would be nonsense: there is no
   image inside to validate, no MIME type that matches its contents, and
   compressing it would destroy it. So it takes a different route — accepted as
   .bin, stored untouched, and recorded with type 'enc'.

   The real filename and MIME type are NOT here: both leak. A directory holding
   "Physics_paper_2024_leaked.pdf" tells the story without anyone opening it,
   and image/jpeg beside a 4MB size says plenty too. Both live inside the
   encrypted header, and the server is told the file is called "Encrypted
   file", which is all it needs to know. */
$encAtt = ((int) post('enc_att') === 1)
    && (!empty($_FILES['attachment']['name']) || !empty($_FILES['voice']['name']));
/* Group threads used to be refused here: with no shared key, an encrypted
   attachment could never have been opened by anybody. They have one now — see
   conversation_keys — so a group file is sealed under the group key exactly as
   a private one is sealed under the pairwise key, and the check is gone.
   Everything below treats both the same, because to this server both are the
   same featureless blob. */

/* --- voice note ------------------------------------------------------------
   A recording arrives in its own field, so the server can enforce the voice
   switch, duration and a size ceiling that matches the claimed duration. */
if (!empty($_FILES['voice']['name'])) {
    if ((int) setting('chat_voice_notes', 1) === 0) {
        json_out(['ok' => false, 'error' => 'Voice messages are switched off right now.']);
    }
    $maxSeconds = max(10, min(300, (int) setting('chat_voice_max_seconds', 120)));
    $voiceSeconds = (int) post('voice_seconds');
    if ($voiceSeconds < 1) {
        json_out(['ok' => false, 'error' => 'That recording came through empty. Try again.']);
    }
    if ($voiceSeconds > $maxSeconds) {
        json_out(['ok' => false, 'error' => 'Voice messages can be up to ' . $maxSeconds . ' seconds.']);
    }

    /* AAC at 96 kbps is about 12 KB/s and Opus at 64 kbps about 8 KB/s.
       Leave safe container overhead while refusing oversized fake clips. */
    $voiceMax = min(MAX_CHAT_FILE_SIZE, max(512 * 1024, $maxSeconds * 16 * 1024));
    if ($encAtt) {
        $up = upload_file($_FILES['voice'], 'chat', 'bin', $voiceMax);
        if (!$up['ok']) { json_out(['ok' => false, 'error' => $up['error']]); }
        $up['ext']  = 'enc';
        $up['name'] = 'Encrypted voice message';
    } else {
        $up = upload_file($_FILES['voice'], 'chat', 'webm,ogg,m4a,mp4,mp3', $voiceMax);
        if (!$up['ok']) { json_out(['ok' => false, 'error' => $up['error']]); }
    }
    $att = $up;
    $content = '';

    /* Stored waveform is filtered before it is rendered as SVG. */
    $voiceWave = preg_replace('/[^0-9a-f]/', '', strtolower((string) post('voice_wave')));
    $voiceWave = substr((string) $voiceWave, 0, 64);
}

if (!$att && !empty($_FILES['attachment']['name'])) {
    if ((int) setting('chat_attachments', 1) === 0) {
        json_out(['ok' => false, 'error' => 'Attachments are switched off right now.']);
    }
    if ($encAtt) {
        $up = upload_file($_FILES['attachment'], 'chat', 'bin', MAX_CHAT_FILE_SIZE);
        if (!$up['ok']) { json_out(['ok' => false, 'error' => $up['error']]); }
        $up['ext']  = 'enc';
        $up['name'] = 'Encrypted file';
        $up['w'] = null; $up['h'] = null;
    } else {
        $up = upload_file($_FILES['attachment'], 'chat', ALLOWED_IMAGE_EXT . ',' . ALLOWED_DOC_EXT, MAX_CHAT_FILE_SIZE);
        if (!$up['ok']) { json_out(['ok' => false, 'error' => $up['error']]); }
    }
    $att = $up;
}

/* Private messages get the hard list only. A one-to-one conversation between
   two students is not a place to hold anything for review — there is no queue
   that could return it, and a message that silently never arrives is worse
   than one that is refused out loud. The words with no innocent reading are
   still refused: this is where the worst of it goes on a student site,
   precisely because nobody else can see it. */
if ($content !== '' && !$isEnc) {
    $filter = wf_check($content);
    if ($filter['action'] === 'block') {
        log_activity(uid(), 'filter_block', 'message blocked: ' . $filter['term']);
        json_out(['ok' => false, 'error' => wf_block_message()]);
    }
}

$messageRow = [
    'conversation_id' => $cid,
    'sender_id'       => uid(),
    'content'         => $content ?: null,
    'enc'             => $isEnc ? 1 : 0,
    'attachment'      => $att['path'] ?? null,
    'attachment_name' => $att['name'] ?? null,
    'attachment_type' => $att['ext'] ?? null,
    'attachment_size' => $att['size'] ?? 0,
    'voice_seconds'   => $voiceSeconds,
    /* Only a message from this same conversation may be replied to — a reply
       pointing anywhere else would quote a thread you might not be in. */
    'reply_to_id'     => (($rid = (int) post('reply_to')) > 0
        && fetch_one('SELECT id FROM messages WHERE id = ? AND conversation_id = ?', [$rid, $cid]))
        ? $rid : null,
];
if ($clientToken !== '') { $messageRow['client_token'] = mb_substr($clientToken, 0, 40); }
if (!empty($voiceWave)) { $messageRow['voice_wave'] = $voiceWave; }

try {
    $mid = insert_row('messages', $messageRow);
} catch (PDOException $e) {
    /* A build uploaded by hand before the migration has run may have no
       client_token column. Idempotency is a useful optimisation, but losing a
       real message is worse, so an unencrypted message can fall back without
       that optional column. */
    unset($messageRow['voice_wave'], $messageRow['client_token']);
    /* `enc` is different in kind. Dropping it would store ciphertext in a row
       flagged as plain text, and every reader would then be shown base64
       forever with no way to tell it was ever encrypted. Better to refuse the
       send and say why: the fix is one page load, which runs the migrator. */
    if (!empty($messageRow['enc'])) {
        try {
            $mid = insert_row('messages', $messageRow);
        } catch (PDOException $e2) {
            json_out(['ok' => false, 'error' => 'Encryption is not ready on the server yet. Open any page once to finish setting it up, then try again.']);
        }
    } else {
        unset($messageRow['enc']);
        $mid = insert_row('messages', $messageRow);
    }
}

/* Generate one compact link card after the message exists. This is deliberately
   best-effort: a slow or unavailable website must never prevent a message from
   being sent. The helper only follows a public http/https host and never follows
   redirects, which also keeps the chat endpoint from becoming an SSRF proxy. */
if ($content !== '' && !$voiceSeconds && !$isEnc) {
    if (preg_match('~https?://[^\s<>]+|www\.[^\s<>]+\.[A-Za-z]{2,}[^\s<>]*~i', $content, $lm)) {
        $link = rtrim((string)$lm[0], '.,!?;:)]}');
        if (!preg_match('~^https?://~i', $link)) $link = 'https://' . $link;
        try {
            $lp = chat_fetch_link_preview($link);
            if ($lp && table_exists('messages')) {
                q('UPDATE messages SET link_preview = ? WHERE id = ?', [json_encode($lp, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE), $mid]);
            }
        } catch (Throwable $e) { /* link metadata is optional */ }
    }
}

$preview = $voiceSeconds > 0
    ? '🎤 Voice message (' . floor($voiceSeconds / 60) . ':' . str_pad((string) ($voiceSeconds % 60), 2, '0', STR_PAD_LEFT) . ')'
    : ($isEnc ? '🔒 Encrypted message'
       : ($content !== '' ? excerpt($content, 90) : 'File: ' . ($att['name'] ?? 'attachment')));
update_row('conversations', [
    'last_message'   => $preview,
    'last_sender_id' => uid(),
    'last_activity'  => date('Y-m-d H:i:s'),
], 'id = ?', [$cid]);

/* is_archived = 0 too: an archived conversation is invisible in the list, so
   without this a new message to somebody who archived the thread would sit
   unread in a place they can no longer see. Every messaging app un-archives
   on new activity for the same reason. */
q('UPDATE conversation_members SET unread_count = unread_count + 1, is_archived = 0
   WHERE conversation_id = ? AND user_id <> ?', [$cid, uid()]);

/* Sending is the end of typing. Left alone, the flag lives out its six
   seconds and the other side sees "typing…" after the message already arrived. */
q('UPDATE conversation_members SET typing_at = NULL
   WHERE conversation_id = ? AND user_id = ?', [$cid, uid()]);

/* --- @mentions -------------------------------------------------------------
   Being named is different from being talked near. A mention reaches you even
   in a group you muted — muting says "not every message", not "not when
   somebody needs me" — and it names the group so the notification is worth
   opening. Only real members can be mentioned: an @ in a group cannot be used
   to poke somebody who is not in it. */
$mentioned = [];
if ($content !== '' && !$isEnc && (int) setting('chat_mentions', 1) === 1
    && preg_match_all('/@([A-Za-z0-9_]{2,40})/', $content, $hits)) {

    $names = array_slice(array_unique(array_map('strtolower', $hits[1])), 0, 10);
    $memberIds = array_map(static fn($o) => (int) $o['user_id'], $others);

    /* One query for up to ten handles instead of ten queries.
       A message mentioning five people ran five separate lookups before the
       message could be acknowledged, with the sender waiting on all of them. */
    $ph   = implode(',', array_fill(0, count($names), '?'));
    $rows = $names ? fetch_all(
        "SELECT id, username FROM users
          WHERE LOWER(username) IN ($ph) AND status = 'active' AND deleted_at IS NULL",
        $names) : [];

    $where = $conversationTitle !== '' ? ' in ' . $conversationTitle : '';
    foreach ($rows as $u) {
        if (!in_array((int) $u['id'], $memberIds, true)) { continue; }
        $mentioned[] = (int) $u['id'];
        notify((int) $u['id'], 'mention', current_user()['name'] . ' mentioned you' . $where,
               url('chat.php?c=' . $cid . '#c-msg-' . $mid), uid(), 'message', $mid);
    }
}

foreach ($others as $o) {
    $recipient = (int) $o['user_id'];
    /* Already told, and told something more specific. */
    if (in_array($recipient, $mentioned, true)) { continue; }

    if ((int) ($o['is_muted'] ?? 0) === 0) {
        /* One bell per sender PER CONVERSATION, not one per message. Ten quick
           messages used to mean ten identical notifications; if they have not
           read the first "sent you a message" from me yet, an eleventh says
           nothing new — the unread badge on the conversation already carries
           the count.

           Per conversation is the part that was missing. Scoped only to the
           sender, an unread notification from me in one thread suppressed the
           notification for a message I sent in a DIFFERENT one — and the
           notification they did have pointed at the first thread, so the
           second conversation went unmentioned entirely. Somebody messaging
           you in a group and then privately got told about one of them. */
        $already = fetch_one("SELECT n.id FROM notifications n
                              JOIN messages m ON m.id = n.target_id
                              WHERE n.user_id = ? AND n.actor_id = ?
                                AND n.type = 'message' AND n.is_read = 0
                                AND n.target_type = 'message'
                                AND m.conversation_id = ?
                              LIMIT 1", [$recipient, uid(), $cid]);
        if ($already) { continue; }
        /* The notification first, the push second.
           The comment here has always said "placed after notify() so a push
           failure can never cost them the notification itself" — and the code
           did the opposite. push_wake() opens curl connections to a push
           service inside this request; if it throws, or the budget inside it
           is exhausted by an unreachable endpoint, the line below it never
           runs. The push is the part that can be missed and re-derived from
           the unread badge; the notification is the part that persists. The
           order now matches the reasoning. */
        notify($recipient, 'message', current_user()['name'] . ' sent you a message',
               url('chat.php?c=' . $cid), uid(), 'message', $mid);

        /* Wake their phone. Empty push — see includes/push.php — so this only
           says "something arrived", and their device asks what. Wrapped
           because a push service that is down is not a reason for a message
           that is already saved to report failure to the sender. */
        if ((int) setting('push_on_message', 1) === 1) {
            try { push_wake($recipient); } catch (Throwable $e) { /* best effort */ }
        }
    }
}

json_out(['ok' => true, 'id' => $mid]);
