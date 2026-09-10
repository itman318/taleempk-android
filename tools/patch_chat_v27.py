from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHAT = ROOT / 'flutter/lib/screens/chat_screen.dart'
PUBSPEC = ROOT / 'flutter/pubspec.yaml'


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f'patch anchor missing: {label}')
    return text.replace(old, new, 1)


c = CHAT.read_text(encoding='utf-8')

c = replace_once(
    c,
    "import 'package:flutter/material.dart';\nimport 'package:flutter/services.dart';\nimport 'package:image_picker/image_picker.dart';",
    "import 'package:flutter/foundation.dart';\nimport 'package:flutter/material.dart';\nimport 'package:flutter/services.dart';\nimport 'package:image/image.dart' as img;\nimport 'package:image_picker/image_picker.dart';",
    'media editor imports',
)

c = replace_once(
    c,
    "import 'call_screen.dart';\n\nclass ChatScreen extends StatefulWidget {",
    """import 'call_screen.dart';

Uint8List _processOutgoingPhoto(Map<String, dynamic> args) {
  final bytes = args['bytes'] as Uint8List;
  final turns = (args['turns'] as int?) ?? 0;
  final square = args['square'] == true;
  var image = img.decodeImage(bytes);
  if (image == null) return bytes;
  final normalizedTurns = ((turns % 4) + 4) % 4;
  if (normalizedTurns != 0) {
    image = img.copyRotate(image, angle: 90 * normalizedTurns);
  }
  if (square) {
    final side = image.width < image.height ? image.width : image.height;
    image = img.copyCrop(
      image,
      x: (image.width - side) ~/ 2,
      y: (image.height - side) ~/ 2,
      width: side,
      height: side,
    );
  }
  return Uint8List.fromList(img.encodeJpg(image, quality: 92));
}

class ChatScreen extends StatefulWidget {""",
    'photo processor',
)

c = replace_once(
    c,
    """    backgroundColor: Theme.of(context).brightness == Brightness.dark
        ? const Color(0xFF08111F)
        : const Color(0xFFF2F5FA),""",
    """    backgroundColor: Theme.of(context).brightness == Brightness.dark
        ? const Color(0xFF07111D)
        : const Color(0xFFEEF3F8),""",
    'chat background palette',
)

c = replace_once(
    c,
    """          gradient: m.mine && m.voiceSeconds == 0
              ? const LinearGradient(
                  colors: [Color(0xFF2459D7), Color(0xFF5545D9)],
                )
              : null,
          color: m.voiceSeconds > 0
              ? (m.mine
                    ? const Color(0xFF172B4D)
                    : (m.playedByMe
                          ? (Theme.of(context).brightness == Brightness.dark
                                ? const Color(0xFF10342F)
                                : const Color(0xFFDDF5EE))
                          : (Theme.of(context).brightness == Brightness.dark
                                ? const Color(0xFF152133)
                                : Colors.white)))
              : (m.mine
                    ? null
                    : (Theme.of(context).brightness == Brightness.dark
                          ? const Color(0xFF141F32)
                          : Colors.white)),""",
    """          gradient: m.mine && m.voiceSeconds == 0
              ? const LinearGradient(
                  colors: [Color(0xFF245FD3), Color(0xFF5146D8)],
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                )
              : null,
          color: m.voiceSeconds > 0
              ? (m.mine
                    ? (m.playedByOther
                          ? const Color(0xFF0D675A)
                          : const Color(0xFF193A64))
                    : (m.playedByMe
                          ? (Theme.of(context).brightness == Brightness.dark
                                ? const Color(0xFF103C35)
                                : const Color(0xFFD8F3EB))
                          : (Theme.of(context).brightness == Brightness.dark
                                ? const Color(0xFF132236)
                                : const Color(0xFFFFFFFF))))
              : (m.mine
                    ? null
                    : (Theme.of(context).brightness == Brightness.dark
                          ? const Color(0xFF132033)
                          : const Color(0xFFFFFFFF))),""",
    'professional bubble palette and played state',
)

c = replace_once(
    c,
    """                onListened: () {
                  if (!m.playedByMe && mounted) {
                    setState(() => m.playedByMe = true);
                  }
                },
              )""",
    """                onListened: () {
                  if (!m.playedByMe && mounted) {
                    setState(() => m.playedByMe = true);
                  }
                },
                onCompleted: () => _playNextVoice(m.id),
              )""",
    'voice completion callback',
)

c = replace_once(
    c,
    """            else
              Text(
                m.content,
                style: TextStyle(
                  color: m.mine ? Colors.white : Theme.of(context).colorScheme.onSurface,
                  height: 1.35,
                  fontStyle: m.deleted ? FontStyle.italic : null,
                ),
              ),""",
    """            else
              Text(
                m.content,
                style: TextStyle(
                  fontSize: _isEmojiOnlyMessage(m.content)
                      ? _emojiMessageSize(m.content)
                      : 15.5,
                  color: m.mine
                      ? Colors.white
                      : (Theme.of(context).brightness == Brightness.dark
                            ? const Color(0xFFE8EEF8)
                            : const Color(0xFF1B2738)),
                  height: _isEmojiOnlyMessage(m.content) ? 1.05 : 1.38,
                  fontWeight: _isEmojiOnlyMessage(m.content)
                      ? FontWeight.w500
                      : FontWeight.w400,
                  fontStyle: m.deleted ? FontStyle.italic : null,
                ),
              ),""",
    'large emoji-only messages',
)

c = replace_once(
    c,
    """              title: const Text('Photo or image'),
              onTap: () async {
                Navigator.pop(sheet);
                final image = await ImagePicker().pickImage(
                  source: ImageSource.gallery,
                  imageQuality: 88,
                  maxWidth: 2200,
                );
                if (image != null) _upload(image.path);
              },""",
    """              title: const Text('Photos or images'),
              subtitle: const Text('Select multiple and review before sending'),
              onTap: () async {
                Navigator.pop(sheet);
                final images = await ImagePicker().pickMultiImage(
                  imageQuality: 88,
                  maxWidth: 2200,
                );
                if (images.isNotEmpty && mounted) {
                  await _reviewImages(images.map((e) => e.path).toList());
                }
              },""",
    'multi photo gallery picker',
)

c = replace_once(
    c,
    """                if (image != null) _upload(image.path);
              },
            ),
          ],""",
    """                if (image != null && mounted) {
                  await _reviewImages([image.path]);
                }
              },
            ),
          ],""",
    'camera photo review',
)

c = replace_once(
    c,
    """  Future<void> _upload(String path) async {
    setState(() {
      sending = true;
      uploadProgress = 0;
    });
    try {
      await AppScope.of(context).api.sendFile(
        widget.conversation.id,
        path,
        replyTo: reply?.id,
        onProgress: (value) {
          if (mounted) setState(() => uploadProgress = value);
        },
      );
      reply = null;
      await _load(jumpToBottom: true);
    } catch (e) {
      if (mounted) showMessage(context, apiMessage(e));
    }
    if (mounted) {
      setState(() {
        sending = false;
        uploadProgress = null;
      });
    }
  }

  void _startVoicePresenceHeartbeat() {""",
    """  Future<void> _reviewImages(List<String> initialPaths) async {
    if (initialPaths.isEmpty || !mounted) return;
    final paths = <String>[...initialPaths];
    var selected = 0;
    final send = await showDialog<bool>(
      context: context,
      barrierDismissible: false,
      builder: (dialog) => StatefulBuilder(
        builder: (context, setLocal) => Dialog.fullscreen(
          backgroundColor: const Color(0xFF08111D),
          child: SafeArea(
            child: Column(
              children: [
                SizedBox(
                  height: 58,
                  child: Row(
                    children: [
                      IconButton(
                        onPressed: () => Navigator.pop(dialog, false),
                        icon: const Icon(Icons.close_rounded, color: Colors.white),
                      ),
                      Expanded(
                        child: Text(
                          paths.isEmpty ? 'Photos' : '${selected + 1} of ${paths.length}',
                          textAlign: TextAlign.center,
                          style: const TextStyle(
                            color: Colors.white,
                            fontSize: 16,
                            fontWeight: FontWeight.w800,
                          ),
                        ),
                      ),
                      IconButton(
                        tooltip: 'Edit photo',
                        onPressed: paths.isEmpty
                            ? null
                            : () async {
                                final edited = await _editPhoto(paths[selected]);
                                if (edited != null && dialog.mounted) {
                                  setLocal(() => paths[selected] = edited);
                                }
                              },
                        icon: const Icon(Icons.tune_rounded, color: Colors.white),
                      ),
                      IconButton(
                        tooltip: 'Remove photo',
                        onPressed: paths.isEmpty
                            ? null
                            : () {
                                setLocal(() {
                                  paths.removeAt(selected);
                                  if (paths.isEmpty) {
                                    selected = 0;
                                  } else if (selected >= paths.length) {
                                    selected = paths.length - 1;
                                  }
                                });
                              },
                        icon: const Icon(Icons.delete_outline_rounded, color: Color(0xFFFF7D89)),
                      ),
                    ],
                  ),
                ),
                const Divider(height: 1, color: Color(0x334B5870)),
                Expanded(
                  child: paths.isEmpty
                      ? const Center(
                          child: Text(
                            'No photos selected',
                            style: TextStyle(color: Colors.white70),
                          ),
                        )
                      : InteractiveViewer(
                          minScale: .8,
                          maxScale: 4,
                          child: Center(
                            child: Image.file(
                              File(paths[selected]),
                              key: ValueKey(paths[selected]),
                              fit: BoxFit.contain,
                              gaplessPlayback: true,
                            ),
                          ),
                        ),
                ),
                if (paths.isNotEmpty)
                  SizedBox(
                    height: 82,
                    child: ListView.separated(
                      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 9),
                      scrollDirection: Axis.horizontal,
                      itemCount: paths.length,
                      separatorBuilder: (_, _) => const SizedBox(width: 8),
                      itemBuilder: (_, i) => InkWell(
                        onTap: () => setLocal(() => selected = i),
                        child: AnimatedContainer(
                          duration: const Duration(milliseconds: 160),
                          width: 62,
                          decoration: BoxDecoration(
                            borderRadius: BorderRadius.circular(12),
                            border: Border.all(
                              color: i == selected
                                  ? const Color(0xFF86A3FF)
                                  : const Color(0x335E6A80),
                              width: i == selected ? 2.4 : 1,
                            ),
                          ),
                          clipBehavior: Clip.antiAlias,
                          child: Image.file(File(paths[i]), fit: BoxFit.cover),
                        ),
                      ),
                    ),
                  ),
                Container(
                  color: const Color(0xFF0D1828),
                  padding: const EdgeInsets.fromLTRB(14, 10, 14, 12),
                  child: Row(
                    children: [
                      OutlinedButton.icon(
                        onPressed: () async {
                          final more = await ImagePicker().pickMultiImage(
                            imageQuality: 88,
                            maxWidth: 2200,
                          );
                          if (more.isNotEmpty && dialog.mounted) {
                            setLocal(() {
                              paths.addAll(more.map((e) => e.path));
                              selected = paths.length - more.length;
                            });
                          }
                        },
                        icon: const Icon(Icons.add_photo_alternate_outlined),
                        label: const Text('Add'),
                        style: OutlinedButton.styleFrom(foregroundColor: Colors.white),
                      ),
                      const Spacer(),
                      FilledButton.icon(
                        onPressed: paths.isEmpty
                            ? null
                            : () => Navigator.pop(dialog, true),
                        icon: const Icon(Icons.send_rounded),
                        label: Text('Send ${paths.length}'),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
    if (send == true && paths.isNotEmpty && mounted) {
      await _uploadManyImages(paths);
    }
  }

  Future<String?> _editPhoto(String sourcePath) async {
    if (!mounted) return null;
    var turns = 0;
    var square = false;
    final apply = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      backgroundColor: const Color(0xFF0B1422),
      builder: (sheet) => StatefulBuilder(
        builder: (context, setLocal) => SizedBox(
          height: MediaQuery.sizeOf(context).height * .82,
          child: Column(
            children: [
              const SizedBox(height: 8),
              Container(
                width: 42,
                height: 4,
                decoration: BoxDecoration(
                  color: Colors.white24,
                  borderRadius: BorderRadius.circular(4),
                ),
              ),
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 10, 8, 8),
                child: Row(
                  children: [
                    const Expanded(
                      child: Text(
                        'Edit photo',
                        style: TextStyle(
                          color: Colors.white,
                          fontSize: 18,
                          fontWeight: FontWeight.w900,
                        ),
                      ),
                    ),
                    TextButton(
                      onPressed: () => setLocal(() {
                        turns = 0;
                        square = false;
                      }),
                      child: const Text('Reset'),
                    ),
                  ],
                ),
              ),
              Expanded(
                child: Padding(
                  padding: const EdgeInsets.all(14),
                  child: Center(
                    child: AspectRatio(
                      aspectRatio: square ? 1 : 4 / 5,
                      child: ClipRRect(
                        borderRadius: BorderRadius.circular(18),
                        child: ColoredBox(
                          color: Colors.black,
                          child: RotatedBox(
                            quarterTurns: turns,
                            child: Image.file(
                              File(sourcePath),
                              fit: square ? BoxFit.cover : BoxFit.contain,
                            ),
                          ),
                        ),
                      ),
                    ),
                  ),
                ),
              ),
              Padding(
                padding: const EdgeInsets.fromLTRB(12, 8, 12, 10),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                  children: [
                    FilledButton.tonalIcon(
                      onPressed: () => setLocal(() => turns = (turns + 3) % 4),
                      icon: const Icon(Icons.rotate_left_rounded),
                      label: const Text('Rotate'),
                    ),
                    FilledButton.tonalIcon(
                      onPressed: () => setLocal(() => square = !square),
                      icon: Icon(square ? Icons.crop_free_rounded : Icons.crop_square_rounded),
                      label: Text(square ? 'Original' : 'Square crop'),
                    ),
                  ],
                ),
              ),
              Padding(
                padding: const EdgeInsets.fromLTRB(14, 0, 14, 14),
                child: Row(
                  children: [
                    Expanded(
                      child: OutlinedButton(
                        onPressed: () => Navigator.pop(sheet, false),
                        child: const Text('Cancel'),
                      ),
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: FilledButton(
                        onPressed: () => Navigator.pop(sheet, true),
                        child: const Text('Apply'),
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
    if (apply != true) return null;
    if (turns == 0 && !square) return sourcePath;
    try {
      final bytes = await File(sourcePath).readAsBytes();
      final edited = await compute(_processOutgoingPhoto, <String, dynamic>{
        'bytes': bytes,
        'turns': turns,
        'square': square,
      });
      final dir = await getTemporaryDirectory();
      final output = '${dir.path}/taleempk_photo_${DateTime.now().microsecondsSinceEpoch}.jpg';
      await File(output).writeAsBytes(edited, flush: true);
      return output;
    } catch (e) {
      if (mounted) showMessage(context, 'Photo could not be edited. The original is still selected.');
      return null;
    }
  }

  Future<void> _uploadManyImages(List<String> paths) async {
    if (paths.isEmpty || _chatBlocked) return;
    final currentReply = reply?.id;
    var sent = 0;
    setState(() {
      sending = true;
      uploadProgress = 0;
    });
    try {
      for (var i = 0; i < paths.length; i++) {
        await AppScope.of(context).api.sendFile(
          widget.conversation.id,
          paths[i],
          replyTo: i == 0 ? currentReply : null,
          onProgress: (value) {
            if (mounted) {
              setState(() => uploadProgress = (i + value) / paths.length);
            }
          },
        );
        sent++;
      }
      reply = null;
      await _load(jumpToBottom: true);
    } catch (e) {
      if (mounted) {
        final prefix = sent > 0 ? '$sent of ${paths.length} photos sent. ' : '';
        showMessage(context, '$prefix${apiMessage(e)}');
      }
    } finally {
      if (mounted) {
        setState(() {
          sending = false;
          uploadProgress = null;
        });
      }
    }
  }

  Future<void> _upload(String path) async {
    setState(() {
      sending = true;
      uploadProgress = 0;
    });
    try {
      await AppScope.of(context).api.sendFile(
        widget.conversation.id,
        path,
        replyTo: reply?.id,
        onProgress: (value) {
          if (mounted) setState(() => uploadProgress = value);
        },
      );
      reply = null;
      await _load(jumpToBottom: true);
    } catch (e) {
      if (mounted) showMessage(context, apiMessage(e));
    }
    if (mounted) {
      setState(() {
        sending = false;
        uploadProgress = null;
      });
    }
  }

  void _startVoicePresenceHeartbeat() {""",
    'multi photo review editor uploader',
)

c = replace_once(
    c,
    """  void _toBottom() => WidgetsBinding.instance.addPostFrameCallback((_) {""",
    """  Future<void> _playNextVoice(int currentId) async {
    final current = messages.indexWhere((m) => m.id == currentId);
    if (current < 0) return;
    for (var i = current + 1; i < messages.length; i++) {
      final next = messages[i];
      if (next.voiceSeconds <= 0 || next.deleted || next.attachmentUrl == null) {
        continue;
      }
      var started = await VoiceBubble.playMessage(next.id);
      if (!started && mounted) {
        await _jumpToMessage(next.id);
        await Future<void>.delayed(const Duration(milliseconds: 140));
        started = await VoiceBubble.playMessage(next.id);
      }
      return;
    }
  }

  bool _isEmojiOnlyMessage(String value) {
    final trimmed = value.trim();
    if (trimmed.isEmpty) return false;
    var hasEmoji = false;
    for (final rune in trimmed.runes) {
      if (rune == 0x20 || rune == 0x0A || rune == 0x0D || rune == 0x09 ||
          rune == 0xFE0F || rune == 0x200D || rune == 0x20E3 ||
          (rune >= 0x1F3FB && rune <= 0x1F3FF)) {
        continue;
      }
      final emojiRune =
          (rune >= 0x1F000 && rune <= 0x1FAFF) ||
          (rune >= 0x2600 && rune <= 0x27BF) ||
          (rune >= 0x2300 && rune <= 0x23FF) ||
          (rune >= 0x1F1E6 && rune <= 0x1F1FF) ||
          rune == 0x00A9 || rune == 0x00AE || rune == 0x203C ||
          rune == 0x2049 || rune == 0x2122 || rune == 0x2139 ||
          rune == 0x3030 || rune == 0x303D || rune == 0x3297 || rune == 0x3299;
      if (!emojiRune) return false;
      hasEmoji = true;
    }
    return hasEmoji;
  }

  double _emojiMessageSize(String value) {
    final count = value.runes.where((r) =>
        r != 0xFE0F && r != 0x200D && r != 0x20E3 &&
        !(r >= 0x1F3FB && r <= 0x1F3FF)).length;
    if (count <= 2) return 40;
    if (count <= 4) return 34;
    if (count <= 7) return 29;
    return 24;
  }

  void _toBottom() => WidgetsBinding.instance.addPostFrameCallback((_) {""",
    'next voice and emoji helpers',
)

c = replace_once(
    c,
    """    this.onListened,
    this.beforePlay,
  });
  final ChatMessage message;
  final ApiClient api;
  final VoidCallback? onListened;
  final Future<void> Function()? beforePlay;

  static Future<void> pauseActivePlayback() async {""",
    """    this.onListened,
    this.beforePlay,
    this.onCompleted,
  });
  final ChatMessage message;
  final ApiClient api;
  final VoidCallback? onListened;
  final Future<void> Function()? beforePlay;
  final Future<void> Function()? onCompleted;

  static Future<void> pauseActivePlayback() async {""",
    'voice completed API',
)

c = replace_once(
    c,
    """  static Future<void> pauseActivePlayback() async {
    final active = _VoiceBubbleState.activeVoice;
    if (active != null) {
      await active._pauseForAnotherVoice();
    }
  }

  @override""",
    """  static Future<void> pauseActivePlayback() async {
    final active = _VoiceBubbleState.activeVoice;
    if (active != null) {
      await active._pauseForAnotherVoice();
    }
  }

  static Future<bool> playMessage(int messageId) async {
    final state = _VoiceBubbleState.instances[messageId];
    if (state == null || !state.mounted) return false;
    await state._toggle(autoStart: true);
    return true;
  }

  @override""",
    'voice registry public helper',
)

c = replace_once(
    c,
    """class _VoiceBubbleState extends State<VoiceBubble> {
  static double rememberedSpeed = 1.0;
  static _VoiceBubbleState? activeVoice;

  final player = AudioPlayer();
  StreamSubscription<Duration?>? durationSub;
  StreamSubscription<PlayerState>? stateSub;
  bool ready = false, listened = false, loading = false, preparing = false;""",
    """class _VoiceBubbleState extends State<VoiceBubble> {
  static double rememberedSpeed = 1.0;
  static _VoiceBubbleState? activeVoice;
  static final Map<int, _VoiceBubbleState> instances = <int, _VoiceBubbleState>{};

  final player = AudioPlayer();
  StreamSubscription<Duration?>? durationSub;
  StreamSubscription<PlayerState>? stateSub;
  bool ready = false,
      listened = false,
      loading = false,
      preparing = false,
      handlingCompletion = false;""",
    'voice registry state',
)

c = replace_once(
    c,
    """    listened = widget.message.playedByMe;
    durationSub = player.durationStream.listen((value) {""",
    """    listened = widget.message.playedByMe;
    instances[widget.message.id] = this;
    durationSub = player.durationStream.listen((value) {""",
    'register voice bubble',
)

c = replace_once(
    c,
    """    stateSub = player.playerStateStream.listen((state) {
      if (state.processingState == ProcessingState.completed) {
        if (activeVoice == this) activeVoice = null;
        if (mounted) setState(() {});
      }
    });""",
    """    stateSub = player.playerStateStream.listen((state) {
      if (state.processingState == ProcessingState.completed) {
        unawaited(_handleCompleted());
      }
    });""",
    'completion listener',
)

c = replace_once(
    c,
    """    if (oldWidget.message.id != widget.message.id) {
      unawaited(_resetForMessage());
    } else if (widget.message.playedByMe) {""",
    """    if (oldWidget.message.id != widget.message.id) {
      if (instances[oldWidget.message.id] == this) {
        instances.remove(oldWidget.message.id);
      }
      instances[widget.message.id] = this;
      unawaited(_resetForMessage());
    } else if (widget.message.playedByMe) {""",
    'voice registry update',
)

c = replace_once(
    c,
    """  @override
  void dispose() {
    if (activeVoice == this) activeVoice = null;
    durationSub?.cancel();""",
    """  @override
  void dispose() {
    if (activeVoice == this) activeVoice = null;
    if (instances[widget.message.id] == this) {
      instances.remove(widget.message.id);
    }
    durationSub?.cancel();""",
    'unregister voice bubble',
)

c = replace_once(
    c,
    """  Future<void> _pauseForAnotherVoice() async {
    if (player.playing) await player.pause();
    if (activeVoice == this) activeVoice = null;
    if (mounted) setState(() {});
  }

  Future<void> _playToEnd() async {""",
    """  Future<void> _pauseForAnotherVoice() async {
    if (player.playing) await player.pause();
    if (activeVoice == this) activeVoice = null;
    if (mounted) setState(() {});
  }

  Future<void> _handleCompleted() async {
    if (handlingCompletion) return;
    handlingCompletion = true;
    final shouldContinue = activeVoice == this;
    if (shouldContinue) activeVoice = null;
    try {
      if (player.playing) await player.pause();
      await player.seek(Duration.zero);
      if (mounted) setState(() {});
      if (shouldContinue && widget.onCompleted != null && mounted) {
        await widget.onCompleted!();
      }
    } catch (_) {
      // Completion cleanup must never break the thread.
    } finally {
      handlingCompletion = false;
    }
  }

  Future<void> _playToEnd() async {""",
    'completion reset and auto next',
)

c = replace_once(
    c,
    """  Future<void> _toggle() async {
    try {
      await _prepare();
      if (!ready) return;

      if (player.playing) {
        await player.pause();
        if (activeVoice == this) activeVoice = null;
        if (mounted) setState(() {});
        return;
      }

      if (activeVoice == this) return;""",
    """  Future<void> _toggle({bool autoStart = false}) async {
    try {
      await _prepare();
      if (!ready) return;

      if (player.processingState == ProcessingState.completed) {
        if (player.playing) await player.pause();
        await player.seek(Duration.zero);
      }
      if (player.playing) {
        if (autoStart) return;
        await player.pause();
        if (activeVoice == this) activeVoice = null;
        if (mounted) setState(() {});
        return;
      }

      if (activeVoice == this) return;""",
    'voice toggle completion guard',
)

c = replace_once(
    c,
    """                        onPressed: loading ? null : _toggle,
                        icon: loading
                            ? const SizedBox(
                                width: 19,
                                height: 19,
                                child: CircularProgressIndicator(strokeWidth: 2),
                              )
                            : StreamBuilder<bool>(
                                stream: player.playingStream,
                                builder: (_, playing) => Icon(
                                  playing.data == true
                                      ? Icons.pause_rounded
                                      : Icons.play_arrow_rounded,
                                  size: 30,
                                ),
                              ),""",
    """                        onPressed: loading ? null : () => _toggle(),
                        icon: loading
                            ? const SizedBox(
                                width: 19,
                                height: 19,
                                child: CircularProgressIndicator(strokeWidth: 2),
                              )
                            : StreamBuilder<PlayerState>(
                                stream: player.playerStateStream,
                                builder: (_, state) {
                                  final value = state.data;
                                  final isPlaying = value?.playing == true &&
                                      value?.processingState != ProcessingState.completed;
                                  return Icon(
                                    isPlaying
                                        ? Icons.pause_rounded
                                        : Icons.play_arrow_rounded,
                                    size: 30,
                                  );
                                },
                              ),""",
    'voice icon completion state',
)

CHAT.write_text(c, encoding='utf-8')

p = PUBSPEC.read_text(encoding='utf-8')
p = replace_once(
    p,
    "  image_picker: ^1.2.3\n",
    "  image_picker: ^1.2.3\n  image: ^4.5.4\n",
    'image dependency',
)
p = replace_once(p, 'version: 2.6.1+261', 'version: 2.7.0+270', 'version bump')
PUBSPEC.write_text(p, encoding='utf-8')
