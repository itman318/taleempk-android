<?php
/** Authenticated native feed and activity. Loaded only by api/mobile.php. */
if (!defined('NATIVE_API_AUTHENTICATED')) { http_response_code(403); exit; }

if ($action === 'post_file') {
    require_feature('feature_feed');
    $id=max(0,(int)($_GET['id'] ?? 0));
    $media=fetch_one("SELECT m.*,p.user_id,p.visibility,p.group_id FROM post_media m JOIN posts p ON p.id=m.post_id WHERE m.id=? AND p.status='active'",[$id]);
    if(!$media || !can_view_post_row($media,$uid))mobile_error('This attachment is not available.',404);
    $base=realpath(UPLOAD_PATH);$file=realpath(UPLOAD_PATH.'/'.ltrim((string)$media['file_path'],'/'));
    if(!$base || !$file || strpos($file,$base.DIRECTORY_SEPARATOR)!==0 || !is_file($file))mobile_error('This attachment is not available.',404);
    $mime=['jpg'=>'image/jpeg','jpeg'=>'image/jpeg','png'=>'image/png','gif'=>'image/gif','webp'=>'image/webp','pdf'=>'application/pdf','txt'=>'text/plain','doc'=>'application/msword','docx'=>'application/vnd.openxmlformats-officedocument.wordprocessingml.document'];
    header('Content-Type: '.($mime[strtolower((string)$media['file_type'])] ?? 'application/octet-stream'));
    header('Content-Length: '.filesize($file));header('Cache-Control: private, no-store');
    header('Content-Disposition: inline; filename="'.preg_replace('/[^A-Za-z0-9._ -]/','_', (string)$media['file_name']).'"');
    readfile($file);exit;
}

if ($action === 'voice_played') {
    require_feature('feature_chat');
    $id=max(0,(int)($_POST['message_id'] ?? 0));
    $message=fetch_one("SELECT m.id FROM messages m JOIN conversation_members cm ON cm.conversation_id=m.conversation_id WHERE m.id=? AND cm.user_id=? AND m.sender_id<>? AND m.voice_seconds>0 AND m.status='sent'",[$id,$uid,$uid]);
    if(!$message)mobile_error('That voice message is not available.',404);
    if((int)($u['show_receipts'] ?? 1)===1 && table_exists('message_plays'))q('INSERT IGNORE INTO message_plays(message_id,user_id) VALUES(?,?)',[$id,$uid]);
    mobile_out();
}

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
        foreach ($p['media'] as $m) $media[] = ['id'=>(int)$m['id'],'name'=>$m['file_name'],'type'=>$m['file_type'], 'url'=>url('api/mobile.php?action=post_file&id='.(int)$m['id'])];
        /* Repost text needs its own byline; never expose anonymous identity. */
        $source = null;
        if(!empty($p['repost_of'])) {
            $source=fetch_one(post_select_sql()." WHERE p.id=? AND p.status='active' AND p.visibility='public' AND p.group_id IS NULL AND u.status='active'",[(int)$p['repost_of']]);
            if($source && in_array((int)$source['user_id'],$blocked,true))$source=null;
        }
        $sourceAuthor=$source ? (!empty($source['is_anonymous']) ? 'Anonymous learner' : (!empty($source['page_id']) ? (string)($source['page_name'] ?? 'Page') : $source['name'])) : '';
        $sourceText = $source ? ($sourceAuthor.":\n".$source['content']) : (!empty($p['repost_of']) ? 'Original post is no longer available.' : null);
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
