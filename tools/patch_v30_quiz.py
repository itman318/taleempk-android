from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]

def replace(path, old, new, count=1):
    p = ROOT / path
    text = p.read_text(encoding='utf-8')
    if old not in text:
        raise SystemExit(f'anchor missing in {path}: {old[:100]!r}')
    p.write_text(text.replace(old, new, count), encoding='utf-8')

replace(
    'flutter/lib/core/api_client.dart',
    "import 'models.dart';",
    "import 'models.dart';\nimport 'quiz_models.dart';"
)
replace(
    'flutter/lib/core/api_client.dart',
    "  Future<Map<String, dynamic>> moduleAction(String action, {int id = 0}) =>\n      _request({'action': 'module_action', 'do': action, 'id': '$id'});",
    "  Future<Map<String, dynamic>> moduleAction(String action, {int id = 0}) =>\n      _request({'action': 'module_action', 'do': action, 'id': '$id'});\n\n  Future<NativeQuizSession> startNativeQuiz(int quizId) async =>\n      NativeQuizSession.fromJson(\n        await _request({\n          'action': 'quiz_start',\n          'quiz_id': '$quizId',\n        }),\n      );\n\n  Future<NativeQuizResult> submitNativeQuiz(\n    int attemptId,\n    Map<int, String> answers,\n    int timeTaken,\n  ) async =>\n      NativeQuizResult.fromJson(\n        await _request({\n          'action': 'quiz_submit',\n          'attempt_id': '$attemptId',\n          'answers': jsonEncode({\n            for (final entry in answers.entries) '\${entry.key}': entry.value,\n          }),\n          'time_taken': '$timeTaken',\n        }),\n      );"
)

replace(
    'flutter/lib/screens/module_screen.dart',
    "import 'home_shell.dart';",
    "import 'home_shell.dart';\nimport 'quiz_screen.dart';"
)
replace(
    'flutter/lib/screens/module_screen.dart',
    "    if (item.kind == 'notification') {\n      try {",
    "    if (item.kind == 'quiz') {\n      await Navigator.push(\n        context,\n        MaterialPageRoute(builder: (_) => QuizScreen(item: item)),\n      );\n      if (mounted) _load();\n      return;\n    }\n    if (item.kind == 'notification') {\n      try {"
)
# Remove the old browser-route warning since quizzes now run natively.
replace(
    'flutter/lib/screens/module_screen.dart',
    "\n    if (item.kind == 'quiz' && item.route.isEmpty) {\n      showMessage(\n        context,\n        'This quiz needs the latest TaleemPK mobile API. Update api/mobile.php, then refresh.',\n      );\n      return;\n    }\n",
    "\n"
)

backend = ROOT / 'flutter/backend/api/mobile.php'
text = backend.read_text(encoding='utf-8')
marker = "/* Bridge the verified bearer identity into the mature browser mutation"
if marker not in text:
    raise SystemExit('backend bridge marker missing')
quiz = r'''if ($action === 'quiz_start') {
    require_feature('feature_quizzes');
    $quizId = max(0, (int) ($_POST['quiz_id'] ?? 0));
    $quiz = fetch_one('SELECT id,title,description,subject,time_limit,pass_percent,shuffle,show_answers,status,is_public,user_id FROM quizzes WHERE id=? LIMIT 1', [$quizId]);
    if (!$quiz
        || ($quiz['status'] !== 'approved' && !is_admin() && (int)$quiz['user_id'] !== $uid)
        || ((int)$quiz['is_public'] !== 1 && !is_admin() && (int)$quiz['user_id'] !== $uid)) {
        mobile_error('That quiz is not available.', 404);
    }
    $questions = fetch_all('SELECT id,question,image,option_a,option_b,option_c,option_d FROM quiz_questions WHERE quiz_id=? ORDER BY sort_order,id', [$quizId]);
    if (!$questions) { mobile_error('This quiz has no questions yet.', 409); }
    if ((int)$quiz['shuffle'] === 1) { shuffle($questions); }
    $attemptId = insert_row('quiz_attempts', [
        'quiz_id' => $quizId,
        'user_id' => $uid,
        'total' => count($questions),
        'status' => 'in_progress',
    ]);
    $items = array_map(static function(array $q): array {
        $options = [];
        foreach (['a','b','c','d'] as $letter) {
            $value = trim((string)($q['option_' . $letter] ?? ''));
            if ($value !== '') { $options[$letter] = $value; }
        }
        return [
            'id' => (int)$q['id'],
            'question' => (string)$q['question'],
            'image' => !empty($q['image']) ? upload_url((string)$q['image']) : null,
            'options' => $options,
        ];
    }, $questions);
    mobile_out([
        'attempt_id' => (int)$attemptId,
        'quiz_id' => $quizId,
        'title' => (string)$quiz['title'],
        'description' => (string)($quiz['description'] ?? ''),
        'subject' => (string)($quiz['subject'] ?? ''),
        'time_limit_seconds' => max(0, (int)$quiz['time_limit']) * 60,
        'pass_percent' => (int)$quiz['pass_percent'],
        'questions' => $items,
    ]);
}

if ($action === 'quiz_submit') {
    require_feature('feature_quizzes');
    $attemptId = max(0, (int) ($_POST['attempt_id'] ?? 0));
    $answersRaw = json_decode((string) ($_POST['answers'] ?? '{}'), true);
    if (!is_array($answersRaw)) { $answersRaw = []; }
    $attempt = fetch_one('SELECT a.*,q.title,q.pass_percent,q.show_answers,q.time_limit FROM quiz_attempts a JOIN quizzes q ON q.id=a.quiz_id WHERE a.id=? AND a.user_id=? LIMIT 1', [$attemptId,$uid]);
    if (!$attempt) { mobile_error('That quiz attempt is not available.', 404); }
    if ((string)$attempt['status'] !== 'in_progress') { mobile_error('This quiz attempt has already been submitted.', 409); }
    $questions = fetch_all('SELECT id,question,option_a,option_b,option_c,option_d,correct_option,explanation FROM quiz_questions WHERE quiz_id=? ORDER BY sort_order,id', [(int)$attempt['quiz_id']]);
    if (!$questions) { mobile_error('This quiz no longer has questions.', 409); }
    $timeTaken = max(0, (int) ($_POST['time_taken'] ?? 0));
    $maxTime = (int)$attempt['time_limit'] > 0 ? ((int)$attempt['time_limit'] * 60 + 30) : 86400;
    $timeTaken = min($timeTaken, $maxTime);
    $correct = 0; $wrong = 0; $skipped = 0; $answerRows = [];
    foreach ($questions as $q) {
        $key = (string)(int)$q['id'];
        $selected = strtolower(trim((string)($answersRaw[$key] ?? '')));
        if (!in_array($selected, ['a','b','c','d'], true)) {
            $selected = null; $isCorrect = 0; $skipped++;
        } else {
            $isCorrect = $selected === (string)$q['correct_option'] ? 1 : 0;
            if ($isCorrect) { $correct++; } else { $wrong++; }
        }
        $answerRows[] = [(int)$q['id'], $selected, $isCorrect];
    }
    $total = count($questions);
    $percentage = $total > 0 ? round($correct / $total * 100, 2) : 0.0;
    db_transaction(static function() use ($attemptId,$answerRows,$correct,$wrong,$skipped,$total,$percentage,$timeTaken,$attempt): void {
        foreach ($answerRows as $answer) {
            insert_row('quiz_answers', [
                'attempt_id' => $attemptId,
                'question_id' => $answer[0],
                'selected' => $answer[1],
                'is_correct' => $answer[2],
            ]);
        }
        update_row('quiz_attempts', [
            'score' => $correct,
            'total' => $total,
            'percentage' => $percentage,
            'correct' => $correct,
            'wrong' => $wrong,
            'skipped' => $skipped,
            'time_taken' => $timeTaken,
            'status' => 'completed',
            'completed_at' => date('Y-m-d H:i:s'),
        ], 'id=? AND user_id=?', [$attemptId,(int)$attempt['user_id']]);
        q('UPDATE quizzes SET attempts_count=attempts_count+1 WHERE id=?', [(int)$attempt['quiz_id']]);
    });
    $review = [];
    if ((int)$attempt['show_answers'] === 1) {
        foreach ($questions as $q) {
            $selected = null; $isCorrect = false;
            foreach ($answerRows as $answer) {
                if ($answer[0] === (int)$q['id']) { $selected = $answer[1]; $isCorrect = $answer[2] === 1; break; }
            }
            $options = [];
            foreach (['a','b','c','d'] as $letter) {
                $value = trim((string)($q['option_' . $letter] ?? ''));
                if ($value !== '') { $options[$letter] = $value; }
            }
            $review[] = [
                'id' => (int)$q['id'],
                'question' => (string)$q['question'],
                'options' => $options,
                'selected' => $selected,
                'correct_option' => (string)$q['correct_option'],
                'is_correct' => $isCorrect,
                'explanation' => (string)($q['explanation'] ?? ''),
            ];
        }
    }
    mobile_out([
        'attempt_id' => $attemptId,
        'title' => (string)$attempt['title'],
        'percentage' => $percentage,
        'correct' => $correct,
        'wrong' => $wrong,
        'skipped' => $skipped,
        'total' => $total,
        'time_taken' => $timeTaken,
        'pass_percent' => (int)$attempt['pass_percent'],
        'passed' => $percentage >= (float)$attempt['pass_percent'],
        'review' => $review,
    ]);
}

'''
text = text.replace(marker, quiz + marker, 1)
backend.write_text(text, encoding='utf-8')
shutil.copyfile(ROOT / 'flutter/backend/api/mobile.php', ROOT / 'backend/api/mobile.php')
