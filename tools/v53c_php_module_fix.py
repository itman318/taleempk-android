from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
START = "\n/* TaleemPK v5.3: cross-app search + actual recipient delivery receipts. */"
NEXT = "require_once __DIR__ . '/mobile_realtime_push_v44.php';"

MODULE = r'''<?php
/** TaleemPK v5.3: cross-app search + actual recipient delivery receipts. */
function mobile_v53_tables(): void {
    static $ready=false; if($ready)return;
    q("CREATE TABLE IF NOT EXISTS mobile_message_delivery (
      message_id BIGINT UNSIGNED NOT NULL,user_id BIGINT UNSIGNED NOT NULL,
      delivered_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
      PRIMARY KEY(message_id,user_id),KEY idx_v53_delivery_user(user_id,delivered_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4");
    $ready=true;
}
if ($action === 'ack_delivery') {
    mobile_v53_tables();
    $ids=array_values(array_unique(array_filter(array_map('intval',explode(',',(string)($_POST['ids']??''))),fn($v)=>$v>0)));
    foreach(array_slice($ids,0,100) as $mid){
      $ok=fetch_one("SELECT m.id FROM messages m JOIN conversation_members cm ON cm.conversation_id=m.conversation_id WHERE m.id=? AND cm.user_id=? AND m.sender_id<>? LIMIT 1",[$mid,$uid,$uid]);
      if($ok) q('INSERT IGNORE INTO mobile_message_delivery(message_id,user_id) VALUES(?,?)',[$mid,$uid]);
    }
    mobile_out(['delivered'=>count($ids)]);
}
if ($action === 'delivery_status') {
    mobile_v53_tables(); $mid=max(0,(int)($_POST['message_id']??0));
    $m=fetch_one('SELECT conversation_id,sender_id FROM messages WHERE id=? LIMIT 1',[$mid]);
    if(!$m || (int)$m['sender_id']!==$uid) mobile_error('Message not available.',403);
    $needed=(int)fetch_col('SELECT COUNT(*) FROM conversation_members WHERE conversation_id=? AND user_id<>?',[(int)$m['conversation_id'],$uid]);
    $got=(int)fetch_col('SELECT COUNT(*) FROM mobile_message_delivery WHERE message_id=?',[$mid]);
    mobile_out(['delivered'=>$needed>0 && $got>0,'delivered_count'=>$got,'recipient_count'=>$needed]);
}
if ($action === 'global_search') {
    $qv=trim((string)($_POST['q']??'')); if(mb_strlen($qv)<2) mobile_out(['results'=>[]]);
    $like='%'.$qv.'%'; $out=[];
    foreach(fetch_all("SELECT id,name,username,role,avatar FROM users WHERE status='active' AND deleted_at IS NULL AND searchable=1 AND (name LIKE ? OR username LIKE ?) ORDER BY is_verified DESC,last_seen DESC LIMIT 12",[$like,$like]) as $x){
      $out[]=['kind'=>'member','id'=>(int)$x['id'],'title'=>(string)$x['name'],'subtitle'=>'@'.(string)$x['username'].' · '.(string)$x['role'],'url'=>'profile.php?u='.rawurlencode((string)$x['username'])];
    }
    if(table_exists('conversations')) foreach(fetch_all("SELECT c.id,c.title FROM conversations c JOIN conversation_members cm ON cm.conversation_id=c.id WHERE cm.user_id=? AND c.type='group' AND c.title LIKE ? ORDER BY c.last_activity DESC LIMIT 10",[$uid,$like]) as $x){
      $out[]=['kind'=>'group','id'=>(int)$x['id'],'title'=>(string)$x['title'],'subtitle'=>'Study group','conversation_id'=>(int)$x['id'],'url'=>'chat.php?c='.(int)$x['id']];
    }
    if(table_exists('posts')) foreach(fetch_all("SELECT p.id,p.content,u.name FROM posts p JOIN users u ON u.id=p.user_id WHERE p.status='published' AND p.content LIKE ? ORDER BY p.id DESC LIMIT 10",[$like]) as $x){
      $out[]=['kind'=>'post','id'=>(int)$x['id'],'title'=>mb_substr(trim(strip_tags((string)$x['content'])),0,90),'subtitle'=>'Post by '.(string)$x['name'],'url'=>'feed.php?post='.(int)$x['id']];
    }
    if(table_exists('pages')) { try { foreach(fetch_all("SELECT id,title,slug FROM pages WHERE title LIKE ? ORDER BY id DESC LIMIT 8",[$like]) as $x){ $out[]=['kind'=>'page','id'=>(int)$x['id'],'title'=>(string)$x['title'],'subtitle'=>'Page','url'=>'page.php?slug='.rawurlencode((string)$x['slug'])]; } } catch(Throwable $e){} }
    mobile_out(['results'=>array_slice($out,0,36)]);
}
'''

for rel in ('backend/api/mobile.php', 'flutter/backend/api/mobile.php'):
    path = ROOT / rel
    text = path.read_text(encoding='utf-8')
    start = text.find(START)
    if start < 0:
        raise RuntimeError(f'v5.3 PHP block start missing in {rel}')
    end = text.find(NEXT, start)
    if end < 0:
        raise RuntimeError(f'v5.3 PHP block end anchor missing in {rel}')
    replacement = "\n/* v5.3 routes: global_search, ack_delivery, delivery_status, mobile_message_delivery */\nrequire_once __DIR__ . '/mobile_v53.php';\n"
    text = text[:start] + replacement + text[end:]
    path.write_text(text, encoding='utf-8')

for rel in ('backend/api/mobile_v53.php', 'flutter/backend/api/mobile_v53.php'):
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(MODULE, encoding='utf-8')

print('TaleemPK v5.3 mobile PHP actions moved to dedicated module')
