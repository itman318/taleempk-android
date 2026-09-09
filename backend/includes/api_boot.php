<?php
/** StudyHub - start an AJAX endpoint: POST only, CSRF checked, JSON out. */
require_once dirname(__DIR__) . '/includes/bootstrap.php';

/* A bearer-authenticated first-party endpoint may dispatch an existing API
   handler internally. The constant can only be defined by PHP code in this
   request; it cannot be supplied by a client. Native callers therefore keep
   the handler's validation and rate limits without pretending to own a
   browser CSRF token. */
$nativeBearerRequest = defined('NATIVE_API_AUTHENTICATED')
    && NATIVE_API_AUTHENTICATED === true;

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    json_out(['ok' => false, 'error' => 'This endpoint only accepts POST.'], 405);
}
/* Same request-too-large case require_csrf() guards against on the non-AJAX
   forms — checked first because when it fires, $_POST (and the CSRF token
   with it) never arrived at all, and csrf_ok() below would otherwise report
   that as an expired session instead of an oversized upload. */
if (post_body_was_too_large()) {
    json_out(['ok' => false, 'error' => post_too_large_message()], 413);
}
if (!$nativeBearerRequest && !csrf_ok()) {
    json_out(['ok' => false, 'error' => 'Your session expired. Refresh the page and try again.'], 419);
}

$apiEndpoint = $nativeBearerRequest && isset($GLOBALS['native_api_endpoint'])
    ? basename($GLOBALS['native_api_endpoint']) : basename((string) ($_SERVER['SCRIPT_NAME'] ?? 'api'));
$apiLimits = [
    'chat_poll.php' => 60, 'pulse.php' => 30, 'feed_more.php' => 60,
    'mention_search.php' => 30, 'notify_read.php' => 60,
    'react.php' => 60, 'save_item.php' => 30, 'follow.php' => 30,
    'block.php' => 20, 'mute.php' => 30, 'comment_create.php' => 20,
    'comment_action.php' => 30, 'post_create.php' => 10, 'post_edit.php' => 20,
    'post_action.php' => 30, 'group_action.php' => 30, 'chat_send.php' => 20,
    'report.php' => 10, 'ai.php' => 20,
    /* These had no ceiling at all. None of them is dangerous on its own; each
       is a query somebody can fire in a loop, and the point of this table is
       that the answer lives in ONE place — an endpoint with its own inline
       limit as well as this one is two limits for one thing, and the tighter
       one wins silently while somebody adjusts the other. */
    'suggest_people.php' => 40, 'similar.php' => 40, 'topic_follow.php' => 30,
    'repost.php' => 20, 'chat_list.php' => 40, 'chat_manage.php' => 30,
    'chat_message.php' => 40, 'chat_group.php' => 30, 'chat_star.php' => 40,
    'chat_pin.php' => 30, 'chat_reaction.php' => 60, 'chat_vote.php' => 30,
];
/* The chat poll runs every two to three seconds while a thread is live, and
   is pulled forward by typing, by sending and by the tab regaining focus. At
   thirty a minute it was tripping its own limit in ordinary use, and a poll
   that is refused backs off for minutes — so the limit was breaking the very
   thing it protected. Sixty leaves room; the adaptive gap keeps real load
   well under it. */
if (isset($apiLimits[$apiEndpoint]) && !api_burst_limit($apiEndpoint, $apiLimits[$apiEndpoint])) {
    header('Retry-After: 60');
    json_out(['ok' => false, 'error' => 'Too many requests. Please wait a moment and try again.'], 429);
}
