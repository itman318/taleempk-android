<?php
/** TaleemPK native E2EE key directory v3.2.
 *
 * This endpoint deliberately never receives a passphrase and never unwraps a
 * private key. It exposes the same key material/protocol as api/keys.php, but
 * authenticates Android with the native bearer token.
 */
if (!defined('NATIVE_API_REQUEST')) { define('NATIVE_API_REQUEST', true); }
header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store, private');
header('X-Content-Type-Options: nosniff');
try {
    require_once dirname(__DIR__) . '/includes/bootstrap.php';
    require_once dirname(__DIR__) . '/includes/chat_helpers.php';
} catch (Throwable $e) {
    http_response_code(500);
    echo json_encode(['ok'=>false,'error'=>'The encryption service could not start.']);
    exit;
}

function native_e2ee_out(array $data=[], int $status=200): void {
    while (ob_get_level()>0) { @ob_end_clean(); }
    http_response_code($status);
    header('Content-Type: application/json; charset=utf-8');
    echo json_encode(['ok'=>$status<400,'data'=>$data], JSON_UNESCAPED_SLASHES|JSON_UNESCAPED_UNICODE);
    exit;
}
function native_e2ee_error(string $message, int $status=400): void {
    while (ob_get_level()>0) { @ob_end_clean(); }
    http_response_code($status);
    header('Content-Type: application/json; charset=utf-8');
    echo json_encode(['ok'=>false,'error'=>$message], JSON_UNESCAPED_SLASHES|JSON_UNESCAPED_UNICODE);
    exit;
}
function native_e2ee_token(): string {
    $h=(string)($_SERVER['HTTP_AUTHORIZATION']??$_SERVER['REDIRECT_HTTP_AUTHORIZATION']??'');
    if($h===''&&function_exists('getallheaders')) foreach((array)getallheaders() as $k=>$v) {
        if(strcasecmp((string)$k,'Authorization')===0){$h=(string)$v;break;}
    }
    if(preg_match('/^Bearer\s+([a-f0-9]{64})$/i',trim($h),$m)) return strtolower($m[1]);
    $f=strtolower(trim((string)($_POST['access_token']??'')));
    return preg_match('/^[a-f0-9]{64}$/',$f)?$f:'';
}
function native_e2ee_user(): array {
    $token=native_e2ee_token();
    if($token==='') native_e2ee_error('Sign in to continue.',401);
    $u=fetch_one("SELECT u.* FROM mobile_sessions s JOIN users u ON u.id=s.user_id WHERE s.token_hash=? AND s.expires_at>NOW() AND u.status='active' LIMIT 1",[hash('sha256',$token)]);
    if(!$u) native_e2ee_error('Your session has expired. Sign in again.',401);
    return $u;
}
function native_e2ee_b64(string $s,int $min,int $max): bool {
    return $s!==''&&strlen($s)>=$min&&strlen($s)<=$max&&(bool)preg_match('/^[A-Za-z0-9+\/]+={0,2}$/',$s);
}

if($_SERVER['REQUEST_METHOD']!=='POST') native_e2ee_error('This endpoint only accepts POST.',405);
if(!api_burst_limit('mobile_e2ee',90)) native_e2ee_error('Too many encryption requests. Wait a moment.',429);
$me=native_e2ee_user(); $uid=(int)$me['id'];
$action=strtolower(trim((string)($_POST['action']??'')));

if($action==='publish'){
    $pub=(string)($_POST['public_key']??'');$wrapped=(string)($_POST['wrapped_key']??'');$salt=(string)($_POST['wrap_salt']??'');$iv=(string)($_POST['wrap_iv']??'');
    if(!native_e2ee_b64($pub,80,200)) native_e2ee_error('That public key does not look right.');
    if(!native_e2ee_b64($wrapped,40,4000)||!native_e2ee_b64($salt,8,64)||!native_e2ee_b64($iv,8,64)) native_e2ee_error('That wrapped key does not look right.');
    $existing=fetch_one('SELECT key_version FROM user_keys WHERE user_id=?',[$uid]);
    if($existing){
        q('UPDATE user_keys SET public_key=?,wrapped_key=?,wrap_salt=?,wrap_iv=?,key_version=key_version+1 WHERE user_id=?',[$pub,$wrapped,$salt,$iv,$uid]);
    }else{
        insert_row('user_keys',['user_id'=>$uid,'public_key'=>$pub,'wrapped_key'=>$wrapped,'wrap_salt'=>$salt,'wrap_iv'=>$iv]);
    }
    log_activity($uid,'mobile_e2ee_key','Updated Android E2EE account key');
    native_e2ee_out();
}

if($action==='mine'){
    $row=fetch_one('SELECT public_key,wrapped_key,wrap_salt,wrap_iv,key_version FROM user_keys WHERE user_id=?',[$uid]);
    native_e2ee_out(['key'=>$row?:null]);
}

if($action==='peer'){
    $peer=max(0,(int)($_POST['user_id']??0));
    if($peer<1) native_e2ee_error('No such person.');
    if($peer!==$uid){
        $shared=(int)fetch_col('SELECT COUNT(*) FROM conversation_members a JOIN conversation_members b ON b.conversation_id=a.conversation_id WHERE a.user_id=? AND b.user_id=?',[$uid,$peer]);
        if($shared<1) native_e2ee_error('No conversation with that person.',403);
    }
    $row=fetch_one('SELECT public_key,key_version FROM user_keys WHERE user_id=?',[$peer]);
    native_e2ee_out(['public_key'=>$row['public_key']??null,'key_version'=>(int)($row['key_version']??0)]);
}

if($action==='peers'){
    $raw=array_values(array_unique(array_slice(array_filter(array_map('intval',explode(',',(string)($_POST['user_ids']??'')))),0,200)));
    if(!$raw) native_e2ee_out(['keys'=>[]]);
    $ph=implode(',',array_fill(0,count($raw),'?'));
    $rows=fetch_all("SELECT k.user_id,k.public_key,k.key_version FROM user_keys k WHERE k.user_id IN ($ph) AND (k.user_id=? OR EXISTS(SELECT 1 FROM conversation_members a JOIN conversation_members b ON b.conversation_id=a.conversation_id WHERE a.user_id=? AND b.user_id=k.user_id))",array_merge($raw,[$uid,$uid]));
    $out=[];foreach($rows as $r)$out[(string)$r['user_id']]=['public_key'=>(string)$r['public_key'],'key_version'=>(int)$r['key_version']];
    native_e2ee_out(['keys'=>$out]);
}

$groupGuard=static function(int $cid)use($uid):array{
    if($cid<1) native_e2ee_error('No such conversation.');
    $conv=fetch_one('SELECT id,type,enc_epoch FROM conversations WHERE id=?',[$cid]);
    if(!$conv||(string)$conv['type']!=='group') native_e2ee_error('That is not a group conversation.');
    if(!fetch_one('SELECT id FROM conversation_members WHERE conversation_id=? AND user_id=?',[$cid,$uid])) native_e2ee_error('That conversation is not yours.',403);
    return $conv;
};

if($action==='group_state'){
    $cid=max(0,(int)($_POST['conversation_id']??0));$conv=$groupGuard($cid);$epoch=(int)$conv['enc_epoch'];$lookAt=max(1,$epoch);
    $mineKeys=fetch_all('SELECT ck.epoch,ck.wrapped_key,ck.sealed_by,uk.public_key AS sealer_public FROM conversation_keys ck LEFT JOIN user_keys uk ON uk.user_id=ck.sealed_by WHERE ck.conversation_id=? AND ck.user_id=? ORDER BY ck.epoch ASC',[$cid,$uid]);
    $needs=fetch_all("SELECT cm.user_id,u.name,k.public_key FROM conversation_members cm JOIN users u ON u.id=cm.user_id JOIN user_keys k ON k.user_id=cm.user_id LEFT JOIN conversation_keys ck ON ck.conversation_id=cm.conversation_id AND ck.user_id=cm.user_id AND ck.epoch=? WHERE cm.conversation_id=? AND ck.id IS NULL LIMIT 200",[$lookAt,$cid]);
    $members=(int)fetch_col('SELECT COUNT(*) FROM conversation_members WHERE conversation_id=?',[$cid]);
    $withKeys=(int)fetch_col('SELECT COUNT(*) FROM conversation_members cm JOIN user_keys k ON k.user_id=cm.user_id WHERE cm.conversation_id=?',[$cid]);
    native_e2ee_out(['me'=>$uid,'epoch'=>$epoch,'my_keys'=>$mineKeys,'needs'=>$needs,'members'=>$members,'with_keys'=>$withKeys]);
}

if($action==='group_put'){
    $cid=max(0,(int)($_POST['conversation_id']??0));$conv=$groupGuard($cid);$epoch=max(0,(int)($_POST['epoch']??0));
    if($epoch<1) native_e2ee_error('Missing epoch.');
    if($epoch>max(1,(int)$conv['enc_epoch'])) native_e2ee_error('That key version is not current.');
    $entries=json_decode((string)($_POST['entries']??'[]'),true);
    if(!is_array($entries)||$entries===[]||count($entries)>200) native_e2ee_error('Nothing valid to store.');
    $members=array_map(static fn($r)=>(int)$r['user_id'],fetch_all('SELECT user_id FROM conversation_members WHERE conversation_id=?',[$cid]));
    $stored=0;
    foreach($entries as $e){
        $recipient=(int)($e['user_id']??0);$blob=(string)($e['wrapped_key']??'');
        if(!in_array($recipient,$members,true))continue;
        if(strlen($blob)<40||strlen($blob)>1000||!preg_match('/^[A-Za-z0-9+\/=.]+$/',$blob))continue;
        $stored+=q('INSERT IGNORE INTO conversation_keys (conversation_id,user_id,epoch,wrapped_key,sealed_by) VALUES (?,?,?,?,?)',[$cid,$recipient,$epoch,$blob,$uid])->rowCount();
    }
    if((int)$conv['enc_epoch']<1&&$stored>0)q('UPDATE conversations SET enc_epoch=1 WHERE id=? AND enc_epoch<1',[$cid]);
    $owner=(int)fetch_col('SELECT sealed_by FROM conversation_keys WHERE conversation_id=? AND epoch=? ORDER BY id ASC LIMIT 1',[$cid,$epoch]);
    native_e2ee_out(['stored'=>$stored,'owner'=>$owner]);
}

native_e2ee_error('Unknown encryption request.',404);
