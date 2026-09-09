<?php
/** The next page of the feed, rendered server side so it matches exactly. */
require_once dirname(__DIR__) . '/includes/api_boot.php'; require_feature('feature_feed');
require_once dirname(__DIR__) . '/includes/feed_query.php';
require_login();

$tab     = in_array(post('tab'), ['following', 'questions', 'unsolved'], true) ? post('tab') : 'latest';
$subject = post('subject');
$before  = (int) ($_POST['before'] ?? 0);   // the id of the oldest post already shown
$groupId = (int) ($_POST['group_id'] ?? 0);

$where  = ["p.status='active'"];
$params = [];

/* Guarded so a build whose migration has not run yet keeps a working feed
   rather than failing on an unknown table. */
$pagesOn = table_exists('page_follows');

if ($groupId > 0) {
    $member = fetch_one("SELECT id FROM group_members
                         WHERE group_id = ? AND user_id = ? AND status='approved'", [$groupId, uid()]);
    $g = fetch_one("SELECT privacy FROM study_groups WHERE id = ? AND status='active'", [$groupId]);
    if (!$g || (!$member && $g['privacy'] === 'private' && !is_admin())) {
        json_out(['ok' => false, 'error' => 'That group is not open to you.'], 403);
    }
    $where[] = 'p.group_id = ?';
    $params[] = $groupId;
} else {
    $where[] = "(p.visibility='public' OR p.user_id=? OR (p.visibility='followers' AND p.user_id IN (SELECT following_id FROM follows WHERE follower_id=?)))";
    $params[] = uid(); $params[] = uid();
    $where[] = 'p.group_id IS NULL';

    if ($tab === 'following') {
        /* Following a Page has to put its posts here too, or following one
           does nothing a person can see: a Page's posts carry a user_id (the
           team member who wrote them) that the follower has no reason to
           follow, so the author test alone silently excluded every Page they
           had followed. */
        $where[] = '(p.user_id IN (SELECT following_id FROM follows WHERE follower_id = ?)'
                 . ($pagesOn ? ' OR p.page_id IN (SELECT page_id FROM page_follows WHERE user_id = ?)' : '')
                 . ')';
        $params[] = uid();
        if ($pagesOn) { $params[] = uid(); }
    }
    if ($tab === 'questions') { $where[] = "p.type='question'"; }
    if ($tab === 'unsolved')  { $where[] = "p.type='question' AND p.is_solved=0"; }
    if ($subject !== '')      { $where[] = 'p.subject = ?'; $params[] = $subject; }
}

$blocked = blocked_ids();
if ($blocked) {
    $where[] = 'p.user_id NOT IN (' . implode(',', array_map('intval', $blocked)) . ')';
}
if ($before > 0) {
    $where[] = 'p.id < ?';
    $params[] = $before;
}

/* Pinned posts are shown above the stream on the first page, so they must
   never come back down it. */
$where[] = 'p.is_pinned = 0';

$per = POSTS_PER_PAGE;
$posts = hydrate_posts(fetch_all(
    post_select_sql() . ' WHERE ' . implode(' AND ', $where)
    . ' ORDER BY p.id DESC LIMIT ' . ($per + 1), $params
));

$more = count($posts) > $per;
if ($more) {
    array_pop($posts);
}

$html = '';
foreach ($posts as $p) {
    $html .= render_post($p);
}

json_out([
    'ok'    => true,
    'html'  => $html,
    'more'  => $more,
    'last'  => $posts ? (int) end($posts)['id'] : 0,
    'count' => count($posts),
]);
