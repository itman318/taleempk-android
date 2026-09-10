from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return (ROOT / path).read_text(encoding='utf-8')


def write(path, text):
    (ROOT / path).write_text(text, encoding='utf-8')


def replace_once(text, old, new, label):
    if new in text:
        return text
    if old not in text:
        raise RuntimeError(f'{label}: marker not found')
    return text.replace(old, new, 1)


def replace_between(text, start, end, new_block, label):
    if new_block in text:
        return text
    a = text.find(start)
    if a < 0:
        raise RuntimeError(f'{label}: start marker not found')
    b = text.find(end, a)
    if b < 0:
        raise RuntimeError(f'{label}: end marker not found')
    return text[:a] + new_block + text[b:]


# ------------------------------------------------------------------ api client
path = 'flutter/lib/core/api_client.dart'
s = read(path)
s = replace_once(
    s,
    "  Future<List<ChatMessage>> messages(\n    int conversationId, {\n    int afterId = 0,\n    int beforeId = 0,\n  }) async {\n    final data = await _request({\n      'action': 'messages',\n      'conversation_id': '$conversationId',\n      'after_id': '$afterId',\n      'before_id': '$beforeId',\n    });",
    "  Future<List<ChatMessage>> messages(\n    int conversationId, {\n    int afterId = 0,\n    int beforeId = 0,\n    int limit = 80,\n  }) async {\n    final data = await _request({\n      'action': 'messages',\n      'conversation_id': '$conversationId',\n      'after_id': '$afterId',\n      'before_id': '$beforeId',\n      'limit': '${limit.clamp(20, 100)}',\n    });",
    'api messages limit',
)
write(path, s)


# -------------------------------------------------------------- mobile backend
for path in ('backend/api/mobile.php', 'flutter/backend/api/mobile.php'):
    s = read(path)
    s = replace_once(
        s,
        "    $beforeId = max(0, (int)($_POST['before_id'] ?? 0));\n    if ($afterId > 0) $beforeId = 0;",
        "    $beforeId = max(0, (int)($_POST['before_id'] ?? 0));\n    $limit = max(20, min(100, (int)($_POST['limit'] ?? 80)));\n    if ($afterId > 0) $beforeId = 0;",
        f'{path} message limit variable',
    )
    s = replace_once(
        s,
        "          ORDER BY m.id DESC LIMIT 150', [$uid,$uid,$cid,$afterId,$afterId,$beforeId,$beforeId,$uid]",
        "          ORDER BY m.id DESC LIMIT '.$limit, [$uid,$uid,$cid,$afterId,$afterId,$beforeId,$beforeId,$uid]",
        f'{path} message limit sql',
    )
    write(path, s)


# ------------------------------------------------------------------- chat screen
path = 'flutter/lib/screens/chat_screen.dart'
s = read(path)

s = replace_once(
    s,
    '  Timer? poll, recordTimer, waveTimer, presenceDebounce, typingHeartbeat;\n',
    '  Timer? poll, recordTimer, waveTimer, presenceDebounce, typingHeartbeat, voiceHeartbeat;\n',
    'voice heartbeat field',
)
s = replace_once(
    s,
    '      historyDone = false;\n',
    '      historyDone = false,\n      foreground = true;\n',
    'foreground field',
)
s = replace_once(
    s,
    '    typingHeartbeat?.cancel();\n    recorder.dispose();',
    '    typingHeartbeat?.cancel();\n    voiceHeartbeat?.cancel();\n    recorder.dispose();',
    'dispose voice heartbeat',
)
s = replace_once(
    s,
    '    _load();\n  }\n\n  @override\n  void dispose()',
    '    _load(jumpToBottom: true);\n  }\n\n  @override\n  void dispose()',
    'initial load bottom',
)

# Lifecycle: stop background network work, resume real-time state cleanly.
lifecycle_start = '  @override\n  void didChangeAppLifecycleState(AppLifecycleState state) {'
lifecycle_end = '  Future<void> _load() async {'
lifecycle_new = '''  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    foreground = state == AppLifecycleState.resumed;
    if (foreground) {
      if (recording && !recordingPaused) _startVoicePresenceHeartbeat();
      _schedulePoll(immediate: true);
      return;
    }
    poll?.cancel();
    typingHeartbeat?.cancel();
    typingHeartbeat = null;
    voiceHeartbeat?.cancel();
    voiceHeartbeat = null;
    typingSent = false;
    AppScope.of(context).api
        .presence(widget.conversation.id, clear: true)
        .catchError((_) => const ChatPresence(
              active: false,
              kind: '',
              name: '',
              readThrough: 0,
            ));
  }

'''
s = replace_between(s, lifecycle_start, lifecycle_end, lifecycle_new, 'lifecycle')

# Faster initial load and no forced jump after edits/reactions.
load_start = '  Future<void> _load() async {'
load_end = '  void _historyListener() {'
load_new = '''  Future<void> _load({bool jumpToBottom = false}) async {
    try {
      final api = AppScope.of(context).api;
      final result = await Future.wait<Object>([
        api.messages(widget.conversation.id, limit: 80),
        api.pinnedMessages(widget.conversation.id),
      ]);
      final fresh = result[0] as List<ChatMessage>;
      messages
        ..clear()
        ..addAll(fresh);
      pinnedMessages = result[1] as List<Map<String, dynamic>>;
      historyDone = fresh.length < 80;
      error = null;
      _schedulePoll();
      if (jumpToBottom) _toBottom();
    } catch (e) {
      error = apiMessage(e);
    }
    if (mounted) setState(() => loading = false);
  }

'''
s = replace_between(s, load_start, load_end, load_new, 'load method')
s = s.replace('      if (older.length < 150) historyDone = true;', '      if (older.length < 80) historyDone = true;')
s = s.replace('        beforeId: before,\n      );', '        beforeId: before,\n        limit: 80,\n      );', 1)

# Poll: parallel requests, sub-second-ish UI cadence, smaller payloads, no rebuild on idle.
poll_start = '  void _schedulePoll() {'
poll_end = '  void _typing() {'
poll_new = '''  void _schedulePoll({bool immediate = false}) {
    poll?.cancel();
    if (!mounted || !foreground) return;
    poll = Timer(
      Duration(milliseconds: immediate ? 80 : 950),
      _poll,
    );
  }

  Future<void> _poll() async {
    if (!mounted || !foreground || polling) return;
    polling = true;
    final shouldStickToBottom = !scroll.hasClients ||
        scroll.position.maxScrollExtent - scroll.position.pixels < 220;
    try {
      pollTicks++;
      final fullSync = pollTicks % 4 == 0;
      final after = messages.isEmpty ? 0 : messages.last.id;
      final api = AppScope.of(context).api;
      final result = await Future.wait<Object>([
        api.messages(
          widget.conversation.id,
          afterId: fullSync ? 0 : after,
          limit: fullSync ? 60 : 30,
        ),
        api.presence(widget.conversation.id),
      ]);
      final fresh = result[0] as List<ChatMessage>;
      final p = result[1] as ChatPresence;
      var changed = false;
      var addedNew = false;

      final played = p.playedIds.toSet();
      for (final message in messages) {
        if (message.mine && message.id <= p.readThrough && !message.read) {
          message.read = true;
          changed = true;
        }
        if (message.mine &&
            message.voiceSeconds > 0 &&
            played.contains(message.id) &&
            !message.playedByOther) {
          message.playedByOther = true;
          changed = true;
        }
      }

      if (fullSync) {
        if (fresh.isNotEmpty) {
          final recentFloor = fresh.first.id;
          final serverIds = fresh.map((m) => m.id).toSet();
          final removed = messages.length;
          messages.removeWhere(
            (m) => m.id >= recentFloor && !serverIds.contains(m.id),
          );
          if (messages.length != removed) changed = true;
        }
        for (final candidate in fresh) {
          final index = messages.indexWhere((m) => m.id == candidate.id);
          if (index >= 0) {
            final old = messages[index];
            if (old.mine && old.read) candidate.read = true;
            if (old.mine && old.playedByOther) {
              candidate.playedByOther = true;
            }
            messages[index] = candidate;
            changed = true;
          } else {
            messages.add(candidate);
            addedNew = true;
            changed = true;
          }
        }
        messages.sort((a, b) => a.id.compareTo(b.id));
        final pins = await api.pinnedMessages(widget.conversation.id);
        if (pins.toString() != pinnedMessages.toString()) {
          pinnedMessages = pins;
          changed = true;
        }
      } else if (fresh.isNotEmpty) {
        final unseen = fresh
            .where((m) => messages.every((old) => old.id != m.id))
            .toList();
        if (unseen.isNotEmpty) {
          messages.addAll(unseen);
          addedNew = true;
          changed = true;
        }
      }

      final presenceChanged = presence?.active != p.active ||
          presence?.kind != p.kind ||
          presence?.name != p.name;
      presence = p;
      if (mounted && (changed || presenceChanged)) setState(() {});
      if (addedNew && shouldStickToBottom) _toBottom();
    } catch (_) {
      // Keep the currently rendered thread during a transient network miss.
    } finally {
      polling = false;
    }
    _schedulePoll();
  }

'''
s = replace_between(s, poll_start, poll_end, poll_new, 'poll runtime')

# Reliable voice presence heartbeat independent of recording timer.
record_marker = '  Future<void> _toggleRecording() async {'
voice_helpers = '''  void _startVoicePresenceHeartbeat() {
    voiceHeartbeat?.cancel();
    if (!mounted || !foreground || !recording || recordingPaused) return;
    void beat() {
      if (!mounted || !foreground || !recording || recordingPaused) return;
      AppScope.of(context).api
          .presence(widget.conversation.id, kind: 'voice')
          .catchError((_) => const ChatPresence(
                active: false,
                kind: '',
                name: '',
                readThrough: 0,
              ));
    }
    beat();
    voiceHeartbeat = Timer.periodic(
      const Duration(milliseconds: 1500),
      (_) => beat(),
    );
  }

  void _stopVoicePresenceHeartbeat({bool clear = true}) {
    voiceHeartbeat?.cancel();
    voiceHeartbeat = null;
    if (!clear || !mounted) return;
    AppScope.of(context).api
        .presence(widget.conversation.id, clear: true)
        .catchError((_) => const ChatPresence(
              active: false,
              kind: '',
              name: '',
              readThrough: 0,
            ));
  }

'''
if voice_helpers not in s:
    idx = s.find(record_marker)
    if idx < 0:
        raise RuntimeError('record marker missing')
    s = s[:idx] + voice_helpers + s[idx:]

s = replace_once(
    s,
    "    AppScope.of(context).api.presence(widget.conversation.id, kind: 'voice');\n    waveTimer?.cancel();",
    "    typingHeartbeat?.cancel();\n    typingHeartbeat = null;\n    presenceDebounce?.cancel();\n    typingSent = false;\n    _startVoicePresenceHeartbeat();\n    waveTimer?.cancel();",
    'recording presence start',
)
s = s.replace(
    "      if (recordSeconds % 3 == 0) {\n        AppScope.of(context).api.presence(widget.conversation.id, kind: 'voice');\n      }\n",
    '',
    1,
)
s = replace_once(
    s,
    "        await recorder.resume();\n        recordingPaused = false;\n        AppScope.of(context).api.presence(widget.conversation.id, kind: 'voice');",
    "        await recorder.resume();\n        recordingPaused = false;\n        _startVoicePresenceHeartbeat();",
    'recording resume presence',
)
s = replace_once(
    s,
    "        await recorder.pause();\n        recordingPaused = true;\n        AppScope.of(context).api.presence(widget.conversation.id, clear: true);",
    "        await recorder.pause();\n        recordingPaused = true;\n        _stopVoicePresenceHeartbeat();",
    'recording pause presence',
)
s = replace_once(
    s,
    "    final path = await recorder.stop();\n    AppScope.of(context).api\n        .presence(widget.conversation.id, clear: true)\n        .catchError((_) => const ChatPresence(\n              active: false,\n              kind: '',\n              name: '',\n              readThrough: 0,\n            ));",
    "    final path = await recorder.stop();\n    _stopVoicePresenceHeartbeat();",
    'recording stop presence',
)
s = replace_once(
    s,
    "    AppScope.of(context).api.presence(widget.conversation.id, clear: true);\n  }\n\n  Widget _blockedBanner()",
    "    _stopVoicePresenceHeartbeat();\n  }\n\n  Widget _blockedBanner()",
    'recording cancel presence',
)

# Voice preview progress: trust the longer of recorder clock and decoder metadata.
s = replace_once(
    s,
    "        final total = voicePreviewPlayer.duration ?? Duration(seconds: recordSeconds);\n        final totalMs = total.inMilliseconds > 0 ? total.inMilliseconds : 1;\n        final progress =\n            (position.inMilliseconds / totalMs).clamp(0.0, 1.0).toDouble();",
    "        final decodedMs = voicePreviewPlayer.duration?.inMilliseconds ?? 0;\n        final recordedMs = recordSeconds * 1000;\n        final totalMs = decodedMs > recordedMs ? decodedMs : (recordedMs > 0 ? recordedMs : 1);\n        var progress =\n            (position.inMilliseconds / totalMs).clamp(0.0, 1.0).toDouble();\n        if (voicePreviewPlayer.processingState != ProcessingState.completed &&\n            progress >= .995) {\n          progress = .985;\n        }",
    'preview progress denominator',
)

# Action sheet: make the complete menu scrollable; show edit even when its time window expired.
action_start = '  Future<void> _messageActions(ChatMessage m) async {'
action_end = '  Future<void> _forward(ChatMessage message) async {'
action_new = '''  Future<void> _messageActions(ChatMessage m) async {
    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      showDragHandle: true,
      builder: (sheet) => FractionallySizedBox(
        heightFactor: .86,
        child: Column(
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(14, 2, 14, 10),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceAround,
                children: ['👍', '❤️', '😂', '😮', '😢', '🔥']
                    .map(
                      (emoji) => InkWell(
                        borderRadius: BorderRadius.circular(30),
                        onTap: () {
                          Navigator.pop(sheet);
                          _reactWith(m, emoji);
                        },
                        child: Padding(
                          padding: const EdgeInsets.all(7),
                          child: Text(emoji, style: const TextStyle(fontSize: 28)),
                        ),
                      ),
                    )
                    .toList(),
              ),
            ),
            const Divider(height: 1),
            Expanded(
              child: ListView(
                children: [
                  ListTile(
                    leading: const Icon(Icons.reply_rounded),
                    title: const Text('Reply'),
                    onTap: () {
                      Navigator.pop(sheet);
                      setState(
                        () => reply = ReplyPreview(
                          id: m.id,
                          sender: m.sender,
                          text: m.content.isNotEmpty
                              ? m.content
                              : (m.voiceSeconds > 0 ? 'Voice message' : 'Attachment'),
                        ),
                      );
                    },
                  ),
                  if (m.content.isNotEmpty && !m.deleted && !m.encrypted)
                    ListTile(
                      leading: const Icon(Icons.copy_rounded),
                      title: const Text('Copy'),
                      onTap: () async {
                        Navigator.pop(sheet);
                        await Clipboard.setData(ClipboardData(text: m.content));
                        if (mounted) showMessage(context, 'Message copied.');
                      },
                    ),
                  ListTile(
                    leading: const Icon(Icons.flag_outlined, color: AppColors.danger),
                    title: const Text(
                      'Report message',
                      style: TextStyle(color: AppColors.danger),
                    ),
                    onTap: () {
                      Navigator.pop(sheet);
                      _reportMessage(m);
                    },
                  ),
                  ListTile(
                    leading: const Icon(Icons.forward_rounded),
                    title: const Text('Forward'),
                    onTap: () {
                      Navigator.pop(sheet);
                      _forward(m);
                    },
                  ),
                  ListTile(
                    leading: Icon(
                      m.starred ? Icons.star_rounded : Icons.star_outline_rounded,
                    ),
                    title: Text(m.starred ? 'Unstar' : 'Star'),
                    onTap: () async {
                      Navigator.pop(sheet);
                      await AppScope.of(context).api.toggleStar(m.id);
                      _load();
                    },
                  ),
                  ListTile(
                    leading: Icon(
                      m.pinned ? Icons.push_pin_rounded : Icons.push_pin_outlined,
                    ),
                    title: Text(m.pinned ? 'Unpin' : 'Pin'),
                    onTap: () async {
                      Navigator.pop(sheet);
                      try {
                        await AppScope.of(context).api.togglePin(m.id);
                        await _load();
                      } catch (e) {
                        if (mounted) showMessage(context, apiMessage(e));
                      }
                    },
                  ),
                  ListTile(
                    leading: const Icon(Icons.check_box_outlined),
                    title: const Text('Select messages'),
                    onTap: () {
                      Navigator.pop(sheet);
                      setState(() => selectedIds.add(m.id));
                    },
                  ),
                  if (m.edited)
                    ListTile(
                      leading: const Icon(Icons.history_rounded),
                      title: const Text('Edit history'),
                      onTap: () {
                        Navigator.pop(sheet);
                        _showEditHistory(m);
                      },
                    ),
                  if (m.mine &&
                      !m.deleted &&
                      m.content.isNotEmpty &&
                      !m.encrypted)
                    ListTile(
                      enabled: m.canEdit,
                      leading: const Icon(Icons.edit_outlined),
                      title: const Text('Edit'),
                      subtitle: m.canEdit
                          ? null
                          : const Text('Editing time has expired'),
                      onTap: m.canEdit
                          ? () {
                              Navigator.pop(sheet);
                              _edit(m);
                            }
                          : null,
                    ),
                  ListTile(
                    leading: const Icon(
                      Icons.delete_outline_rounded,
                      color: AppColors.danger,
                    ),
                    title: Text(
                      m.mine ? 'Delete' : 'Delete for me',
                      style: const TextStyle(color: AppColors.danger),
                    ),
                    onTap: () {
                      Navigator.pop(sheet);
                      _delete(m);
                    },
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

'''
s = replace_between(s, action_start, action_end, action_new, 'message action sheet')

# Replace the voice player state with a duration-safe, cached, website-like player.
voice_start = 'class _VoiceBubbleState extends State<VoiceBubble> {'
voice_end = 'class _VoiceWavePainter extends CustomPainter {'
voice_new = '''class _VoiceBubbleState extends State<VoiceBubble> {
  static double rememberedSpeed = 1.0;
  final player = AudioPlayer();
  StreamSubscription<Duration?>? durationSub;
  bool ready = false, listened = false, loading = false;
  String? localPath;
  Duration? decodedDuration;
  late double speed = rememberedSpeed;

  @override
  void initState() {
    super.initState();
    listened = widget.message.playedByMe;
    durationSub = player.durationStream.listen((value) {
      if (value != null && value.inMilliseconds > 0 && mounted) {
        decodedDuration = value;
        setState(() {});
      }
    });
  }

  @override
  void dispose() {
    durationSub?.cancel();
    player.dispose();
    super.dispose();
  }

  Future<void> _prepare() async {
    if (ready || loading) return;
    loading = true;
    if (mounted) setState(() {});
    try {
      final dir = await getTemporaryDirectory();
      localPath = '${dir.path}/taleempk_voice_${widget.message.id}.m4a';
      final file = File(localPath!);
      if (!await file.exists() || await file.length() == 0) {
        final bytes = await widget.api.attachmentBytes(
          widget.message.attachmentUrl!,
        );
        await file.writeAsBytes(bytes, flush: true);
      }
      await player.setFilePath(localPath!);
      decodedDuration = player.duration;
      await player.setSpeed(speed);
      ready = true;
    } finally {
      loading = false;
      if (mounted) setState(() {});
    }
  }

  Future<void> _toggle() async {
    try {
      await _prepare();
      if (!ready) return;
      if (!listened && !widget.message.mine) {
        listened = true;
        widget.api.markVoicePlayed(widget.message.id).catchError((_) {});
      }
      if (player.processingState == ProcessingState.completed) {
        await player.seek(Duration.zero);
      }
      if (player.playing) {
        await player.pause();
      } else {
        await player.play();
      }
      if (mounted) setState(() {});
    } catch (e) {
      if (mounted) showMessage(context, apiMessage(e));
    }
  }

  Future<void> _cycleSpeed() async {
    speed = speed == 1.0
        ? 1.5
        : speed == 1.5
        ? 2.0
        : 1.0;
    rememberedSpeed = speed;
    if (ready) await player.setSpeed(speed);
    if (mounted) setState(() {});
  }

  int _totalMs(Duration position) {
    final stored = widget.message.voiceSeconds * 1000;
    final decoded = decodedDuration?.inMilliseconds ??
        player.duration?.inMilliseconds ??
        0;
    var total = decoded > stored ? decoded : stored;
    if (total <= 0) total = 1;
    if (position.inMilliseconds >= total &&
        player.processingState != ProcessingState.completed) {
      total = position.inMilliseconds + 350;
    }
    return total;
  }

  Future<void> _seek(double fraction) async {
    await _prepare();
    if (!ready) return;
    final total = _totalMs(player.position);
    await player.seek(
      Duration(milliseconds: (total * fraction.clamp(0.0, 1.0)).round()),
    );
  }

  @override
  Widget build(BuildContext context) => StreamBuilder<Duration>(
    stream: player.positionStream,
    builder: (_, snap) {
      final position = snap.data ?? Duration.zero;
      final totalMs = _totalMs(position);
      var progress =
          (position.inMilliseconds / totalMs).clamp(0.0, 1.0).toDouble();
      if (player.processingState == ProcessingState.completed) {
        progress = 1.0;
      } else if (progress >= .995) {
        progress = .985;
      }
      final totalSeconds = (totalMs / 1000).round();
      final heard = widget.message.mine
          ? widget.message.playedByOther
          : listened;
      final dark = Theme.of(context).brightness == Brightness.dark;
      final playColor = widget.message.mine
          ? Colors.white
          : const Color(0xFF118B78);
      final playIcon = widget.message.mine
          ? const Color(0xFF13284B)
          : Colors.white;
      final active = heard
          ? const Color(0xFF118B78)
          : (widget.message.mine
                ? const Color(0xFFBBD94C)
                : const Color(0xFF56B9AA));
      final inactive = widget.message.mine
          ? const Color(0x667D9250)
          : (dark ? const Color(0xFF526274) : const Color(0xFFBBDDD8));
      final meta = widget.message.mine ? Colors.white70 : AppColors.muted;

      Widget rateChip() => InkWell(
        borderRadius: BorderRadius.circular(18),
        onTap: _cycleSpeed,
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
          decoration: BoxDecoration(
            border: Border.all(color: active.withValues(alpha: .62)),
            borderRadius: BorderRadius.circular(18),
          ),
          child: Text(
            '${speed.toStringAsFixed(speed == 1.0 ? 0 : 1)}×',
            style: TextStyle(
              fontSize: 10.5,
              fontWeight: FontWeight.w900,
              color: active,
            ),
          ),
        ),
      );

      return ConstrainedBox(
        constraints: const BoxConstraints(minWidth: 250, maxWidth: 310),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Row(
              children: [
                Stack(
                  clipBehavior: Clip.none,
                  children: [
                    SizedBox(
                      width: 50,
                      height: 50,
                      child: IconButton.filled(
                        style: IconButton.styleFrom(
                          backgroundColor: playColor,
                          foregroundColor: playIcon,
                          padding: EdgeInsets.zero,
                        ),
                        onPressed: loading ? null : _toggle,
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
                              ),
                      ),
                    ),
                    if (!widget.message.mine && !heard)
                      Positioned(
                        right: -1,
                        top: -1,
                        child: Container(
                          width: 12,
                          height: 12,
                          decoration: BoxDecoration(
                            color: const Color(0xFFD9FF58),
                            shape: BoxShape.circle,
                            border: Border.all(
                              color: dark
                                  ? const Color(0xFF152133)
                                  : Colors.white,
                              width: 2,
                            ),
                          ),
                        ),
                      ),
                  ],
                ),
                const SizedBox(width: 9),
                Expanded(
                  child: LayoutBuilder(
                    builder: (context, constraints) => GestureDetector(
                      behavior: HitTestBehavior.opaque,
                      onTapDown: (d) => _seek(
                        d.localPosition.dx / constraints.maxWidth,
                      ),
                      onHorizontalDragUpdate: (d) => _seek(
                        d.localPosition.dx / constraints.maxWidth,
                      ),
                      child: SizedBox(
                        height: 34,
                        child: CustomPaint(
                          painter: _VoiceWavePainter(
                            progress: progress,
                            active: active,
                            inactive: inactive,
                            seed: widget.message.id,
                            wave: widget.message.voiceWave,
                          ),
                          child: const SizedBox.expand(),
                        ),
                      ),
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 4),
            Padding(
              padding: const EdgeInsets.only(left: 58),
              child: Row(
                children: [
                  Text(
                    _voiceDuration(totalSeconds),
                    style: TextStyle(
                      fontSize: 11,
                      fontWeight: FontWeight.w900,
                      color: active,
                    ),
                  ),
                  if (!widget.message.mine && !heard) ...[
                    const SizedBox(width: 7),
                    Container(
                      width: 7,
                      height: 7,
                      decoration: const BoxDecoration(
                        shape: BoxShape.circle,
                        color: Color(0xFF118B78),
                      ),
                    ),
                  ],
                  const Spacer(),
                  Text(
                    widget.message.time,
                    style: TextStyle(
                      fontSize: 10.5,
                      fontWeight: FontWeight.w500,
                      color: meta,
                    ),
                  ),
                  const SizedBox(width: 6),
                  rateChip(),
                  if (widget.message.mine && heard) ...[
                    const SizedBox(width: 5),
                    Text(
                      'played',
                      style: TextStyle(
                        fontSize: 10,
                        fontWeight: FontWeight.w800,
                        color: active,
                      ),
                    ),
                  ],
                  if (widget.message.mine) ...[
                    const SizedBox(width: 4),
                    Icon(
                      widget.message.read
                          ? Icons.done_all_rounded
                          : Icons.check_rounded,
                      size: 16,
                      color: widget.message.read
                          ? const Color(0xFF7CE8FF)
                          : Colors.white70,
                    ),
                  ],
                ],
              ),
            ),
          ],
        ),
      );
    },
  );

  String _voiceDuration(int s) =>
      '${s ~/ 60}:${(s % 60).toString().padLeft(2, '0')}';
}

'''
s = replace_between(s, voice_start, voice_end, voice_new, 'voice player')

# Sending/upload completion should jump only when a new message was added.
s = s.replace('      await _load();\n    } catch (e) {\n      textController.text = text;', '      await _load(jumpToBottom: true);\n    } catch (e) {\n      textController.text = text;', 1)
s = s.replace('      reply = null;\n      await _load();\n    } catch (e) {', '      reply = null;\n      await _load(jumpToBottom: true);\n    } catch (e) {', 1)
s = s.replace('      await _discardVoicePreview();\n      await _load();\n    } catch (e) {', '      await _discardVoicePreview();\n      await _load(jumpToBottom: true);\n    } catch (e) {', 1)
write(path, s)


# --------------------------------------------------------- conversation list refresh
path = 'flutter/lib/screens/conversations_screen.dart'
s = read(path)
s = replace_once(s, "import 'package:flutter/material.dart';\n", "import 'dart:async';\n\nimport 'package:flutter/material.dart';\n", 'conversation timer import')
s = replace_once(
    s,
    "  bool loading = true, archivedMode = false;\n  @override\n  void initState() {\n    super.initState();\n    _load();\n  }",
    "  bool loading = true, archivedMode = false, silentRefreshing = false;\n  Timer? refreshTimer;\n  @override\n  void initState() {\n    super.initState();\n    _load();\n    refreshTimer = Timer.periodic(\n      const Duration(seconds: 3),\n      (_) => _refreshSilently(),\n    );\n  }\n\n  @override\n  void dispose() {\n    refreshTimer?.cancel();\n    super.dispose();\n  }",
    'conversation timer state',
)
load_marker = '  @override\n  Widget build(BuildContext context) {'
refresh_method = '''  Future<void> _refreshSilently() async {
    if (!mounted || loading || silentRefreshing) return;
    silentRefreshing = true;
    try {
      final fresh = await AppScope.of(context).api.conversations(
        archived: archivedMode,
      );
      if (mounted && fresh.toString() != all.toString()) {
        setState(() => all = fresh);
      }
    } catch (_) {
      // Keep the inbox responsive when one background refresh misses.
    } finally {
      silentRefreshing = false;
    }
  }

'''
if refresh_method not in s:
    idx = s.find(load_marker)
    if idx < 0:
        raise RuntimeError('conversation build marker missing')
    s = s[:idx] + refresh_method + s[idx:]
write(path, s)


# ------------------------------------------------------------------ profile cleanup
path = 'flutter/lib/screens/profile_screen.dart'
s = read(path)
about_start = "            _tile(\n              Icons.info_outline_rounded,\n              'About TaleemPK',"
if about_start in s:
    a = s.find(about_start)
    # Find the end of this _tile entry by the next "            )," after the showAboutDialog block.
    marker = "              ),\n            ),\n"
    b = s.find(marker, a)
    if b < 0:
        raise RuntimeError('About TaleemPK block end not found')
    b += len(marker)
    s = s[:a] + s[b:]
s = s.replace("Version 2.3.0 · Made for Pakistan", "Version 2.5.0 · Made for Pakistan")
s = s.replace("applicationVersion: '2.3.0'", "applicationVersion: '2.5.0'")
write(path, s)


# --------------------------------------------------------------------- version
path = 'flutter/pubspec.yaml'
s = read(path)
import re
s = re.sub(r'^version:\s*[0-9.]+\+\d+$', 'version: 2.5.0+250', s, flags=re.M)
write(path, s)

print('chat runtime v2.5 patch applied')
