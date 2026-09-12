from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
script_path = ROOT / 'tools' / 'v43_chat_stability.py'
source = script_path.read_text(encoding='utf-8')

# v3.8+ owns the final composer and uses a block body.
old = "cs, ce = function_bounds(text, '  Widget _composer() => Container(')"
new = "cs, ce = function_bounds(text, '  Widget _composer() {')"
if old not in source:
    raise RuntimeError('v4.3b composer compatibility marker missing')
source = source.replace(old, new, 1)

# Arrow-bodied widgets do not have a function-body brace. The generic brace
# scanner therefore used to stop on ${...} interpolation inside _outboxBar,
# corrupting the rest of ChatScreen. Replace this one widget by explicit stable
# neighboring method boundaries instead.
source = source.replace(
    """        ),
      )'''
text = replace_function(text, '  Widget _outboxBar() => Container(', outbox_bar)""",
    """        ),
      );'''
outbox_start = text.find('  Widget _outboxBar() => Container(')
outbox_end = text.find('\\n\\n  Future<void> _pickAttachment() async {', outbox_start)
if outbox_start < 0 or outbox_end < 0:
    raise RuntimeError('v4.3 generated outbox boundary missing')
text = text[:outbox_start] + outbox_bar + text[outbox_end:]""",
    1,
)
if "outbox_end = text.find('\\n\\n  Future<void> _pickAttachment() async {'" not in source:
    raise RuntimeError('v4.3b outbox safe-boundary rewrite missing')

# Preserve native E2EE + group mentions from v3.2 while adding v4.3 draft and
# failure recovery. Encryption preparation failures must never be mistaken for
# an offline transport failure and queued as plaintext.
send_start = source.find("send_text = r'''")
send_marker = "text = replace_function(text, '  Future<void> _sendText() async {', send_text)"
send_call = source.find(send_marker, send_start)
if send_start < 0 or send_call < 0:
    raise RuntimeError('v4.3b sendText source boundary missing')
send_end = send_call + len(send_marker)
send_replacement = r"""send_text = r'''  Future<void> _sendText() async {
    if (_chatBlocked) return;
    final plainText = textController.text.trim();
    if (plainText.isEmpty) return;
    final currentReply = reply;
    final api = AppScope.of(context).api;
    final token = api.newClientToken();
    final mentions = _mentionIds(plainText);
    setState(() {
      sending = true;
      reply = null;
      composerHasText = false;
    });
    textController.clear();
    await _persistDraft('');

    var wireText = plainText;
    var encrypted = false;
    var wireReady = !e2eeState.enabled;
    try {
      if (e2eeState.enabled) {
        wireText = await e2ee.encryptText(widget.conversation, plainText);
        encrypted = true;
        wireReady = true;
      }
      await api.sendText(
        widget.conversation.id,
        wireText,
        replyTo: currentReply?.id,
        clientToken: token,
        encrypted: encrypted,
        mentionIds: mentions,
      );
      await _syncAfterSend();
    } catch (e) {
      if (wireReady && e is ApiException && e.status == 0) {
        await outbox.enqueue(
          OutboxItem(
            token: token,
            conversationId: widget.conversation.id,
            text: wireText,
            replyTo: currentReply?.id,
            createdAt: DateTime.now().millisecondsSinceEpoch,
            encrypted: encrypted,
            mentionIds: mentions,
          ),
        );
        await _refreshOutboxCount();
        if (mounted) {
          showMessage(
            context,
            encrypted
                ? 'Encrypted message queued. It will send when the connection returns.'
                : 'Message queued. It will send automatically when the connection returns.',
          );
        }
      } else {
        restoringDraft = true;
        textController.value = TextEditingValue(
          text: plainText,
          selection: TextSelection.collapsed(offset: plainText.length),
        );
        restoringDraft = false;
        await _persistDraft(plainText);
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
text = replace_function(text, '  Future<void> _sendText() async {', send_text)"""
source = source[:send_start] + send_replacement + source[send_end:]

# Preserve encrypted/mention metadata when retrying queued messages. A 4xx
# rejection is surfaced as review-needed instead of looping forever.
flush_start = source.find("flush = r'''")
flush_marker = "text = replace_function(text, '  Future<void> _flushOutbox() async {', flush)"
flush_call = source.find(flush_marker, flush_start)
if flush_start < 0 or flush_call < 0:
    raise RuntimeError('v4.3b outbox retry source boundary missing')
flush_end = flush_call + len(flush_marker)
flush_replacement = r"""flush = r'''  Future<void> _flushOutbox() async {
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
            encrypted: item.encrypted,
            mentionIds: item.mentionIds,
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
text = replace_function(text, '  Future<void> _flushOutbox() async {', flush)"""
source = source[:flush_start] + flush_replacement + source[flush_end:]

# Never put encrypted ciphertext into the visible composer during manual queue
# recovery. Let the user explicitly discard that rejected encrypted queue item.
review_old = r'''    final item = pending.first;
    await outbox.remove(item.token);'''
review_new = r'''    final item = pending.first;
    if (item.encrypted) {
      if (!mounted) return;
      final discard = await showDialog<bool>(
        context: context,
        builder: (dialog) => AlertDialog(
          title: const Text('Encrypted message needs review'),
          content: const Text(
            'This queued encrypted message cannot be safely converted back into editable text. Discard it and type the message again?',
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(dialog, false),
              child: const Text('Keep queued'),
            ),
            FilledButton(
              onPressed: () => Navigator.pop(dialog, true),
              child: const Text('Discard'),
            ),
          ],
        ),
      );
      if (discard == true) {
        await outbox.remove(item.token);
        outboxIssue = null;
        await _refreshOutboxCount();
        if (mounted) showMessage(context, 'Encrypted queued message discarded.');
      }
      return;
    }
    await outbox.remove(item.token);'''
if review_old not in source:
    raise RuntimeError('v4.3b queue review marker missing')
source = source.replace(review_old, review_new, 1)

code = compile(source, str(script_path), 'exec')
exec(code, {'__name__': '__main__', '__file__': str(script_path)})

# v4.2 server consumption is global, so view-once must stay direct-chat-only
# for voice as well as photos until per-recipient group consumption is added.
chat_path = ROOT / 'flutter/lib/screens/chat_screen.dart'
chat = chat_path.read_text(encoding='utf-8')
voice_tooltip_old = "tooltip: voicePreviewViewOnce ? 'View once enabled' : 'Send as view once',"
voice_tooltip_new = """tooltip: widget.conversation.isGroup
                  ? 'View once is available in direct chats only'
                  : (voicePreviewViewOnce ? 'View once enabled' : 'Send as view once'),"""
if voice_tooltip_old not in chat:
    raise RuntimeError('v4.3b voice once tooltip marker missing')
chat = chat.replace(voice_tooltip_old, voice_tooltip_new, 1)
voice_toggle_old = """onPressed: sending
                  ? null
                  : () => setState(() => voicePreviewViewOnce = !voicePreviewViewOnce),"""
voice_toggle_new = """onPressed: sending || widget.conversation.isGroup
                  ? null
                  : () => setState(() => voicePreviewViewOnce = !voicePreviewViewOnce),"""
if voice_toggle_old not in chat:
    raise RuntimeError('v4.3b voice once toggle marker missing')
chat = chat.replace(voice_toggle_old, voice_toggle_new, 1)
if 'final sendViewOnce = voicePreviewViewOnce;' in chat:
    chat = chat.replace(
        'final sendViewOnce = voicePreviewViewOnce;',
        'final sendViewOnce = voicePreviewViewOnce && !widget.conversation.isGroup;',
        1,
    )
else:
    raise RuntimeError('v4.3b voice send once marker missing')
chat_path.write_text(chat, encoding='utf-8')

chat = chat_path.read_text(encoding='utf-8')
assert 'mentionIds: mentions' in chat
assert 'encrypted: encrypted' in chat
assert 'encrypted: item.encrypted' in chat and 'mentionIds: item.mentionIds' in chat
assert 'wireReady && e is ApiException && e.status == 0' in chat
assert 'sending || widget.conversation.isGroup' in chat
assert 'voicePreviewViewOnce && !widget.conversation.isGroup' in chat
print('TaleemPK v4.3 compatibility, E2EE and direct-only view-once fixes applied successfully')
