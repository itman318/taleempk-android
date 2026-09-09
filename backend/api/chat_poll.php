<?php
require_once dirname(__DIR__) . '/includes/api_boot.php';
require_once dirname(__DIR__) . '/includes/chat_helpers.php'; require_feature('feature_chat');
require_login();
require_verified_api();

/* Identity is known; nothing below writes to the session. Releasing the lock
   here is what stops this endpoint from serialising every other request this
   person makes. See session_release(). */
session_release();

$cid    = (int) ($_POST['conversation_id'] ?? 0);
$after  = (int) ($_POST['after'] ?? 0);
$seek   = (int) ($_POST['seek'] ?? 0) === 1;

/* 'typing' is a small flag: truthy while composing, '0' when stopped. */
/* Asking for what came BEFORE something, rather than after it.
   A conversation opens on its last CHAT_POLL_LIMIT messages, and until now
   that was the entire history anybody could reach: scrolling up hit the top of
   forty messages and stopped, with the rest of the thread still in the
   database and no way to ask for it. Everything older than that had simply
   disappeared from the person's point of view.

   It rides this endpoint rather than a new one so that the whole row-shaping
   pipeline below — reply previews, reactions, polls, starred, played, voice
   waveforms — is the same code and cannot drift. What it must NOT do is any of
   the side effects: reading old messages is not reading new ones, and marking
   them would clear an unread badge for messages the person has not seen. */
$before  = (int) ($_POST['before'] ?? 0);
$history = $before > 0;

$typingRaw  = trim((string) ($_POST['typing'] ?? ''));
$iAmTyping  = $typingRaw !== '' && $typingRaw !== '0';
$typingKind = $typingRaw === 'voice' ? 'voice' : 'text';

/* Whether the voice-played feature has a table to stand on.
   Reading your messages must not depend on it. When a build is uploaded by
   hand, a missing table from the newest migration is a normal failure — and
   the first version of this endpoint answered that with a 500, which the page
   showed as "Loading messages…" forever. A conversation that will not open is
   a far worse outcome than a voice note that cannot say it was heard. */
$playsReady = table_exists('message_plays');

/* "Deleted for me" messages, filtered out of every query below rather than
   after the fact. Filtering in PHP would still send them to the browser, and a
   message the reader was promised was gone should not be sitting in the page
   source. */
$hidesReady = table_exists('message_hides');
$notHidden  = $hidesReady
    ? ' AND NOT EXISTS (SELECT 1 FROM message_hides h WHERE h.message_id = m.id AND h.user_id = ' . uid() . ') '
    : ' ';

/* Membership and the conversation's key epoch in one lookup.
   The epoch has to be on EVERY poll, not on the occasional full=1 beat, and
   the reason is a security one rather than a tidiness one: when somebody is
   removed from a group the server bumps the epoch, and a client still holding
   the old number would go on encrypting under the key that person still has.
   The removed member would keep reading a conversation they were removed from,
   for as long as the sender left the tab open.

   Joined onto the membership check rather than fetched separately, so a fact
   needed on every poll costs no extra round trip. */
$member = fetch_one(
    'SELECT cm.id, c.enc_epoch
       FROM conversation_members cm
       JOIN conversations c ON c.id = cm.conversation_id
      WHERE cm.conversation_id = ? AND cm.user_id = ?',
    [$cid, uid()]
);
if (!$member) { json_out(['ok' => false, 'error' => 'That conversation is not yours.'], 403); }
$encEpoch = (int) ($member['enc_epoch'] ?? 0);

/* Tell the other side what we are doing. The flag ages out on its own after a
   few seconds, so it cannot get stuck on — but a recording that is cancelled
   or sent says so at once rather than leaving the other person watching a
   microphone that is no longer on.

   Wrapped, because a build uploaded by hand before the migration has run has
   no typing_kind column, and an indicator is not worth taking a conversation
   down for. */
/* Not written at all when the setting is off. Filtering it out on the way back
   would leave the flag sitting in the database for anybody who ever reads that
   table directly — the honest place to respect this is before it is stored. */
$sharesTyping = (int) ((current_user()['show_typing'] ?? 1)) === 1;

try {
    if ($history || !$sharesTyping) {
        /* Nothing below. Reading yesterday's messages is not typing, and it is
           not reading today's. */
    } elseif ($iAmTyping) {
        q('UPDATE conversation_members SET typing_at = NOW(), typing_kind = ?
           WHERE conversation_id = ? AND user_id = ?', [$typingKind, $cid, uid()]);
    } elseif ($typingRaw === '0') {
        q('UPDATE conversation_members SET typing_at = NULL
           WHERE conversation_id = ? AND user_id = ? AND typing_at IS NOT NULL', [$cid, uid()]);
    }
} catch (PDOException $e) {
    if ($iAmTyping) {
        q('UPDATE conversation_members SET typing_at = NOW() WHERE conversation_id = ? AND user_id = ?', [$cid, uid()]);
    }
}

/* Voice notes this device has just started playing, sent along with the poll
   the page was going to make anyway. A separate endpoint would have meant a
   second request every time somebody taps play, on connections where the whole
   point of a voice note is that typing is slow. Ids are filtered against this
   conversation in SQL, so a forged id cannot mark a stranger's message played. */
$playedIn = array_slice(array_filter(array_map('intval', explode(',', (string) ($_POST['played'] ?? '')))), 0, 20);
if ($playedIn && $playsReady) {
    $ph  = implode(',', array_fill(0, count($playedIn), '?'));
    $ok  = fetch_all(
        "SELECT id FROM messages
         WHERE conversation_id = ? AND sender_id <> ? AND voice_seconds > 0 AND status = 'sent'
           AND id IN (" . $ph . ")",
        array_merge([$cid, uid()], $playedIn)
    );
    /* A play row exists for one reason: telling the sender you listened. With
       receipts off there is nobody to tell, so it is not recorded — the row
       would be a fact about somebody kept for no purpose. */
    if ((int) ((current_user()['show_receipts'] ?? 1)) === 1) {
        foreach ($ok as $row) {
            q('INSERT IGNORE INTO message_plays (message_id, user_id) VALUES (?,?)', [(int) $row['id'], uid()]);
        }
    }
}

/* Deleted messages are fetched too, as a tombstone. A message that vanishes
   without trace lets somebody say something and pretend they never did. */
/* The first request should open at the newest messages, not the oldest
   messages in a large thread. Subsequent polls remain cursor-based. Without
   this split, a busy conversation could show its first 100 messages and mark
   newer unread messages as read before the user ever saw them. */
$playSel  = $playsReady ? '(mp.id IS NOT NULL) AS played_by_me,' : '0 AS played_by_me,';
$playJoin = $playsReady ? '         LEFT JOIN message_plays mp ON mp.message_id = m.id AND mp.user_id = ?' : '';

if ($history) {
    /* One page further back, oldest-last so the client can prepend it whole. */
    $rows = fetch_all(
        "SELECT m.id, m.sender_id, m.content, m.enc, m.attachment, m.attachment_name, m.attachment_type, m.attachment_size,
                m.created_at, m.status, m.edited_at, m.link_preview, m.forwarded_from, m.reply_to_id, m.is_pinned, m.pinned_by,
                m.voice_seconds, m.voice_wave,
                su.name AS sender_name,
                (st.id IS NOT NULL) AS starred,
                " . $playSel . "
                r.content AS reply_text, r.enc AS reply_enc, r.status AS reply_status, r.attachment_name AS reply_att,
                r.attachment_type AS reply_type, r.voice_seconds AS reply_voice, r.attachment AS reply_attachment,
                ru.name AS reply_name
         FROM messages m
         LEFT JOIN users    su ON su.id = m.sender_id
         LEFT JOIN message_stars st ON st.message_id = m.id AND st.user_id = ?
" . $playJoin . "
         LEFT JOIN messages r  ON r.id = m.reply_to_id
         LEFT JOIN users    ru ON ru.id = r.sender_id
         WHERE m.conversation_id = ? AND m.id < ?" . $notHidden . "
         ORDER BY m.id DESC LIMIT " . CHAT_POLL_LIMIT,
        array_merge([uid()], $playsReady ? [uid()] : [], [$cid, $before])
    );
    $rows = array_reverse($rows);
} elseif ($after === 0) {
    $rows = fetch_all(
        "SELECT m.id, m.sender_id, m.content, m.enc, m.attachment, m.attachment_name, m.attachment_type, m.attachment_size,
                m.created_at, m.status, m.edited_at, m.link_preview, m.forwarded_from, m.reply_to_id, m.is_pinned, m.pinned_by,
                m.voice_seconds, m.voice_wave,
                su.name AS sender_name,
                (st.id IS NOT NULL) AS starred,
                " . $playSel . "
                r.content AS reply_text, r.enc AS reply_enc, r.status AS reply_status, r.attachment_name AS reply_att,
                r.attachment_type AS reply_type, r.voice_seconds AS reply_voice, r.attachment AS reply_attachment,
                ru.name AS reply_name
         FROM messages m
         LEFT JOIN users    su ON su.id = m.sender_id
         LEFT JOIN message_stars st ON st.message_id = m.id AND st.user_id = ?
" . $playJoin . "
         LEFT JOIN messages r  ON r.id = m.reply_to_id
         LEFT JOIN users    ru ON ru.id = r.sender_id
         WHERE m.conversation_id = ?" . $notHidden . "
         ORDER BY m.id DESC LIMIT " . CHAT_POLL_LIMIT, array_merge([uid()], $playsReady ? [uid()] : [], [$cid])
    );
    $rows = array_reverse($rows);
} else {
    $rows = fetch_all(
        "SELECT m.id, m.sender_id, m.content, m.enc, m.attachment, m.attachment_name, m.attachment_type, m.attachment_size,
                m.created_at, m.status, m.edited_at, m.link_preview, m.forwarded_from, m.reply_to_id, m.is_pinned, m.pinned_by,
                m.voice_seconds, m.voice_wave,
                su.name AS sender_name,
                (st.id IS NOT NULL) AS starred,
                " . $playSel . "
                r.content AS reply_text, r.enc AS reply_enc, r.status AS reply_status, r.attachment_name AS reply_att,
                r.attachment_type AS reply_type, r.voice_seconds AS reply_voice, r.attachment AS reply_attachment,
                ru.name AS reply_name
         FROM messages m
         LEFT JOIN users    su ON su.id = m.sender_id
         LEFT JOIN message_stars st ON st.message_id = m.id AND st.user_id = ?
" . $playJoin . "
         LEFT JOIN messages r  ON r.id = m.reply_to_id
         LEFT JOIN users    ru ON ru.id = r.sender_id
         WHERE m.conversation_id = ? AND m.id > ?" . $notHidden . "
         ORDER BY m.id ASC LIMIT " . CHAT_POLL_LIMIT, array_merge([uid()], $playsReady ? [uid()] : [], [$cid, $after])
    );
}

/* The pinned bar and the voice "played" list change rarely. The client asks
   for them on the first load and then every few polls (full=1); the polls in
   between carry only what moves every second. Two queries fewer per tick,
   which across every open chat is the cheapest speed-up on the site. */
/* A history page needs none of the extras: the pinned bar, the played list and
   the presence line are already on screen and have not changed because
   somebody scrolled up. */
$full = !$history && ($after === 0 || !empty($_POST['full']));
$pinnedRows = $full ? fetch_all("SELECT m.id,m.sender_id,m.content,m.enc,m.attachment_name,m.voice_seconds,m.created_at,u.name FROM messages m JOIN users u ON u.id=m.sender_id WHERE m.conversation_id=? AND m.is_pinned=1 AND m.status='sent' ORDER BY m.id DESC LIMIT 5", [$cid]) : null;
/* A pinned photo or voice note has no text of its own. Left as-is it drew an
   empty row in the pinned bar — something was clearly pinned, but the bar
   could not say what. */
$pinned = $pinnedRows === null ? null : array_map(static function ($r) {
    /* A pinned encrypted message cannot be summarised here — the text is not
       readable on this side. Showing the base64 would be worse than useless. */
    $text = (int) ($r['enc'] ?? 0) === 1 ? '🔒 Encrypted message'
          : mb_substr(trim((string) $r['content']), 0, 120);
    if ($text === '') {
        $text = (int) $r['voice_seconds'] > 0
            ? '🎤 Voice message'
            : (($r['attachment_name'] ?? '') !== '' ? '📎 ' . mb_substr((string) $r['attachment_name'], 0, 60) : 'Attachment');
    }
    return ['id' => (int) $r['id'], 'sender' => (string) $r['name'], 'text' => $text, 'time' => time_ago($r['created_at'])];
}, $pinnedRows);

$reactionMap = [];
if ($rows) {
    $ids = array_map(static fn($r) => (int)$r['id'], $rows);
    $placeholders = implode(',', array_fill(0, count($ids), '?'));
    $rr = fetch_all(
        'SELECT message_id, emoji, COUNT(*) AS n, MAX(user_id = ?) AS mine
         FROM message_reactions WHERE message_id IN (' . $placeholders . ')
         GROUP BY message_id, emoji ORDER BY MIN(id)',
        array_merge([uid()], $ids)
    );
    foreach ($rr as $r) {
        $reactionMap[(int)$r['message_id']][] = [
            'emoji' => (string)$r['emoji'],
            'count' => (int)$r['n'],
            'mine'  => (bool)$r['mine'],
        ];
    }
}

/* Polls attached to any of these messages. Fetched as a set rather than one
   query per message, so a screen of fifty messages is still three queries. */
$pollMap = [];
if ($rows) {
    $ids = array_map(static fn($r) => (int)$r['id'], $rows);
    $placeholders = implode(',', array_fill(0, count($ids), '?'));
    $polls = fetch_all('SELECT id, message_id, question, multi, closed_at, created_by
                        FROM chat_polls WHERE message_id IN (' . $placeholders . ')', $ids);

    if ($polls) {
        $pollIds = array_map(static fn($p) => (int) $p['id'], $polls);
        $pp = implode(',', array_fill(0, count($pollIds), '?'));

        $options = fetch_all('SELECT id, poll_id, label FROM chat_poll_options
                              WHERE poll_id IN (' . $pp . ') ORDER BY position, id', $pollIds);
        $counts  = fetch_all('SELECT poll_id, option_id, COUNT(*) AS n FROM chat_poll_votes
                              WHERE poll_id IN (' . $pp . ') GROUP BY poll_id, option_id', $pollIds);
        $voterN  = fetch_all('SELECT poll_id, COUNT(DISTINCT user_id) AS n FROM chat_poll_votes
                              WHERE poll_id IN (' . $pp . ') GROUP BY poll_id', $pollIds);
        $mine    = fetch_all('SELECT poll_id, option_id FROM chat_poll_votes
                              WHERE poll_id IN (' . $pp . ') AND user_id = ?', array_merge($pollIds, [uid()]));

        $countBy = []; foreach ($counts as $c) { $countBy[(int)$c['poll_id']][(int)$c['option_id']] = (int)$c['n']; }
        $voterBy = []; foreach ($voterN as $v) { $voterBy[(int)$v['poll_id']] = (int)$v['n']; }
        $mineBy  = []; foreach ($mine as $v)   { $mineBy[(int)$v['poll_id']][] = (int)$v['option_id']; }
        $optBy   = []; foreach ($options as $o) { $optBy[(int)$o['poll_id']][] = $o; }

        foreach ($polls as $p) {
            $pid    = (int) $p['id'];
            /* Percentages are of PEOPLE, not of votes — on a multi-choice poll
               the votes outnumber the voters and a share of votes means
               nothing. */
            $voters = $voterBy[$pid] ?? 0;
            $picked = $mineBy[$pid] ?? [];

            $opts = [];
            foreach ($optBy[$pid] ?? [] as $o) {
                $n = $countBy[$pid][(int)$o['id']] ?? 0;
                $opts[] = [
                    'id'      => (int) $o['id'],
                    'label'   => (string) $o['label'],
                    'votes'   => $n,
                    'percent' => $voters > 0 ? (int) round($n * 100 / $voters) : 0,
                    'mine'    => in_array((int) $o['id'], $picked, true),
                ];
            }

            $pollMap[(int) $p['message_id']] = [
                'id'       => $pid,
                'question' => (string) $p['question'],
                'multi'    => (bool) $p['multi'],
                'closed'   => $p['closed_at'] !== null,
                'is_owner' => (int) $p['created_by'] === uid(),
                'voters'   => $voters,
                'voted'    => $picked !== [],
                'options'  => $opts,
            ];
        }
    }
}

$out = [];
foreach ($rows as $m) {
    if ($m['status'] === 'deleted') {
        $m['content'] = null;
        $m['attachment'] = null;
        $m['attachment_name'] = null;
        $m['attachment_type'] = null;
        /* A deleted message must not still report the size of the file it used
           to carry — the tombstone would go on advertising "2.4 MB". */
        $m['attachment_size'] = 0;
    }
    /* Attachment type has existed in two formats across StudyHub builds:
       older rows store an extension (jpg/png), newer upload paths can store a
       MIME type (image/jpeg). Treat both forms as images so a reply preview
       never falls back to a text-only "📷 Photo" card when the file exists. */
    $isImageType = static function ($type, $name = ''): bool {
        $type = strtolower(trim((string) $type));
        $name = strtolower(trim((string) $name));
        if (strpos($type, 'image/') === 0) return true;
        if (in_array($type, ['jpg','jpeg','png','gif','webp','avif','heic','heif'], true)) return true;
        $ext = pathinfo($name, PATHINFO_EXTENSION);
        return in_array(strtolower((string) $ext), ['jpg','jpeg','png','gif','webp','avif','heic','heif'], true);
    };
    $isImage = $isImageType($m['attachment_type'], $m['attachment_name']);
    /* The reply preview used to collapse two different states into one:
       content is NULL both for a deleted message and for an attachment-only
       message, so replying to a photo showed "Message deleted". The status
       column tells them apart. */
    $replyText = null;
    if ($m['reply_to_id']) {
        if (($m['reply_status'] ?? '') === 'deleted') {
            $replyText = 'Message deleted';
        } else {
            /* Quoting an encrypted message would have put ninety characters
               of base64 in the quote bar. The server cannot summarise what it
               cannot read, so it says what the thing IS and leaves it there —
               the reader can scroll to the message itself, which their own
               device can open. */
            $replyText = (int) ($m['reply_enc'] ?? 0) === 1
                ? '🔒 Encrypted message'
                : mb_substr(trim((string) ($m['reply_text'] ?? '')), 0, 90);
            if ($replyText === '') {
                /* "File: voice.m4a" was what a reply to a voice note said. The
                   filename is a detail of how the recording was stored — it is
                   not what was replied to, it is the same for everybody, and it
                   tells the reader nothing. What they need is the kind of thing
                   and, for a recording, how long it is. */
                $rSecs = (int) ($m['reply_voice'] ?? 0);
                $rType = strtolower((string) ($m['reply_type'] ?? ''));
                if ($rSecs > 0) {
                    $replyText = '🎤 Voice message (' . floor($rSecs / 60) . ':'
                        . str_pad((string) ($rSecs % 60), 2, '0', STR_PAD_LEFT) . ')';
                } elseif ($isImageType($rType, $m['reply_att'])) {
                    $replyText = '📷 Photo';
                } elseif ($m['reply_att'] !== null && $m['reply_att'] !== '') {
                    $replyText = '📎 ' . mb_substr((string) $m['reply_att'], 0, 60);
                } else {
                    $replyText = 'Attachment';
                }
            }
        }
    }
    $linkPreview = null;
    if ($m['status'] !== 'deleted' && !empty($m['link_preview'])) {
        $decoded = json_decode((string)$m['link_preview'], true);
        if (is_array($decoded) && !empty($decoded['url'])) {
            $linkPreview = [
                'url' => (string)$decoded['url'],
                'domain' => mb_substr((string)($decoded['domain'] ?? ''), 0, 120),
                'title' => mb_substr((string)($decoded['title'] ?? ''), 0, 180),
                'description' => mb_substr((string)($decoded['description'] ?? ''), 0, 300),
                'image' => (string)($decoded['image'] ?? ''),
            ];
        }
    }
    $out[] = [
        'id'              => (int) $m['id'],
        'sender_id'       => (int) $m['sender_id'],
        'sender'          => (string) ($m['sender_name'] ?? ''),
        'content'         => $m['content'],
        /* 1 means `content` is ciphertext this server cannot read. The client
           decrypts it before it is ever shown; nothing here may treat it as
           text. */
        'enc'             => (int) ($m['enc'] ?? 0),
        'link_preview'    => $linkPreview,
        /* The client only needs presence here. Never expose the storage path;
           authorized bytes are addressed by message id through chat-file. */
        'attachment'      => !empty($m['attachment']) ? true : null,
        /* Through the gate, not straight at the file. A private conversation's
           photos should stop being reachable the moment somebody is not in
           that conversation any more — a static URL cannot do that. */
        'attachment_url'  => $m['attachment'] ? url('chat-file.php?m=' . (int) $m['id']) : null,
        'attachment_name' => $m['attachment_name'],
        /* Needed by the client to recognise an end-to-end encrypted file, and
           to label it with its size while it is still sealed — the real name
           and type are inside the packet and only the recipient can read
           them. */
        'attachment_type' => $m['attachment_type'],
        'attachment_size' => (int) ($m['attachment_size'] ?? 0),
        'is_image'        => $isImage,
        'voice'           => (int) $m['voice_seconds'] > 0 ? (int) $m['voice_seconds'] : 0,
        /* Empty for anything recorded before this shipped; the client falls
           back to a generated shape for those rather than drawing nothing. */
        'wave'            => (string) ($m['voice_wave'] ?? ''),
        'starred'         => (bool) $m['starred'],
        'played_by_me'    => (bool) $m['played_by_me'],
        'poll'            => $pollMap[(int) $m['id']] ?? null,
        'time'            => date('g:i A', strtotime($m['created_at'])),
        /* Raw seconds as well as the pretty label. The menu needs to know
           whether the edit window has closed, and "3:42 PM" cannot answer
           that. The server decides for real in chat_message.php — this only
           stops the menu offering something that would be refused. */
        'ts'              => strtotime((string) $m['created_at']),
        /* The client draws a divider when this changes, so a thread spanning
           three days does not read as one conversation with odd gaps. */
        'day'             => day_label($m['created_at']),
        'deleted'         => $m['status'] === 'deleted',
        'edited'          => !empty($m['edited_at']),
        'forwarded'       => !empty($m['forwarded_from']),
        'pinned'          => !empty($m['is_pinned']),
        'reactions'       => $reactionMap[(int)$m['id']] ?? [],
        /* The client's tap-the-quote-to-jump needs the quoted message's id;
           it was checking m.reply.id and the id was never sent, so the
           feature was dead on arrival. */
        'reply'           => $m['reply_to_id'] ? [
            'id'       => (int) $m['reply_to_id'],
            'name'     => (string) ($m['reply_name'] ?? 'Someone'),
            'text'     => $replyText,
            'is_image' => ($m['reply_status'] ?? '') !== 'deleted' && $isImageType($m['reply_type'] ?? '', $m['reply_att'] ?? ''),
            'image_url'=> (($m['reply_status'] ?? '') !== 'deleted' && !empty($m['reply_attachment']) && $isImageType($m['reply_type'] ?? '', $m['reply_att'] ?? ''))
                ? url('chat-file.php?m=' . (int) $m['reply_to_id']) : null,
        ] : null,
    ];
}

/* A history page answers here and goes no further. Everything below this point
   is about the LIVE end of the conversation — marking read, watermarks,
   presence, receipts — and none of it is true of a page of old messages.
   Running it would set last_read_id backwards and clear an unread badge for
   messages the person has not reached. */
if ($history) {
    json_out([
        'ok'       => true,
        'history'  => true,
        'enc_epoch'=> $encEpoch,
        'messages' => $out,
        /* A full page back means there is probably another one. A short page
           means this is the start of the conversation, and the client can stop
           asking and say so. */
        'more'     => count($out) >= CHAT_POLL_LIMIT,
    ]);
}

$cleared = null;
if ($rows) {
    $lastId = (int) end($rows)['id'];

    /* A live cursor can be more than one page behind. Only a completely
       drained cursor may zero the badge and clear its notifications; the old
       code did both after the first hundred rows, even when row 101 was still
       waiting. The extra existence query runs only for a saturated batch. */
    $moreLive = false;
    if (!$seek && $after > 0 && count($rows) >= CHAT_POLL_LIMIT) {
        $moreLive = (bool) fetch_col(
            'SELECT 1 FROM messages m WHERE m.conversation_id = ? AND m.id > ?'
            . $notHidden . ' LIMIT 1',
            [$cid, $lastId]
        );
    }
    $unreadSeen = 0;
    foreach ($rows as $seenRow) {
        if ((int) $seenRow['sender_id'] !== uid()) { $unreadSeen++; }
    }

    /* One UPDATE, and only when it would change something.
       This used to be two writes on every poll that returned a row: one to
       advance last_fetched_id, a second for last_read_id and unread_count.
       Two round trips, two row locks and two binlog entries on the busiest
       loop on the site — for a row whose values are usually already correct,
       because the common case is a poll that returns the message this device
       has just sent and already knows about.

       The WHERE clause is what makes it cheap: with the watermarks already at
       or past these ids, MySQL matches nothing and there is no write at all.
       GREATEST keeps the columns monotonic, so an out-of-order response can
       never walk a watermark backwards. */
    $newest = $out ? max(array_map(static fn($m) => (int) $m['id'], $out)) : 0;

    if (!$seek) {
        q('UPDATE conversation_members
              SET last_fetched_id = GREATEST(last_fetched_id, ?),
                  last_read_id    = GREATEST(last_read_id, ?),
                  unread_count    = CASE WHEN ? = 1
                                         THEN GREATEST(unread_count - ?, 0)
                                         ELSE 0 END
            WHERE conversation_id = ? AND user_id = ?
              AND (last_fetched_id < ? OR last_read_id < ? OR unread_count > 0)',
          [$newest, $lastId, $moreLive ? 1 : 0, $unreadSeen,
           $cid, uid(), $newest, $lastId]);

        if ((int) ((current_user()['show_receipts'] ?? 1)) === 1) {
            q('INSERT IGNORE INTO message_reads (message_id, user_id) VALUES (?,?)', [$lastId, uid()]);
        }

        /* The bell goes quiet the moment the messages are actually read, by
           whatever route the person arrived — the notification, the
           conversation list, or a link somebody sent them. A notification for
           a message now on their screen is not a reminder, it is a lie.

           Only done when something changed, so the ordinary idle poll is not
           writing to notifications every few seconds for nothing. */
        if (!$moreLive && $cleared === null && ($out || $after === 0)) {
            /* $after === 0 is the thread being opened. That case matters on its
               own: somebody who read these messages on their phone still has
               the bell showing on their laptop, and opening the chat there
               delivers no NEW messages — so keying this only on $out would
               leave the badge sitting there with nothing behind it. */
            $cleared = notifications_clear_for_conversation(uid(), $cid);
        }
    } elseif ($newest > 0) {
        /* A date seek is navigation, not reading. It advances only the
           delivery watermark and deliberately leaves the read one alone —
           jumping to last March must not clear an unread badge for messages
           the person has not come back to. */
        q('UPDATE conversation_members SET last_fetched_id = GREATEST(last_fetched_id, ?)
            WHERE conversation_id = ? AND user_id = ? AND last_fetched_id < ?',
          [$newest, $cid, uid(), $newest]);
    }
} elseif (!$seek && $after === 0) {
    /* An all-hidden thread returns no rows, but opening it is still an explicit
       read action. Clear a stale badge against the real conversation tail. */
    $lastId = (int) (fetch_col(
        'SELECT COALESCE(MAX(id), 0) FROM messages WHERE conversation_id = ?',
        [$cid]
    ) ?? 0);
    q('UPDATE conversation_members
          SET last_fetched_id = GREATEST(last_fetched_id, ?),
              last_read_id    = GREATEST(last_read_id, ?),
              unread_count    = 0
        WHERE conversation_id = ? AND user_id = ?
          AND (last_fetched_id < ? OR last_read_id < ? OR unread_count > 0)',
      [$lastId, $lastId, $cid, uid(), $lastId, $lastId]);
    $cleared = notifications_clear_for_conversation(uid(), $cid);
}

/* What the other side is doing right now. */
$presence  = '';
$theirRead = 0;
$typing    = false;
$otherOnline = false;

/* A group has more than one recipient. Looking at only the first member
   made its ticks/presence depend on whichever row happened to be returned.
   Use the slowest recipient for receipts: "seen" means everybody has read it,
   while "delivered" means everybody has fetched it. */
$otherTypingKind = 'text';
$others = fetch_all("SELECT cm.last_read_id, cm.last_fetched_id, cm.typing_at, cm.typing_kind,
                           u.last_seen, u.show_online,
                           COALESCE(u.show_receipts, 1) AS show_receipts,
                           COALESCE(u.show_typing, 1)   AS show_typing
                    FROM conversation_members cm
                    JOIN users u ON u.id = cm.user_id
                    WHERE cm.conversation_id = ? AND cm.user_id <> ?", [$cid, uid()]);

/* Both of these are applied as MINE AND THEIRS.

   A one-way switch is not privacy. Turn receipts off, keep seeing everybody
   else's, and all it does is give you an advantage — which is why every
   messenger that offers this makes it reciprocal, and why it has to be
   enforced on the server rather than by hiding a tick in the client. */
$me = current_user() ?: [];
$iShareReceipts = (int) ($me['show_receipts'] ?? 1) === 1;
$iShareTyping   = (int) ($me['show_typing'] ?? 1) === 1;

$delivered = 0;
if ($others) {
    $theirRead = PHP_INT_MAX;
    $theirFetched = PHP_INT_MAX;
    $typing = false;
    $latestVisibleSeen = null;
    $onlineCount = 0;

    foreach ($others as $other) {
        /* Somebody who does not send receipts does not receive them either.
           Their watermark is simply not read, so the ticks stay at "sent". */
        if ($iShareReceipts && (int) ($other['show_receipts'] ?? 1) === 1) {
            $theirRead = min($theirRead, (int) $other['last_read_id']);
            $theirFetched = min($theirFetched, (int) ($other['last_fetched_id'] ?? 0));
        } else {
            $theirRead = 0;
            $theirFetched = 0;
        }

        /* Typing is shown whatever the "show online" setting says. That
           setting hides when somebody was last around, which is a history;
           typing is an action they are taking towards you right now, and
           every messaging app shows it regardless. Left behind the gate, a
           person with the setting off was invisible while typing — which is
           the other reason the indicator "did not work". */
        if ($iShareTyping && (int) ($other['show_typing'] ?? 1) === 1
            && $other['typing_at'] && (time() - strtotime($other['typing_at'])) < 8) {
            $typing = true;
            if (($other['typing_kind'] ?? '') === 'voice') $otherTypingKind = 'voice';
        }
        if ((int) $other['show_online'] !== 0) {
            if ($other['last_seen']) {
                if ($latestVisibleSeen === null || strtotime($other['last_seen']) > strtotime($latestVisibleSeen)) {
                    $latestVisibleSeen = $other['last_seen'];
                }
                if ((time() - strtotime($other['last_seen'])) < ONLINE_WINDOW) {
                    $onlineCount++;
                }
            }
        }
    }

    $theirRead = $theirRead === PHP_INT_MAX ? 0 : $theirRead;
    $delivered = $theirFetched === PHP_INT_MAX ? 0 : max($theirRead, $theirFetched);

    /* Online presence is useful for how quickly the client polls, but it is
       not a delivery receipt. A user can be active elsewhere on the site while
       this conversation is unopened. Delivery comes only from that member's
       own last_fetched_id, advanced above when their device actually fetches
       the thread. This also removes an UPDATE plus MAX query from every idle
       poll while both people happen to be online. */
    $otherOnline = $onlineCount > 0;

    if ($typing) {
        $presence = 'typing…';
    } elseif ($onlineCount > 0) {
        $presence = $onlineCount === 1 ? 'online now' : $onlineCount . ' online now';
    } elseif ($latestVisibleSeen) {
        $presence = 'last seen ' . time_ago($latestVisibleSeen);
    }
}

/* Which of MY voice notes everybody on the other side has now heard.
   This cannot ride on the read watermark the ticks use. A watermark works for
   text because reading is sequential — everything below the line has been
   seen. Listening is not: somebody can play the newest note and leave three
   older ones untouched, so each one has to be asked about individually. Capped
   at the most recent sixty, which is far more than fits on a screen. */
$playedIds = $full ? [] : null;
$otherCount = count($others);
if ($full && $otherCount > 0 && $playsReady) {
    $rowsPlayed = fetch_all(
        "SELECT m.id, COUNT(DISTINCT p.user_id) AS heard
         FROM messages m
         LEFT JOIN message_plays p ON p.message_id = m.id AND p.user_id <> ?
         WHERE m.conversation_id = ? AND m.sender_id = ? AND m.voice_seconds > 0 AND m.status = 'sent'
         GROUP BY m.id ORDER BY m.id DESC LIMIT 60",
        [uid(), $cid, uid()]
    );
    foreach ($rowsPlayed as $r) {
        /* In a group, "played" means everybody has heard it — the same rule the
           double tick already uses for "seen". Anything looser would light up
           on one listener out of nine. */
        if ((int) $r['heard'] >= $otherCount) { $playedIds[] = (int) $r['id']; }
    }
}

/* v22.02 — messages already on screen that have since been deleted or edited.
   The loop only ever asks for ids ABOVE the last one it has, so a deletion was
   invisible to everybody except the person who made it: the confirmation says
   "everyone will see that it was deleted" and, until they happened to reload,
   they did not. An edit was worse — the other side kept reading the original
   wording with no sign it had been changed.

   Rides the same full=1 beat as the pinned bar, and only touches rows that
   have actually been deleted or edited, which in a normal thread is none. */
$changed = null;
if ($full && $after > 0) {
    $changed = array_map(static function ($r) {
        return [
            'id'      => (int) $r['id'],
            'deleted' => $r['status'] === 'deleted',
            'text'    => $r['status'] === 'deleted' ? '' : (string) ($r['content'] ?? ''),
            'enc'     => (int) ($r['enc'] ?? 0),
            'link_preview' => ($r['status'] === 'deleted' || empty($r['link_preview'])) ? null : (json_decode((string)$r['link_preview'], true) ?: null),
            'edited'  => $r['edited_at'] !== null,
        ];
    }, fetch_all(
        /* A floor as well as a ceiling. Without the lower bound this walked
           EVERY message the conversation has ever held, on every sixth poll,
           for a screen that can only show the last few dozen — the one query
           in the chat loop whose cost grew with the age of the thread. A
           message far enough up the thread to be outside this window is also
           far outside the window the client is holding. */
        "SELECT m.id, m.status, m.content, m.enc, m.edited_at, m.link_preview
         FROM messages m
         WHERE m.conversation_id = ? AND m.id <= ? AND m.id > ?
           AND (m.status = 'deleted' OR m.edited_at IS NOT NULL)" . $notHidden . "
         ORDER BY m.id DESC LIMIT 40",
        [$cid, $after, max(0, $after - 400)]
    ));
}

json_out([
    'ok'         => true,
    /* How many bell notifications this read just made pointless. The client
       repaints the badge when it is non-zero, so the number disappears at the
       same moment as the reason for it — rather than up to three minutes
       later, when the background poller next happens to look. */
    'notif_cleared' => (int) ($cleared ?? 0),
    'messages'   => $out,
    'changed'    => $changed,
    'played'     => $playedIds,
    'presence'   => $presence,
    /* Sent on its own as well as folded into presence: the client was
       matching the literal string 'typing…', which is one translation or one
       wording change away from never matching again. */
    'typing'     => $typing,
    /* A stable machine value avoids matching translated display text. */
    'typing_kind' => $typing ? $otherTypingKind : '',
    'their_read' => $theirRead,
    'delivered'  => $delivered,
    'other_online' => $otherOnline,
    'pinned'     => $pinned,
    /* The group's current key version. The client compares it with the one it
       is encrypting under and re-keys itself when they differ — see the note
       on the membership lookup above for why this cannot wait for a reload. */
    'enc_epoch'  => $encEpoch,
]);
