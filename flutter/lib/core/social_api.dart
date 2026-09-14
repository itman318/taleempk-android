import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:http/http.dart' as http;

import 'api_client.dart';
import 'social_models.dart';

class SocialApi {
  SocialApi(this.api, {http.Client? client}) : _http = client ?? http.Client();
  final ApiClient api;
  final http.Client _http;

  static final Map<String, _CachedProfile> _profiles = {};

  Future<SocialFeedPage> feed({
    String tab = 'latest',
    String subject = '',
    int before = 0,
    int limit = 15,
  }) async =>
      SocialFeedPage.fromJson(await _request({
        'action': 'feed_v2',
        'tab': tab,
        'subject': subject,
        'before': '$before',
        'limit': '$limit',
      }));

  Future<void> createPost({
    required String content,
    required String type,
    required String visibility,
    String subject = '',
    bool anonymous = false,
    List<String> files = const [],
    void Function(double progress)? onProgress,
  }) async {
    final fields = <String, String>{
      'action': 'create_post',
      'content': content,
      'type': type,
      'visibility': visibility,
      'subject': subject,
      if (anonymous && type == 'question') 'anonymous': '1',
    };
    if (files.isEmpty) {
      await _request(fields);
    } else {
      await _multipart(fields, {'files[]': files.take(4).toList()}, onProgress: onProgress);
    }
  }

  Future<Map<String, dynamic>> reactPost(int id, String type) => _request({
        'action': 'react_post',
        'target': 'post:$id',
        'type': type,
      });

  Future<Map<String, dynamic>> toggleSave(int id) =>
      _request({'action': 'save_post', 'post_id': '$id'});

  Future<Map<String, dynamic>> toggleRepost(int id) =>
      _request({'action': 'repost_post', 'post_id': '$id'});

  Future<void> editPost(int id, String content, {String subject = ''}) => _request({
        'action': 'edit_post',
        'post_id': '$id',
        'content': content,
        'subject': subject,
      });

  Future<void> deletePost(int id) =>
      _request({'action': 'delete_post', 'post_id': '$id'});

  Future<ProfileData> profile({String username = '', int userId = 0, bool refresh = false}) async {
    final key = username.isNotEmpty ? 'u:$username' : 'i:$userId';
    final cached = _profiles[key];
    if (!refresh && cached != null && DateTime.now().difference(cached.at).inMinutes < 3) {
      return cached.value;
    }
    final data = await _request({
      'action': 'profile_get',
      if (username.isNotEmpty) 'username': username,
      if (userId > 0) 'user_id': '$userId',
    });
    final value = ProfileData.fromJson(smMap(data['profile']));
    _profiles[key] = _CachedProfile(value, DateTime.now());
    _profiles['i:${value.id}'] = _CachedProfile(value, DateTime.now());
    if (value.username.isNotEmpty) _profiles['u:${value.username}'] = _CachedProfile(value, DateTime.now());
    return value;
  }

  Future<ProfileActivityPage> profileActivity(
    int userId,
    String kind, {
    int before = 0,
    int limit = 15,
  }) async =>
      ProfileActivityPage.fromJson(await _request({
        'action': 'profile_activity',
        'user_id': '$userId',
        'kind': kind,
        'before': '$before',
        'limit': '$limit',
      }));

  Future<bool> toggleFollow(int userId) async {
    final data = await _request({'action': 'profile_follow', 'user_id': '$userId'});
    _profiles.clear();
    return smBool(data['following']);
  }

  Future<void> updateProfile({
    required Map<String, String> fields,
    String? avatarPath,
    String? coverPath,
  }) async {
    final request = <String, String>{'action': 'profile_update_v2', ...fields};
    final files = <String, List<String>>{};
    if (avatarPath != null && avatarPath.isNotEmpty) files['avatar'] = [avatarPath];
    if (coverPath != null && coverPath.isNotEmpty) files['cover'] = [coverPath];
    if (files.isEmpty) {
      await _request(request);
    } else {
      await _multipart(request, files);
    }
    _profiles.clear();
  }

  Future<VerificationState> verificationStatus() async =>
      VerificationState.fromJson(await _request({'action': 'verification_status'}));

  Future<String> submitVerification({
    required Map<String, String> fields,
    String? idDocument,
    String? proofDocument,
    String? extraDocument,
    void Function(double progress)? onProgress,
  }) async {
    final files = <String, List<String>>{};
    if (idDocument != null && idDocument.isNotEmpty) files['doc_id'] = [idDocument];
    if (proofDocument != null && proofDocument.isNotEmpty) files['doc_proof'] = [proofDocument];
    if (extraDocument != null && extraDocument.isNotEmpty) files['doc_extra'] = [extraDocument];
    final data = await _multipart(
      {'action': 'verification_apply', ...fields, 'declaration': '1'},
      files,
      onProgress: onProgress,
    );
    _profiles.clear();
    return '${data['message'] ?? 'Your verification application was submitted.'}';
  }

  Future<String> withdrawVerification() async {
    final data = await _request({'action': 'verification_withdraw'});
    return '${data['message'] ?? 'Your verification application was withdrawn.'}';
  }

  Future<Map<String, dynamic>> _request(Map<String, String> fields) async {
    _requireToken();
    final body = <String, String>{...fields, 'access_token': api.token!};
    try {
      final response = await _http
          .post(_endpoint, headers: api.authHeaders, body: body)
          .timeout(const Duration(seconds: 28));
      return _decode(response.statusCode, response.bodyBytes);
    } on TimeoutException {
      throw const ApiException('The server took too long to respond. Please try again.');
    } on SocketException {
      throw const ApiException('You appear to be offline. Check your internet connection.');
    } on http.ClientException {
      throw const ApiException('Could not connect securely to TaleemPK.');
    }
  }

  Future<Map<String, dynamic>> _multipart(
    Map<String, String> fields,
    Map<String, List<String>> files, {
    void Function(double progress)? onProgress,
  }) async {
    _requireToken();
    final request = http.MultipartRequest('POST', _endpoint)
      ..headers.addAll(api.authHeaders)
      ..fields.addAll({...fields, 'access_token': api.token!});

    var total = 0;
    for (final paths in files.values) {
      for (final path in paths) {
        if (path.isNotEmpty) total += await File(path).length();
      }
    }
    var loaded = 0;
    for (final entry in files.entries) {
      for (final path in entry.value) {
        if (path.isEmpty) continue;
        final file = File(path);
        final length = await file.length();
        final stream = file.openRead().transform<List<int>>(
          StreamTransformer<List<int>, List<int>>.fromHandlers(
            handleData: (chunk, sink) {
              loaded += chunk.length;
              if (total > 0) onProgress?.call((loaded / total).clamp(0, 1).toDouble());
              sink.add(chunk);
            },
          ),
        );
        request.files.add(http.MultipartFile(
          entry.key,
          http.ByteStream(stream),
          length,
          filename: path.split(Platform.pathSeparator).last,
        ));
      }
    }
    try {
      final streamed = await _http.send(request).timeout(const Duration(seconds: 120));
      final bytes = await streamed.stream.toBytes();
      return _decode(streamed.statusCode, bytes);
    } on TimeoutException {
      throw const ApiException('Upload timed out. Please try again.');
    } on SocketException {
      throw const ApiException('Upload stopped because the connection was lost.');
    }
  }

  Uri get _endpoint {
    final base = Uri.parse(ApiClient.endpoint);
    final parts = [...base.pathSegments];
    if (parts.isEmpty) return base;
    parts[parts.length - 1] = 'mobile_social_v31.php';
    return base.replace(pathSegments: parts, query: null);
  }

  void _requireToken() {
    if (api.token == null || api.token!.isEmpty) {
      throw const ApiException('Sign in to continue.', status: 401);
    }
  }

  Map<String, dynamic> _decode(int status, List<int> bytes) {
    final raw = utf8.decode(bytes, allowMalformed: true).replaceFirst('\uFEFF', '').trim();
    Map<String, dynamic>? envelope;
    try {
      final decoded = jsonDecode(raw);
      envelope = smMap(decoded);
    } catch (_) {
      final candidates = _extract(raw);
      for (final candidate in candidates.reversed) {
        if (candidate.containsKey('ok')) {
          envelope = candidate;
          break;
        }
      }
    }
    if (envelope == null || envelope.isEmpty) {
      throw ApiException(
        status >= 500 ? 'TaleemPK is temporarily unavailable.' : 'The server returned an invalid response.',
        status: status,
      );
    }
    final message = '${envelope['error'] ?? 'Something went wrong.'}';
    if (status == 401) {
      unawaited(api.clearToken());
      api.onSessionExpired?.call(message);
    }
    if (status >= 400 || envelope['ok'] != true) throw ApiException(message, status: status);
    if (envelope['data'] is Map) return smMap(envelope['data']);
    return <String, dynamic>{...envelope}..remove('ok');
  }

  List<Map<String, dynamic>> _extract(String raw) {
    final found = <Map<String, dynamic>>[];
    var start = -1, depth = 0;
    var quoted = false, escaped = false;
    for (var i = 0; i < raw.length; i++) {
      final ch = raw[i];
      if (start < 0) {
        if (ch == '{') {
          start = i;
          depth = 1;
        }
        continue;
      }
      if (quoted) {
        if (escaped) {
          escaped = false;
        } else if (ch == '\\') {
          escaped = true;
        } else if (ch == '"') {
          quoted = false;
        }
        continue;
      }
      if (ch == '"') {
        quoted = true;
      } else if (ch == '{') {
        depth++;
      } else if (ch == '}') {
        depth--;
        if (depth == 0) {
          try {
            final value = smMap(jsonDecode(raw.substring(start, i + 1)));
            if (value.isNotEmpty) found.add(value);
          } catch (_) {}
          start = -1;
        }
      }
    }
    return found;
  }
}

class _CachedProfile {
  const _CachedProfile(this.value, this.at);
  final ProfileData value;
  final DateTime at;
}
