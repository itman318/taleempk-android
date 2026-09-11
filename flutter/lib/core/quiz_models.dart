class NativeQuizQuestion {
  const NativeQuizQuestion({
    required this.id,
    required this.question,
    required this.options,
    this.image,
  });

  final int id;
  final String question;
  final Map<String, String> options;
  final String? image;

  factory NativeQuizQuestion.fromJson(Map<String, dynamic> json) {
    final raw = json['options'];
    final options = <String, String>{};
    if (raw is Map) {
      for (final entry in raw.entries) {
        final key = '${entry.key}'.toLowerCase();
        final value = '${entry.value ?? ''}'.trim();
        if (value.isNotEmpty) options[key] = value;
      }
    }
    return NativeQuizQuestion(
      id: _int(json['id']),
      question: '${json['question'] ?? ''}',
      options: options,
      image: _nullable(json['image']),
    );
  }
}

class NativeQuizSession {
  const NativeQuizSession({
    required this.attemptId,
    required this.quizId,
    required this.title,
    required this.description,
    required this.subject,
    required this.timeLimitSeconds,
    required this.passPercent,
    required this.questions,
  });

  final int attemptId, quizId, timeLimitSeconds, passPercent;
  final String title, description, subject;
  final List<NativeQuizQuestion> questions;

  factory NativeQuizSession.fromJson(Map<String, dynamic> json) =>
      NativeQuizSession(
        attemptId: _int(json['attempt_id']),
        quizId: _int(json['quiz_id']),
        title: '${json['title'] ?? 'Quiz'}',
        description: '${json['description'] ?? ''}',
        subject: '${json['subject'] ?? ''}',
        timeLimitSeconds: _int(json['time_limit_seconds']),
        passPercent: _int(json['pass_percent']),
        questions: _list(json['questions'])
            .map((e) => NativeQuizQuestion.fromJson(_map(e)))
            .toList(),
      );
}

class NativeQuizReview {
  const NativeQuizReview({
    required this.id,
    required this.question,
    required this.options,
    required this.selected,
    required this.correctOption,
    required this.correct,
    required this.explanation,
  });

  final int id;
  final String question, selected, correctOption, explanation;
  final Map<String, String> options;
  final bool correct;

  factory NativeQuizReview.fromJson(Map<String, dynamic> json) {
    final raw = json['options'];
    final options = <String, String>{};
    if (raw is Map) {
      for (final entry in raw.entries) {
        final key = '${entry.key}'.toLowerCase();
        final value = '${entry.value ?? ''}'.trim();
        if (value.isNotEmpty) options[key] = value;
      }
    }
    return NativeQuizReview(
      id: _int(json['id']),
      question: '${json['question'] ?? ''}',
      options: options,
      selected: '${json['selected'] ?? ''}',
      correctOption: '${json['correct_option'] ?? ''}',
      correct: _bool(json['is_correct']),
      explanation: '${json['explanation'] ?? ''}',
    );
  }
}

class NativeQuizResult {
  const NativeQuizResult({
    required this.attemptId,
    required this.title,
    required this.percentage,
    required this.correct,
    required this.wrong,
    required this.skipped,
    required this.total,
    required this.timeTaken,
    required this.passPercent,
    required this.passed,
    required this.review,
  });

  final int attemptId, correct, wrong, skipped, total, timeTaken, passPercent;
  final String title;
  final double percentage;
  final bool passed;
  final List<NativeQuizReview> review;

  factory NativeQuizResult.fromJson(Map<String, dynamic> json) =>
      NativeQuizResult(
        attemptId: _int(json['attempt_id']),
        title: '${json['title'] ?? 'Quiz'}',
        percentage: _double(json['percentage']),
        correct: _int(json['correct']),
        wrong: _int(json['wrong']),
        skipped: _int(json['skipped']),
        total: _int(json['total']),
        timeTaken: _int(json['time_taken']),
        passPercent: _int(json['pass_percent']),
        passed: _bool(json['passed']),
        review: _list(json['review'])
            .map((e) => NativeQuizReview.fromJson(_map(e)))
            .toList(),
      );
}

Map<String, dynamic> _map(dynamic value) => value is Map
    ? value.map((key, value) => MapEntry('$key', value))
    : <String, dynamic>{};

List<dynamic> _list(dynamic value) => value is List ? value : const [];

String? _nullable(dynamic value) {
  final text = value?.toString().trim() ?? '';
  return text.isEmpty ? null : text;
}

int _int(dynamic value) => value is int ? value : int.tryParse('$value') ?? 0;

double _double(dynamic value) =>
    value is num ? value.toDouble() : double.tryParse('$value') ?? 0;

bool _bool(dynamic value) =>
    value == true || value == 1 || '$value'.toLowerCase() == 'true';
