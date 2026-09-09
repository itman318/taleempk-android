import 'package:flutter_test/flutter_test.dart';
import 'package:studyhub_flutter/core/models.dart';

void main() {
  test('bootstrap model tolerates numeric strings and missing values', () {
    final data = BootstrapData.fromJson({
      'user': {
        'id': '7',
        'name': 'Ayesha Khan',
        'username': 'ayesha',
        'role': 'student',
        'verified': 1,
      },
      'stats': {'members': '1473', 'active_today': 1127},
      'shortcuts': [
        {
          'title': 'Study',
          'subtitle': 'Plan',
          'route': 'study.php',
          'icon': 'study',
        },
      ],
    });
    expect(data.user.id, 7);
    expect(data.user.verified, isTrue);
    expect(data.stats.members, 1473);
    expect(data.shortcuts.single.route, 'study.php');
  });

  test('chat message parses reply and reactions safely', () {
    final message = ChatMessage.fromJson({
      'id': 9,
      'sender_id': 2,
      'sender': 'Teacher',
      'content': 'Well done',
      'time': '9:30 AM',
      'mine': false,
      'voice_seconds': 0,
      'read': true,
      'date_label': 'Today',
      'reply': {'id': 4, 'sender': 'Student', 'text': 'My answer'},
      'reactions': [
        {'emoji': '👍', 'count': 2, 'mine': true},
      ],
    });
    expect(message.reply?.id, 4);
    expect(message.reactions.single.count, 2);
  });
}
