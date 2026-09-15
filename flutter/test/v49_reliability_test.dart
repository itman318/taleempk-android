import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:studyhub_flutter/core/api_client.dart';
import 'package:studyhub_flutter/core/app_state.dart';
import 'package:studyhub_flutter/core/outbox.dart';
import 'package:studyhub_flutter/core/social_api.dart';
import 'package:studyhub_flutter/widgets/profile_identity.dart';
import 'package:studyhub_flutter/widgets/common.dart';
import 'package:studyhub_flutter/screens/security_screen.dart';

class SessionClient extends ApiClient {
  String? session = 'viewer-a';
  @override
  String? get token => session;
  @override
  Map<String, String> get authHeaders => {'Accept': 'application/json'};
  @override
  Future<void> clearToken() async => session = null;
}

class SecurityClient extends ApiClient {
  @override
  Future<Map<String, dynamic>> securitySnapshot() async => {
    'settings': <String, dynamic>{}, 'sessions': <Map<String, dynamic>>[],
  };
  @override
  Future<List<Map<String, dynamic>>> blockedUsers() async => [
    {'id': 5, 'name': 'Blocked member', 'username': 'blocked_member'},
  ];
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() {
    SharedPreferences.setMockInitialValues({});
    FlutterSecureStorage.setMockInitialValues({});
  });

  for (final brightness in Brightness.values) {
    testWidgets('badge stays beside short name in $brightness mode', (tester) async {
      await tester.pumpWidget(MaterialApp(
        theme: ThemeData(brightness: brightness),
        home: const Scaffold(body: SizedBox(
          width: 360,
          child: ProfileIdentity(name: 'Ms admin', verified: true, badgeColor: Colors.amber),
        )),
      ));
      final name = tester.getRect(find.text('Ms admin'));
      final badge = tester.getRect(find.byIcon(Icons.verified_rounded));
      expect(badge.left - name.right, closeTo(6, .1));
      expect(tester.takeException(), isNull);
    });
  }

  testWidgets('long name and large text keep badge inside narrow layout', (tester) async {
    await tester.pumpWidget(MaterialApp(home: Scaffold(body: MediaQuery(
      data: const MediaQueryData(textScaler: TextScaler.linear(2)),
      child: const SizedBox(width: 240, child: ProfileIdentity(
        name: 'Muhammad Shareef Administrator of TaleemPK',
        verified: true, badgeColor: Colors.amber,
      )),
    ))));
    expect(tester.getRect(find.byIcon(Icons.verified_rounded)).right, lessThanOrEqualTo(240));
    expect(tester.takeException(), isNull);
  });

  testWidgets('unverified profile does not display verification badge', (tester) async {
    await tester.pumpWidget(const MaterialApp(home: ProfileIdentity(
      name: 'Student', verified: false, badgeColor: Colors.blue,
    )));
    expect(find.byIcon(Icons.verified_rounded), findsNothing);
  });

  testWidgets('empty avatar URL uses a complete Unicode initial', (tester) async {
    await tester.pumpWidget(const MaterialApp(home: UserAvatar(name: '  👩🏽‍🏫 Teacher', url: '')));
    expect(find.text('👩🏽‍🏫'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('security page fetches blocked users rather than claiming none', (tester) async {
    final state = AppState(SecurityClient());
    await tester.pumpWidget(AppScope(state: state,
      child: const MaterialApp(home: SecurityScreen())));
    await tester.pumpAndSettle();
    await tester.scrollUntilVisible(find.text('Blocked member'), 300,
      scrollable: find.byType(Scrollable).first);
    expect(find.text('Blocked member'), findsOneWidget);
    expect(find.text('You have not blocked anyone.'), findsNothing);
    expect(tester.takeException(), isNull);
    await tester.pumpWidget(const SizedBox.shrink());
    state.dispose();
  });

  test('social validation errors preserve server message and status', () async {
    final social = SocialApi(SessionClient(), client: MockClient((_) async =>
        http.Response(jsonEncode({'ok': false, 'error': 'This profile is private.'}), 403)));
    await expectLater(social.profile(userId: 10), throwsA(isA<ApiException>()
        .having((e) => e.message, 'message', 'This profile is private.')
        .having((e) => e.status, 'status', 403)));
  });

  test('profile cache is invalidated when account changes', () async {
    final api = SessionClient();
    var calls = 0;
    final social = SocialApi(api, client: MockClient((_) async {
      calls++;
      return http.Response(jsonEncode({'ok': true, 'data': {'profile': {
        'id': 10, 'username': 'member', 'name': api.session,
      }}}), 200);
    }));
    expect((await social.profile(userId: 10)).name, 'viewer-a');
    await social.profile(userId: 10);
    expect(calls, 1);
    api.session = 'viewer-b';
    expect((await social.profile(userId: 10)).name, 'viewer-b');
    expect(calls, 2);
  });

  test('late social 401 cannot sign out a different account', () async {
    final response = Completer<http.Response>();
    final api = SessionClient();
    var expired = false;
    api.onSessionExpired = (_) => expired = true;
    final social = SocialApi(api, client: MockClient((_) => response.future));
    final pending = social.profile(userId: 10);
    final assertion = expectLater(pending, throwsA(isA<ApiException>()
        .having((e) => e.status, 'status', 409)));
    api.session = 'viewer-b';
    response.complete(http.Response('{"ok":false,"error":"Session expired"}', 401));
    await assertion;
    expect(expired, isFalse);
    expect(api.token, 'viewer-b');
  });

  test('empty successful HTTP response is not a success acknowledgement', () async {
    final api = ApiClient(httpClient: MockClient((_) async => http.Response('', 200)));
    await expectLater(api.health(), throwsA(isA<ApiException>()));
  });

  test('late mobile API 401 cannot invalidate a new session', () async {
    final response = Completer<http.Response>();
    final api = ApiClient(httpClient: MockClient((_) => response.future));
    await api.saveToken('first-session');
    final pending = api.notificationPeek();
    final assertion = expectLater(pending, throwsA(isA<ApiException>()
        .having((e) => e.status, 'status', 409)));
    await api.saveToken('second-session');
    response.complete(http.Response('{"ok":false,"error":"Session expired"}', 401));
    await assertion;
    expect(api.token, 'second-session');
  });

  test('concurrent outbox writes retain both messages', () async {
    final outbox = MessageOutbox(ownerId: 1);
    await Future.wait([
      outbox.enqueue(const OutboxItem(token: 'one', conversationId: 1, text: 'First', createdAt: 1)),
      outbox.enqueue(const OutboxItem(token: 'two', conversationId: 1, text: 'Second', createdAt: 2)),
    ]);
    expect((await outbox.all()).map((e) => e.token), ['one', 'two']);
  });

  test('shared conversation outboxes remain private to each owner', () async {
    final first = MessageOutbox(ownerId: 1);
    final second = MessageOutbox(ownerId: 2);
    await first.enqueue(const OutboxItem(token: 'one', conversationId: 10, text: 'Private', createdAt: 1));
    expect(await second.forConversation(10), isEmpty);
    await second.clearConversation(10);
    expect(await first.forConversation(10), hasLength(1));
  });
}
