import 'dart:async';

import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';

import 'api_client.dart';
import 'realtime_service.dart';

class PushService {
  PushService._();
  static final PushService instance = PushService._();

  StreamSubscription<String>? _tokenSub;
  StreamSubscription<RemoteMessage>? _foregroundSub;
  StreamSubscription<RemoteMessage>? _openedSub;
  ApiClient? _api;
  String? _registeredToken;
  bool _binding = false;
  bool _firebaseReady = false;

  Future<void> bind(ApiClient api) async {
    if (_binding) return;
    _binding = true;
    try {
      _api = api;
      final config = await api.pushConfig();
      if (config['enabled'] != true) return;

      if (!_firebaseReady) {
        final options = FirebaseOptions(
          apiKey: '${config['api_key'] ?? ''}',
          appId: '${config['app_id'] ?? ''}',
          messagingSenderId: '${config['sender_id'] ?? ''}',
          projectId: '${config['project_id'] ?? ''}',
        );
        if (options.apiKey.isEmpty ||
            options.appId.isEmpty ||
            options.messagingSenderId.isEmpty ||
            options.projectId.isEmpty) {
          return;
        }
        if (Firebase.apps.isEmpty) {
          await Firebase.initializeApp(options: options);
        }
        _firebaseReady = true;
      }

      final messaging = FirebaseMessaging.instance;
      await messaging.requestPermission(
        alert: true,
        badge: true,
        sound: true,
        provisional: false,
      );

      final token = await messaging.getToken();
      if (token != null && token.isNotEmpty) {
        _registeredToken = token;
        await api.registerPushToken(token);
      }

      await _tokenSub?.cancel();
      _tokenSub = messaging.onTokenRefresh.listen((token) async {
        _registeredToken = token;
        final bound = _api;
        if (bound == null || token.isEmpty) return;
        try {
          await bound.registerPushToken(token);
        } catch (_) {}
      });

      await _foregroundSub?.cancel();
      _foregroundSub = FirebaseMessaging.onMessage.listen(_handleMessage);

      await _openedSub?.cancel();
      _openedSub = FirebaseMessaging.onMessageOpenedApp.listen(_handleMessage);

      final initial = await messaging.getInitialMessage();
      if (initial != null) _handleMessage(initial);
    } catch (_) {
      // Push is optional and must never make account access fail.
    } finally {
      _binding = false;
    }
  }

  void _handleMessage(RemoteMessage message) {
    final conversationId = _asInt(message.data['conversation_id']);
    if (conversationId <= 0) return;
    RealtimeService.instance.inject(
      conversationId,
      type: '${message.data['event'] ?? 'message'}',
      messageId: _asInt(message.data['message_id']),
      fromPush: true,
    );
  }

  Future<void> unbind(ApiClient api) async {
    final token = _registeredToken;
    _api = null;
    _registeredToken = null;
    if (token != null && token.isNotEmpty) {
      try {
        await api.unregisterPushToken(token);
      } catch (_) {}
    }
    detach();
  }

  void detach() {
    _api = null;
    _tokenSub?.cancel();
    _tokenSub = null;
    _foregroundSub?.cancel();
    _foregroundSub = null;
    _openedSub?.cancel();
    _openedSub = null;
  }

  static int _asInt(dynamic value) =>
      value is int ? value : int.tryParse('$value') ?? 0;
}
