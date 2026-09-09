import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:http/http.dart' as http;

import 'models.dart';

class ApiException implements Exception {
  const ApiException(this.message, {this.status = 0});
  final String message;
  final int status;
  @override
  String toString() => message;
}

class AuthResult {
  const AuthResult({
    this.token,
    this.user,
    this.challenge,
    this.needsTwoFactor = false,
    this.message,
  });
  final String? token, challenge, message;
  final User? user;
  final bool needsTwoFactor;
}

class ApiClient {
  ApiClient({http.Client? httpClient}) : _http = httpClient ?? http.Client();

  static const endpoint = String.fromEnvironment(
    'STUDYHUB_API_URL',
    defaultValue: 'https://taleempk.online/api/mobile.php',
  );
  static final _storage = FlutterSecureStorage(aOptions: AndroidOptions());
  static const _tokenKey = 'taleempk_mobile_token';
  static const _legacyTokenKey = 'studyhub_mobile_token';
  final http.Client _http;
  String? _token;
  void Function(String message)? onSessionExpired;

  String? get token => _token;
  Map<String, String> get authHeaders =>
      _token == null ? const {} : {'Authorization': 'Bearer $_token'};

  Future<bool> restoreSession() async {
    _token = await _storage.read(key: _tokenKey);
    if (_token == null || _token!.isEmpty) {
      _token = await _storage.read(key: _legacyTokenKey);
      if (_token != null && _token!.isNotEmpty) {
        await _storage.write(key: _tokenKey, value: _token);
        await _storage.delete(key: _legacyTokenKey);
      }
    }
    return _token != null && _token!.isNotEmpty;
  }

  Future<void> saveToken(String value) async {
    _token = value;
    await _storage.write(key: _tokenKey, value: value);
  }

  Future<void> clearToken() async {
    _token = null;
    await _storage.delete(key: _tokenKey);
    await _storage.delete(key: _legacyTokenKey);
  }

  Future<Map<String, dynamic>> health() =>
      _request({'action': 'health'}, get: true, authenticated: false);

  Future<AuthResult> login(String identifier, String password) async {
    final data = await _request({
      'action': 'login',
      'identifier': identifier.trim(),
      'password': password,
      'device': '${Platform.operatingSystem} Flutter app',
    }, authenticated: false);
    return _authResult(data);
  }

  Future<AuthResult> verifyTwoFactor(String challenge, String code) async {
    final data = await _request({
      'action': 'verify_2fa',
      'challenge': challenge,
      'code': code.trim(),
      'device': '${Platform.operatingSystem} Flutter app',
    }, authenticated: false);
    return _authResult(data);
  }

  Future<String> forgotPassword(String email) async {
    final data = await _request({
      'action': 'forgot_password',
      'email': email.trim(),
    }, authenticated: false);
    return '${data['message'] ?? 'If that email exists, a password reset link has been sent.'}';
  }

  Future<String> register({
    required String role,
    required String name,
    required String username,
    required String email,
    required String phone,
    required String dob,
    required String password,
  }) async {
    final data = await _request({
      'action': 'register',
      'role': role,
      'name': name,
      'username': username,
      'email': email,
      'phone': phone,
      'dob': dob,
      'password': password,
    }, authenticated: false);
    return '${data['message'] ?? 'Account created successfully.'}';
  }

  Future<BootstrapData> bootstrap() async =>
      BootstrapData.fromJson(await _request({'action': 'bootstrap'}));

  Future<List<FeedPost>> feed({int page = 1}) async {
    final data = await _request({'action': 'feed', 'page': '$page'});
    return _list(data['posts']).map((e) => FeedPost.fromJson(_map(e))).toList();
  }

  Future<void> createPost(String content, {bool question = false}) => _request({
    'action': 'create_post',
    'content': content,
    'type': question ? 'question' : 'text',
    'visibility': 'public',
  });

  Future<void> togglePostLike(int id) =>
      _request({'action': 'react_post', 'target': 'post:$id', 'type': 'like'});

  Future<List<FeedComment>> comments(int postId) async {
    final data = await _request({
      'action': 'feed_comments',
      'post_id': '$postId',
    });
    return _list(data['comments'])
        .map((e) => FeedComment.fromJson(_map(e)))
        .toList();
  }

  Future<void> addComment(int postId, String content) => _request({
    'action': 'create_comment',
    'post_id': '$postId',
    'content': content,
  });

  Future<ModuleData> module(String key) async =>
      ModuleData.fromJson(await _request({'action': 'module', 'module': key}));
  Future<Map<String, dynamic>> moduleAction(String action, {int id = 0}) =>
      _request({'action': 'module_action', 'do': action, 'id': '$id'});

  Future<void> updateProfile(
    String name,
    String city,
    String headline,
    String bio,
  ) => _request({
    'action': 'update_profile',
    'name': name,
    'city': city,
    'headline': headline,
    'bio': bio,
  });

  Future<String> createTicket(String topic, String subject, String body) async {
    final data = await _request({
      'action': 'create_ticket',
      'topic': topic,
      'subject': subject,
      'body': body,
    });
    return '${data['message'] ?? 'Support request created.'}';
  }

  Future<List<Conversation>> conversations() async {
    final data = await _request({'action': 'conversations'});
    return _list(data['conversations'])
        .map((e) => Conversation.fromJson(_map(e)))
        .toList();
  }

  Future<List<ChatMessage>> messages(
    int conversationId, {
    int afterId = 0,
  }) async {
    final data = await _request({
      'action': 'messages',
      'conversation_id': '$conversationId',
      'after_id': '$afterId',
    });
    return _list(data['messages'])
        .map((e) => ChatMessage.fromJson(_map(e)))
        .toList();
  }

  Future<ChatPresence> presence(int conversationId, String kind) async =>
      ChatPresence.fromJson(
        await _request({
          'action': 'presence',
          'conversation_id': '$conversationId',
          'kind': kind,
        }),
      );

  Future<void> sendText(int conversationId, String text, {int? replyTo}) =>
      _request({
        'action': 'send',
        'conversation_id': '$conversationId',
        'content': text,
        'client_token': _clientToken(),
        if (replyTo != null) 'reply_to': '$replyTo',
      });

  Future<void> sendFile(
    int conversationId,
    String filePath, {
    String field = 'attachment',
    int voiceSeconds = 0,
    int? replyTo,
    void Function(double progress)? onProgress,
  }) async {
    final fields = <String, String>{
      'action': 'send',
      'conversation_id': '$conversationId',
      'content': '',
      'client_token': _clientToken(),
      if (voiceSeconds > 0) 'voice_seconds': '$voiceSeconds',
      if (replyTo != null) 'reply_to': '$replyTo',
    };
    await _multipart(fields, field, filePath, onProgress: onProgress);
  }

  Future<Uint8List> attachmentBytes(String url) async {
    if (_token == null || _token!.isEmpty) {
      throw const ApiException('Sign in to continue.', status: 401);
    }
    try {
      final source = Uri.parse(url);
      final id = source.queryParameters['id'];
      if (id == null || int.tryParse(id) == null) {
        throw const ApiException('This attachment link is invalid.');
      }
      final response = await _http
          .post(
            Uri.parse(endpoint),
            headers: authHeaders,
            body: {'action': 'file', 'id': id, 'access_token': _token!},
          )
          .timeout(const Duration(seconds: 45));
      if (response.statusCode == 401) {
        await _expireSession('Your session has expired. Please sign in again.');
        throw const ApiException(
          'Your session has expired. Please sign in again.',
          status: 401,
        );
      }
      if (response.statusCode < 200 || response.statusCode >= 300) {
        throw ApiException(
          response.statusCode == 404
              ? 'This attachment is no longer available.'
              : 'The attachment could not be downloaded.',
          status: response.statusCode,
        );
      }
      return response.bodyBytes;
    } on TimeoutException {
      throw const ApiException('The attachment download timed out.');
    } on SocketException {
      throw const ApiException('The connection was lost during download.');
    } on http.ClientException {
      throw const ApiException('Could not download the secure attachment.');
    }
  }

  Future<void> toggleConversationMute(int conversationId) => _request({
    'action': 'manage_chat',
    'id': '$conversationId',
    'do': 'toggle_mute',
  });

  Future<void> forwardMessage(int messageId, int conversationId) =>
      _request({
        'action': 'message_action',
        'do': 'forward',
        'id': '$messageId',
        'conversation_id': '$conversationId',
      });

  Future<void> react(int id, String emoji) =>
      _request({'action': 'reaction', 'message_id': '$id', 'emoji': emoji});
  Future<void> toggleStar(int id) =>
      _request({'action': 'star', 'message_id': '$id'});
  Future<void> togglePin(int id) =>
      _request({'action': 'pin', 'message_id': '$id'});
  Future<void> editMessage(int id, String content) => _request({
    'action': 'message_action',
    'do': 'edit',
    'id': '$id',
    'content': content,
  });
  Future<void> deleteMessage(int id, {required bool everyone}) => _request({
    'action': 'message_action',
    'do': 'delete',
    'ids': '$id',
    'scope': everyone ? 'all' : 'me',
  });

  Future<void> logout() async {
    try {
      if (_token != null) await _request({'action': 'logout'});
    } finally {
      await clearToken();
    }
  }

  Future<Map<String, dynamic>> _request(
    Map<String, String> fields, {
    bool authenticated = true,
    bool get = false,
  }) async {
    if (authenticated && (_token == null || _token!.isEmpty)) {
      throw const ApiException('Sign in to continue.', status: 401);
    }
    final requestFields = <String, String>{...fields};
    if (authenticated && _token != null) {
      requestFields['access_token'] = _token!;
    }
    try {
      final response = get
          ? await _http
                .get(
                  Uri.parse(endpoint).replace(queryParameters: requestFields),
                  headers: authHeaders,
                )
                .timeout(const Duration(seconds: 18))
          : await _http
                .post(
                  Uri.parse(endpoint),
                  headers: authHeaders,
                  body: requestFields,
                )
                .timeout(const Duration(seconds: 24));
      return await _decode(
        response.statusCode,
        response.bodyBytes,
        expireSessionOn401: authenticated,
      );
    } on TimeoutException {
      throw const ApiException(
        'The server took too long to respond. Check your connection and try again.',
      );
    } on SocketException {
      throw const ApiException(
        'You appear to be offline. Check your internet connection.',
      );
    } on http.ClientException {
      throw const ApiException('Could not connect securely to TaleemPK.');
    }
  }

  Future<Map<String, dynamic>> _multipart(
    Map<String, String> fields,
    String fileField,
    String filePath, {
    void Function(double progress)? onProgress,
  }) async {
    if (_token == null || _token!.isEmpty) {
      throw const ApiException('Sign in to continue.', status: 401);
    }
    final file = File(filePath);
    final length = await file.length();
    var sent = 0;
    final stream = file.openRead().transform<List<int>>(
      StreamTransformer<List<int>, List<int>>.fromHandlers(
        handleData: (chunk, sink) {
          sent += chunk.length;
          if (length > 0) onProgress?.call((sent / length).clamp(0, 1));
          sink.add(chunk);
        },
      ),
    );
    final request = http.MultipartRequest('POST', Uri.parse(endpoint))
      ..fields.addAll(fields)
      ..headers.addAll(authHeaders);
    request.fields['access_token'] = _token!;
    request.files.add(
      http.MultipartFile(
        fileField,
        http.ByteStream(stream),
        length,
        filename: filePath.split(Platform.pathSeparator).last,
      ),
    );
    try {
      final streamed = await _http
          .send(request)
          .timeout(const Duration(seconds: 90));
      final bytes = await streamed.stream.toBytes();
      return await _decode(
        streamed.statusCode,
        bytes,
        expireSessionOn401: true,
      );
    } on TimeoutException {
      throw const ApiException('Upload timed out. Please try again.');
    } on SocketException {
      throw const ApiException(
        'Upload stopped because the connection was lost.',
      );
    }
  }

  Future<Map<String, dynamic>> _decode(
    int status,
    List<int> bytes, {
    required bool expireSessionOn401,
  }) async {
    final raw = utf8.decode(bytes, allowMalformed: true)
        .replaceFirst('\uFEFF', '')
        .trim();

    Map<String, dynamic>? map;
    try {
      final decoded = jsonDecode(raw);
      map = _map(decoded);
    } catch (_) {
      // Shared hosting can prepend PHP warnings/banners or append a second
      // response even when the TaleemPK request itself succeeded. Mirror the
      // proven native Android parser and use the final valid API envelope.
      final envelopes = _extractJsonEnvelopes(raw);
      for (final candidate in envelopes.reversed) {
        if (candidate.containsKey('ok')) {
          map = candidate;
          break;
        }
      }
    }

    if (map == null || map.isEmpty) {
      throw ApiException(
        status >= 500
            ? 'TaleemPK is temporarily unavailable.'
            : status == 404
            ? 'The TaleemPK mobile service is not installed correctly.'
            : raw.isEmpty
            ? 'The server returned an empty response.'
            : 'The server returned an invalid response.',
        status: status,
      );
    }

    final message = '${map['error'] ?? 'Something went wrong.'}';
    final authFailure = status == 401 && _isSessionFailure(message);
    if (authFailure && expireSessionOn401) {
      await _expireSession(message);
    }
    if (status >= 400 || map['ok'] != true) {
      throw ApiException(message, status: status);
    }
    return _map(map['data']);
  }

  bool _isSessionFailure(String message) {
    final value = message.toLowerCase();
    return value.contains('session') ||
        value.contains('sign in') ||
        value.contains('token') ||
        value.contains('authentication') ||
        value.contains('unauthorized');
  }

  List<Map<String, dynamic>> _extractJsonEnvelopes(String raw) {
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
            final decoded = jsonDecode(raw.substring(start, i + 1));
            final candidate = _map(decoded);
            if (candidate.isNotEmpty) found.add(candidate);
          } catch (_) {}
          start = -1;
        }
      }
    }
    return found;
  }

  Future<void> _expireSession(String message) async {
    await clearToken();
    onSessionExpired?.call(message);
  }

  AuthResult _authResult(Map<String, dynamic> data) => AuthResult(
    token: _nullable(data['token']),
    user: data['user'] is Map ? User.fromJson(_map(data['user'])) : null,
    challenge: _nullable(data['challenge']),
    needsTwoFactor: data['needs_2fa'] == true,
    message: _nullable(data['message']),
  );

  String _clientToken() =>
      '${DateTime.now().microsecondsSinceEpoch}_${_token?.substring(0, 8) ?? 'guest'}';
}

Map<String, dynamic> _map(dynamic value) => value is Map<String, dynamic>
    ? value
    : value is Map
    ? value.cast<String, dynamic>()
    : <String, dynamic>{};
List<dynamic> _list(dynamic value) => value is List ? value : const [];
String? _nullable(dynamic value) =>
    value == null || '$value'.isEmpty ? null : '$value';
