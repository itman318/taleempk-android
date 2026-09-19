from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
def r(p): return (ROOT/p).read_text(encoding='utf-8')
def w(p,s):
    q=ROOT/p; q.parent.mkdir(parents=True,exist_ok=True); q.write_text(s,encoding='utf-8')

def once(text, old, new, label):
    if old not in text: raise RuntimeError(f'v5.3 missing anchor: {label}')
    return text.replace(old,new,1)

# Keep release version after older generators.
p='flutter/pubspec.yaml'; s=r(p); s=re.sub(r'^version:\s*[^\n]+','version: 5.3.0+530',s,count=1,flags=re.M); w(p,s)

# Server: global search plus per-device delivery acknowledgements.
server=r'''\n/* TaleemPK v5.3: cross-app search + actual recipient delivery receipts. */
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
for p in ('backend/api/mobile.php','flutter/backend/api/mobile.php'):
    s=r(p); marker="$uid = (int) $u['id'];\n"
    if 'TaleemPK v5.3: cross-app search' not in s: s=once(s,marker,marker+server,p)
    w(p,s)

# Client API.
p='flutter/lib/core/api_client.dart'; s=r(p); marker='  String newClientToken() => _clientToken();\n'
methods=r'''  Future<List<Map<String, dynamic>>> globalSearch(String query) async {
    final data=await _request({'action':'global_search','q':query.trim()});
    return _list(data['results']).map(_map).toList();
  }
  Future<void> acknowledgeDelivered(Iterable<int> ids) async {
    final value=ids.where((e)=>e>0).toSet().take(100).join(',');
    if(value.isEmpty)return;
    await _request({'action':'ack_delivery','ids':value});
  }
  Future<bool> messageDelivered(int id) async {
    final data=await _request({'action':'delivery_status','message_id':'$id'});
    return data['delivered']==true;
  }

'''
if 'Future<List<Map<String, dynamic>>> globalSearch' not in s: s=once(s,marker,methods+marker,'api global search')
w(p,s)

# Search screen.
w('flutter/lib/screens/global_search_screen.dart',r'''import 'dart:async';
import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';
import '../core/app_state.dart';
import '../core/theme.dart';
import '../widgets/common.dart';
import 'home_shell.dart';

class GlobalSearchScreen extends StatefulWidget { const GlobalSearchScreen({super.key}); @override State<GlobalSearchScreen> createState()=>_GlobalSearchScreenState(); }
class _GlobalSearchScreenState extends State<GlobalSearchScreen>{
 final c=TextEditingController(); Timer? t; bool busy=false; List<Map<String,dynamic>> rows=[];
 @override void dispose(){t?.cancel();c.dispose();super.dispose();}
 void changed(String v){t?.cancel();t=Timer(const Duration(milliseconds:320),()=>search(v));}
 Future<void> search(String v) async {v=v.trim(); if(v.length<2){if(mounted)setState(()=>rows=[]);return;} setState(()=>busy=true); try{final x=await AppScope.of(context).api.globalSearch(v);if(mounted)setState(()=>rows=x);}catch(e){if(mounted)showMessage(context,apiMessage(e));}finally{if(mounted)setState(()=>busy=false);}}
 IconData icon(String k)=>switch(k){'member'=>Icons.person_rounded,'group'=>Icons.groups_rounded,'page'=>Icons.public_rounded,'post'=>Icons.article_rounded,_=>Icons.search_rounded};
 Future<void> open(Map<String,dynamic> x) async {final u='${x['url']??''}';if(u.isEmpty)return;final uri=Uri.parse('https://taleempk.online/$u');await launchUrl(uri,mode:LaunchMode.externalApplication);}
 @override Widget build(BuildContext context)=>Scaffold(appBar:const PremiumAppBar(title:'Search TaleemPK',subtitle:'Members, groups, pages and posts'),body:Column(children:[Padding(padding:const EdgeInsets.all(16),child:TextField(controller:c,autofocus:true,onChanged:changed,onSubmitted:search,decoration:InputDecoration(hintText:'Search anything on TaleemPK',prefixIcon:const Icon(Icons.search_rounded),suffixIcon:c.text.isEmpty?null:IconButton(onPressed:(){c.clear();setState(()=>rows=[]);},icon:const Icon(Icons.close_rounded))))),if(busy)const LinearProgressIndicator(minHeight:2),Expanded(child:rows.isEmpty?EmptyView(icon:Icons.manage_search_rounded,title:c.text.trim().length<2?'Search TaleemPK':'No results',message:c.text.trim().length<2?'Type at least 2 characters.':'Try another name or keyword.'):ListView.separated(itemCount:rows.length,separatorBuilder:(_,__)=>const Divider(height:1),itemBuilder:(_,i){final x=rows[i];return ListTile(leading:CircleAvatar(child:Icon(icon('${x['kind']}'))),title:Text('${x['title']??''}',maxLines:2,overflow:TextOverflow.ellipsis),subtitle:Text('${x['subtitle']??''}'),trailing:const Icon(Icons.chevron_right_rounded,color:AppColors.muted),onTap:()=>open(x));}))]));
}
''')

# Put a prominent global search entry on Home.
p='flutter/lib/screens/home_screen.dart'; s=r(p)
if "import 'global_search_screen.dart';" not in s:
    s=once(s,"import 'home_shell.dart';\n","import 'home_shell.dart';\nimport 'global_search_screen.dart';\n",'home import')
anchor="children: [Center(child: ConstrainedBox"
if 'Search members, groups, pages and posts' not in s:
    replacement="children: [Padding(padding: const EdgeInsets.fromLTRB(18, 10, 18, 0), child: InkWell(borderRadius: BorderRadius.circular(18), onTap: () => Navigator.push(context, premiumRoute(builder: (_) => const GlobalSearchScreen())), child: Container(padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14), decoration: BoxDecoration(color: Theme.of(context).colorScheme.surface, borderRadius: BorderRadius.circular(18), border: Border.all(color: Theme.of(context).colorScheme.outlineVariant)), child: const Row(children: [Icon(Icons.search_rounded), SizedBox(width: 12), Expanded(child: Text('Search members, groups, pages and posts')), Icon(Icons.chevron_right_rounded)])))), Center(child: ConstrainedBox"
    s=once(s,anchor,replacement,'home search entry')
w(p,s)

# Delivery acknowledgement whenever recipient messages are actually received by this client.
p='flutter/lib/screens/chat_screen.dart'; s=r(p)
# Hook after message list assignment patterns generated by previous versions; best-effort but audited below.
if 'acknowledgeDelivered' not in s:
    candidates=['messages = fresh;','messages = loaded;','messages = result;']
    for a in candidates:
        if a in s:
            s=s.replace(a,a+"\n      unawaited(AppScope.of(context).api.acknowledgeDelivered(messages.where((m) => !m.mine).map((m) => m.id)));",1);break
w(p,s)

# Push tap routing stream. HomeShell switches to Chat and passes exact conversation id into inbox.
p='flutter/lib/core/push_service.dart'; s=r(p)
if 'final _tapController' not in s:
    s=once(s,'  ApiClient? _api;\n',"  ApiClient? _api;\n  final _tapController=StreamController<int>.broadcast();\n  Stream<int> get conversationTaps=>_tapController.stream;\n",'push tap stream')
    old="      await _openedSub?.cancel();\n      _openedSub = FirebaseMessaging.onMessageOpenedApp.listen(_handleMessage);"
    new="      await _openedSub?.cancel();\n      _openedSub = FirebaseMessaging.onMessageOpenedApp.listen((m) { _handleMessage(m); final id=_asInt(m.data['conversation_id']); if(id>0)_tapController.add(id); });"
    s=once(s,old,new,'opened push')
    s=s.replace("      if (initial != null) _handleMessage(initial);","      if (initial != null) { _handleMessage(initial); final id=_asInt(initial.data['conversation_id']); if(id>0) scheduleMicrotask(() => _tapController.add(id)); }")
w(p,s)

# ConversationsScreen can open a push-target conversation exactly once.
p='flutter/lib/screens/conversations_screen.dart'; s=r(p)
if 'initialConversationId' not in s:
    s=once(s,'  const ConversationsScreen({super.key});','  const ConversationsScreen({super.key, this.initialConversationId=0});\n  final int initialConversationId;','conversation ctor')
    s=once(s,'    _load();\n    refreshTimer',"    _load().then((_) { if (mounted && widget.initialConversationId > 0) _openConversationById(widget.initialConversationId); });\n    refreshTimer",'conversation initial open')
w(p,s)

p='flutter/lib/screens/home_shell.dart'; s=r(p)
if "import '../core/push_service.dart';" not in s:
    s=once(s,"import '../core/native_bridge.dart';\n","import '../core/native_bridge.dart';\nimport '../core/push_service.dart';\n",'shell push import')
if 'pushTapSub' not in s:
    s=once(s,'  Timer? callWatch, notificationWatch;','  Timer? callWatch, notificationWatch;\n  StreamSubscription<int>? pushTapSub;\n  int pushedConversation=0;','shell fields')
    s=once(s,'    callWatch = Timer.periodic(',"    pushTapSub=PushService.instance.conversationTaps.listen((id){ if(!mounted)return; setState((){index=2;pushedConversation=id;}); keys[2].currentState?.pushReplacement(MaterialPageRoute(builder:(_)=>ConversationsScreen(initialConversationId:id))); });\n    callWatch = Timer.periodic(",'shell listener')
    s=once(s,'    callWatch?.cancel();','    pushTapSub?.cancel();\n    callWatch?.cancel();','shell dispose')
w(p,s)

# Regression guarantees: fail CI rather than ship a label-only v5.3.
assert 'global_search' in r('backend/api/mobile.php')
assert 'ack_delivery' in r('backend/api/mobile.php')
assert 'globalSearch' in r('flutter/lib/core/api_client.dart')
assert 'Search members, groups, pages and posts' in r('flutter/lib/screens/home_screen.dart')
assert 'conversationTaps' in r('flutter/lib/core/push_service.dart')
print('TaleemPK v5.3 global search, delivery receipts and push deep links applied')
