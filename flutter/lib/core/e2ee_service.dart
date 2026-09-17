import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/services.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:http/http.dart' as http;

import 'api_client.dart';
import 'models.dart';

class E2eeThreadState {
  const E2eeThreadState({
    required this.state,
    this.epoch = 0,
    this.members = 0,
    this.withKeys = 0,
  });
  final String state; // on, off, locked, waiting, unavailable
  final int epoch, members, withKeys;
  bool get enabled => state == 'on';
  bool get locked => state == 'locked';
}

class E2eeFileResult {
  const E2eeFileResult({required this.path, required this.name, required this.mime});
  final String path, name, mime;
}

class E2eeService {
  E2eeService(this.api, this.userId, {http.Client? client}) : _http = client ?? http.Client();

  final ApiClient api;
  final int userId;
  final http.Client _http;
  static const _channel = MethodChannel('taleempk/e2ee');
  static const _storage = FlutterSecureStorage(aOptions: AndroidOptions());

  String? _privateKey;
  String? _publicKey;
  final Map<int, String> _peerPublic = <int, String>{};
  final Map<int, String> _pairwise = <int, String>{};
  final Map<String, String> _groupKeys = <String, String>{};

  String get _privateStorageKey => 'taleempk_e2ee_private_$userId';
  String get _publicStorageKey => 'taleempk_e2ee_public_$userId';
  bool get ready => (_privateKey?.isNotEmpty ?? false) && (_publicKey?.isNotEmpty ?? false);

  Uri get _endpoint {
    final base = Uri.parse(ApiClient.endpoint);
    final parts = [...base.pathSegments];
    if (parts.isNotEmpty) parts[parts.length - 1] = 'mobile_e2ee_v32.php';
    return base.replace(pathSegments: parts, query: null);
  }

  Future<bool> resume() async {
    _privateKey ??= await _storage.read(key: _privateStorageKey);
    _publicKey ??= await _storage.read(key: _publicStorageKey);
    return ready;
  }

  Future<bool> haveServerKey() async {
    final data = await _post('mine');
    final key = data['key'];
    return key is Map && '${key['wrapped_key'] ?? ''}'.isNotEmpty;
  }

  Future<void> setup(String passphrase) async {
    if (passphrase.length < 8) {
      throw const ApiException('Use at least 8 characters for your encryption passphrase.');
    }
    final pair = await _nativeMap('generateKeyPair');
    final privateKey = '${pair['private_key'] ?? ''}';
    final publicKey = '${pair['public_key'] ?? ''}';
    if (privateKey.isEmpty || publicKey.isEmpty) {
      throw const ApiException('The device could not create an encryption key.');
    }
    final wrapped = await _nativeMap('wrapPrivate', {
      'private_key': privateKey,
      'passphrase': passphrase,
    });
    await _post('publish', {
      'public_key': publicKey,
      'wrapped_key': '${wrapped['wrapped_key'] ?? ''}',
      'wrap_salt': '${wrapped['wrap_salt'] ?? ''}',
      'wrap_iv': '${wrapped['wrap_iv'] ?? ''}',
    });
    _privateKey = privateKey;
    _publicKey = publicKey;
    await _storage.write(key: _privateStorageKey, value: privateKey);
    await _storage.write(key: _publicStorageKey, value: publicKey);
    _clearDerived();
  }

  Future<void> unlock(String passphrase) async {
    final data = await _post('mine');
    final raw = data['key'];
    if (raw is! Map || '${raw['wrapped_key'] ?? ''}'.isEmpty) {
      throw const ApiException('No encryption key is stored for this account yet.');
    }
    try {
      final privateKey = await _channel.invokeMethod<String>('unwrapPrivate', {
        'wrapped_key': '${raw['wrapped_key']}',
        'wrap_salt': '${raw['wrap_salt']}',
        'wrap_iv': '${raw['wrap_iv']}',
        'passphrase': passphrase,
      });
      if (privateKey == null || privateKey.isEmpty) throw const FormatException();
      _privateKey = privateKey;
      _publicKey = '${raw['public_key'] ?? ''}';
      await _storage.write(key: _privateStorageKey, value: _privateKey);
      await _storage.write(key: _publicStorageKey, value: _publicKey);
      _clearDerived();
    } catch (_) {
      throw const ApiException('That encryption passphrase is not correct.');
    }
  }

  Future<void> forgetDevice() async {
    _privateKey = null;
    _publicKey = null;
    _clearDerived();
    await _storage.delete(key: _privateStorageKey);
    await _storage.delete(key: _publicStorageKey);
  }

  void _clearDerived() {
    _peerPublic.clear();
    _pairwise.clear();
    _groupKeys.clear();
  }

  Future<E2eeThreadState> prepareThread(Conversation conversation) async {
    await resume();
    if (conversation.isGroup) {
      final state = await _groupState(conversation.id);
      final epoch = _int(state['epoch']);
      final members = _int(state['members']);
      final withKeys = _int(state['with_keys']);
      if (!ready) {
        return E2eeThreadState(
          state: await haveServerKey() ? 'locked' : 'off',
          epoch: epoch,
          members: members,
          withKeys: withKeys,
        );
      }
      if (epoch < 1) {
        return E2eeThreadState(state: 'off', epoch: 0, members: members, withKeys: withKeys);
      }
      try {
        await _groupResume(conversation.id, state);
        return E2eeThreadState(state: 'on', epoch: epoch, members: members, withKeys: withKeys);
      } on ApiException catch (e) {
        final waiting = e.message.contains('waiting') || e.message.contains('key copy');
        return E2eeThreadState(state: waiting ? 'waiting' : 'unavailable', epoch: epoch, members: members, withKeys: withKeys);
      }
    }

    final mine = ready || await haveServerKey();
    if (!ready) return E2eeThreadState(state: mine ? 'locked' : 'off');
    if (conversation.otherId <= 0) return const E2eeThreadState(state: 'unavailable');
    final theirs = await peerHasKey(conversation.otherId);
    return E2eeThreadState(state: theirs ? 'on' : 'waiting');
  }

  Future<bool> peerHasKey(int peerId) async {
    if (_peerPublic[peerId]?.isNotEmpty == true) return true;
    final data = await _post('peer', {'user_id': '$peerId'});
    final key = '${data['public_key'] ?? ''}';
    if (key.isNotEmpty) _peerPublic[peerId] = key;
    return key.isNotEmpty;
  }

  Future<String> safetyNumber(Conversation conversation) async {
    await resume();
    if (!ready || conversation.isGroup || conversation.otherId <= 0) {
      throw const ApiException('Safety number is available for unlocked private chats.');
    }
    await _peerKey(conversation.otherId);
    final value = await _channel.invokeMethod<String>('fingerprint', {
      'public_a': _publicKey,
      'public_b': _peerPublic[conversation.otherId],
    });
    return value ?? '';
  }

  Future<void> enableGroup(int conversationId) async {
    await resume();
    if (!ready) throw const ApiException('Unlock your encryption key first.');
    final state = await _groupState(conversationId);
    if (_int(state['epoch']) > 0) return;
    final needs = _mapList(state['needs']);
    if (needs.length < 2) {
      throw const ApiException('At least two group members must set up encryption first.');
    }
    await _groupMint(conversationId, 1, state);
  }

  Future<String> encryptText(Conversation conversation, String text) async {
    await resume();
    if (!ready) throw const ApiException('Unlock encryption before sending.');
    if (conversation.isGroup) {
      final state = await _groupState(conversation.id);
      final epoch = _int(state['epoch']);
      if (epoch < 1) throw const ApiException('Turn on encryption for this group first.');
      final key = await _groupKeyFor(conversation.id, epoch, state);
      final packet = await _sealText(key, text);
      final parts = packet.split('.');
      if (parts.length != 3) throw const ApiException('Encryption failed.');
      return 'g1.$epoch.${parts[1]}.${parts[2]}';
    }
    final key = await _peerKey(conversation.otherId);
    return _sealText(key, text);
  }

  Future<String> decryptText(Conversation conversation, ChatMessage message) async {
    await resume();
    if (!ready) throw const ApiException('Unlock your encryption key to read this message.');
    final packet = message.ciphertext;
    if (packet.isEmpty) throw const ApiException('This encrypted message has no payload.');
    if (packet.startsWith('g1.')) {
      final parts = packet.split('.');
      if (parts.length != 4) throw const ApiException('Encrypted message format is invalid.');
      final epoch = int.tryParse(parts[1]) ?? 0;
      final key = await _groupKeyFor(conversation.id, epoch);
      return _openText(key, '1.${parts[2]}.${parts[3]}');
    }
    final peerId = message.mine ? conversation.otherId : message.senderId;
    final key = await _peerKey(peerId);
    return _openText(key, packet);
  }

  Future<E2eeFileResult> encryptFile(
    Conversation conversation,
    String inputPath, {
    required String originalName,
    required String mime,
  }) async {
    await resume();
    if (!ready) throw const ApiException('Unlock encryption before sending files.');
    String key;
    if (conversation.isGroup) {
      final state = await _groupState(conversation.id);
      final epoch = _int(state['epoch']);
      if (epoch < 1) throw const ApiException('Turn on encryption for this group first.');
      key = await _groupKeyFor(conversation.id, epoch, state);
    } else {
      key = await _peerKey(conversation.otherId);
    }
    final out = await _nativeMap('sealFile', {
      'key': key,
      'path': inputPath,
      'name': originalName,
      'mime': mime,
    });
    return E2eeFileResult(
      path: '${out['path'] ?? ''}',
      name: 'a.bin',
      mime: 'application/octet-stream',
    );
  }

  Future<E2eeFileResult> decryptFile(
    Conversation conversation,
    ChatMessage message,
    String encryptedPath,
  ) async {
    await resume();
    if (!ready) throw const ApiException('Unlock your encryption key to open this file.');
    String key;
    final packet = message.ciphertext;
    if (packet.startsWith('g1.')) {
      final parts = packet.split('.');
      final epoch = parts.length > 1 ? int.tryParse(parts[1]) ?? 0 : 0;
      key = await _groupKeyFor(conversation.id, epoch);
    } else if (conversation.isGroup) {
      final state = await _groupState(conversation.id);
      key = await _groupKeyFor(conversation.id, _int(state['epoch']), state);
    } else {
      final peerId = message.mine ? conversation.otherId : message.senderId;
      key = await _peerKey(peerId);
    }
    final out = await _nativeMap('openFile', {'key': key, 'path': encryptedPath});
    return E2eeFileResult(
      path: '${out['path'] ?? ''}',
      name: '${out['name'] ?? 'file'}',
      mime: '${out['mime'] ?? 'application/octet-stream'}',
    );
  }

  Future<String> _peerKey(int peerId) async {
    if (peerId <= 0) throw const ApiException('Encryption peer is unavailable.');
    final cached = _pairwise[peerId];
    if (cached != null) return cached;
    await resume();
    if (!ready) throw const ApiException('Unlock your encryption key first.');
    if (!await peerHasKey(peerId)) {
      throw const ApiException('The other person has not set up encryption yet.');
    }
    final key = await _channel.invokeMethod<String>('deriveShared', {
      'private_key': _privateKey,
      'public_key': _peerPublic[peerId],
    });
    if (key == null || key.isEmpty) throw const ApiException('Could not derive the chat key.');
    _pairwise[peerId] = key;
    return key;
  }

  Future<String> _sealText(String key, String text) async {
    final packet = await _channel.invokeMethod<String>('sealText', {'key': key, 'text': text});
    if (packet == null || packet.isEmpty) throw const ApiException('Could not encrypt the message.');
    return packet;
  }

  Future<String> _openText(String key, String packet) async {
    try {
      final plain = await _channel.invokeMethod<String>('openText', {'key': key, 'packet': packet});
      if (plain == null) throw const FormatException();
      return plain;
    } catch (_) {
      throw const ApiException('This message could not be opened with your current encryption key.');
    }
  }

  Future<Map<String, dynamic>> _groupState(int cid) => _post('group_state', {'conversation_id': '$cid'});

  Future<String> _groupKeyFor(int cid, int epoch, [Map<String, dynamic>? supplied]) async {
    if (epoch < 1) throw const ApiException('No group encryption key exists yet.');
    final tag = '$cid:$epoch';
    final cached = _groupKeys[tag];
    if (cached != null) return cached;
    final state = supplied ?? await _groupState(cid);
    final mine = _mapList(state['my_keys']).where((row) => _int(row['epoch']) == epoch).toList();
    if (mine.isEmpty) throw const ApiException('Waiting for a group encryption key copy.');
    final row = mine.first;
    final sealer = _int(row['sealed_by']);
    final pub = '${row['sealer_public'] ?? ''}';
    if (sealer <= 0 || pub.isEmpty) throw const ApiException('The group key sealer is unavailable.');
    _peerPublic[sealer] = pub;
    final pairwise = await _peerKey(sealer);
    try {
      final raw = await _channel.invokeMethod<String>('openRawKey', {
        'key': pairwise,
        'packet': '${row['wrapped_key'] ?? ''}',
      });
      if (raw == null || raw.isEmpty) throw const FormatException();
      _groupKeys[tag] = raw;
      return raw;
    } catch (_) {
      throw const ApiException('The group encryption key could not be opened.');
    }
  }

  Future<void> _groupResume(int cid, Map<String, dynamic> state) async {
    final epoch = _int(state['epoch']);
    try {
      final key = await _groupKeyFor(cid, epoch, state);
      await _groupShare(cid, epoch, _mapList(state['needs']), key);
      return;
    } on ApiException {
      final needs = _mapList(state['needs']);
      final withKeys = _int(state['with_keys']);
      final wasHere = _mapList(state['my_keys']).isNotEmpty;
      final nobodyHas = withKeys > 0 && needs.length >= withKeys;
      if (nobodyHas && wasHere) {
        await _groupMint(cid, epoch, state);
        return;
      }
      throw const ApiException('Waiting for another member to share the group key copy.');
    }
  }

  Future<String> _randomKey() async {
    final value = await _channel.invokeMethod<String>('randomKey');
    if (value == null || value.isEmpty) throw const ApiException('Could not create a group key.');
    return value;
  }

  Future<String> _sealRawFor(String publicKey, String rawKey) async {
    final pairwise = await _channel.invokeMethod<String>('deriveShared', {
      'private_key': _privateKey,
      'public_key': publicKey,
    });
    if (pairwise == null || pairwise.isEmpty) throw const ApiException('Could not derive a member key.');
    final packet = await _channel.invokeMethod<String>('sealRawKey', {
      'key': pairwise,
      'raw_key': rawKey,
    });
    if (packet == null || packet.isEmpty) throw const ApiException('Could not seal the group key.');
    return packet;
  }

  Future<void> _groupShare(int cid, int epoch, List<Map<String, dynamic>> needs, String rawKey) async {
    if (needs.isEmpty) return;
    final entries = <Map<String, dynamic>>[];
    for (final row in needs) {
      final id = _int(row['user_id']);
      final pub = '${row['public_key'] ?? ''}';
      if (id <= 0 || pub.isEmpty) continue;
      try {
        entries.add({'user_id': id, 'wrapped_key': await _sealRawFor(pub, rawKey)});
      } catch (_) {}
    }
    if (entries.isEmpty) return;
    await _post('group_put', {
      'conversation_id': '$cid',
      'epoch': '$epoch',
      'entries': jsonEncode(entries),
    });
  }

  Future<void> _groupMint(int cid, int epoch, Map<String, dynamic> state) async {
    final needs = _mapList(state['needs']);
    final me = needs.where((row) => _int(row['user_id']) == userId).toList();
    if (me.isEmpty || '${me.first['public_key'] ?? ''}'.isEmpty) {
      throw const ApiException('Your account public key is missing from this group.');
    }
    final raw = await _randomKey();
    final selfPacket = await _sealRawFor('${me.first['public_key']}', raw);
    final first = await _post('group_put', {
      'conversation_id': '$cid',
      'epoch': '$epoch',
      'entries': jsonEncode([{'user_id': userId, 'wrapped_key': selfPacket}]),
    });
    final owner = _int(first['owner']);
    if (_int(first['stored']) == 0 || (owner > 0 && owner != userId)) {
      _groupKeys.remove('$cid:$epoch');
      throw const ApiException('Another member created the group key first; refresh the chat.');
    }
    _groupKeys['$cid:$epoch'] = raw;
    await _groupShare(cid, epoch, needs.where((row) => _int(row['user_id']) != userId).toList(), raw);
  }

  Future<Map<String, dynamic>> _post(String action, [Map<String, String> extra = const {}]) async {
    final token = api.token;
    if (token == null || token.isEmpty) throw const ApiException('Sign in to continue.', status: 401);
    try {
      final response = await _http.post(
        _endpoint,
        headers: api.authHeaders,
        body: {'action': action, 'access_token': token, ...extra},
      ).timeout(const Duration(seconds: 28));
      final raw = utf8.decode(response.bodyBytes, allowMalformed: true).replaceFirst('\uFEFF', '').trim();
      final decoded = jsonDecode(raw);
      final map = decoded is Map ? decoded.cast<String, dynamic>() : <String, dynamic>{};
      if (response.statusCode == 401) {
        await api.clearToken();
        api.onSessionExpired?.call('${map['error'] ?? 'Your session has expired.'}');
      }
      if (response.statusCode >= 400 || map['ok'] != true) {
        throw ApiException('${map['error'] ?? 'Encryption service error.'}', status: response.statusCode);
      }
      if (map['data'] is Map) return (map['data'] as Map).cast<String, dynamic>();
      return <String, dynamic>{...map}..remove('ok');
    } on ApiException {
      rethrow;
    } on TimeoutException {
      throw const ApiException('The encryption service took too long to respond.');
    } on SocketException {
      throw const ApiException('You appear to be offline.');
    } catch (_) {
      throw const ApiException('The encryption service returned an invalid response.');
    }
  }

  Future<Map<String, dynamic>> _nativeMap(String method, [Map<String, dynamic>? args]) async {
    final value = await _channel.invokeMethod<dynamic>(method, args);
    return value is Map ? value.cast<String, dynamic>() : <String, dynamic>{};
  }

  static int _int(dynamic value) => value is int ? value : int.tryParse('$value') ?? 0;
  static List<Map<String, dynamic>> _mapList(dynamic value) => value is List
      ? value.whereType<Map>().map((row) => row.cast<String, dynamic>()).toList()
      : <Map<String, dynamic>>[];
}
