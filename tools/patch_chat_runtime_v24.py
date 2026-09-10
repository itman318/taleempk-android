from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def load(path):
    p = ROOT / path
    return p, p.read_text(encoding='utf-8')


def save(p, text):
    p.write_text(text, encoding='utf-8')


def once(text, old, new, label):
    if old not in text:
        raise SystemExit(f'patch anchor missing: {label}')
    return text.replace(old, new, 1)


# ---------------------------------------------------------------------------
# Flutter API: presence reads must never clear the sender's state.
# ---------------------------------------------------------------------------
p, c = load('flutter/lib/core/api_client.dart')
old = """  Future<ChatPresence> presence(int conversationId, String kind) async =>
      ChatPresence.fromJson(
        await _request({
          'action': 'presence',
          'conversation_id': '$conversationId',
          'kind': kind,
        }),
      );
"""
new = """  Future<ChatPresence> presence(
    int conversationId, {
    String? kind,
    bool clear = false,
  }) async =>
      ChatPresence.fromJson(
        await _request({
          'action': 'presence',
          'conversation_id': '$conversationId',
          if (kind != null && kind.isNotEmpty) 'kind': kind,
          if (clear) 'clear': '1',
        }),
      );
"""
c = once(c, old, new, 'api presence signature')
save(p, c)


# ---------------------------------------------------------------------------
# Flutter chat runtime: durable typing/recording presence, visible indicators,
# website-shaped voice player, and correct delete-for-me behavior.
# ---------------------------------------------------------------------------
p, c = load('flutter/lib/screens/chat_screen.dart')

c = once(
    c,
    "Timer? poll, recordTimer, waveTimer, presenceDebounce;",
    "Timer? poll, recordTimer, waveTimer, presenceDebounce, typingHeartbeat;",
    'typing heartbeat timer',
)

c = once(
    c,
    """    waveTimer?.cancel();
    presenceDebounce?.cancel();
    recorder.dispose();
""",
    """    waveTimer?.cancel();
    presenceDebounce?.cancel();
    typingHeartbeat?.cancel();
    recorder.dispose();
""",
    'dispose heartbeat',
)

c = once(
    c,
    """  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) _poll();
  }
""",
    """  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) {
      _poll();
      return;
    }
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
  }
""",
    'lifecycle presence clear',
)

c = once(
    c,
    """      final p = await AppScope.of(context).api
          .presence(widget.conversation.id, '');
""",
    """      final p = await AppScope.of(context).api
          .presence(widget.conversation.id);
""",
    'poll read-only presence',
)

old_typing = """  void _typing() {
    if (mounted) setState(() {});
    presenceDebounce?.cancel();
    if (textController.text.trim().isNotEmpty && !typingSent) {
      typingSent = true;
      AppScope.of(context).api
          .presence(widget.conversation.id, 'text')
          .catchError(
            (_) => const ChatPresence(
              active: false,
              kind: '',
              name: '',
              readThrough: 0,
            ),
          );
    }
    presenceDebounce = Timer(const Duration(seconds: 2), () {
      typingSent = false;
      if (mounted) {
        AppScope.of(context).api.presence(widget.conversation.id, '');
      }
    });
  }
"""
new_typing = """  void _typing() {
    if (mounted) setState(() {});
    presenceDebounce?.cancel();
    final hasText = textController.text.trim().isNotEmpty;

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
  }
"""
c = once(c, old_typing, new_typing, 'typing heartbeat implementation')

# Header wording mirrors the website terminology.
c = c.replace("? '${presence!.name} is recording…'", "? '${presence!.name} is recording voice…'")

# Add an in-thread presence card directly above the composer.
c = once(
    c,
    """          ),
          if (recording) _recordingBar(),
""",
    """          ),
          if (presence?.active == true)
            _ChatPresenceBubble(
              name: presence!.name,
              voice: presence!.kind == 'voice',
            ),
          if (recording) _recordingBar(),
""",
    'presence bubble in body',
)

# Presence API call sites.
c = c.replace(".presence(widget.conversation.id, 'voice')", ".presence(widget.conversation.id, kind: 'voice')")
c = c.replace(".presence(widget.conversation.id, '')", ".presence(widget.conversation.id, clear: true)")

# Received messages must also support delete-for-me, just like the website.
old_delete_tile = """            if (m.mine)
              ListTile(
                leading: const Icon(
                  Icons.delete_outline_rounded,
                  color: AppColors.danger,
                ),
                title: const Text(
                  'Delete',
                  style: TextStyle(color: AppColors.danger),
                ),
                onTap: () {
                  Navigator.pop(sheet);
                  _delete(m);
                },
              ),
"""
new_delete_tile = """            ListTile(
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
"""
c = once(c, old_delete_tile, new_delete_tile, 'received delete-for-me menu')

old_delete = """  Future<void> _delete(ChatMessage m) async {
    final everyone =
        await showDialog<bool>(
          context: context,
          builder: (d) => AlertDialog(
            title: const Text('Delete message?'),
            content: const Text(
              'Choose whether to remove it only for you or for everyone.',
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(d, false),
                child: const Text('For me'),
              ),
              FilledButton(
                onPressed: () => Navigator.pop(d, true),
                child: const Text('For everyone'),
              ),
            ],
          ),
        ) ??
        false;
    await AppScope.of(context).api.deleteMessage(m.id, everyone: everyone);
    _load();
  }
"""
new_delete = """  Future<void> _delete(ChatMessage m) async {
    var everyone = false;
    if (m.mine) {
      everyone =
          await showDialog<bool>(
            context: context,
            builder: (d) => AlertDialog(
              title: const Text('Delete message?'),
              content: const Text(
                'Choose whether to remove it only for you or for everyone.',
              ),
              actions: [
                TextButton(
                  onPressed: () => Navigator.pop(d, false),
                  child: const Text('For me'),
                ),
                FilledButton(
                  onPressed: () => Navigator.pop(d, true),
                  child: const Text('For everyone'),
                ),
              ],
            ),
          ) ??
          false;
    } else {
      final confirmed =
          await showDialog<bool>(
            context: context,
            builder: (d) => AlertDialog(
              title: const Text('Delete for me?'),
              content: const Text(
                'This message will disappear from your copy of the conversation only.',
              ),
              actions: [
                TextButton(
                  onPressed: () => Navigator.pop(d, false),
                  child: const Text('Cancel'),
                ),
                FilledButton(
                  onPressed: () => Navigator.pop(d, true),
                  child: const Text('Delete for me'),
                ),
              ],
            ),
          ) ??
          false;
      if (!confirmed) return;
    }
    try {
      await AppScope.of(context).api.deleteMessage(m.id, everyone: everyone);
      await _load();
    } catch (e) {
      if (mounted) showMessage(context, apiMessage(e));
    }
  }
"""
c = once(c, old_delete, new_delete, 'delete behavior')

# Replace the voice player with the website layout: play + waveform + speed on
# the first row, duration/unplayed dot on the left of the meta row, time/played/
# receipt on the right. Speed is remembered for the next voice note.
start = c.index('class VoiceBubble extends StatefulWidget')
end = c.index('class _VoiceWavePainter extends CustomPainter')
voice = r'''class VoiceBubble extends StatefulWidget {
  const VoiceBubble({super.key, required this.message, required this.api});
  final ChatMessage message;
  final ApiClient api;

  @override
  State<VoiceBubble> createState() => _VoiceBubbleState();
}

class _VoiceBubbleState extends State<VoiceBubble> {
  static double rememberedSpeed = 1.0;
  final player = AudioPlayer();
  bool ready = false, listened = false, loading = false;
  String? localPath;
  late double speed = rememberedSpeed;

  @override
  void initState() {
    super.initState();
    listened = widget.message.playedByMe;
  }

  @override
  void dispose() {
    player.dispose();
    final path = localPath;
    if (path != null) {
      try {
        File(path).deleteSync();
      } catch (_) {}
    }
    super.dispose();
  }

  Future<void> _prepare() async {
    if (ready || loading) return;
    loading = true;
    if (mounted) setState(() {});
    try {
      final bytes = await widget.api.attachmentBytes(
        widget.message.attachmentUrl!,
      );
      final dir = await getTemporaryDirectory();
      localPath = '${dir.path}/taleempk_voice_${widget.message.id}.m4a';
      await File(localPath!).writeAsBytes(bytes, flush: true);
      await player.setFilePath(localPath!);
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

  Future<void> _seek(double fraction) async {
    await _prepare();
    if (!ready) return;
    final total = player.duration ?? Duration(seconds: widget.message.voiceSeconds);
    await player.seek(
      Duration(
        milliseconds: (total.inMilliseconds * fraction.clamp(0.0, 1.0)).round(),
      ),
    );
  }

  @override
  Widget build(BuildContext context) => StreamBuilder<Duration>(
    stream: player.positionStream,
    builder: (_, snap) {
      final position = snap.data ?? Duration.zero;
      final knownTotal =
          player.duration ?? Duration(seconds: widget.message.voiceSeconds);
      final totalMs = knownTotal.inMilliseconds > 0
          ? knownTotal.inMilliseconds
          : 1;
      final progress =
          (position.inMilliseconds / totalMs).clamp(0.0, 1.0).toDouble();
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
                const SizedBox(width: 8),
                InkWell(
                  borderRadius: BorderRadius.circular(22),
                  onTap: _cycleSpeed,
                  child: Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 10,
                      vertical: 6,
                    ),
                    decoration: BoxDecoration(
                      border: Border.all(
                        color: active.withValues(alpha: .65),
                      ),
                      borderRadius: BorderRadius.circular(22),
                    ),
                    child: Text(
                      '${speed.toStringAsFixed(speed == 1.0 ? 0 : 1)}×',
                      style: TextStyle(
                        fontSize: 11,
                        fontWeight: FontWeight.w900,
                        color: active,
                      ),
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 2),
            Padding(
              padding: const EdgeInsets.only(left: 58),
              child: Row(
                children: [
                  Text(
                    _voiceDuration(widget.message.voiceSeconds),
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
c = c[:start] + voice + c[end:]

# Add animated typing / voice-recording bubble before the existing pulse dot.
presence_widget = r'''class _ChatPresenceBubble extends StatefulWidget {
  const _ChatPresenceBubble({required this.name, required this.voice});
  final String name;
  final bool voice;

  @override
  State<_ChatPresenceBubble> createState() => _ChatPresenceBubbleState();
}

class _ChatPresenceBubbleState extends State<_ChatPresenceBubble>
    with SingleTickerProviderStateMixin {
  late final AnimationController controller = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 900),
  )..repeat();

  @override
  void dispose() {
    controller.dispose();
    super.dispose();
  }

  double pulse(double phase) {
    final v = (controller.value + phase) % 1.0;
    return v < .5 ? .35 + v * 1.3 : 1.0 - (v - .5) * 1.3;
  }

  @override
  Widget build(BuildContext context) => AnimatedBuilder(
    animation: controller,
    builder: (_, __) => Align(
      alignment: Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.fromLTRB(14, 3, 14, 7),
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        decoration: BoxDecoration(
          color: Theme.of(context).brightness == Brightness.dark
              ? const Color(0xFF152133)
              : Colors.white,
          borderRadius: const BorderRadius.only(
            topLeft: Radius.circular(18),
            topRight: Radius.circular(18),
            bottomRight: Radius.circular(18),
            bottomLeft: Radius.circular(5),
          ),
          boxShadow: const [
            BoxShadow(
              color: Color(0x1008142F),
              blurRadius: 9,
              offset: Offset(0, 3),
            ),
          ],
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            if (widget.voice) ...[
              const Icon(
                Icons.mic_rounded,
                size: 17,
                color: Color(0xFF118B78),
              ),
              const SizedBox(width: 7),
              for (var i = 0; i < 4; i++) ...[
                Container(
                  width: 3,
                  height: 7 + 11 * pulse(i * .17),
                  decoration: BoxDecoration(
                    color: const Color(0xFF118B78),
                    borderRadius: BorderRadius.circular(3),
                  ),
                ),
                if (i != 3) const SizedBox(width: 2),
              ],
              const SizedBox(width: 8),
              Text(
                '${widget.name} is recording voice…',
                style: const TextStyle(
                  fontSize: 11.5,
                  fontWeight: FontWeight.w700,
                  color: Color(0xFF118B78),
                ),
              ),
            ] else ...[
              for (var i = 0; i < 3; i++) ...[
                Opacity(
                  opacity: pulse(i * .22).clamp(.3, 1.0),
                  child: const CircleAvatar(
                    radius: 3.2,
                    backgroundColor: AppColors.blue,
                  ),
                ),
                if (i != 2) const SizedBox(width: 4),
              ],
              const SizedBox(width: 9),
              Text(
                '${widget.name} is typing…',
                style: const TextStyle(
                  fontSize: 11.5,
                  fontWeight: FontWeight.w700,
                  color: AppColors.blue,
                ),
              ),
            ],
          ],
        ),
      ),
    ),
  );
}

'''
marker = 'class _PulseDot extends StatefulWidget {'
if marker not in c:
    raise SystemExit('patch anchor missing: presence widget insertion')
c = c.replace(marker, presence_widget + marker, 1)

# Draw a visible playhead over the waveform, like the website control.
old_paint_tail = """      canvas.drawLine(Offset(x, y1), Offset(x, y2), paint);
    }
  }
"""
new_paint_tail = """      canvas.drawLine(Offset(x, y1), Offset(x, y2), paint);
    }
    if (progress > 0 && progress < 1) {
      final head = Paint()
        ..color = active
        ..strokeWidth = 2.2
        ..strokeCap = StrokeCap.round;
      final x = (size.width * progress).clamp(1.0, size.width - 1.0);
      canvas.drawLine(Offset(x, 2), Offset(x, size.height - 2), head);
    }
  }
"""
c = once(c, old_paint_tail, new_paint_tail, 'waveform playhead')

save(p, c)


# ---------------------------------------------------------------------------
# Mobile backend: read-only presence queries; explicit update/clear; privacy.
# ---------------------------------------------------------------------------
for path in ('flutter/backend/api/mobile.php', 'backend/api/mobile.php'):
    p, c = load(path)
    start = c.index("if ($action === 'presence') {")
    end = c.index("if ($action === 'messages') {", start)
    block = r'''if ($action === 'presence') {
    require_feature('feature_chat');
    $cid = (int)($_POST['conversation_id'] ?? 0);
    $member = fetch_one('SELECT id FROM conversation_members WHERE conversation_id=? AND user_id=?', [$cid,$uid]);
    if (!$member) mobile_error('That conversation is not yours.', 403);

    /* Reading another person's presence must never mutate mine. The previous
       mobile endpoint treated an omitted/empty kind as "clear my status", and
       the Flutter poll used exactly that call every ~2 seconds. The app was
       therefore erasing its own typing/recording flag as fast as it set it. */
    $hasKind = array_key_exists('kind', $_POST);
    $clear = !empty($_POST['clear']);
    $kind = strtolower(trim((string)($_POST['kind'] ?? '')));
    if (!in_array($kind, ['text','voice'], true)) $kind = '';
    $sharesTyping = (int)($u['show_typing'] ?? 1) === 1;

    try {
        if ($clear) {
            q('UPDATE conversation_members SET typing_at=NULL,typing_kind=NULL WHERE conversation_id=? AND user_id=?', [$cid,$uid]);
        } elseif ($hasKind && $sharesTyping && $kind !== '') {
            q('UPDATE conversation_members SET typing_at=NOW(),typing_kind=? WHERE conversation_id=? AND user_id=?', [$kind,$cid,$uid]);
        } elseif ($hasKind && !$sharesTyping) {
            q('UPDATE conversation_members SET typing_at=NULL,typing_kind=NULL WHERE conversation_id=? AND user_id=?', [$cid,$uid]);
        }
        $other = $sharesTyping ? fetch_one("SELECT cm.typing_kind,u.name FROM conversation_members cm
                             JOIN users u ON u.id=cm.user_id
                            WHERE cm.conversation_id=? AND cm.user_id<>?
                              AND COALESCE(u.show_typing,1)=1
                              AND cm.typing_at>=DATE_SUB(NOW(),INTERVAL 8 SECOND)
                            ORDER BY cm.typing_at DESC LIMIT 1", [$cid,$uid]) : null;
    } catch (PDOException $e) {
        if ($clear) {
            q('UPDATE conversation_members SET typing_at=NULL WHERE conversation_id=? AND user_id=?', [$cid,$uid]);
        } elseif ($hasKind && $sharesTyping && $kind !== '') {
            q('UPDATE conversation_members SET typing_at=NOW() WHERE conversation_id=? AND user_id=?', [$cid,$uid]);
        } elseif ($hasKind && !$sharesTyping) {
            q('UPDATE conversation_members SET typing_at=NULL WHERE conversation_id=? AND user_id=?', [$cid,$uid]);
        }
        $other = $sharesTyping ? fetch_one("SELECT 'text' typing_kind,u.name FROM conversation_members cm
                             JOIN users u ON u.id=cm.user_id
                            WHERE cm.conversation_id=? AND cm.user_id<>?
                              AND COALESCE(u.show_typing,1)=1
                              AND cm.typing_at>=DATE_SUB(NOW(),INTERVAL 8 SECOND)
                            ORDER BY cm.typing_at DESC LIMIT 1", [$cid,$uid]) : null;
    }
    $readThrough = (int)fetch_col('SELECT COALESCE(MAX(last_read_id),0) FROM conversation_members WHERE conversation_id=? AND user_id<>?', [$cid,$uid]);
    mobile_out([
        'active'=>(bool)$other,
        'kind'=>$other ? (string)($other['typing_kind'] ?: 'text') : '',
        'name'=>$other ? (string)$other['name'] : '',
        'read_through'=>$readThrough,
    ]);
}

'''
    c = c[:start] + block + c[end:]
    save(p, c)


# ---------------------------------------------------------------------------
# Website backend parity: web was sending `typing=voice` but always storing
# typing_kind=text, so web->app recording presence could never be truthful.
# ---------------------------------------------------------------------------
for path in ('backend/api/chat_poll.php', 'flutter/backend/api/chat_poll.php'):
    p = ROOT / path
    if not p.exists():
        continue
    c = p.read_text(encoding='utf-8')
    c = once(
        c,
        "$typingKind = 'text';",
        "$typingKind = $typingRaw === 'voice' ? 'voice' : 'text';",
        f'{path} voice typing kind',
    )
    save(p, c)

print('Deep chat runtime patch applied.')
