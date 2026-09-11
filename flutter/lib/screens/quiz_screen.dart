import 'dart:async';

import 'package:flutter/material.dart';

import '../core/app_state.dart';
import '../core/models.dart';
import '../core/quiz_models.dart';
import '../core/theme.dart';
import '../widgets/common.dart';
import 'home_shell.dart';

class QuizScreen extends StatefulWidget {
  const QuizScreen({super.key, required this.item});

  final ModuleItem item;

  @override
  State<QuizScreen> createState() => _QuizScreenState();
}

class _QuizScreenState extends State<QuizScreen> {
  NativeQuizSession? session;
  NativeQuizResult? result;
  final answers = <int, String>{};
  final page = PageController();
  Timer? timer;
  int index = 0, elapsed = 0, secondsLeft = 0;
  bool loading = true, submitting = false;
  String? error;

  @override
  void initState() {
    super.initState();
    _start();
  }

  @override
  void dispose() {
    timer?.cancel();
    page.dispose();
    super.dispose();
  }

  Future<void> _start() async {
    timer?.cancel();
    if (mounted) {
      setState(() {
        loading = true;
        submitting = false;
        error = null;
        result = null;
        answers.clear();
        index = 0;
        elapsed = 0;
      });
    }
    try {
      final loaded = await AppScope.of(context).api.startNativeQuiz(widget.item.id);
      session = loaded;
      secondsLeft = loaded.timeLimitSeconds;
      if (loaded.timeLimitSeconds > 0) {
        timer = Timer.periodic(const Duration(seconds: 1), (_) {
          if (!mounted || submitting || result != null) return;
          setState(() {
            elapsed++;
            secondsLeft = (loaded.timeLimitSeconds - elapsed)
                .clamp(0, loaded.timeLimitSeconds)
                .toInt();
          });
          if (secondsLeft <= 0) {
            timer?.cancel();
            _submit(auto: true);
          }
        });
      } else {
        timer = Timer.periodic(const Duration(seconds: 1), (_) {
          if (mounted && !submitting && result == null) setState(() => elapsed++);
        });
      }
    } catch (e) {
      error = apiMessage(e);
    }
    if (mounted) setState(() => loading = false);
  }

  @override
  Widget build(BuildContext context) => PopScope(
        canPop: result != null || session == null,
        onPopInvokedWithResult: (didPop, _) {
          if (!didPop) _confirmLeave();
        },
        child: Scaffold(
          appBar: PremiumAppBar(
            title: result == null ? widget.item.title : 'Quiz result',
            subtitle: result == null ? widget.item.subtitle : result!.title,
          ),
          body: loading
              ? const Center(child: CircularProgressIndicator())
              : error != null
                  ? ErrorView(message: error!, retry: _start)
                  : result != null
                      ? _resultView(result!)
                      : _quizView(session!),
        ),
      );

  Widget _quizView(NativeQuizSession quiz) {
    if (quiz.questions.isEmpty) {
      return const EmptyView(
        icon: Icons.quiz_outlined,
        title: 'No questions available',
        message: 'This quiz does not have any questions yet.',
      );
    }
    final answered = answers.length;
    final progress = quiz.questions.isEmpty ? 0.0 : (index + 1) / quiz.questions.length;
    return Column(
      children: [
        Container(
          margin: const EdgeInsets.fromLTRB(16, 8, 16, 8),
          padding: const EdgeInsets.all(15),
          decoration: BoxDecoration(
            color: Theme.of(context).colorScheme.surface,
            borderRadius: BorderRadius.circular(20),
            border: Border.all(color: Theme.of(context).dividerColor),
          ),
          child: Column(
            children: [
              Row(
                children: [
                  Expanded(
                    child: Text(
                      'Question ${index + 1} of ${quiz.questions.length}',
                      style: const TextStyle(fontWeight: FontWeight.w900),
                    ),
                  ),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                    decoration: BoxDecoration(
                      color: secondsLeft > 0 && secondsLeft < 60
                          ? AppColors.danger.withValues(alpha: .10)
                          : AppColors.blue.withValues(alpha: .10),
                      borderRadius: BorderRadius.circular(20),
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        const Icon(Icons.timer_outlined, size: 16),
                        const SizedBox(width: 5),
                        Text(
                          _clock(quiz.timeLimitSeconds > 0 ? secondsLeft : elapsed),
                          style: const TextStyle(fontWeight: FontWeight.w900),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 10),
              LinearProgressIndicator(value: progress, minHeight: 6),
              const SizedBox(height: 8),
              Row(
                children: [
                  Text(
                    '$answered answered',
                    style: const TextStyle(fontSize: 11.5, color: AppColors.muted),
                  ),
                  const Spacer(),
                  Text(
                    'Pass ${quiz.passPercent}%',
                    style: const TextStyle(
                      fontSize: 11.5,
                      color: AppColors.blue,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
        Expanded(
          child: PageView.builder(
            controller: page,
            physics: const NeverScrollableScrollPhysics(),
            itemCount: quiz.questions.length,
            onPageChanged: (value) => setState(() => index = value),
            itemBuilder: (_, i) => _questionCard(quiz.questions[i], i),
          ),
        ),
        SafeArea(
          top: false,
          child: Container(
            padding: const EdgeInsets.fromLTRB(14, 10, 14, 14),
            decoration: BoxDecoration(
              color: Theme.of(context).colorScheme.surface,
              border: Border(top: BorderSide(color: Theme.of(context).dividerColor)),
            ),
            child: Row(
              children: [
                OutlinedButton.icon(
                  onPressed: index == 0
                      ? null
                      : () => page.previousPage(
                            duration: const Duration(milliseconds: 220),
                            curve: Curves.easeOut,
                          ),
                  icon: const Icon(Icons.arrow_back_rounded),
                  label: const Text('Back'),
                ),
                const Spacer(),
                if (index < quiz.questions.length - 1)
                  FilledButton.icon(
                    onPressed: () => page.nextPage(
                      duration: const Duration(milliseconds: 220),
                      curve: Curves.easeOut,
                    ),
                    iconAlignment: IconAlignment.end,
                    icon: const Icon(Icons.arrow_forward_rounded),
                    label: const Text('Next'),
                  )
                else
                  FilledButton.icon(
                    onPressed: submitting ? null : () => _submit(auto: false),
                    icon: submitting
                        ? const SizedBox(
                            width: 17,
                            height: 17,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : const Icon(Icons.flag_rounded),
                    label: const Text('Finish quiz'),
                  ),
              ],
            ),
          ),
        ),
      ],
    );
  }

  Widget _questionCard(NativeQuizQuestion question, int questionIndex) =>
      ListView(
        padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
        children: [
          Card(
            child: Padding(
              padding: const EdgeInsets.all(18),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'QUESTION ${questionIndex + 1}',
                    style: const TextStyle(
                      color: AppColors.blue,
                      fontSize: 11,
                      fontWeight: FontWeight.w900,
                      letterSpacing: .8,
                    ),
                  ),
                  const SizedBox(height: 9),
                  Text(
                    question.question,
                    style: const TextStyle(fontSize: 18, height: 1.4, fontWeight: FontWeight.w800),
                  ),
                  const SizedBox(height: 18),
                  for (final option in question.options.entries) ...[
                    _optionTile(question, option.key, option.value),
                    const SizedBox(height: 9),
                  ],
                ],
              ),
            ),
          ),
        ],
      );

  Widget _optionTile(NativeQuizQuestion question, String key, String text) {
    final selected = answers[question.id] == key;
    return InkWell(
      borderRadius: BorderRadius.circular(16),
      onTap: () => setState(() => answers[question.id] = key),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 160),
        padding: const EdgeInsets.all(13),
        decoration: BoxDecoration(
          color: selected
              ? AppColors.blue.withValues(alpha: .10)
              : Theme.of(context).colorScheme.surfaceContainerLowest,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(
            color: selected ? AppColors.blue : Theme.of(context).dividerColor,
            width: selected ? 1.6 : 1,
          ),
        ),
        child: Row(
          children: [
            Container(
              width: 34,
              height: 34,
              alignment: Alignment.center,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: selected ? AppColors.blue : AppColors.blue.withValues(alpha: .08),
              ),
              child: Text(
                key.toUpperCase(),
                style: TextStyle(
                  color: selected ? Colors.white : AppColors.blue,
                  fontWeight: FontWeight.w900,
                ),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Text(
                text,
                style: const TextStyle(fontSize: 15, height: 1.35, fontWeight: FontWeight.w600),
              ),
            ),
            if (selected)
              const Icon(Icons.check_circle_rounded, color: AppColors.blue),
          ],
        ),
      ),
    );
  }

  Future<void> _submit({required bool auto}) async {
    final quiz = session;
    if (quiz == null || submitting) return;
    if (!auto && answers.length < quiz.questions.length) {
      final proceed = await showDialog<bool>(
            context: context,
            builder: (dialog) => AlertDialog(
              title: const Text('Finish quiz?'),
              content: Text(
                '${quiz.questions.length - answers.length} question(s) are unanswered. You can still submit now.',
              ),
              actions: [
                TextButton(
                  onPressed: () => Navigator.pop(dialog, false),
                  child: const Text('Keep answering'),
                ),
                FilledButton(
                  onPressed: () => Navigator.pop(dialog, true),
                  child: const Text('Submit'),
                ),
              ],
            ),
          ) ??
          false;
      if (!proceed) return;
    }
    setState(() => submitting = true);
    timer?.cancel();
    try {
      result = await AppScope.of(context).api.submitNativeQuiz(
            quiz.attemptId,
            answers,
            elapsed,
          );
      if (mounted) setState(() {});
    } catch (e) {
      if (mounted) {
        showMessage(context, apiMessage(e));
        setState(() => submitting = false);
      }
    }
  }

  Widget _resultView(NativeQuizResult score) {
    final passed = score.passed;
    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 8, 16, 30),
      children: [
        Container(
          padding: const EdgeInsets.all(22),
          decoration: BoxDecoration(
            gradient: LinearGradient(
              colors: passed
                  ? const [Color(0xFF0F6A5E), Color(0xFF15977E)]
                  : const [Color(0xFF7E3D55), Color(0xFFB45165)],
            ),
            borderRadius: BorderRadius.circular(26),
          ),
          child: Column(
            children: [
              Icon(
                passed ? Icons.emoji_events_rounded : Icons.auto_stories_rounded,
                color: Colors.white,
                size: 54,
              ),
              const SizedBox(height: 10),
              Text(
                '${score.percentage.round()}%',
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 46,
                  fontWeight: FontWeight.w900,
                ),
              ),
              Text(
                passed ? 'Passed — well done!' : 'Not passed yet — keep practising',
                textAlign: TextAlign.center,
                style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w800),
              ),
              const SizedBox(height: 18),
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                children: [
                  _metric('Correct', score.correct),
                  _metric('Wrong', score.wrong),
                  _metric('Skipped', score.skipped),
                  _metric('Time', _clock(score.timeTaken)),
                ],
              ),
            ],
          ),
        ),
        const SizedBox(height: 14),
        Row(
          children: [
            Expanded(
              child: OutlinedButton.icon(
                onPressed: _start,
                icon: const Icon(Icons.replay_rounded),
                label: const Text('Try again'),
              ),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: FilledButton.icon(
                onPressed: () => Navigator.pop(context),
                icon: const Icon(Icons.quiz_outlined),
                label: const Text('More quizzes'),
              ),
            ),
          ],
        ),
        if (score.review.isNotEmpty) ...[
          const SizedBox(height: 22),
          Text(
            'Answer review',
            style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w900),
          ),
          const SizedBox(height: 9),
          for (var i = 0; i < score.review.length; i++)
            _reviewCard(score.review[i], i),
        ],
      ],
    );
  }

  Widget _reviewCard(NativeQuizReview review, int reviewIndex) => Card(
        margin: const EdgeInsets.only(bottom: 10),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Question ${reviewIndex + 1}',
                style: const TextStyle(
                  color: AppColors.muted,
                  fontSize: 11,
                  fontWeight: FontWeight.w800,
                ),
              ),
              const SizedBox(height: 6),
              Text(review.question, style: const TextStyle(fontWeight: FontWeight.w800)),
              const SizedBox(height: 10),
              for (final option in review.options.entries)
                Container(
                  width: double.infinity,
                  margin: const EdgeInsets.only(bottom: 6),
                  padding: const EdgeInsets.all(10),
                  decoration: BoxDecoration(
                    color: option.key == review.correctOption
                        ? AppColors.success.withValues(alpha: .10)
                        : option.key == review.selected && !review.correct
                            ? AppColors.danger.withValues(alpha: .09)
                            : Colors.transparent,
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(
                      color: option.key == review.correctOption
                          ? AppColors.success
                          : option.key == review.selected && !review.correct
                              ? AppColors.danger
                              : Theme.of(context).dividerColor,
                    ),
                  ),
                  child: Text(
                    '${option.key.toUpperCase()}. ${option.value}${option.key == review.correctOption ? '  ✓' : ''}',
                  ),
                ),
              if (review.explanation.isNotEmpty) ...[
                const SizedBox(height: 6),
                Text(
                  review.explanation,
                  style: const TextStyle(color: AppColors.muted, height: 1.4),
                ),
              ],
            ],
          ),
        ),
      );

  Widget _metric(String label, Object value) => Column(
        children: [
          Text(
            '$value',
            style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w900),
          ),
          const SizedBox(height: 2),
          Text(label, style: const TextStyle(color: Colors.white70, fontSize: 10)),
        ],
      );

  Future<void> _confirmLeave() async {
    final leave = await showDialog<bool>(
          context: context,
          builder: (dialog) => AlertDialog(
            title: const Text('Leave this quiz?'),
            content: const Text('Your current answers have not been submitted yet.'),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(dialog, false),
                child: const Text('Stay'),
              ),
              FilledButton(
                onPressed: () => Navigator.pop(dialog, true),
                child: const Text('Leave'),
              ),
            ],
          ),
        ) ??
        false;
    if (leave && mounted) Navigator.pop(context);
  }

  String _clock(int seconds) {
    final safe = seconds < 0 ? 0 : seconds;
    final minutes = safe ~/ 60;
    final remain = safe % 60;
    return '$minutes:${remain.toString().padLeft(2, '0')}';
  }
}
