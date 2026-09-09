<?php
/** Authenticated native feed and activity. Loaded only by api/mobile.php. */
if (!defined('NATIVE_API_AUTHENTICATED')) { http_response_code(403); exit; }

if ($action === 'notifications') {
    $before = max(0,(int)($_POST['before'] ?? 0));
    $rows = fetch_all('SELECT id,message,type,url,is_read,created_at,target_type,target_id FROM notifications WHERE user_id=? AND (?=0 OR id<?) ORDER BY id DESC LIMIT 40', [$uid,$before,$before]);
    $items = array_map(static fn($n) => [
        'id'=>(int)$n['id'],'message'=>$n['message'],'type'=>$n['type'],
        'route'=>(string)($n['url'] ?? ''),'read'=>(bool)$n['is_read'],'time'=>time_ago($n['created_at'])
    ],$rows);
    mobile_out(['items'=>$items,'unread'=>(int)fetch_col('SELECT COUNT(*) FROM notifications WHERE user_id=? AND is_read=0',[$uid])]);
}

if ($action === 'feed') {
    require_feature('feature_feed');
    require_once __DIR__ . '/feed_query.php';
    $before = max(0,(int)($_POST['before'] ?? 0));
    $postId = max(0,(int)($_POST['post_id'] ?? 0));
    $where = ["p.status='active'","u.status='active'","p.group_id IS NULL",
        "(p.visibility='public' OR p.user_id=? OR (p.visibility='followers' AND EXISTS(SELECT 1 FROM follows f WHERE f.follower_id=? AND f.following_id=p.user_id)))"];
    $params = [$uid,$uid];
    if ($before) { $where[]='p.id<?'; $params[]=$before; }
    if ($postId) { $where[]='p.id=?'; $params[]=$postId; }
    $blocked = blocked_ids();
    if ($blocked) { $where[]='p.user_id NOT IN ('.implode(',',array_fill(0,count($blocked),'?')).')'; $params=array_merge($params,$blocked); }
    $rows = hydrate_posts(fetch_all(post_select_sql().' WHERE '.implode(' AND ',$where).' ORDER BY p.id DESC LIMIT 20',$params));
    $posts = [];
    foreach ($rows as $p) {
        $anon = !empty($p['is_anonymous']);
        $page = !empty($p['page_id']) && ($p['page_status'] ?? '') === 'active';
        $author = $anon ? 'Anonymous learner' : ($page ? $p['page_name'] : $p['name']);
        $avatar = $anon ? null : ($page ? $p['page_avatar'] : $p['avatar']);
        $media = [];
        foreach ($p['media'] as $m) $media[] = ['id'=>(int)$m['id'],'name'=>$m['file_name'],'type'=>$m['file_type'], 'url'=>upload_url($m['file_path'])];
        /* Repost text needs its own byline; never expose anonymous identity. */
        $source = $p['source'];
        $sourceText = $source ? ((!empty($source['is_anonymous']) ? 'Anonymous learner' : $source['name']).":\n".$source['content']) : null;
        $posts[] = ['id'=>(int)$p['id'],'author'=>$author,'username'=>$anon ? '' : ($page ? ($p['page_username'] ?? '') : $p['username']),
            'avatar'=>$avatar ? upload_url($avatar) : null,'type'=>$p['type'],'content'=>(string)($p['content'] ?? ''),
            'created_at'=>time_ago($p['created_at']),'likes'=>(int)$p['likes_count'],'comments'=>(int)$p['comments_count'],
            'solved'=>(bool)$p['is_solved'],'liked'=>$p['my_reaction']==='like','reaction'=>$p['my_reaction'],
            'dislikes'=>(int)($p['dislikes_count'] ?? 0),'saved'=>(bool)$p['is_saved'],'subject'=>(string)($p['subject'] ?? ''),
            'verified'=>!$anon && (bool)($page ? ($p['page_verified'] ?? false) : $p['is_verified']),
            'mine'=>(int)$p['user_id']===$uid,'media'=>$media,'source'=>$sourceText,
            'can_repost'=>(int)$p['user_id']!==$uid && $p['visibility']==='public',
            'show_dislikes'=>setting('feed_dislikes','1')==='1'];
    }
    mobile_out(['posts'=>$posts,'has_more'=>count($rows)===20]);
}
