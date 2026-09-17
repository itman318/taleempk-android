from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return (ROOT / path).read_text(encoding='utf-8')


def write(path, text):
    p = ROOT / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding='utf-8')


def replace_once(text, old, new, label):
    if old not in text:
        raise RuntimeError(f'v3.2 hotfix target missing: {label}')
    return text.replace(old, new, 1)


# Keep encrypted voice notes in the voice upload field so the mature website
# handler retains duration/waveform metadata while storing the payload as a
# featureless encrypted blob.
path = 'flutter/lib/screens/chat_screen.dart'
text = read(path)
text = replace_once(
    text,
    "field: encrypted ? 'attachment' : 'voice',",
    "field: 'voice',",
    'encrypted voice field',
)
write(path, text)


# Older encrypted attachment rows may have attachment_type=enc even if the
# historical row-level enc bit was not set. Recognize both forms so native
# clients can decrypt those files as well as newly corrected rows.
for path in ('backend/api/mobile.php', 'flutter/backend/api/mobile.php'):
    p = ROOT / path
    if not p.exists():
        continue
    text = read(path)
    text = replace_once(
        text,
        "$encrypted = !$deleted && (int)($m['enc'] ?? 0)===1;",
        "$encrypted = !$deleted && ((int)($m['enc'] ?? 0)===1 || strtolower((string)($m['attachment_type'] ?? ''))==='enc');",
        f'encrypted attachment serializer ({path})',
    )
    write(path, text)


# Shared website send handler: mark encrypted attachments at row level and let
# E2EE clients route explicit mention notifications with member IDs. The server
# learns only who was mentioned, never the encrypted plaintext.
path = 'backend/api/chat_send.php'
p = ROOT / path
if p.exists():
    text = read(path)
    text = replace_once(
        text,
        "'enc'             => $isEnc ? 1 : 0,",
        "'enc'             => ($isEnc || $encAtt) ? 1 : 0,",
        'encrypted attachment row flag',
    )
    old = """$mentioned = [];
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
"""
    new = """$mentioned = [];
$memberIds = array_map(static fn($o) => (int) $o['user_id'], $others);
$where = $conversationTitle !== '' ? ' in ' . $conversationTitle : '';

/* Native E2EE cannot expose plaintext @handles to the server. The Android
   composer therefore sends only the IDs of explicitly selected group members.
   Treat those IDs as notification routing metadata, never as message content,
   and accept them only when they are real members of this conversation. */
if ($isEnc && (int) setting('chat_mentions', 1) === 1) {
    $rawMentionIds = array_values(array_unique(array_filter(array_map(
        'intval', explode(',', (string) ($_POST['mention_ids'] ?? ''))
    ), static fn($id) => $id > 0)));
    foreach (array_slice($rawMentionIds, 0, 10) as $mentionId) {
        if ($mentionId === uid() || !in_array($mentionId, $memberIds, true)) { continue; }
        $mentioned[] = $mentionId;
        notify($mentionId, 'mention', current_user()['name'] . ' mentioned you' . $where,
               url('chat.php?c=' . $cid . '#c-msg-' . $mid), uid(), 'message', $mid);
    }
}

if ($content !== '' && !$isEnc && (int) setting('chat_mentions', 1) === 1
    && preg_match_all('/@([A-Za-z0-9_]{2,40})/', $content, $hits)) {

    $names = array_slice(array_unique(array_map('strtolower', $hits[1])), 0, 10);

    /* One query for up to ten handles instead of ten queries.
       A message mentioning five people ran five separate lookups before the
       message could be acknowledged, with the sender waiting on all of them. */
    $ph   = implode(',', array_fill(0, count($names), '?'));
    $rows = $names ? fetch_all(
        "SELECT id, username FROM users
          WHERE LOWER(username) IN ($ph) AND status = 'active' AND deleted_at IS NULL",
        $names) : [];

    foreach ($rows as $u) {
        if (!in_array((int) $u['id'], $memberIds, true)) { continue; }
        $mentioned[] = (int) $u['id'];
        notify((int) $u['id'], 'mention', current_user()['name'] . ' mentioned you' . $where,
               url('chat.php?c=' . $cid . '#c-msg-' . $mid), uid(), 'message', $mid);
    }
}
$mentioned = array_values(array_unique($mentioned));
"""
    text = replace_once(text, old, new, 'E2EE mention routing')
    write(path, text)

    flutter_copy = ROOT / 'flutter/backend/api/chat_send.php'
    if flutter_copy.parent.exists():
        write('flutter/backend/api/chat_send.php', text)
