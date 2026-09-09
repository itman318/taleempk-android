import 'dart:async';
import 'dart:convert';
import 'dart:io';

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
  static const _tokenKey = 'studyhub_mobile_token';
  final http.Client _http;
  String? _token;

  String? get token => _token;
  Map<String, String> get authHeaders =>
      _token == null ? const {} : {'Authorization': 'Bearer $_token'};

  Future<bool> restoreSession() async {
    _token = await _storage.read(key: _tokenKey);
    return _token != null && _token!.isNotEmpty;
  }

  Future<void> saveToken(String value) async {
    _token = value;
    await _storage.write(key: _tokenKey, value: value);
  }

  Future<void> clearToken() async {
    _token = null;
    await _storage.delete(key: _tokenKey);
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
  }) async {
    final fields = <String, String>{
      'action': 'send',
      'conversation_id': '$conversationId',
      'content': '',
      'client_token': _clientToken(),
      if (voiceSeconds > 0) 'voice_seconds': '$voiceSeconds',
      if (replyTo != null) 'reply_to': '$replyTo',
    };
    await _multipart(fields, field, filePath);
  }

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
    if (authenticated && (_token == null || _token!.isEmpty))
      throw const ApiException('Sign in to continue.', status: 401);
    try {
      final response = get
          ? await _http
                .get(
                  Uri.parse(endpoint).replace(queryParameters: fields),
                  headers: authHeaders,
                )
                .timeout(const Duration(seconds: 18))
          : await _http
                .post(Uri.parse(endpoint), headers: authHeaders, body: fields)
                .timeout(const Duration(seconds: 24));
      return _decode(response.statusCode, response.bodyBytes);
    } on TimeoutException {
      throw const ApiException(
        'The server took too long to respond. Check your connection and try again.',
      );
    } on SocketException {
      throw const ApiException(
        'You appear to be offline. Check your internet connection.',
      );
    } on http.ClientException {
      throw const ApiException('Could not connect securely to StudyHub.');
    }
  }

  Future<Map<String, dynamic>> _multipart(
    Map<String, String> fields,
    String fileField,
    String filePath,
  ) async {
    final request = http.MultipartRequest('POST', Uri.parse(endpoint))
      ..fields.addAll(fields)
      ..headers.addAll(authHeaders);
    request.files.add(await http.MultipartFile.fromPath(fileField, filePath));
    try {
      final streamed = await _http
          .send(request)
          .timeout(const Duration(seconds: 90));
      final bytes = await streamed.stream.toBytes();
      return _decode(streamed.statusCode, bytes);
    } on TimeoutException {
      throw const ApiException('Upload timed out. Please try again.');
    } on SocketException {
      throw const ApiException(
        'Upload stopped because the connection was lost.',
      );
    }
  }

  Map<String, dynamic> _decode(int status, List<int> bytes) {
    dynamic root;
    try {
      root = jsonDecode(utf8.decode(bytes));
    } catch (_) {
      throw ApiException(
        status >= 500
            ? 'StudyHub is temporarily unavailable.'
            : 'The server returned an invalid response.',
        status: status,
      );
    }
    final map = _map(root);
    if (status == 401) clearToken();
    if (status >= 400 || map['ok'] != true)
      throw ApiException(
        '${map['error'] ?? 'Something went wrong.'}',
        status: status,
      );
    return _map(map['data']);
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
