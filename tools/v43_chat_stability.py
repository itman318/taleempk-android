from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def r(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def w(path: str, text: str) -> None:
    p = ROOT / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding='utf-8')


def function_bounds(text: str, signature: str):
    start = text.find(signature)
    if start < 0:
        raise RuntimeError(f'v4.3 missing function: {signature}')
    brace = text.find('{', start)
    if brace < 0:
        raise RuntimeError(f'v4.3 malformed function: {signature}')
    depth = 0
    quote = None
    escape = False
    line_comment = False
    block_comment = False
    i = brace
    while i < len(text):
        ch = text[i]
        nxt = text[i + 1] if i + 1 < len(text) else ''
        if line_comment:
            if ch == '\n':
                line_comment = False
            i += 1
            continue
        if block_comment:
            if ch == '*' and nxt == '/':
                block_comment = False
                i += 2
                continue
            i += 1
            continue
        if quote is not None:
            if escape:
                escape = False
            elif ch == '\\':
                escape = True
            elif ch == quote:
                quote = None
            i += 1
            continue
        if ch == '/' and nxt == '/':
            line_comment = True
            i += 2
            continue
        if ch == '/' and nxt == '*':
            block_comment = True
            i += 2
            continue
        if ch in ("'", '"'):
            quote = ch
            i += 1
            continue
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                return start, i + 1
        i += 1
    raise RuntimeError(f'v4.3 unterminated function: {signature}')


def replace_function(text: str, signature: str, replacement: str) -> str:
    s, e = function_bounds(text, signature)
    return text[:s] + replacement + text[e:]


# ---------------------------------------------------------------------------
# Chat stability: draft recovery, lighter composer rebuilds, reliable replies,
# and an outbox review path for messages rejected permanently by the server.
# ---------------------------------------------------------------------------
path = 'flutter/lib/screens/chat_screen.dart'
text = r(path)

state_marker = '  ChatPresence? presence;\n'
if 'Timer? draftDebounce;' not in text:
    if state_marker not in text:
        raise RuntimeError('v4.3 chat state marker missing')
    text = text.replace(
        state_marker,
        "  Timer? draftDebounce;\n  bool composerHasText = false;\n  bool restoringDraft = false;\n  String? outboxIssue;\n  ChatPresence? presence;\n",
        1,
    )

# Restore the per-conversation draft as soon as the screen is ready.
init_marker = '    _loadRecentEmojis();\n'
if '    _restoreDraft();\n' not in text:
    if init_marker not in text:
        raise RuntimeError('v4.3 init draft marker missing')
    text = text.replace(init_marker, init_marker + '    _restoreDraft();\n', 1)

# Persist the last text when leaving and stop the debounce timer.
dispose_marker = '    voiceHeartbeat?.cancel();\n'
if '    draftDebounce?.cancel();\n' not in text:
    if dispose_marker not in text:
        raise RuntimeError('v4.3 dispose timer marker missing')
    text = text.replace(
        dispose_marker,
        dispose_marker
        + '    draftDebounce?.cancel();\n'
        + '    unawaited(_persistDraft(textController.text));\n',
        1,
    )

# Draft helpers are intentionally independent of network state.
typing_pos = text.find('  void _typing() {')
if typing_pos < 0:
    raise RuntimeError('v4.3 typing marker missing')
if "String get _draftKey" not in text:
    draft_helpers = r'''  String get _draftKey => 'chat_draft_${widget.conversation.id}';

  Future<void> _restoreDraft() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      var saved = prefs.getString(_draftKey) ?? '';
      if (saved.length > 4000) saved = saved.substring(0, 4000);
      if (!mounted || saved.isEmpty) return;
      restoringDraft = true;
      textController.value = TextEditingValue(
        text: saved,
        selection: TextSelection.collapsed(offset: saved.length),
      );
      restoringDraft = false;
      final hasText = saved.trim().isNotEmpty;
      if (mounted && composerHasText != hasText) {
        setState(() => composerHasText = hasText);
      }
    } catch (_) {
      // Draft recovery is a convenience feature; chat remains usable without it.
    } finally {
      restoringDraft = false;
    }
  }

  void _scheduleDraftSave() {
    draftDebounce?.cancel();
    final value = textController.text;
    draftDebounce = Timer(const Duration(milliseconds: 350), () {
      unawaited(_persistDraft(value));
    });
  }

  Future<void> _persistDraft(String value) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final trimmed = value.trim();
      if (trimmed.isEmpty) {
        await prefs.remove(_draftKey);
      } else {
        final safe = value.length > 4000 ? value.substring(0, 4000) : value;
        await prefs.setString(_draftKey, safe);
      }
    } catch (_) {}
  }

  ReplyPreview? _replyPreviewForId(int? id) {
    if (id == null || id <= 0) return null;
    for (final message in messages) {
      if (message.id != id) continue;
      return ReplyPreview(
        id: message.id,
        sender: message.sender,
        text: message.content.isNotEmpty
            ? message.content
            : (message.voiceSeconds > 0
                  ? 'Voice message'
                  : message.attachmentName ?? 'Attachment'),
      );
    }
    return null;
  }

  bool _isPermanentOutboxError(Object error) {
    if (error is! ApiException) return false;
    final status = error.status;
    if (status < 400 || status >= 500) return false;
    return !<int>{401, 408, 409, 425, 429}.contains(status);
  }

  Future<void> _reviewQueuedMessage() async {
    final pending = await outbox.forConversation(widget.conversation.id);
    if (pending.isEmpty) {
      outboxIssue = null;
      await _refreshOutboxCount();
      return;
    }
    if (textController.text.trim().isNotEmpty) {
      if (mounted) {
        showMessage(context, 'Finish or clear your current draft, then review the queued message.');
      }
      return;
    }
    final item = pending.first;
    await outbox.remove(item.token);
    restoringDraft = true;
    textController.value = TextEditingValue(
      text: item.text,
      selection: TextSelection.collapsed(offset: item.text.length),
    );
    restoringDraft = false;
    await _persistDraft(item.text);
    final restoredReply = _replyPreviewForId(item.replyTo);
    if (mounted) {
      setState(() {
        composerHasText = item.text.trim().isNotEmpty;
        reply = restoredReply;
        outboxIssue = null;
      });
      showMessage(context, 'Queued message restored to the composer for review.');
    }
    await _refreshOutboxCount();
  }

'''
    text = text[:typing_pos] + draft_helpers + text[typing_pos:]

# Do not rebuild the whole conversation list on every typed character. Only the
# empty/non-empty composer transition needs a visual rebuild for mic/send icon.
typing = r'''  void _typing() {
    idlePolls = 0;
    final hasText = textController.text.trim().isNotEmpty;
    if (mounted && composerHasText != hasText) {
      setState(() => composerHasText = hasText);
    }
    if (!restoringDraft) _scheduleDraftSave();
    if (restoringDraft) return;

    presenceDebounce?.cancel();
    if (!hasText) {
      typingHeartbeat?.cancel();
      typingHeartbeat = null;
      typingSent = false;
      AppScope.of(context).api
          .presence(widget.conversation.id, clear: true)
          .catchError((_) => const ChatPresence(
                active: false,
                kind: '',
                name: '',
                readThrough: 0,
              ));
      return;
    }

    if (!typingSent) {
      typingSent = true;
      AppScope.of(context).api
          .presence(widget.conversation.id, kind: 'text')
          .catchError((_) => const ChatPresence(
                active: false,
                kind: '',
                name: '',
                readThrough: 0,
              ));
    }

    typingHeartbeat ??= Timer.periodic(const Duration(milliseconds: 2500), (_) {
      if (!mounted || recording || textController.text.trim().isEmpty) return;
      AppScope.of(context).api
          .presence(widget.conversation.id, kind: 'text')
          .catchError((_) => const ChatPresence(
                active: false,
                kind: '',
                name: '',
                readThrough: 0,
              ));
    });

    presenceDebounce = Timer(const Duration(seconds: 2), () {
      typingHeartbeat?.cancel();
      typingHeartbeat = null;
      typingSent = false;
      if (mounted) {
        AppScope.of(context).api
            .presence(widget.conversation.id, clear: true)
            .catchError((_) => const ChatPresence(
                  active: false,
                  kind: '',
                  name: '',
                  readThrough: 0,
                ));
      }
    });
  }'''
text = replace_function(text, '  void _typing() {', typing)

# Composer uses the cached empty/non-empty state so its send button changes
# without forcing message bubbles to rebuild for every keystroke.
cs, ce = function_bounds(text, '  Widget _composer() => Container(')
composer = text[cs:ce]
composer = composer.replace('textController.text.trim().isEmpty', '!composerHasText')
text = text[:cs] + composer + text[ce:]

# Preserve reply context when a send is rejected; network failures still enter
# the idempotent outbox. Successful sends use the incremental sync path.
send_text = r'''  Future<void> _sendText() async {
    if (_chatBlocked) return;
    final text = textController.text.trim();
    if (text.isEmpty) return;
    final currentReply = reply;
    final api = AppScope.of(context).api;
    final token = api.newClientToken();
    setState(() {
      sending = true;
      reply = null;
      composerHasText = false;
    });
    textController.clear();
    await _persistDraft('');
    try {
      await api.sendText(
        widget.conversation.id,
        text,
        replyTo: currentReply?.id,
        clientToken: token,
      );
      await _syncAfterSend();
    } catch (e) {
      if (e is ApiException && e.status == 0) {
        await outbox.enqueue(
          OutboxItem(
            token: token,
            conversationId: widget.conversation.id,
            text: text,
            replyTo: currentReply?.id,
            createdAt: DateTime.now().millisecondsSinceEpoch,
          ),
        );
        await _refreshOutboxCount();
        if (mounted) {
          showMessage(context, 'Message queued. It will send automatically when the connection returns.');
        }
      } else {
        restoringDraft = true;
        textController.value = TextEditingValue(
          text: text,
          selection: TextSelection.collapsed(offset: text.length),
        );
        restoringDraft = false;
        await _persistDraft(text);
        if (mounted) {
          setState(() {
            reply = currentReply;
            composerHasText = true;
          });
          showMessage(context, apiMessage(e));
        }
      }
    } finally {
      if (mounted) setState(() => sending = false);
    }
  }'''
text = replace_function(text, '  Future<void> _sendText() async {', send_text)

refresh = r'''  Future<void> _refreshOutboxCount() async {
    final count = await outbox.countForConversation(widget.conversation.id);
    if (!mounted) return;
    if (count == 0) outboxIssue = null;
    if (count != queuedMessages) setState(() => queuedMessages = count);
  }'''
text = replace_function(text, '  Future<void> _refreshOutboxCount() async {', refresh)

flush = r'''  Future<void> _flushOutbox() async {
    if (flushingOutbox || queuedMessages <= 0 || !mounted) return;
    flushingOutbox = true;
    var sentAny = false;
    try {
      final api = AppScope.of(context).api;
      final pending = await outbox.forConversation(widget.conversation.id);
      for (final item in pending) {
        try {
          await api.sendText(
            item.conversationId,
            item.text,
            replyTo: item.replyTo,
            clientToken: item.token,
          );
          await outbox.remove(item.token);
          sentAny = true;
          outboxIssue = null;
        } catch (e) {
          await outbox.updateAttempts(item.token, item.attempts + 1);
          if (_isPermanentOutboxError(e)) {
            outboxIssue = apiMessage(e);
            if (mounted) {
              setState(() {});
              showMessage(
                context,
                'A queued message needs review: ${apiMessage(e)}',
              );
            }
          }
          break;
        }
      }
      if (sentAny && mounted) await _syncAfterSend();
    } finally {
      flushingOutbox = false;
      await _refreshOutboxCount();
      if (mounted) setState(() {});
    }
  }'''
text = replace_function(text, '  Future<void> _flushOutbox() async {', flush)

outbox_bar = r'''  Widget _outboxBar() => Container(
        margin: const EdgeInsets.fromLTRB(10, 4, 10, 3),
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 9),
        decoration: BoxDecoration(
          color: (outboxIssue == null ? AppColors.violet : AppColors.danger)
              .withValues(alpha: .10),
          borderRadius: BorderRadius.circular(15),
          border: Border.all(
            color: (outboxIssue == null ? AppColors.violet : AppColors.danger)
                .withValues(alpha: .18),
          ),
        ),
        child: Row(
          children: [
            Icon(
              outboxIssue == null
                  ? Icons.cloud_upload_outlined
                  : Icons.edit_note_rounded,
              size: 18,
              color: outboxIssue == null ? AppColors.violet : AppColors.danger,
            ),
            const SizedBox(width: 8),
            Expanded(
              child: Text(
                outboxIssue == null
                    ? '$queuedMessages message${queuedMessages == 1 ? '' : 's'} waiting for connection'
                    : '$queuedMessages queued message${queuedMessages == 1 ? '' : 's'} · review needed',
                style: const TextStyle(fontSize: 11.5, fontWeight: FontWeight.w800),
              ),
            ),
            TextButton(
              onPressed: flushingOutbox
                  ? null
                  : (outboxIssue == null ? _flushOutbox : _reviewQueuedMessage),
              child: Text(outboxIssue == null ? 'Retry' : 'Review'),
            ),
          ],
        ),
      )'''
text = replace_function(text, '  Widget _outboxBar() => Container(', outbox_bar)

# Current v4.2 server deletes one-time media globally after consumption. That is
# correct for direct chats but not for groups with multiple recipients, so the
# client must not offer Once in group chats until per-recipient receipts exist.
ps, pe = function_bounds(text, '  Future<void> _pickAttachment() async {')
picker = text[ps:pe]
picker = picker.replace('segments: const [', 'segments: [', 1)
picker, n = re.subn(
    r'(ButtonSegment<bool>\(\s*value:\s*true,\s*)(icon:)',
    r'\1enabled: !widget.conversation.isGroup,\n                          \2',
    picker,
    count=1,
)
if n != 1:
    raise RuntimeError('v4.3 view-once segment marker missing')
animated = '              AnimatedSwitcher(\n'
if 'View once is available in direct chats only.' not in picker:
    if animated not in picker:
        raise RuntimeError('v4.3 view-once note marker missing')
    group_note = r'''              if (widget.conversation.isGroup)
                Container(
                  margin: const EdgeInsets.fromLTRB(16, 0, 16, 8),
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                  decoration: BoxDecoration(
                    color: AppColors.blue.withValues(alpha: .07),
                    borderRadius: BorderRadius.circular(13),
                  ),
                  child: const Row(
                    children: [
                      Icon(Icons.info_outline_rounded, size: 17, color: AppColors.blue),
                      SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          'View once is available in direct chats only.',
                          style: TextStyle(fontSize: 11.5, fontWeight: FontWeight.w700),
                        ),
                      ),
                    ],
                  ),
                ),
'''
    picker = picker.replace(animated, group_note + animated, 1)
text = text[:ps] + picker + text[pe:]

w(path, text)


# ---------------------------------------------------------------------------
# Call stability: avoid using a stale BuildContext after renderer/media awaits,
# and cache the API before signalling awaits.
# ---------------------------------------------------------------------------
path = 'flutter/lib/screens/call_screen.dart'
text = r(path)
ss, se = function_bounds(text, '  Future<void> _start() async {')
start_chunk = text[ss:se]
needle = '    await remoteRenderer.initialize();\n'
if '    if (!mounted) return;\n' not in start_chunk.split('    try {', 1)[0]:
    if needle not in start_chunk:
        raise RuntimeError('v4.3 call renderer marker missing')
    start_chunk = start_chunk.replace(needle, needle + '    if (!mounted) return;\n', 1)
text = text[:ss] + start_chunk + text[se:]

ps, pe = function_bounds(text, '  Future<void> _poll() async {')
poll_chunk = text[ps:pe]
old = """    try {
      final state = await AppScope.of(context).api.callState(
"""
new = """    final api = AppScope.of(context).api;
    try {
      final state = await api.callState(
"""
if old not in poll_chunk:
    raise RuntimeError('v4.3 call poll API marker missing')
poll_chunk = poll_chunk.replace(old, new, 1)
poll_chunk = poll_chunk.replace('await AppScope.of(context).api.sendCallSignal(', 'await api.sendCallSignal(')
text = text[:ps] + poll_chunk + text[pe:]
w(path, text)


# Release version.
path = 'flutter/pubspec.yaml'
pubspec = r(path)
pubspec = re.sub(r'^version:\s*[^\n]+', 'version: 4.3.0+430', pubspec, count=1, flags=re.M)
w(path, pubspec)

# Regression guarantees for the final generated source.
chat = r('flutter/lib/screens/chat_screen.dart')
call = r('flutter/lib/screens/call_screen.dart')
pubspec = r('flutter/pubspec.yaml')
assert "String get _draftKey => 'chat_draft_${widget.conversation.id}'" in chat
assert 'Timer? draftDebounce;' in chat and 'Duration(milliseconds: 350)' in chat
assert 'bool composerHasText = false;' in chat
assert 'if (mounted && composerHasText != hasText)' in chat
assert 'reply = currentReply;' in chat and "await _persistDraft(text);" in chat
assert '_isPermanentOutboxError' in chat and '_reviewQueuedMessage' in chat
assert 'review needed' in chat and "child: Text(outboxIssue == null ? 'Retry' : 'Review')" in chat
assert 'enabled: !widget.conversation.isGroup' in chat
assert 'View once is available in direct chats only.' in chat
assert 'Future<void> _syncAfterSend() async' in chat
assert 'recordingPaused = true;' in chat and 'await recorder.resume();' in chat
assert '_setSecureViewOnce(true)' in chat and '_setSecureViewOnce(false)' in chat
assert 'await remoteRenderer.initialize();\n    if (!mounted) return;' in call
assert 'final api = AppScope.of(context).api;\n    try {\n      final state = await api.callState(' in call
assert 'version: 4.3.0+430' in pubspec
print('TaleemPK v4.3 chat stability and draft recovery applied successfully')
