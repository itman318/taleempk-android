<?php
/** TaleemPK native social/profile/verification API v3.1. */
if (!defined('NATIVE_API_REQUEST')) { define('NATIVE_API_REQUEST', true); }
header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store, private');
header('X-Content-Type-Options: nosniff');

try {
    require_once dirname(__DIR__) . '/includes/bootstrap.php';
    require_once dirname(__DIR__) . '/includes/feed_query.php';
} catch (Throwable $e) {
    http_response_code(500);
    echo json_encode(['ok'=>false,'error'=>'The TaleemPK social service could not start.']);
    exit;
}

function mobile_out(array $data = [], int $status = 200): void {
    while (ob_get_level() > 0) { @ob_end_clean(); }
    http_response_code($status);
    header('Content-Type: application/json; charset=utf-8');
    echo json_encode(['ok'=>$status<400,'data'=>$data], JSON_UNESCAPED_SLASHES|JSON_UNESCAPED_UNICODE);
    exit;
}
function mobile_error(string $message, int $status = 400): void {
    while (ob_get_level() > 0) { @ob_end_clean(); }
    http_response_code($status);
    header('Content-Type: application/json; charset=utf-8');
    echo json_encode(['ok'=>false,'error'=>$message], JSON_UNESCAPED_SLASHES|JSON_UNESCAPED_UNICODE);
    exit;
}
function mobile_bearer(): string {
    $header=(string)($_SERVER['HTTP_AUTHORIZATION']??$_SERVER['REDIRECT_HTTP_AUTHORIZATION']??'');
    if($header===''&&function_exists('getallheaders')) foreach((array)getallheaders() as $k=>$v) {
        if(strcasecmp((string)$k,'Authorization')===0){$header=(string)$v;break;}
    }
    if(preg_match('/^Bearer\s+([a-f0-9]{64})$/i',trim($header),$m)) return strtolower($m[1]);
    $fallback=strtolower(trim((string)($_POST['access_token']??'')));
    return preg_match('/^[a-f0-9]{64}$/',$fallback)?$fallback:'';
}
function mobile_user(): array {
    $token=mobile_bearer();
    if($token==='') mobile_error('Sign in to continue.',401);
    $row=fetch_one("SELECT u.* FROM mobile_sessions s JOIN users u ON u.id=s.user_id WHERE s.token_hash=? AND s.expires_at>NOW() AND u.status='active' LIMIT 1",[hash('sha256',$token)]);
    if(!$row) mobile_error('Your session has expired. Sign in again.',401);
    q('UPDATE mobile_sessions SET last_seen=NOW() WHERE token_hash=? AND last_seen<DATE_SUB(NOW(),INTERVAL 5 MINUTE)',[hash('sha256',$token)]);
    return $row;
}
function mobile_social_bridge(array $user, int $uid): void {
    $_SESSION['uid']=$uid;
    $GLOBALS['NATIVE_API_USER']=$user;
    $_SERVER['HTTP_X_REQUESTED_WITH']='XMLHttpRequest';
    if(!defined('NATIVE_API_AUTHENTICATED')) define('NATIVE_API_AUTHENTICATED',true);
}
function mobile_social_bool($value): bool {
    return $value===true||$value===1||$value==='1'||$value==='true';
}
function mobile_social_post_payload(array $p,int $uid,array $media=[],array $mine=[],array $saved=[],array $sources=[],array $reposted=[]): array {
    $anonymous=(int)($p['is_anonymous']??0)===1&&(string)($p['type']??'')==='question';
    $pageName=trim((string)($p['page_name']??''));
    $isPage=$pageName!==''&&(string)($p['page_status']??'active')==='active';
    $author=$anonymous?'Anonymous student':($isPage?$pageName:(string)($p['name']??'TaleemPK member'));
    $username=$anonymous?'':($isPage?(string)($p['page_username']??''):(string)($p['username']??''));
    $avatar=null;
    if(!$anonymous){$path=$isPage?($p['page_avatar']??null):($p['avatar']??null);if(!empty($path))$avatar=upload_url((string)$path);}
    $id=(int)$p['id'];
    $source=null;
    if(!empty($p['repost_of'])&&isset($sources[(int)$p['repost_of']])){
        $s=$sources[(int)$p['repost_of']];
        $source=['id'=>(int)$s['id'],'author'=>(int)($s['is_anonymous']??0)===1?'Anonymous student':(string)$s['name'],
            'username'=>(int)($s['is_anonymous']??0)===1?'':(string)$s['username'],'content'=>(string)($s['content']??''),
            'subject'=>(string)($s['subject']??''),'type'=>(string)($s['type']??'text'),'created_at'=>time_ago($s['created_at'])];
    }
    return ['id'=>$id,'author_id'=>(int)($p['user_id']??0),'author'=>$author,'username'=>$username,'avatar'=>$avatar,
        'role'=>$anonymous?'student':(string)($p['role']??'student'),'verified'=>!$anonymous&&(int)($isPage?($p['page_verified']??0):($p['is_verified']??0))===1,
        'type'=>(string)($p['type']??'text'),'content'=>(string)($p['content']??''),'subject'=>(string)($p['subject']??''),
        'visibility'=>(string)($p['visibility']??'public'),'anonymous'=>$anonymous,'created_at'=>time_ago($p['created_at']),
        'likes'=>(int)($p['likes_count']??0),'dislikes'=>(int)($p['dislikes_count']??0),'comments'=>(int)($p['comments_count']??0),
        'reposts'=>(int)($p['reposts_count']??0),'solved'=>(int)($p['is_solved']??0)===1,'pinned'=>(int)($p['is_pinned']??0)===1,
        'my_reaction'=>$mine[$id]??null,'saved'=>isset($saved[$id]),'reposted'=>isset($reposted[$id]),
        'mine'=>(int)($p['user_id']??0)===$uid&&!$isPage,
        'media'=>array_values(array_map(static function(array $m):array{$path=(string)($m['file_path']??'');return ['id'=>(int)($m['id']??0),'url'=>$path!==''?upload_url($path):'','type'=>(string)($m['file_type']??'file'),'name'=>(string)($m['file_name']??basename($path))];},$media[$id]??[])),
        'source'=>$source];
}

if($_SERVER['REQUEST_METHOD']!=='POST') mobile_error('This endpoint only accepts POST.',405);
$action=strtolower(trim((string)($_POST['action']??'')));
$u=mobile_user();$uid=(int)$u['id'];

if(in_array($action,['create_post','react_post'],true)){
    mobile_social_bridge($u,$uid);
    if($action==='create_post') require __DIR__.'/post_create.php';
    require __DIR__.'/react.php';
}

if($action==='feed_v2'){
    require_feature('feature_feed');
    $tab=strtolower(trim((string)($_POST['tab']??'latest')));if(!in_array($tab,['latest','following','questions','unsolved'],true))$tab='latest';
    $subject=mb_substr(trim((string)($_POST['subject']??'')),0,100);$before=max(0,(int)($_POST['before']??0));$limit=max(8,min(24,(int)($_POST['limit']??15)));
    $where=["p.status='active'","p.visibility IN ('public','followers')",'p.group_id IS NULL'];$params=[];
    if(function_exists('blocked_ids')){$blocked=blocked_ids();if($blocked)$where[]='p.user_id NOT IN ('.implode(',',array_map('intval',$blocked)).')';}
    if($tab==='following'){$where[]='p.user_id IN (SELECT following_id FROM follows WHERE follower_id=?)';$params[]=$uid;}
    elseif($tab==='questions')$where[]="p.type='question'";elseif($tab==='unsolved')$where[]="p.type='question' AND p.is_solved=0";
    if($subject!==''){$where[]='p.subject=?';$params[]=$subject;}if($before>0){$where[]='p.id<?';$params[]=$before;}
    $pageCols='';$pageJoin='';if(table_exists('creator_pages')){$pageCols=',pg.name page_name,pg.username page_username,pg.avatar page_avatar,pg.status page_status,pg.is_verified page_verified';$pageJoin=' LEFT JOIN creator_pages pg ON pg.id=p.page_id';}
    $sql="SELECT p.*,u.name,u.username,u.avatar,u.role,u.is_verified{$pageCols} FROM posts p JOIN users u ON u.id=p.user_id{$pageJoin} WHERE ".implode(' AND ',$where)." AND u.status='active'";
    $rows=fetch_all($sql.' ORDER BY p.is_pinned DESC,p.id DESC LIMIT '.($limit+1),$params);$hasMore=count($rows)>$limit;if($hasMore)array_pop($rows);
    $ids=array_values(array_unique(array_map(static fn(array $r):int=>(int)$r['id'],$rows)));$media=[];$mine=[];$saved=[];$sources=[];$reposted=[];
    if($ids){$in=implode(',',array_fill(0,count($ids),'?'));
        foreach(fetch_all('SELECT * FROM post_media WHERE post_id IN ('.$in.') ORDER BY sort_order,id',$ids) as $m)$media[(int)$m['post_id']][]=$m;
        $mineParams=array_merge([$uid],$ids);
        foreach(fetch_all("SELECT target_id,type FROM reactions WHERE user_id=? AND target_type='post' AND target_id IN ({$in})",$mineParams) as $r)$mine[(int)$r['target_id']]=(string)$r['type'];
        foreach(fetch_all("SELECT target_id FROM saved_items WHERE user_id=? AND target_type='post' AND target_id IN ({$in})",$mineParams) as $r)$saved[(int)$r['target_id']]=true;
        foreach(fetch_all("SELECT repost_of FROM posts WHERE user_id=? AND repost_of IN ({$in}) AND status='active'",$mineParams) as $r)$reposted[(int)$r['repost_of']]=true;
        $sourceIds=[];foreach($rows as $r)if(!empty($r['repost_of']))$sourceIds[]=(int)$r['repost_of'];
        if($sourceIds){$sourceIds=array_values(array_unique($sourceIds));$sIn=implode(',',array_fill(0,count($sourceIds),'?'));
            foreach(fetch_all("SELECT p.id,p.user_id,p.content,p.subject,p.type,p.is_anonymous,p.created_at,u.name,u.username FROM posts p JOIN users u ON u.id=p.user_id WHERE p.id IN ({$sIn}) AND p.status='active'",$sourceIds) as $s)$sources[(int)$s['id']]=$s;}
    }
    $posts=array_map(static fn(array $p):array=>mobile_social_post_payload($p,$uid,$media,$mine,$saved,$sources,$reposted),$rows);
    $next=$rows?min(array_map(static fn(array $r):int=>(int)$r['id'],$rows)):0;$subjects=[];
    if($before===0)$subjects=array_map(static fn(array $r):string=>(string)$r['subject'],fetch_all("SELECT subject,COUNT(*) n FROM posts WHERE status='active' AND group_id IS NULL AND subject IS NOT NULL AND subject<>'' AND created_at>=DATE_SUB(NOW(),INTERVAL 30 DAY) GROUP BY subject ORDER BY n DESC,subject LIMIT 12"));
    mobile_out(['posts'=>$posts,'has_more'=>$hasMore,'next_before'=>$next,'subjects'=>$subjects,'show_dislikes'=>(int)setting('feed_dislikes',0)===1]);
}

if($action==='save_post'){
    mobile_social_bridge($u,$uid);$saveId=max(0,(int)($_POST['post_id']??$_POST['id']??0));$_POST['target']='post:'.$saveId;require __DIR__.'/save_item.php';
}
if($action==='repost_post'){mobile_social_bridge($u,$uid);$_POST['id']=(string)max(0,(int)($_POST['post_id']??$_POST['id']??0));require __DIR__.'/repost.php';}
if($action==='delete_post'){mobile_social_bridge($u,$uid);$_POST['id']=(string)max(0,(int)($_POST['post_id']??$_POST['id']??0));$_POST['do']='delete';require __DIR__.'/post_action.php';}
if($action==='edit_post'){mobile_social_bridge($u,$uid);$_POST['kind']='post';$_POST['id']=(string)max(0,(int)($_POST['post_id']??$_POST['id']??0));require __DIR__.'/post_edit.php';}

if($action==='profile_get'){
    $username=strtolower(trim((string)($_POST['username']??'')));$targetId=max(0,(int)($_POST['user_id']??0));
    $select='SELECT u.*,p.level,p.class_grade,p.institute_txt,p.institute_id,p.degree,p.department,p.semester,p.subjects profile_subjects,p.qualification profile_qualification,p.experience,p.teaches,p.website profile_website FROM users u LEFT JOIN profiles p ON p.user_id=u.id WHERE ';
    $target=$username!==''?fetch_one($select.'u.username=? LIMIT 1',[$username]):fetch_one($select.'u.id=? LIMIT 1',[$targetId?:$uid]);
    if(!$target||((string)$target['status']==='banned'&&!is_admin()))mobile_error('Profile not found.',404);
    $tid=(int)$target['id'];$isMe=$tid===$uid;$iBlocked=!$isMe&&(bool)fetch_one('SELECT id FROM blocks WHERE user_id=? AND blocked_id=? LIMIT 1',[$uid,$tid]);$theyBlocked=!$isMe&&(bool)fetch_one('SELECT id FROM blocks WHERE user_id=? AND blocked_id=? LIMIT 1',[$tid,$uid]);
    $private=(string)($target['profile_privacy']??'public')==='private'&&!$isMe&&!is_admin();$following=!$isMe&&(bool)fetch_one('SELECT id FROM follows WHERE follower_id=? AND following_id=? LIMIT 1',[$uid,$tid]);$followsYou=!$isMe&&(bool)fetch_one('SELECT id FROM follows WHERE follower_id=? AND following_id=? LIMIT 1',[$tid,$uid]);
    $profile=['id'=>$tid,'name'=>(string)$target['name'],'username'=>(string)$target['username'],'role'=>(string)$target['role'],'avatar'=>!empty($target['avatar'])?upload_url((string)$target['avatar']):null,'cover'=>!empty($target['cover'])?upload_url((string)$target['cover']):null,
        'verified'=>(int)($target['is_verified']??0)===1,'verified_at'=>(string)($target['verified_at']??''),'verified_kind'=>(string)($target['verified_kind']??''),'headline'=>$private?'':(string)($target['headline']??''),'bio'=>$private?'':(string)($target['bio']??''),'city'=>$private?'':(string)($target['city']??''),'country'=>$private?'':(string)($target['country']??''),
        'posts'=>(int)($target['posts_count']??0),'followers'=>(int)($target['followers_count']??0),'following'=>(int)($target['following_count']??0),'profile_privacy'=>(string)($target['profile_privacy']??'public'),'private'=>$private,'blocked'=>$iBlocked||$theyBlocked,'i_blocked'=>$iBlocked,'blocked_me'=>$theyBlocked,'is_me'=>$isMe,'is_following'=>$following,'follows_you'=>$followsYou,'allow_dm'=>(string)($target['allow_dm']??'everyone'),
        'level'=>(string)($target['level']??''),'class_grade'=>(string)($target['class_grade']??''),'institute'=>(string)($target['institute_txt']??''),'degree'=>(string)($target['degree']??''),'department'=>(string)($target['department']??''),'semester'=>(string)($target['semester']??''),'subjects'=>$private?'':(string)($target['subjects']??$target['profile_subjects']??''),'qualification'=>$private?'':(string)($target['qualification']??$target['profile_qualification']??''),'experience'=>(int)($target['experience_yrs']??$target['experience']??0),'teaches'=>$private?'':(string)($target['teaches']??''),'website'=>$private?'':(string)($target['profile_website']??''),'accepting_students'=>(int)($target['accepting_students']??0)===1,'rating'=>(float)($target['rating_avg']??0),'ratings'=>(int)($target['rating_count']??0),'phone'=>$isMe?(string)($target['phone']??''):'','gender'=>$isMe?(string)($target['gender']??''):'','dob'=>$isMe?(string)($target['dob']??''):'' ];
    mobile_out(['profile'=>$profile]);
}

if($action==='profile_activity'){
    $targetId=max(1,(int)($_POST['user_id']??$uid));$kind=strtolower(trim((string)($_POST['kind']??'posts')));if(!in_array($kind,['posts','uploads','answers','badges'],true))$kind='posts';$before=max(0,(int)($_POST['before']??0));$limit=max(8,min(24,(int)($_POST['limit']??15)));
    $target=fetch_one("SELECT id,status,profile_privacy FROM users WHERE id=? LIMIT 1",[$targetId]);if(!$target||(string)$target['status']!=='active')mobile_error('Profile not found.',404);if((string)$target['profile_privacy']==='private'&&$targetId!==$uid&&!is_admin())mobile_out(['items'=>[],'has_more'=>false,'next_before'=>0]);$items=[];
    if($kind==='posts'||$kind==='uploads'){$where="p.user_id=? AND p.status='active' AND p.group_id IS NULL";$params=[$targetId];if($kind==='uploads')$where.=" AND EXISTS(SELECT 1 FROM post_media pm WHERE pm.post_id=p.id)";if($before>0){$where.=' AND p.id<?';$params[]=$before;}$rows=fetch_all("SELECT p.id,p.type,p.content,p.subject,p.created_at,p.likes_count,p.comments_count,p.is_solved FROM posts p WHERE {$where} ORDER BY p.id DESC LIMIT ".($limit+1),$params);$more=count($rows)>$limit;if($more)array_pop($rows);foreach($rows as $r)$items[]=['id'=>(int)$r['id'],'title'=>excerpt((string)$r['content'],120)?:ucfirst((string)$r['type']),'subtitle'=>(string)($r['subject']??''),'meta'=>time_ago($r['created_at']).' · '.(int)$r['likes_count'].' likes · '.(int)$r['comments_count'].' comments','kind'=>'post'];mobile_out(['items'=>$items,'has_more'=>$more,'next_before'=>$rows?min(array_map(static fn($r)=>(int)$r['id'],$rows)):0]);}
    if($kind==='answers'){$params=[$targetId];$where="c.user_id=? AND c.status='active'";if($before>0){$where.=' AND c.id<?';$params[]=$before;}$rows=fetch_all("SELECT c.id,c.content,c.created_at,p.content post_content FROM comments c JOIN posts p ON p.id=c.post_id WHERE {$where} ORDER BY c.id DESC LIMIT ".($limit+1),$params);$more=count($rows)>$limit;if($more)array_pop($rows);foreach($rows as $r)$items[]=['id'=>(int)$r['id'],'title'=>excerpt((string)$r['content'],130),'subtitle'=>'On: '.excerpt((string)$r['post_content'],90),'meta'=>time_ago($r['created_at']),'kind'=>'answer'];mobile_out(['items'=>$items,'has_more'=>$more,'next_before'=>$rows?min(array_map(static fn($r)=>(int)$r['id'],$rows)):0]);}
    if($kind==='badges'){if(table_exists('user_badges')&&table_exists('badges')){$rows=fetch_all('SELECT ub.id,b.name,b.description,ub.awarded_at FROM user_badges ub JOIN badges b ON b.id=ub.badge_id WHERE ub.user_id=? ORDER BY ub.id DESC LIMIT 50',[$targetId]);foreach($rows as $r)$items[]=['id'=>(int)$r['id'],'title'=>(string)$r['name'],'subtitle'=>(string)($r['description']??''),'meta'=>!empty($r['awarded_at'])?time_ago($r['awarded_at']):'Earned badge','kind'=>'badge'];}mobile_out(['items'=>$items,'has_more'=>false,'next_before'=>0]);}
}

if($action==='profile_follow'){
    $targetId=max(1,(int)($_POST['user_id']??0));if($targetId===$uid)mobile_error('You cannot follow yourself.');$target=fetch_one("SELECT id,name FROM users WHERE id=? AND status='active'",[$targetId]);if(!$target)mobile_error('That account is not available.',404);
    if((bool)fetch_one('SELECT id FROM blocks WHERE (user_id=? AND blocked_id=?) OR (user_id=? AND blocked_id=?) LIMIT 1',[$uid,$targetId,$targetId,$uid]))mobile_error('You cannot follow this person.',403);
    $exists=(bool)fetch_one('SELECT id FROM follows WHERE follower_id=? AND following_id=? LIMIT 1',[$uid,$targetId]);
    if($exists){db_transaction(static function()use($uid,$targetId):void{delete_row('follows','follower_id=? AND following_id=?',[$uid,$targetId]);q('UPDATE users SET followers_count=GREATEST(followers_count-1,0) WHERE id=?',[$targetId]);q('UPDATE users SET following_count=GREATEST(following_count-1,0) WHERE id=?',[$uid]);});mobile_out(['following'=>false]);}
    db_transaction(static function()use($uid,$targetId):void{insert_row('follows',['follower_id'=>$uid,'following_id'=>$targetId]);q('UPDATE users SET followers_count=followers_count+1 WHERE id=?',[$targetId]);q('UPDATE users SET following_count=following_count+1 WHERE id=?',[$uid]);});notify($targetId,'follow',(string)$u['name'].' started following you',url('profile.php?u='.(string)$u['username']),$uid,'user',$uid);mobile_out(['following'=>true]);
}

if($action==='profile_update_v2'){
    $name=mail_header_safe(trim((string)($_POST['name']??'')));if(mb_strlen($name)<3)mobile_error('Enter your full name.');$bio=mb_substr(trim((string)($_POST['bio']??'')),0,480);$headline=mb_substr(trim((string)($_POST['headline']??'')),0,160);$city=mb_substr(trim((string)($_POST['city']??'')),0,80);$phone=mb_substr(trim((string)($_POST['phone']??'')),0,30);$gender=strtolower(trim((string)($_POST['gender']??'')));if(!in_array($gender,['male','female','other',''],true))$gender='';
    $userUpdate=['name'=>$name,'bio'=>$bio?:null,'headline'=>$headline?:null,'city'=>$city?:null,'phone'=>$phone?:null,'gender'=>$gender?:null];
    foreach(['subjects'=>'subjects','qualification'=>'qualification'] as $key=>$col){$v=mb_substr(trim((string)($_POST[$key]??'')),0,$key==='subjects'?255:160);if($v!==''||array_key_exists($key,$_POST))$userUpdate[$col]=$v?:null;}if(array_key_exists('experience',$_POST))$userUpdate['experience_yrs']=max(0,min(60,(int)$_POST['experience']);if(array_key_exists('accepting_students',$_POST))$userUpdate['accepting_students']=mobile_social_bool($_POST['accepting_students'])?1:0;
    update_row('users',$userUpdate,'id=?',[$uid]);if(!fetch_one('SELECT user_id FROM profiles WHERE user_id=? LIMIT 1',[$uid]))insert_row('profiles',['user_id'=>$uid]);$profileUpdate=[];
    foreach(['level','class_grade','institute','degree','department','semester','teaches','website'] as $field){if(array_key_exists($field,$_POST)){$v=trim((string)$_POST[$field]);$col=$field==='institute'?'institute_txt':$field;$profileUpdate[$col]=$v!==''?$v:null;}}if($profileUpdate)update_row('profiles',$profileUpdate,'user_id=?',[$uid]);
    if(!empty($_FILES['avatar']['name'])){$up=upload_file($_FILES['avatar'],'avatars',ALLOWED_IMAGE_EXT,MAX_IMAGE_SIZE);if(!$up['ok'])mobile_error((string)$up['error']);if(!empty($u['avatar']))delete_upload((string)$u['avatar']);update_row('users',['avatar'=>$up['path']],'id=?',[$uid]);}
    if(!empty($_FILES['cover']['name'])){$up=upload_file($_FILES['cover'],'covers',ALLOWED_IMAGE_EXT,MAX_IMAGE_SIZE);if(!$up['ok'])mobile_error((string)$up['error']);if(!empty($u['cover']))delete_upload((string)$u['cover']);update_row('users',['cover'=>$up['path']],'id=?',[$uid]);}
    log_activity($uid,'mobile_profile_update','Updated full profile in Android app');mobile_out(['message'=>'Profile updated.']);
}

if($action==='verification_status'){
    $row=fetch_one('SELECT * FROM verifications WHERE user_id=? ORDER BY id DESC LIMIT 1',[$uid]);$emailVerified=(int)($u['email_verified']??0)===1;$verified=(int)($u['is_verified']??0)===1;$lapsed=$row&&(string)$row['status']==='approved'&&!$verified;$payload=null;
    if($row)$payload=['id'=>(int)$row['id'],'case_id'=>(int)($row['case_id']??0),'kind'=>(string)$row['kind'],'status'=>$lapsed?'expired':(string)$row['status'],'full_name'=>(string)($row['full_name']??''),'id_number'=>(string)($row['id_number']??''),'org_name'=>(string)($row['org_name']??''),'role_title'=>(string)($row['role_title']??''),'subjects'=>(string)($row['subjects']??''),'experience'=>(int)($row['experience']??0),'website'=>(string)($row['website']??''),'contact_phone'=>(string)($row['contact_phone']??''),'notes'=>(string)($row['notes']??''),'admin_note'=>(string)($row['admin_note']??''),'attempt_no'=>(int)($row['attempt_no']??1),'created_at'=>time_ago($row['created_at']),'viewed'=>!empty($row['viewed_at']),'reviewed'=>!empty($row['reviewed_at']),'has_doc_id'=>!empty($row['doc_id']),'has_doc_proof'=>!empty($row['doc_proof']),'has_doc_extra'=>!empty($row['doc_extra'])];
    mobile_out(['email_verified'=>$emailVerified,'verified'=>$verified,'application'=>$payload,'can_apply'=>$emailVerified&&(!$row||in_array($lapsed?'expired':(string)$row['status'],['rejected','withdrawn','expired','info'],true))]);
}
if($action==='verification_withdraw'){$row=fetch_one("SELECT id,case_id FROM verifications WHERE user_id=? AND status IN ('pending','info') ORDER BY id DESC LIMIT 1",[$uid]);if(!$row)mobile_error('There is no open verification application to withdraw.',409);update_row('verifications',['status'=>'withdrawn'],'id=? AND user_id=?',[(int)$row['id'],$uid]);if(!empty($row['case_id'])&&function_exists('case_touch'))case_touch((int)$row['case_id'],'closed','normal');log_activity($uid,'verify_withdraw','Withdrew verification request #'.(int)$row['id'],'verification',(int)$row['id']);mobile_out(['message'=>'Your application has been withdrawn.']);}

if($action==='verification_apply'){
    if((int)($u['email_verified']??0)!==1)mobile_error('Confirm your email address before applying.',403);if(!api_burst_limit('verify_apply',2))mobile_error('Too many submissions in a short period. Please wait a minute and try again.',429);$current=fetch_one('SELECT * FROM verifications WHERE user_id=? ORDER BY id DESC LIMIT 1',[$uid]);$verified=(int)($u['is_verified']??0)===1;$lapsed=$current&&(string)$current['status']==='approved'&&!$verified;if($current&&(string)$current['status']==='pending')mobile_error('You already have an application under review.',409);if($current&&(string)$current['status']==='approved'&&!$lapsed)mobile_error('You are already verified.',409);
    $kind=strtolower(trim((string)($_POST['kind']??'student')));if(!in_array($kind,['teacher','institute','student'],true))$kind='student';$fullName=mb_substr(trim((string)($_POST['full_name']??$u['name']??'')),0,120);if($fullName==='')mobile_error('Your full name is needed.');$idRaw=(string)($_POST['id_number']??'');$problem=function_exists('cnic_problem')?cnic_problem($idRaw):'';if($problem!=='')mobile_error($problem);if((string)($_POST['declaration']??'')!=='1')mobile_error('Please confirm the declaration before submitting your application.');$idNumber=function_exists('cnic_format')?cnic_format($idRaw):trim($idRaw);
    $data=['user_id'=>$uid,'kind'=>$kind,'full_name'=>$fullName,'id_number'=>$idNumber,'org_name'=>mb_substr(trim((string)($_POST['org_name']??'')),0,160)?:null,'role_title'=>mb_substr(trim((string)($_POST['role_title']??'')),0,120)?:null,'subjects'=>mb_substr(trim((string)($_POST['subjects']??'')),0,255)?:null,'experience'=>($_POST['experience']??'')!==''?max(0,min(60,(int)$_POST['experience'])):null,'website'=>mb_substr(trim((string)($_POST['website']??'')),0,200)?:null,'contact_phone'=>mb_substr(trim((string)($_POST['contact_phone']??'')),0,30)?:null,'notes'=>mb_substr(trim((string)($_POST['notes']??'')),0,2000)?:null,'status'=>'pending'];
    if($current&&(string)$current['status']==='info')foreach(['doc_id','doc_proof','doc_extra'] as $f)$data[$f]=!empty($current[$f])?$current[$f]:null;$data['id_hash']=function_exists('verify_id_hash')?verify_id_hash($idNumber):hash('sha256',preg_replace('/\D+/','',$idNumber));if(!empty($data['id_hash'])){$dup=fetch_one("SELECT id FROM verifications WHERE id_hash=? AND user_id<>? AND status IN ('pending','info','approved') LIMIT 1",[$data['id_hash'],$uid]);if($dup)mobile_error('This ID number is already linked to another TaleemPK account. Contact support if that account is yours.',409);}
    $replaced=[];foreach(['doc_id','doc_proof','doc_extra'] as $field){if(empty($_FILES[$field]['name']))continue;$up=upload_file($_FILES[$field],'verify','jpg,jpeg,png,webp,pdf',MAX_IMAGE_SIZE*2);if(!$up['ok'])mobile_error((string)$up['error']);if($current&&!empty($current[$field])&&$current[$field]!==$up['path'])$replaced[]=(string)$current[$field];$data[$field]=$up['path'];}if(empty($data['doc_id']))mobile_error('An identity document is required — CNIC, student card, or passport photo page.');if($kind!=='student'&&empty($data['doc_proof']))mobile_error('Proof of your teacher or institute role is required.');
    $case=null;if($current&&!empty($current['case_id'])&&function_exists('case_get'))$case=case_get((int)$current['case_id']);if(!$case||$lapsed||($current&&in_array((string)$current['status'],['rejected','withdrawn'],true)))$caseId=function_exists('case_create')?case_create($uid,'verification','Verification · '.$fullName,'Identity verification review for '.$fullName,'high'):null;else $caseId=(int)$case['id'];if($caseId)$data['case_id']=$caseId;
    if($current&&(string)$current['status']==='info'){$update=$data;$update['attempt_no']=(int)($current['attempt_no']??1)+1;$update['admin_note']=null;$update['reviewed_by']=null;$update['reviewed_at']=null;$update['viewed_by']=null;$update['viewed_at']=null;unset($update['user_id']);update_row('verifications',$update,"id=? AND user_id=? AND status='info'",[(int)$current['id'],$uid]);$id=(int)$current['id'];foreach($replaced as $old)delete_upload($old);if($caseId&&function_exists('case_touch'))case_touch((int)$caseId,'in_review','high');log_activity($uid,'verify_resubmit','Updated verification request #'.$id,'verification',$id);}else{$data['attempt_no']=1+(int)fetch_col('SELECT COUNT(*) FROM verifications WHERE user_id=?',[$uid]);$id=insert_row('verifications',$data);log_activity($uid,'verify_apply','Submitted verification request #'.$id,'verification',$id);}
    if(function_exists('alert_staff'))alert_staff('verify_request',(string)$u['name'].' submitted verification',url('admin/verifications.php'),$uid,'verification',$id,'Verification request',(string)$u['name'].' submitted verification from the Android app.','Review the request');mobile_out(['id'=>$id,'message'=>'Your verification application is in the review queue.'],201);
}

mobile_error('That social action is not available.',404);
