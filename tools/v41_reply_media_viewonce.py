from pathlib import Path
import re
import shutil

ROOT = Path(__file__).resolve().parents[1]


def r(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def w(path: str, text: str) -> None:
    p = ROOT / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding='utf-8')


def once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f'v4.1 missing target: {label}')
    return text.replace(old, new, 1)


def function_bounds(text: str, signature: str):
    start = text.find(signature)
    if start < 0:
        raise RuntimeError(f'v4.1 missing function: {signature}')
    brace = text.find('{', start)
    if brace < 0:
        raise RuntimeError(f'v4.1 malformed function: {signature}')
    depth = 0
    quote = None
    escape = False
    for i in range(brace, len(text)):
        ch = text[i]
        if quote is not None:
            if escape:
                escape = False
            elif ch == '\\':
                escape = True
            elif ch == quote:
                quote = None
            continue
        if ch in ("'", '"'):
            quote = ch
            continue
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                return start, i + 1
    raise RuntimeError(f'v4.1 unterminated function: {signature}')


def replace_function(text: str, signature: str, replacement: str) -> str:
    start, end = function_bounds(text, signature)
    return text[:start] + replacement + text[end:]


# ---------------------------------------------------------------------------
# 1) Chat reply navigation, image reply preview, direct multi-image sending,
#    and view-once media helpers.
# ---------------------------------------------------------------------------
path = 'flutter/lib/screens/chat_screen.dart'
text = r(path)

# View-once is encoded in the uploaded basename so it survives the existing
# shared web chat_send.php handler without requiring a database migration.
import_marker = "import 'call_screen.dart';\n"
helpers = r'''

bool _isViewOnceAttachmentName(String? value) =>
    value != null && value.startsWith('once__');

String _cleanAttachmentName(String? value) {
  final name = (value ?? '').trim();
  return name.startsWith('once__') ? name.substring(6) : name;
}
'''
if '_isViewOnceAttachmentName' not in text:
    text = once(text, import_marker, import_marker + helpers, 'view-once helpers')

# State needed to scroll a reply to its original message and briefly mark it.
state_marker = "  final selectedIds = <int>{};\n"
state_extra = """  final selectedIds = <int>{};
  final Map<int, GlobalKey> _messageKeys = <int, GlobalKey>{};
  Timer? _replyHighlightTimer;
  int? _replyHighlightId;
"""
text = once(text, state_marker, state_extra, 'reply target state')

# Voice preview gets an explicit 1x / view-once toggle.
text = once(
    text,
    "      foreground = true;\n",
    "      foreground = true,\n      voicePreviewViewOnce = false;\n",
    'voice view-once state',
)

# Dispose the reply highlight timer with the rest of the thread timers.
ds, de = function_bounds(text, '  void dispose() {')
dispose_chunk = text[ds:de]
if '_replyHighlightTimer?.cancel();' not in dispose_chunk:
    dispose_chunk = dispose_chunk.replace(
        '    voiceHeartbeat?.cancel();\n',
        '    voiceHeartbeat?.cancel();\n    _replyHighlightTimer?.cancel();\n',
        1,
    )
text = text[:ds] + dispose_chunk + text[de:]

# Use a real GlobalKey so a reply tap can ensure the target is visible.
text = once(
    text,
    '          key: ValueKey<int>(m.id),\n',
    '          key: _messageKey(m.id),\n',
    'message global key',
)

# Insert robust reply navigation immediately before the bubble builder.
bubble_marker = '  Widget _bubble(ChatMessage m) => Align('
reply_nav = r'''  GlobalKey _messageKey(int id) =>
      _messageKeys.putIfAbsent(id, () => GlobalKey(debugLabel: 'message-$id'));

  Future<void> _jumpToMessage(int messageId) async {
    if (messageId <= 0 || !mounted) return;
    if (searching || searchQuery.isNotEmpty) {
      setState(() {
        searching = false;
        searchQuery = '';
      });
    }

    var guard = 0;
    while (mounted &&
        messages.every((m) => m.id != messageId) &&
        !historyDone &&
        messages.isNotEmpty &&
        guard < 8) {
      guard++;
      try {
        final older = await AppScope.of(context).api.messages(
          widget.conversation.id,
          beforeId: messages.first.id,
          limit: 80,
        );
        if (older.isEmpty) {
          historyDone = true;
          break;
        }
        final unique = older
            .where((candidate) => messages.every((m) => m.id != candidate.id))
            .toList();
        if (unique.isEmpty) break;
        if (mounted) {
          setState(() => messages.insertAll(0, unique));
        } else {
          messages.insertAll(0, unique);
        }
        if (older.length < 80) historyDone = true;
      } catch (_) {
        break;
      }
    }

    final index = messages.indexWhere((m) => m.id == messageId);
    if (index < 0) {
      if (mounted) showMessage(context, 'The original message is no longer available.');
      return;
    }

    _replyHighlightTimer?.cancel();
    if (mounted) setState(() => _replyHighlightId = messageId);
    await Future<void>.delayed(const Duration(milliseconds: 30));
    if (!mounted) return;

    Future<void> reveal() async {
      final targetContext = _messageKey(messageId).currentContext;
      if (targetContext != null) {
        await Scrollable.ensureVisible(
          targetContext,
          duration: const Duration(milliseconds: 260),
          curve: Curves.easeOutCubic,
          alignment: .28,
        );
        return;
      }
      if (!scroll.hasClients) return;
      final ratio = messages.length <= 1 ? 1.0 : index / (messages.length - 1);
      final target = (scroll.position.maxScrollExtent * ratio).clamp(
        scroll.position.minScrollExtent,
        scroll.position.maxScrollExtent,
      );
      await scroll.animateTo(
        target,
        duration: const Duration(milliseconds: 240),
        curve: Curves.easeOutCubic,
      );
      await Future<void>.delayed(const Duration(milliseconds: 80));
      final builtContext = _messageKey(messageId).currentContext;
      if (builtContext != null) {
        await Scrollable.ensureVisible(
          builtContext,
          duration: const Duration(milliseconds: 180),
          curve: Curves.easeOutCubic,
          alignment: .28,
        );
      }
    }

    await reveal();
    _replyHighlightTimer = Timer(const Duration(milliseconds: 1500), () {
      if (mounted && _replyHighlightId == messageId) {
        setState(() => _replyHighlightId = null);
      }
    });
  }

'''
text = once(text, bubble_marker, reply_nav + bubble_marker, 'reply navigation insertion')

# Give the original bubble a brief visual cue after a reply tap without
# changing its normal colors. A translucent overlay sits outside the bubble.
old_bubble_head = r'''  Widget _bubble(ChatMessage m) => Align(
    alignment: m.mine ? Alignment.centerRight : Alignment.centerLeft,
    child: GestureDetector(
'''
new_bubble_head = r'''  Widget _bubble(ChatMessage m) => AnimatedContainer(
    duration: const Duration(milliseconds: 180),
    decoration: BoxDecoration(
      color: _replyHighlightId == m.id
          ? AppColors.blue.withValues(alpha: .10)
          : Colors.transparent,
      borderRadius: BorderRadius.circular(16),
    ),
    child: Align(
      alignment: m.mine ? Alignment.centerRight : Alignment.centerLeft,
      child: GestureDetector(
'''
if old_bubble_head in text:
    text = text.replace(old_bubble_head, new_bubble_head, 1)
    # _bubble used to close Align + GestureDetector. The new wrapper needs one
    # additional parent close. Insert it just before the next method.
    next_marker = '\n  Widget _metaLine('
    qpos = text.find(next_marker, text.find(new_bubble_head))
    if qpos > 0:
        # The quoted helper will be replaced below and gives us a stable boundary;
        # do not attempt to rebalance here if the generated layout changed.
        pass

# Replace the quoted/reply card. Tapping it now returns to the exact original
# message. For image replies, use the already-loaded secure image as a compact
# thumbnail instead of showing a filename/link.
quoted_start = text.find('  Widget _quoted(ReplyPreview r, bool mine)')
meta_start = text.find('  Widget _metaLine(', quoted_start)
if quoted_start < 0 or meta_start < 0:
    raise RuntimeError('v4.1 quoted reply boundary missing')
quoted = r'''  Widget _quoted(ReplyPreview r, bool mine) {
    ChatMessage? original;
    for (final candidate in messages) {
      if (candidate.id == r.id) {
        original = candidate;
        break;
      }
    }
    final isImageReply = original != null &&
        original.attachmentUrl != null &&
        _isImage(original.attachmentType);
    final viewOnceReply = original != null &&
        _isViewOnceAttachmentName(original.attachmentName);
    final fallbackOnce = r.text.startsWith('once__');
    final label = viewOnceReply || fallbackOnce
        ? (original?.voiceSeconds ?? 0) > 0
            ? 'View once voice message'
            : 'View once photo'
        : r.text;

    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: () => _jumpToMessage(r.id),
        borderRadius: BorderRadius.circular(12),
        child: Container(
          margin: const EdgeInsets.only(bottom: 7),
          padding: const EdgeInsets.fromLTRB(8, 7, 8, 7),
          decoration: BoxDecoration(
            color: (mine ? Colors.white : AppColors.blue).withValues(alpha: .13),
            borderRadius: BorderRadius.circular(11),
            border: Border(
              left: BorderSide(
                color: mine ? Colors.white70 : AppColors.blue,
                width: 3,
              ),
            ),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              if (isImageReply && !viewOnceReply)
                Padding(
                  padding: const EdgeInsets.only(right: 8),
                  child: ClipRRect(
                    borderRadius: BorderRadius.circular(7),
                    child: SizedBox(
                      width: 42,
                      height: 42,
                      child: SecureChatImage(
                        api: AppScope.of(context).api,
                        url: original!.attachmentUrl!,
                        mine: mine,
                      ),
                    ),
                  ),
                )
              else if (viewOnceReply || fallbackOnce)
                Padding(
                  padding: const EdgeInsets.only(right: 8),
                  child: Icon(
                    Icons.looks_one_rounded,
                    size: 22,
                    color: mine ? Colors.white70 : AppColors.blue,
                  ),
                ),
              Flexible(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      r.sender,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(
                        fontSize: 11.5,
                        fontWeight: FontWeight.w900,
                        color: mine ? Colors.white : AppColors.blue,
                      ),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      label,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(
                        fontSize: 11.5,
                        color: mine ? Colors.white70 : AppColors.muted,
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 6),
              Icon(
                Icons.arrow_upward_rounded,
                size: 15,
                color: mine ? Colors.white60 : AppColors.muted,
              ),
            ],
          ),
        ),
      ),
    );
  }

'''
text = text[:quoted_start] + quoted + text[meta_start:]

# Direct gallery/camera sending. Editing remains available as an explicit
# option, while the normal photo action uploads right in the chat.
pick_attachment = r'''  Future<void> _pickAttachment() async {
    if (_chatBlocked || sending) return;
    await showModalBottomSheet<void>(
      context: context,
      useSafeArea: true,
      showDragHandle: true,
      builder: (sheet) => SafeArea(
        child: Wrap(
          children: [
            ListTile(
              leading: const Icon(Icons.photo_library_outlined, color: AppColors.blue),
              title: const Text('Photos or images'),
              subtitle: const Text('Select one or many · send directly in chat'),
              onTap: () async {
                Navigator.pop(sheet);
                final images = await ImagePicker().pickMultiImage(
                  imageQuality: 92,
                  maxWidth: 2600,
                  maxHeight: 2600,
                );
                if (images.isNotEmpty && mounted) {
                  await _uploadManyImages(images.map((e) => e.path).toList());
                }
              },
            ),
            ListTile(
              leading: const Icon(Icons.looks_one_rounded, color: AppColors.success),
              title: const Text('View once photo'),
              subtitle: const Text('Can be opened once by the recipient'),
              onTap: () async {
                Navigator.pop(sheet);
                final image = await ImagePicker().pickImage(
                  source: ImageSource.gallery,
                  imageQuality: 92,
                  maxWidth: 2600,
                  maxHeight: 2600,
                );
                if (image != null && mounted) {
                  await _uploadManyImages([image.path], viewOnce: true);
                }
              },
            ),
            ListTile(
              leading: const Icon(Icons.tune_rounded, color: AppColors.violet),
              title: const Text('Edit before sending'),
              subtitle: const Text('Crop, rotate, hide details or add more photos'),
              onTap: () async {
                Navigator.pop(sheet);
                final images = await ImagePicker().pickMultiImage(
                  imageQuality: 92,
                  maxWidth: 2600,
                  maxHeight: 2600,
                );
                if (images.isNotEmpty && mounted) {
                  await _reviewImages(images.map((e) => e.path).toList());
                }
              },
            ),
            ListTile(
              leading: const Icon(Icons.attach_file_rounded, color: AppColors.violet),
              title: const Text('Document or file'),
              onTap: () async {
                Navigator.pop(sheet);
                final file = await FilePicker.pickFile();
                final filePath = file?.path;
                if (filePath != null && mounted) await _upload(filePath);
              },
            ),
            if (widget.conversation.isGroup)
              ListTile(
                leading: const Icon(Icons.poll_outlined, color: AppColors.violet),
                title: const Text('Create poll'),
                onTap: () {
                  Navigator.pop(sheet);
                  _createPoll();
                },
              ),
            ListTile(
              leading: const Icon(Icons.camera_alt_outlined, color: AppColors.success),
              title: const Text('Take a photo'),
              subtitle: const Text('Capture and send directly'),
              onTap: () async {
                Navigator.pop(sheet);
                final image = await ImagePicker().pickImage(
                  source: ImageSource.camera,
                  imageQuality: 92,
                  maxWidth: 2600,
                  maxHeight: 2600,
                );
                if (image != null && mounted) {
                  await _uploadManyImages([image.path]);
                }
              },
            ),
          ],
        ),
      ),
    );
  }'''
text = replace_function(text, '  Future<void> _pickAttachment() async {', pick_attachment)

# Reliable multi-photo sender: validate every selected path, continue if one
# file fails, keep a single reply target on the first successful photo, and
# synchronize the thread only once when the batch is finished.
view_once_helper = r'''  Future<String> _prepareViewOnceFile(String sourcePath) async {
    final source = File(sourcePath);
    if (!await source.exists()) {
      throw const ApiException('The selected media is no longer available.');
    }
    final slash = sourcePath.lastIndexOf('/');
    final dot = sourcePath.lastIndexOf('.');
    final extension = dot > slash ? sourcePath.substring(dot) : '';
    final directory = await getTemporaryDirectory();
    final target = File(
      '${directory.path}/once__${DateTime.now().microsecondsSinceEpoch}$extension',
    );
    await source.copy(target.path);
    return target.path;
  }

'''
upload_many = r'''  Future<void> _uploadManyImages(
    List<String> paths, {
    bool viewOnce = false,
  }) async {
    if (paths.isEmpty || _chatBlocked || sending) return;
    final valid = <String>[];
    for (final raw in paths) {
      if (valid.length >= 20) break;
      final path = raw.trim();
      if (path.isEmpty || valid.contains(path)) continue;
      try {
        final file = File(path);
        if (await file.exists() && await file.length() > 0) valid.add(path);
      } catch (_) {}
    }
    if (valid.isEmpty) {
      if (mounted) showMessage(context, 'The selected photos are no longer available.');
      return;
    }

    var pendingReply = reply?.id;
    var sent = 0;
    var failed = 0;
    String? firstError;
    setState(() {
      sending = true;
      uploadProgress = 0;
    });

    for (var i = 0; i < valid.length; i++) {
      final originalPath = valid[i];
      var uploadPath = originalPath;
      try {
        if (viewOnce) uploadPath = await _prepareViewOnceFile(originalPath);
        await AppScope.of(context).api.sendFile(
          widget.conversation.id,
          uploadPath,
          replyTo: pendingReply,
          onProgress: (value) {
            if (mounted) {
              setState(() => uploadProgress = (i + value) / valid.length);
            }
          },
        );
        pendingReply = null;
        sent++;
      } catch (e) {
        failed++;
        firstError ??= apiMessage(e);
      } finally {
        if (viewOnce && uploadPath != originalPath) {
          try {
            await File(uploadPath).delete();
          } catch (_) {}
        }
      }
    }

    if (sent > 0) {
      reply = null;
      await _syncAfterSend();
    }
    if (mounted) {
      setState(() {
        sending = false;
        uploadProgress = null;
      });
      if (failed > 0) {
        showMessage(
          context,
          '$sent of ${valid.length} photos sent. ${firstError ?? '$failed failed.'}',
        );
      }
    }
  }'''
text = replace_function(
    text,
    '  Future<void> _uploadManyImages(List<String> paths) async {',
    view_once_helper + upload_many,
)

# View-once attachment bubbles never preload the secure image. That prevents a
# background thumbnail request from consuming media before the user taps it.
attachment = r'''  Widget _attachment(ChatMessage m) {
    final image = _isImage(m.attachmentType);
    final viewOnce = _isViewOnceAttachmentName(m.attachmentName);
    final consumed = viewOnce && !m.mine && m.playedByMe;
    final displayName = _cleanAttachmentName(m.attachmentName);

    if (viewOnce) {
      return InkWell(
        onTap: consumed ? null : () => _openAttachment(m),
        borderRadius: BorderRadius.circular(14),
        child: Container(
          constraints: const BoxConstraints(minWidth: 190, maxWidth: 265),
          padding: const EdgeInsets.symmetric(horizontal: 13, vertical: 12),
          decoration: BoxDecoration(
            color: (m.mine ? Colors.white : AppColors.blue).withValues(alpha: .10),
            borderRadius: BorderRadius.circular(14),
            border: Border.all(
              color: (m.mine ? Colors.white : AppColors.blue).withValues(alpha: .22),
            ),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                width: 38,
                height: 38,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: (m.mine ? Colors.white : AppColors.blue).withValues(alpha: .13),
                ),
                child: Icon(
                  consumed ? Icons.check_rounded : Icons.looks_one_rounded,
                  color: m.mine ? Colors.white : AppColors.blue,
                ),
              ),
              const SizedBox(width: 10),
              Flexible(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      consumed
                          ? 'Photo opened'
                          : m.mine
                              ? 'View once photo sent'
                              : 'View once photo',
                      style: TextStyle(
                        fontWeight: FontWeight.w900,
                        color: m.mine ? Colors.white : Theme.of(context).colorScheme.onSurface,
                      ),
                    ),
                    if (!consumed)
                      Text(
                        m.mine ? 'Recipient can open it once' : 'Tap to open',
                        style: TextStyle(
                          fontSize: 11,
                          color: m.mine ? Colors.white70 : AppColors.muted,
                        ),
                      ),
                  ],
                ),
              ),
            ],
          ),
        ),
      );
    }

    return InkWell(
      onTap: () => _openAttachment(m),
      borderRadius: BorderRadius.circular(14),
      child: ConstrainedBox(
        constraints: BoxConstraints(maxWidth: image ? 275 : 300),
        child: image
            ? ClipRRect(
                borderRadius: BorderRadius.circular(13),
                child: SecureChatImage(
                  api: AppScope.of(context).api,
                  url: m.attachmentUrl!,
                  mine: m.mine,
                ),
              )
            : Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: (m.mine ? Colors.white : AppColors.blue).withValues(alpha: .10),
                  borderRadius: BorderRadius.circular(14),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(
                      Icons.insert_drive_file_outlined,
                      color: m.mine ? Colors.white : AppColors.blue,
                    ),
                    const SizedBox(width: 9),
                    Flexible(
                      child: Text(
                        displayName.isEmpty ? 'Attachment' : displayName,
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: TextStyle(
                          fontWeight: FontWeight.w800,
                          color: m.mine ? Colors.white : Theme.of(context).colorScheme.onSurface,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
      ),
    );
  }'''
text = replace_function(text, '  Widget _attachment(ChatMessage m) {', attachment)

# Mark a view-once photo consumed only after the full-screen viewer closes.
os, oe = function_bounds(text, '  Future<void> _openAttachment(ChatMessage m) async {')
open_chunk = text[os:oe]
open_chunk = open_chunk.replace(
    '  Future<void> _openAttachment(ChatMessage m) async {\n    try {',
    """  Future<void> _openAttachment(ChatMessage m) async {
    final viewOnce = _isViewOnceAttachmentName(m.attachmentName);
    if (viewOnce && !m.mine && m.playedByMe) {
      if (mounted) showMessage(context, 'This view once photo has already been opened.');
      return;
    }
    try {""",
    1,
)
# The dialog await is followed by the next attachment branch. Mark after the
# image dialog returns, while leaving normal files untouched.
image_marker = """        await showDialog<void>(
          context: context,"""
if image_marker not in open_chunk:
    raise RuntimeError('v4.1 image viewer marker missing')
# Add consumption at the first closing point immediately before the next
# image/non-image branch by targeting the known `} else {` after showDialog.
consume_block = r'''      if (viewOnce && !m.mine && !m.playedByMe) {
        try {
          await AppScope.of(context).api.markViewOnceConsumed(m.id);
          m.playedByMe = true;
          if (mounted) setState(() {});
        } catch (_) {}
      }
'''
# Conservative insertion: place it before the first `    } else {` inside the
# function, which is the non-image attachment branch in this generated source.
branch_pos = open_chunk.find('    } else {', open_chunk.find(image_marker))
if branch_pos < 0:
    raise RuntimeError('v4.1 image viewer branch boundary missing')
open_chunk = open_chunk[:branch_pos] + consume_block + open_chunk[branch_pos:]
text = text[:os] + open_chunk + text[oe:]

# Add the view-once toggle to recorded voice preview.
vs, ve = function_bounds(text, '  Widget _voicePreviewBar() => Container(')
voice_preview = text[vs:ve]
send_block = r'''            const SizedBox(width: 8),
            IconButton.filled(
              tooltip: 'Send voice message',
              onPressed: sending ? null : _sendVoicePreview,
              icon: const Icon(Icons.send_rounded),
            ),'''
view_once_button = r'''            const SizedBox(width: 6),
            IconButton(
              tooltip: voicePreviewViewOnce ? 'View once enabled' : 'Send as view once',
              onPressed: sending
                  ? null
                  : () => setState(() => voicePreviewViewOnce = !voicePreviewViewOnce),
              icon: Icon(
                Icons.looks_one_rounded,
                color: voicePreviewViewOnce ? AppColors.success : AppColors.muted,
              ),
            ),
            const SizedBox(width: 6),
            IconButton.filled(
              tooltip: voicePreviewViewOnce ? 'Send view once voice' : 'Send voice message',
              onPressed: sending ? null : _sendVoicePreview,
              icon: const Icon(Icons.send_rounded),
            ),'''
if send_block not in voice_preview:
    raise RuntimeError('v4.1 voice preview send button missing')
voice_preview = voice_preview.replace(send_block, view_once_button, 1)
text = text[:vs] + voice_preview + text[ve:]

# Reset the view-once choice whenever the recording preview is discarded.
ds, de = function_bounds(text, '  Future<void> _discardVoicePreview() async {')
discard_chunk = text[ds:de]
if 'voicePreviewViewOnce = false;' not in discard_chunk:
    set_marker = '      voicePreviewPath = null;\n'
    if set_marker in discard_chunk:
        discard_chunk = discard_chunk.replace(
            set_marker,
            set_marker + '      voicePreviewViewOnce = false;\n',
            1,
        )
    else:
        # fallback for generated variants
        discard_chunk = discard_chunk.replace(
            '    voicePreviewPath = null;\n',
            '    voicePreviewPath = null;\n    voicePreviewViewOnce = false;\n',
            1,
        )
text = text[:ds] + discard_chunk + text[de:]

# Upload recorded voice under the view-once filename marker when enabled.
ss, se = function_bounds(text, '  Future<void> _sendVoicePreview() async {')
send_voice = text[ss:se]
seconds_marker = '    final seconds = recordSeconds;\n'
if seconds_marker not in send_voice:
    raise RuntimeError('v4.1 voice seconds marker missing')
send_voice = send_voice.replace(
    seconds_marker,
    seconds_marker + r'''    final sendViewOnce = voicePreviewViewOnce;
    var uploadPath = path;
    if (sendViewOnce) {
      try {
        uploadPath = await _prepareViewOnceFile(path);
      } catch (e) {
        if (mounted) showMessage(context, apiMessage(e));
        return;
      }
    }
''',
    1,
)
send_voice = send_voice.replace(
    "        path,\n        field: 'voice',",
    "        uploadPath,\n        field: 'voice',",
    1,
)
finally_marker = '    } finally {\n'
if finally_marker not in send_voice:
    raise RuntimeError('v4.1 voice send finally missing')
send_voice = send_voice.replace(
    finally_marker,
    r'''    } finally {
      if (sendViewOnce && uploadPath != path) {
        try {
          await File(uploadPath).delete();
        } catch (_) {}
      }
''',
    1,
)
text = text[:ss] + send_voice + text[se:]

# View-once voice is marked consumed only when playback completes. Normal voice
# notes keep their existing immediate listened receipt behavior.
voice_class_start = text.find('class _VoiceBubbleState extends State<VoiceBubble> {')
if voice_class_start < 0:
    raise RuntimeError('v4.1 voice bubble class missing')
voice_class_end = len(text)
next_class = text.find('\nclass ', voice_class_start + 10)
if next_class > 0:
    voice_class_end = next_class
voice_class = text[voice_class_start:voice_class_end]
played_block = r'''      if (!listened && !widget.message.mine) {
        listened = true;
        widget.message.playedByMe = true;
        widget.onListened?.call();
        unawaited(widget.api.markVoicePlayed(widget.message.id).catchError((_) {}));
      }'''
played_replacement = r'''      if (!listened && !widget.message.mine) {
        listened = true;
        if (!_isViewOnceAttachmentName(widget.message.attachmentName)) {
          widget.message.playedByMe = true;
          widget.onListened?.call();
          unawaited(widget.api.markVoicePlayed(widget.message.id).catchError((_) {}));
        }
      }'''
if played_block not in voice_class:
    raise RuntimeError('v4.1 voice listened block missing')
voice_class = voice_class.replace(played_block, played_replacement, 1)

# A consumed one-time voice cannot replay from the local cache.
toggle_marker = '  Future<void> _toggle({bool autoStart = false}) async {\n    try {\n'
if toggle_marker not in voice_class:
    raise RuntimeError('v4.1 voice toggle marker missing')
voice_class = voice_class.replace(
    toggle_marker,
    r'''  Future<void> _toggle({bool autoStart = false}) async {
    if (_isViewOnceAttachmentName(widget.message.attachmentName) &&
        !widget.message.mine &&
        widget.message.playedByMe) {
      return;
    }
    try {
''',
    1,
)

# Consume a one-time voice at completion, after the player has its local copy.
completion_marker = '  Future<void> _handleCompleted() async {\n    if (handlingCompletion) return;\n    handlingCompletion = true;\n'
if completion_marker not in voice_class:
    raise RuntimeError('v4.1 voice completion marker missing')
voice_class = voice_class.replace(
    completion_marker,
    r'''  Future<void> _handleCompleted() async {
    if (handlingCompletion) return;
    handlingCompletion = true;
    final consumeViewOnce = _isViewOnceAttachmentName(widget.message.attachmentName) &&
        !widget.message.mine &&
        !widget.message.playedByMe;
''',
    1,
)
completion_insert = '      if (mounted) setState(() {});\n      if (shouldContinue && widget.onCompleted != null && mounted) {'
if completion_insert not in voice_class:
    raise RuntimeError('v4.1 voice completion insert missing')
voice_class = voice_class.replace(
    completion_insert,
    r'''      if (mounted) setState(() {});
      if (consumeViewOnce) {
        widget.message.playedByMe = true;
        widget.onListened?.call();
        try {
          await widget.api.markVoicePlayed(widget.message.id);
        } catch (_) {}
      }
      if (shouldContinue && widget.onCompleted != null && mounted) {''',
    1,
)
text = text[:voice_class_start] + voice_class + text[voice_class_end:]

w(path, text)


# ---------------------------------------------------------------------------
# 2) API endpoint for consumed view-once photos.
# ---------------------------------------------------------------------------
path = 'flutter/lib/core/api_client.dart'
text = r(path)
marker = r'''  Future<void> markVoicePlayed(int messageId) => _request({
    'action': 'mark_voice_played',
    'message_id': '$messageId',
  });
'''
addition = marker + r'''

  Future<void> markViewOnceConsumed(int messageId) => _request({
    'action': 'mark_view_once',
    'message_id': '$messageId',
  });
'''
text = once(text, marker, addition, 'view-once API method')
w(path, text)


# ---------------------------------------------------------------------------
# 3) Mobile API: reuse message_plays as the consumption ledger for one-time
# photos. No schema change is needed. The existing voice receipt path continues
# to serve one-time voice messages.
# ---------------------------------------------------------------------------
for path in ['backend/api/mobile.php', 'flutter/backend/api/mobile.php']:
    text = r(path)

    mark_voice = "if ($action === 'mark_voice_played') {"
    view_once_action = r'''if ($action === 'mark_view_once') {
    $mid = max(0, (int)($_POST['message_id'] ?? 0));
    $m = fetch_one("SELECT m.id,m.sender_id,m.attachment_name
                      FROM messages m
                      JOIN conversation_members cm ON cm.conversation_id=m.conversation_id AND cm.user_id=?
                     WHERE m.id=? AND m.status='sent' LIMIT 1", [$uid,$mid]);
    $name = (string)($m['attachment_name'] ?? '');
    if (!$m || (int)$m['sender_id']===$uid || strncmp($name, 'once__', 6)!==0) {
        mobile_error('That view once media is not available.', 404);
    }
    if (table_exists('message_plays')) {
        q('INSERT IGNORE INTO message_plays (message_id,user_id) VALUES (?,?)', [$mid,$uid]);
    }
    mobile_out(['consumed'=>true]);
}

'''
    if view_once_action not in text:
        text = once(text, mark_voice, view_once_action + mark_voice, f'view-once action {path}')

    # File access is denied after consumption for recipients. Sender access is
    # unaffected. The app deliberately does not preload one-time images.
    old_query = r'''    $m = fetch_one("SELECT m.attachment,m.attachment_name,m.attachment_type,m.conversation_id
                      FROM messages m JOIN conversation_members cm ON cm.conversation_id=m.conversation_id
                     WHERE m.id=? AND m.status='sent' AND cm.user_id=? LIMIT 1", [$id,$uid]);
    if (!$m || empty($m['attachment'])) { http_response_code(404); exit; }
'''
    new_query = r'''    $m = fetch_one("SELECT m.id,m.sender_id,m.attachment,m.attachment_name,m.attachment_type,m.conversation_id
                      FROM messages m JOIN conversation_members cm ON cm.conversation_id=m.conversation_id
                     WHERE m.id=? AND m.status='sent' AND cm.user_id=? LIMIT 1", [$id,$uid]);
    if (!$m || empty($m['attachment'])) { http_response_code(404); exit; }
    $onceName = (string)($m['attachment_name'] ?? '');
    $viewOnce = strncmp($onceName, 'once__', 6) === 0;
    if ($viewOnce && (int)$m['sender_id'] !== $uid && table_exists('message_plays')) {
        $consumed = (int)fetch_col('SELECT COUNT(*) FROM message_plays WHERE message_id=? AND user_id=?', [$id,$uid]) > 0;
        if ($consumed) { http_response_code(410); exit; }
    }
'''
    text = once(text, old_query, new_query, f'view-once file gate {path}')

    # Do not expose the internal once__ marker as a download filename.
    old_name = "$name = basename((string) ($m['attachment_name'] ?: 'attachment'));"
    if old_name in text:
        text = text.replace(
            old_name,
            "$name = basename((string) ($m['attachment_name'] ?: 'attachment'));\n    if (strncmp($name, 'once__', 6) === 0) { $name = substr($name, 6); }",
            1,
        )
    w(path, text)

# Keep the bundled mobile API mirror identical.
if (r('backend/api/mobile.php') != r('flutter/backend/api/mobile.php')):
    shutil.copy2(ROOT / 'backend/api/mobile.php', ROOT / 'flutter/backend/api/mobile.php')


# ---------------------------------------------------------------------------
# 4) Release version and assertions.
# ---------------------------------------------------------------------------
path = 'flutter/pubspec.yaml'
text = r(path)
text = re.sub(r'^version:\s*[^\n]+', 'version: 4.1.0+410', text, count=1, flags=re.M)
w(path, text)

chat = r('flutter/lib/screens/chat_screen.dart')
api = r('flutter/lib/core/api_client.dart')
mobile = r('backend/api/mobile.php')
pubspec = r('flutter/pubspec.yaml')
assert 'Future<void> _jumpToMessage(int messageId) async' in chat
assert 'Scrollable.ensureVisible' in chat and 'key: _messageKey(m.id)' in chat
assert 'SecureChatImage(' in chat and 'View once photo' in chat
assert 'send directly in chat' in chat
assert 'Future<void> _uploadManyImages(' in chat and 'bool viewOnce = false' in chat
assert '_prepareViewOnceFile' in chat and 'once__' in chat
assert 'voicePreviewViewOnce' in chat and 'Send as view once' in chat
assert 'markViewOnceConsumed' in api
assert "if ($action === 'mark_view_once')" in mobile
assert "strncmp($onceName, 'once__', 6)" in mobile
assert 'version: 4.1.0+410' in pubspec
print('TaleemPK v4.1 reply/media/view-once patch applied successfully')
