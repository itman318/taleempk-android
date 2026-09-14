import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:studyhub_flutter/core/outbox.dart';

void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues(<String, Object>{});
  });

  test('outbox persists and removes a queued message', () async {
    final outbox = MessageOutbox();
    const item = OutboxItem(
      token: 'token-1',
      conversationId: 42,
      text: 'hello offline',
      replyTo: 7,
      createdAt: 1234,
    );

    await outbox.enqueue(item);
    final pending = await outbox.forConversation(42);
    expect(pending, hasLength(1));
    expect(pending.first.text, 'hello offline');
    expect(pending.first.replyTo, 7);

    await outbox.updateAttempts('token-1', 2);
    expect((await outbox.forConversation(42)).single.attempts, 2);

    await outbox.remove('token-1');
    expect(await outbox.countForConversation(42), 0);
  });

  test('outbox keeps conversations isolated', () async {
    final outbox = MessageOutbox();
    await outbox.enqueue(const OutboxItem(
      token: 'a',
      conversationId: 1,
      text: 'one',
      createdAt: 1,
    ));
    await outbox.enqueue(const OutboxItem(
      token: 'b',
      conversationId: 2,
      text: 'two',
      createdAt: 2,
    ));

    expect(await outbox.countForConversation(1), 1);
    expect(await outbox.countForConversation(2), 1);
    await outbox.clearConversation(1);
    expect(await outbox.countForConversation(1), 0);
    expect(await outbox.countForConversation(2), 1);
  });
}
