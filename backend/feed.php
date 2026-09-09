<?php
require_once __DIR__ . '/includes/bootstrap.php';
require_feature('feature_feed');
require_once INC_PATH . '/feed_query.php';
require_login();

$me     = current_user();
/* No tab in the URL means open on whichever one they picked in settings. */
$defaultTab = current_user()['feed_default'] ?? 'latest';
if ($defaultTab === 'subject') { $defaultTab = 'latest'; }
$tab    = in_array(get('tab'), ['following','questions','unsolved','latest'], true)
        ? get('tab') : $defaultTab;
$subject = get('subject');
$before  = int_get('before');

$where  = ["p.status='active'", "(p.visibility='public' OR p.user_id=? OR (p.visibility='followers' AND p.user_id IN (SELECT following_id FROM follows WHERE follower_id=?)))", "p.group_id IS NULL"];
$params = [uid(),uid()];

$blocked = blocked_ids();
if ($blocked) {
    $where[] = 'p.user_id NOT IN (' . implode(',', array_map('intval', $blocked)) . ')';
}
$pagesOn = table_exists('page_follows');
if ($tab === 'following') {
    /* A Page you follow belongs in Following. Its posts carry the user_id of
       whichever team member wrote them, and that person is not who you
       followed — so matching on the author alone left every followed Page out
       of the one tab built to show what you follow. */
    $where[] = '(p.user_id IN (SELECT following_id FROM follows WHERE follower_id = ?)'
             . ($pagesOn ? ' OR p.page_id IN (SELECT page_id FROM page_follows WHERE user_id = ?)' : '')
             . ')';
    $params[] = uid();
    if ($pagesOn) { $params[] = uid(); }
}
if ($tab === 'questions') { $where[] = "p.type='question'"; }
if ($tab === 'unsolved')  { $where[] = "p.type='question' AND p.is_solved=0"; }
if ($subject !== '')      { $where[] = 'p.subject = ?'; $params[] = $subject; }
if ($before > 0)          { $where[] = 'p.id < ?';      $params[] = $before; }

$w = implode(' AND ', $where);

/* Pinned posts sit above the stream. They are pulled separately, because a
   cursor cannot order by pin and by id at the same time without repeating
   them further down. */
$pinned = $before > 0 ? [] : hydrate_posts(fetch_all(
    post_select_sql() . ' WHERE ' . $w . ' AND p.is_pinned = 1 ORDER BY p.id DESC LIMIT 3',
    $params
));

/* Cursor paging rather than OFFSET: new posts arriving while someone reads
   would otherwise push rows across page boundaries and repeat them. */
$posts = hydrate_posts(fetch_all(
    post_select_sql() . ' WHERE ' . $w . ' AND p.is_pinned = 0 ORDER BY p.id DESC LIMIT ' . (POSTS_PER_PAGE + 1),
    $params
));
$hasMore = count($posts) > POSTS_PER_PAGE;
if ($hasMore) { array_pop($posts); }
$lastId = $posts ? (int) end($posts)['id'] : 0;

/* A compact strip of what matters today, so the feed is a home page rather
   than only a wall of other people's posts. */
$nextExam = fetch_one("SELECT d.title, d.slug, d.start_date, b.short_name
                       FROM datesheets d JOIN boards b ON b.id = d.board_id
                       WHERE d.status='published' AND d.start_date >= CURDATE()
                       ORDER BY d.start_date ASC LIMIT 1");

$myGroups = fetch_all("SELECT g.name, g.slug FROM group_members gm
                       JOIN study_groups g ON g.id = gm.group_id
                       WHERE gm.user_id = ? AND gm.status='approved' AND g.status='active'
                       ORDER BY g.posts_count DESC LIMIT 6", [uid()]);

$openQuestions = (int) fetch_col("SELECT COUNT(*) FROM posts
                                  WHERE status='active' AND type='question' AND is_solved=0
                                    AND created_at >= DATE_SUB(NOW(), INTERVAL 3 DAY)");

$page_title = 'Feed';
$active     = 'feed';
require INC_PATH . '/header.php';
?>

<?php if ((int) $me['onboarded'] === 0): ?>
  <div class="flash flash-info">
    <div>Two minutes to set up your subjects and your feed fills itself.
      <a href="<?= url('welcome.php') ?>"><strong>Finish setting up</strong></a></div>
  </div>
<?php endif; ?>

<?php if ((int) $me['email_verified'] === 0 && (int) setting('require_email_verify', 1) === 1): ?>
  <div class="flash flash-info">
    <div>Confirm your email to post and message. <a href="<?= url('verify.php') ?>">Send the link again</a></div>
  </div>
<?php endif; ?>

<?php
/* A new account lands on an empty feed with no way to fill it. These are ranked
   by what the person actually shares with somebody — their institute, their
   class, their board — because "popular on the site" means nothing to someone
   who wants their own classmates. Shown while the feed is still thin. */
$suggestions = ($tab === 'latest' && !$before && (int) current_user()['following_count'] < 10)
             ? suggested_people(6) : [];
?>
<?php
/* The search box that used to sit here has gone. The header already carries
   search on both sizes — the magnifier opens a full-width sheet on a phone and
   the command palette on desktop — so this was a second copy of the same
   control, and on a 6" screen it cost an entire card of height above the fold
   before anybody saw a single post. */
?>
<?php
/* The three queries above — next exam, your groups, open questions — have been
   running on every feed load since they were written and their results were
   never printed. The comment beside them promised "a compact strip of what
   matters today" and the markup for it was never there.

   It matters most on a phone, which is where nearly everybody is: the rail
   that carries the same information is desktop-only, so a student on mobile
   got a search box, a composer, and then other people's posts. Hidden above
   820px so it does not repeat what the rail is already saying. */
$days = $nextExam
      ? (int) floor((strtotime($nextExam['start_date']) - strtotime('today')) / 86400)
      : null;
?>
<?php if ($days !== null || $openQuestions > 0 || $myGroups): ?>
<div class="todaystrip">
  <?php if ($days !== null): ?>
    <a class="todaystrip-item todaystrip-exam" href="<?= url('datesheet.php?s=' . urlencode($nextExam['slug'])) ?>">
      <strong><?= $days === 0 ? 'Today' : $days ?></strong>
      <span><?= $days === 0 ? e($nextExam['short_name']) . ' exams start'
              : 'day' . ($days === 1 ? '' : 's') . ' to ' . e($nextExam['short_name']) ?></span>
    </a>
  <?php endif; ?>

  <?php if ($openQuestions > 0): ?>
    <a class="todaystrip-item" href="<?= url('feed.php?tab=unsolved') ?>">
      <strong><?= (int) $openQuestions ?></strong>
      <span>question<?= $openQuestions === 1 ? '' : 's' ?> still unanswered</span>
    </a>
  <?php endif; ?>

  <?php foreach (array_slice($myGroups, 0, 3) as $g): ?>
    <a class="todaystrip-item" href="<?= url('group.php?g=' . urlencode($g['slug'])) ?>">
      <?= icon('groups', 16) ?><span><?= e($g['name']) ?></span>
    </a>
  <?php endforeach; ?>
</div>
<?php endif; ?>

<?= render_composer() ?>

<div class="row" style="gap:6px;overflow-x:auto;margin:16px 0 6px;padding-bottom:4px">
  <?php
  $tabs = ['latest'=>'Latest','following'=>'Following','questions'=>'Questions','unsolved'=>'Unsolved'];
  foreach ($tabs as $k=>$l): ?>
    <a class="chip <?= $tab===$k?'chip-marker':'' ?>" href="<?= url('feed.php?tab=' . $k) ?>"><?= e($l) ?></a>
  <?php endforeach; ?>
</div>

<?php
/* What is unusually busy this week, not what is biggest. See
   trending_subjects(): ranked against each subject's own recent past, because
   "biggest" on a study site means Maths wins every week forever and the strip
   stops being information.

   Hidden entirely when nothing is genuinely rising. A trending strip that is
   always there, always showing the same names, is furniture — and once people
   read it as furniture they stop seeing it on the week it matters. */
$trending = feature_enabled('feature_feed') ? trending_subjects(6) : [];
$trendingLive = array_values(array_filter($trending, static fn($t) => $t['rising']));
?>
<?php if ($trendingLive): ?>
<div class="trendstrip">
  <span class="trendstrip-label"><?= icon('spark', 14) ?> Busy this week</span>
  <div class="trendstrip-items">
    <?php foreach ($trendingLive as $t): ?>
      <a class="chip" href="<?= url('feed.php?subject=' . urlencode($t['subject'])) ?>">
        <?= e($t['subject']) ?>
        <span class="trendstrip-n"><?= (int) $t['posts'] ?></span>
      </a>
    <?php endforeach; ?>
  </div>
</div>
<?php endif; ?>

<?php foreach ($pinned as $p): ?>
  <div class="pinned-wrap">
    <div class="pinned-tag"><?= icon('pin', 14) ?> Pinned</div>
    <?= render_post($p) ?>
  </div>
<?php endforeach; ?>

<div id="feed-list" data-tab="<?= e($tab) ?>" data-subject="<?= e($subject) ?>">
<?php if (!$posts && !$pinned): ?>
  <?= $tab === 'following'
      ? empty_state('groups', 'Your following feed is empty',
          'Follow a few classmates and teachers and their questions land here.',
          'Find people', url('search.php?t=people'))
      : empty_state('spark', 'Be the first to post',
          'Ask the thing you are stuck on. Someone in your class has almost certainly hit the same wall.',
          'Invite your class', url('invite.php')) ?>
<?php else:
  $every = max(3, (int) setting('ad_feed_every', 6));
  foreach ($posts as $i => $p) {
      echo render_post($p);
      if (($i + 1) % $every === 0) { echo ad_slot('feed'); }

      /* Slipped in after the third post rather than pinned to the top, so it
         reads as part of the feed rather than an advert for the site. */
      if ($i === 2 && $suggestions) { echo render_suggestions($suggestions); }
  }
  if (count($posts) < 3 && $suggestions) { echo render_suggestions($suggestions); }
endif; ?>
</div>

<div id="feed-end" data-last="<?= $lastId ?>" data-more="<?= $hasMore ? 1 : 0 ?>">
  <?php if ($hasMore): ?>
    <button class="btn btn-quiet btn-block" id="load-more">Load more</button>
    <noscript>
      <a class="btn btn-quiet btn-block" style="margin-top:8px"
         href="<?= url('feed.php?' . http_build_query(array_filter(['tab' => $tab, 'subject' => $subject, 'before' => $lastId]))) ?>">
        Next page</a>
    </noscript>
  <?php endif; ?>

  <?php
  /* Always rendered, hidden while there is more to come. app.js reveals it
     when the feed runs out, rather than replacing everything here with a
     single grey sentence — which is what it used to do, so the people who
     scrolled furthest ended up with the least to do next.

     On a young site the feed runs out after a post or two, so this is where
     most sessions actually end. */
  ?>
  <?php if ($posts || $pinned): ?>
  <div class="feed-end"<?= $hasMore ? ' hidden' : '' ?>>
    <p class="small muted">That is everything for now.</p>
    <div class="feed-end-ways">
      <a class="btn btn-sm" href="<?= url('invite.php') ?>">Invite your class</a>
      <?php if ($tab !== 'unsolved' && $openQuestions > 0): ?>
        <a class="btn btn-sm btn-quiet" href="<?= url('feed.php?tab=unsolved') ?>">
          Answer <?= (int) $openQuestions ?> open question<?= $openQuestions === 1 ? '' : 's' ?></a>
      <?php endif; ?>
      <a class="btn btn-sm btn-quiet" href="<?= url('library.php') ?>">Past papers &amp; notes</a>
      <a class="btn btn-sm btn-quiet" href="<?= url('quiz.php') ?>">Take a quiz</a>
    </div>
  </div>
  <?php endif; ?>
</div>


<?php require INC_PATH . '/footer.php'; ?>
