<?php
require_once dirname(__DIR__) . '/includes/api_boot.php'; require_feature('feature_comments');
require_login();
block_if_restricted('comment');
require_verified_api();

$postId  = (int) ($_POST['post_id'] ?? 0);
$content = trim((string) ($_POST['content'] ?? ''));
$parent  = (int) ($_POST['parent_id'] ?? 0);

if ($content === '')                 { json_out(['ok' => false, 'error' => 'Write something first.']); }
if (mb_strlen($content) > 5000)      { json_out(['ok' => false, 'error' => 'Keep it under 5000 characters.']); }
if (bad_words($content))             { json_out(['ok' => false, 'error' => 'That comment contains words this community does not allow.']); }

$p = fetch_one('SELECT id, user_id, type, status, visibility, group_id FROM posts WHERE id = ?', [$postId]);
if (!$p || $p['status'] !== 'active') { json_out(['ok' => false, 'error' => 'That post is gone.']); }
if (!can_view_post_row($p, uid())) { json_out(['ok' => false, 'error' => 'That post is not available.'], 404); }
if (is_blocked(uid(), (int) $p['user_id'])) { json_out(['ok' => false, 'error' => 'You cannot reply to this person.']); }
if (!can_comment_on((int) $p['user_id'])) {
    json_out(['ok' => false, 'error' => 'This person has limited who can reply to their posts.']);
}

/* A reply may only point to a live comment on this exact post. Accepting an
   arbitrary parent id created cross-post threads and could make a reply appear
   under content the author was never allowed to see. */
$parentRow = null;
if ($parent > 0) {
    $parentRow = fetch_one(
        "SELECT id, user_id FROM comments WHERE id = ? AND post_id = ? AND status = 'active'",
        [$parent, $postId]
    );
    if (!$parentRow) {
        json_out(['ok' => false, 'error' => 'The comment you replied to is no longer available.']);
    }
    if (is_blocked(uid(), (int) $parentRow['user_id'])) {
        json_out(['ok' => false, 'error' => 'You cannot reply to this person.']);
    }
}

/* Answers and replies go through the same check as posts. Abuse arrives under
   a question at least as often as in one, and the person it lands on is the
   student who asked. */
$filter = wf_check($content);
if ($filter['action'] === 'block') {
    log_activity(uid(), 'filter_block', 'comment blocked: ' . $filter['term'], 'post', $postId);
    json_out(['ok' => false, 'error' => wf_block_message()]);
}
if ($filter['action'] === 'review') {
    /* Comments have no pending state to sit in, and a silently swallowed
       reply is worse than a refused one — the person believes it posted and
       waits for an answer that nobody can see. Told plainly instead. */
    log_activity(uid(), 'filter_block', 'comment held: ' . $filter['term'], 'post', $postId);
    json_out(['ok' => false, 'error' =>
        'That reply may contain language which is not allowed here. Please reword it.']);
}

$cid = db_transaction(function () use ($postId, $parent, $content): int {
    $cid = insert_row('comments', [
        'post_id'   => $postId,
        'user_id'   => uid(),
        'parent_id' => $parent ?: null,
        'content'   => $content,
    ]);
    q('UPDATE posts SET comments_count = comments_count + 1 WHERE id = ?', [$postId]);
    return $cid;
});
add_points(uid(), 'comment', 'comment', $cid);

notify_mentions($content, 'a comment', url('post.php?id=' . $postId . '#c-' . $cid), 'comment', $cid);

notify((int) $p['user_id'],
    $p['type'] === 'question' ? 'answer' : 'comment',
    current_user()['name'] . ($p['type'] === 'question' ? ' answered your question' : ' commented on your post'),
    url('post.php?id=' . $postId . '#c-' . $cid), uid(), 'post', $postId);

if ($parentRow && (int) $parentRow['user_id'] !== (int) $p['user_id']) {
    notify((int) $parentRow['user_id'], 'comment', current_user()['name'] . ' replied to your comment',
           url('post.php?id=' . $postId . '#c-' . $cid), uid(), 'comment', $cid);
}

/* The rendered card comes back with the reply, so the page can slot the new
   comment into the list instead of reloading and throwing the reader back to
   the top of the post. */
$fresh = fetch_one(
    'SELECT c.*, u.name, u.username, u.avatar, u.role, u.staff_title, u.is_verified
     FROM comments c JOIN users u ON u.id = c.user_id WHERE c.id = ?', [$cid]);

$html = '';
if ($fresh) {
    $fresh['my_reaction'] = false;
    $html = render_comment($fresh, (int) $p['user_id'], $p['type'] === 'question');
}

json_out(['ok' => true, 'id' => $cid, 'html' => $html]);
