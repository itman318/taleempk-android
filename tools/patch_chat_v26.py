from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
CHAT = ROOT / 'flutter/lib/screens/chat_screen.dart'
MODELS = ROOT / 'flutter/lib/core/models.dart'
PUBSPEC = ROOT / 'flutter/pubspec.yaml'


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f'patch anchor missing: {label}')
    return text.replace(old, new, 1)


c = CHAT.read_text(encoding='utf-8')

# Recent emoji history is stored locally on-device.
c = replace_once(
    c,
    "import 'package:record/record.dart';\nimport 'package:url_launcher/url_launcher.dart';",
    "import 'package:record/record.dart';\nimport 'package:shared_preferences/shared_preferences.dart';\nimport 'package:url_launcher/url_launcher.dart';",
    'shared_preferences import',
)

c = replace_once(
    c,
    "  final voiceLevels = <double>[];\n  List<Map<String, dynamic>> pinnedMessages = const [];",
    "  final voiceLevels = <double>[];\n  List<String> recentEmojis = <String>[];\n  List<Map<String, dynamic>> pinnedMessages = const [];",
    'recent emoji state',
)

c = replace_once(
    c,
    "    scroll.addListener(_historyListener);\n    _load(jumpToBottom: true);",
    "    scroll.addListener(_historyListener);\n    _loadRecentEmojis();\n    _load(jumpToBottom: true);",
    'load recent emojis',
)

# Preserve locally acknowledged voice-play state while the periodic server reconciliation replaces objects.
c = replace_once(
    c,
    "            if (old.mine && old.playedByOther) {\n              candidate.playedByOther = true;\n            }\n            messages[index] = candidate;",
    "            if (old.mine && old.playedByOther) {\n              candidate.playedByOther = true;\n            }\n            if (!old.mine && old.playedByMe) {\n              candidate.playedByMe = true;\n            }\n            messages[index] = candidate;",
    'preserve played by me',
)

# Message identity must survive list insertions/removals. This prevents an AudioPlayer state
# from being recycled onto another voice bubble during realtime updates.
c = replace_once(
    c,
    "        return Column(\n          children: [\n            if (showDate)",
    "        return KeyedSubtree(\n          key: ValueKey<int>(m.id),\n          child: Column(\n            children: [\n            if (showDate)",
    'message keyed subtree open',
)
c = replace_once(
    c,
    "            _bubble(m),\n          ],\n        );\n      },\n    );\n  }\n\n  Widget _bubble",
    "            _bubble(m),\n            ],\n          ),\n        );\n      },\n    );\n  }\n\n  Widget _bubble",
    'message keyed subtree close',
)

# Null-safe swipe velocity and animated full voice-bubble listened colour.
bstart = c.index('  Widget _bubble(ChatMessage m) => Align(')
bend = c.index('  Widget _quoted(', bstart)
b = c[bstart:bend]
b = replace_once(
    b,
    "      onHorizontalDragEnd: (d) {\n        if (d.primaryVelocity!.abs() > 280)",
    "      onHorizontalDragEnd: (d) {\n        final velocity = d.primaryVelocity ?? 0;\n        if (velocity.abs() > 280)",
    'safe swipe velocity',
)
b = replace_once(
    b,
    "      child: Container(\n        constraints: BoxConstraints(",
    "      child: AnimatedContainer(\n        duration: const Duration(milliseconds: 220),\n        curve: Curves.easeOut,\n        constraints: BoxConstraints(",
    'animated bubble',
)
b = replace_once(
    b,
    "          color: m.voiceSeconds > 0\n              ? (m.mine\n                    ? const Color(0xFF172B4D)\n                    : (Theme.of(context).brightness == Brightness.dark\n                          ? const Color(0xFF152133)\n                          : Colors.white))",
    "          color: m.voiceSeconds > 0\n              ? (m.mine\n                    ? const Color(0xFF172B4D)\n                    : (m.playedByMe\n                          ? (Theme.of(context).brightness == Brightness.dark\n                                ? const Color(0xFF10342F)\n                                : const Color(0xFFDDF5EE))\n                          : (Theme.of(context).brightness == Brightness.dark\n                                ? const Color(0xFF152133)\n                                : Colors.white)))",
    'voice listened bubble color',
)
b = replace_once(
    b,
    "              VoiceBubble(message: m, api: AppScope.of(context).api)",
    "              VoiceBubble(\n                key: ValueKey<String>('voice-${m.id}'),\n                message: m,\n                api: AppScope.of(context).api,\n                beforePlay: () async {\n                  if (voicePreviewPlayer.playing) {\n                    await voicePreviewPlayer.pause();\n                  }\n                },\n                onListened: () {\n                  if (!m.playedByMe && mounted) {\n                    setState(() => m.playedByMe = true);\n                  }\n                },\n              )",
    'voice bubble callback',
)
c = c[:bstart] + b + c[bend:]

# Rich emoji picker with WhatsApp-style recent history.
emoji_pattern = re.compile(r"  Widget _emojiPanel\(\) \{.*?\n  Widget _recordingBar\(\)", re.S)
emoji_replacement = r'''  Future<void> _loadRecentEmojis() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final saved = prefs.getStringList('chat_recent_emojis') ?? const <String>[];
      if (!mounted) return;
      setState(() {
        recentEmojis = saved.where((e) => e.trim().isNotEmpty).take(24).toList();
      });
    } catch (_) {
      // Emoji history is a convenience feature; chat remains usable without it.
    }
  }

  Future<void> _insertEmoji(String emoji) async {
    final value = textController.value;
    final text = value.text;
    var start = value.selection.start;
    var end = value.selection.end;
    if (start < 0 || end < 0 || start > text.length || end > text.length) {
      start = text.length;
      end = text.length;
    }
    if (start > end) {
      final tmp = start;
      start = end;
      end = tmp;
    }
    final next = text.replaceRange(start, end, emoji);
    final caret = start + emoji.length;
    textController.value = TextEditingValue(
      text: next,
      selection: TextSelection.collapsed(offset: caret),
    );

    final updated = <String>[
      emoji,
      ...recentEmojis.where((e) => e != emoji),
    ].take(24).toList();
    if (mounted) setState(() => recentEmojis = updated);
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setStringList('chat_recent_emojis', updated);
    } catch (_) {}
  }

  Widget _emojiPanel() {
    const emoji = <String>[
      '😀','😃','😄','😁','😆','😅','😂','🤣','🥲','☺️','😊','😇','🙂','🙃','😉','😌',
      '😍','🥰','😘','😗','😙','😚','😋','😛','😝','😜','🤪','🤨','🧐','🤓','😎','🥸','🤩','🥳',
      '😏','😒','😞','😔','😟','😕','🙁','☹️','😣','😖','😫','😩','🥺','😢','😭','😤','😠','😡','🤬',
      '🤯','😳','🥵','🥶','😱','😨','😰','😥','😓','🤗','🤔','🫡','🤭','🫢','🫣','🤫','🤥','😶','🫥',
      '😐','🫤','😑','😬','🙄','😯','😦','😧','😮','😲','🥱','😴','🤤','😪','😵','😵‍💫','🤐','🥴',
      '🤢','🤮','🤧','😷','🤒','🤕','🤑','🤠','😈','👿','👹','👺','🤡','💩','👻','💀','☠️','👽','👾','🤖',
      '👍','👎','👌','🤌','🤏','✌️','🤞','🫰','🤟','🤘','🤙','👈','👉','👆','👇','☝️','✋','🤚','🖐️',
      '🖖','👋','🤝','👏','🙌','🫶','👐','🤲','🙏','✍️','💅','🤳','💪','🦾','🦵','🦶','👂','👃','🧠','🫀',
      '🫁','🦷','🦴','👀','👁️','👅','👄','🫦','👶','🧒','👦','👧','🧑','👱','👨','🧔','👩','🧓','👴','👵',
      '❤️','🩷','🧡','💛','💚','💙','🩵','💜','🤎','🖤','🩶','🤍','💔','❤️‍🔥','❤️‍🩹','❣️','💕','💞','💓',
      '💗','💖','💘','💝','💟','💋','💌','💢','💥','💫','💦','💨','🕳️','💬','👁️‍🗨️','🗨️','🗯️','💭','💤',
      '🔥','✨','⭐','🌟','⚡','☀️','🌤️','⛅','🌥️','☁️','🌧️','⛈️','🌩️','🌨️','❄️','☃️','🌈','☔','💧','🌊',
      '🎉','🎊','🎈','🎁','🎀','🏆','🥇','🥈','🥉','⚽','🏏','🏀','🏐','🎾','🏸','🎯','🎮','🎲','♟️','🎵','🎶',
      '📚','📖','📕','📗','📘','📙','📓','📔','📒','📝','✏️','🖊️','🖋️','📌','📍','📎','📐','📏','🎓','💡','🔬',
      '💻','⌨️','🖥️','📱','☎️','📷','🎥','🎙️','🔋','🔌','💾','💿','📀','⌚','⏰','🔔','🔕','✅','❌','⚠️',
      '❓','❗','‼️','⁉️','💯','🔒','🔓','🔐','🔑','🛡️','🚀','✈️','🚗','🏠','🏢','🏫','🏥','🕌','🌍','🌎','🌏',
      '🍎','🍏','🍊','🍋','🍌','🍉','🍇','🍓','🫐','🍒','🥭','🍍','🥝','🍅','🥑','🥕','🌽','🍞','🥐','🍕','🍔',
      '🍟','🍗','🍚','🍜','🍰','🎂','🍫','🍪','☕','🫖','🥤','🧃','💐','🌹','🌷','🌸','🌺','🌻','🌼','🍀','🌿',
      '🐶','🐱','🐭','🐹','🐰','🦊','🐻','🐼','🐨','🐯','🦁','🐮','🐷','🐸','🐵','🐔','🐧','🐦','🦅','🦆','🦋',
      '🇵🇰','🇦🇪','🇦🇺','🇬🇧','🇺🇸','🇨🇦','🇸🇦','🇹🇷','🇶🇦','🇯🇵','🇰🇷','🇨🇳','🇩🇪','🇫🇷','🇮🇹','🇪🇸'
    ];

    Widget emojiButton(String e, {double size = 25}) => Material(
      color: Colors.transparent,
      child: InkWell(
        borderRadius: BorderRadius.circular(12),
        onTap: () => _insertEmoji(e),
        child: Center(child: Text(e, style: TextStyle(fontSize: size))),
      ),
    );

    return Container(
      height: 292,
      color: Theme.of(context).colorScheme.surface,
      padding: const EdgeInsets.fromLTRB(10, 8, 10, 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (recentEmojis.isNotEmpty) ...[
            Padding(
              padding: const EdgeInsets.fromLTRB(4, 0, 4, 5),
              child: Row(
                children: [
                  const Icon(Icons.history_rounded, size: 16, color: AppColors.muted),
                  const SizedBox(width: 6),
                  Text(
                    'Recent',
                    style: TextStyle(
                      fontSize: 11.5,
                      fontWeight: FontWeight.w800,
                      color: Theme.of(context).colorScheme.onSurfaceVariant,
                    ),
                  ),
                ],
              ),
            ),
            SizedBox(
              height: 45,
              child: ListView.separated(
                scrollDirection: Axis.horizontal,
                itemCount: recentEmojis.length,
                separatorBuilder: (_, _) => const SizedBox(width: 2),
                itemBuilder: (_, i) => SizedBox(
                  width: 42,
                  child: emojiButton(recentEmojis[i], size: 24),
                ),
              ),
            ),
            const Divider(height: 10),
          ],
          Padding(
            padding: const EdgeInsets.fromLTRB(4, 0, 4, 5),
            child: Row(
              children: [
                const Icon(Icons.emoji_emotions_outlined, size: 16, color: AppColors.muted),
                const SizedBox(width: 6),
                Text(
                  'Emojis',
                  style: TextStyle(
                    fontSize: 11.5,
                    fontWeight: FontWeight.w800,
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
                ),
                const Spacer(),
                Text(
                  '${emoji.length}',
                  style: const TextStyle(fontSize: 10.5, color: AppColors.muted),
                ),
              ],
            ),
          ),
          Expanded(
            child: GridView.builder(
              padding: EdgeInsets.zero,
              gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                crossAxisCount: 8,
                mainAxisSpacing: 2,
                crossAxisSpacing: 2,
              ),
              itemCount: emoji.length,
              itemBuilder: (_, i) => emojiButton(emoji[i]),
            ),
          ),
        ],
      ),
    );
  }

  Widget _recordingBar()'''
if not emoji_pattern.search(c):
    raise SystemExit('patch anchor missing: emoji panel function')
c = emoji_pattern.sub(emoji_replacement, c, count=1)

# Fix the block banner collapse caused by the global FilledButton infinite-width minimum.
blocked_pattern = re.compile(r"  Widget _blockedBanner\(\) => Container\(.*?\n  Future<void> _startCall", re.S)
blocked_replacement = r'''  Widget _blockedBanner() => Container(
    margin: const EdgeInsets.fromLTRB(12, 8, 12, 10),
    padding: const EdgeInsets.fromLTRB(16, 13, 14, 13),
    decoration: BoxDecoration(
      color: Theme.of(context).colorScheme.surface,
      borderRadius: BorderRadius.circular(20),
      border: Border.all(color: Theme.of(context).dividerColor),
    ),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      mainAxisSize: MainAxisSize.min,
      children: [
        Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Container(
              width: 38,
              height: 38,
              decoration: BoxDecoration(
                color: AppColors.muted.withValues(alpha: .10),
                shape: BoxShape.circle,
              ),
              child: const Icon(
                Icons.lock_outline_rounded,
                size: 20,
                color: AppColors.muted,
              ),
            ),
            const SizedBox(width: 11),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(
                    selfBlocked
                        ? 'You blocked ${widget.conversation.title}'
                        : 'Messaging is unavailable',
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(
                      fontSize: 14,
                      fontWeight: FontWeight.w800,
                      color: Theme.of(context).colorScheme.onSurface,
                    ),
                  ),
                  const SizedBox(height: 3),
                  Text(
                    selfBlocked
                        ? 'You can’t send or receive new messages from this person.'
                        : 'This person has blocked this conversation.',
                    style: const TextStyle(
                      fontSize: 12,
                      height: 1.32,
                      color: AppColors.muted,
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
        if (selfBlocked) ...[
          const SizedBox(height: 10),
          Align(
            alignment: Alignment.centerRight,
            child: SizedBox(
              width: 112,
              child: FilledButton(
                style: FilledButton.styleFrom(
                  minimumSize: const Size(0, 42),
                  padding: const EdgeInsets.symmetric(horizontal: 14),
                  textStyle: const TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.w800,
                  ),
                ),
                onPressed: _toggleBlock,
                child: const Text('Unblock'),
              ),
            ),
          ),
        ],
      ],
    ),
  );

  Future<void> _startCall'''
if not blocked_pattern.search(c):
    raise SystemExit('patch anchor missing: blocked banner')
c = blocked_pattern.sub(blocked_replacement, c, count=1)

# Replace voice playback with one-active-player coordination, retryable cache,
# immediate listened state, and a clearer premium footer.
voice_pattern = re.compile(r"class VoiceBubble extends StatefulWidget \{.*?\nclass _VoiceWavePainter", re.S)
voice_replacement = r'''class VoiceBubble extends StatefulWidget {
  const VoiceBubble({
    super.key,
    required this.message,
    required this.api,
    this.onListened,
    this.beforePlay,
  });
  final ChatMessage message;
  final ApiClient api;
  final VoidCallback? onListened;
  final Future<void> Function()? beforePlay;

  @override
  State<VoiceBubble> createState() => _VoiceBubbleState();
}

class _VoiceBubbleState extends State<VoiceBubble> {
  static double rememberedSpeed = 1.0;
  static _VoiceBubbleState? activeVoice;

  final player = AudioPlayer();
  StreamSubscription<Duration?>? durationSub;
  StreamSubscription<PlayerState>? stateSub;
  bool ready = false, listened = false, loading = false, preparing = false;
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
    stateSub = player.playerStateStream.listen((state) {
      if (state.processingState == ProcessingState.completed) {
        if (activeVoice == this) activeVoice = null;
        if (mounted) setState(() {});
      }
    });
  }

  @override
  void didUpdateWidget(covariant VoiceBubble oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.message.id != widget.message.id) {
      unawaited(_resetForMessage());
    } else if (widget.message.playedByMe) {
      listened = true;
    }
  }

  Future<void> _resetForMessage() async {
    if (activeVoice == this) activeVoice = null;
    await player.stop();
    ready = false;
    loading = false;
    preparing = false;
    decodedDuration = null;
    localPath = null;
    listened = widget.message.playedByMe;
    if (mounted) setState(() {});
  }

  @override
  void dispose() {
    if (activeVoice == this) activeVoice = null;
    durationSub?.cancel();
    stateSub?.cancel();
    player.dispose();
    super.dispose();
  }

  Future<void> _downloadFresh(File file) async {
    final bytes = await widget.api.attachmentBytes(widget.message.attachmentUrl!);
    await file.writeAsBytes(bytes, flush: true);
  }

  Future<void> _prepare() async {
    if (ready || preparing) return;
    preparing = true;
    loading = true;
    if (mounted) setState(() {});
    try {
      final dir = await getTemporaryDirectory();
      localPath = '${dir.path}/taleempk_voice_${widget.message.id}.m4a';
      final file = File(localPath!);
      if (!await file.exists() || await file.length() < 256) {
        await _downloadFresh(file);
      }
      try {
        await player.setFilePath(localPath!);
      } catch (_) {
        // A partial/corrupt cached voice note must never be reused.
        try {
          if (await file.exists()) await file.delete();
        } catch (_) {}
        await _downloadFresh(file);
        await player.setFilePath(localPath!);
      }
      await player.setLoopMode(LoopMode.off);
      decodedDuration = player.duration;
      await player.setSpeed(speed);
      ready = true;
    } finally {
      preparing = false;
      loading = false;
      if (mounted) setState(() {});
    }
  }

  Future<void> _pauseForAnotherVoice() async {
    if (player.playing) await player.pause();
    if (mounted) setState(() {});
  }

  Future<void> _playToEnd() async {
    try {
      await player.play();
    } catch (_) {
      // The visible toggle path reports preparation errors. Playback interruptions
      // are treated like a normal pause so the user can tap play again.
    } finally {
      if (activeVoice == this && !player.playing) activeVoice = null;
      if (mounted) setState(() {});
    }
  }

  Future<void> _toggle() async {
    try {
      await _prepare();
      if (!ready) return;

      if (player.playing) {
        await player.pause();
        if (activeVoice == this) activeVoice = null;
        if (mounted) setState(() {});
        return;
      }

      final previous = activeVoice;
      if (previous != null && previous != this) {
        await previous._pauseForAnotherVoice();
      }
      activeVoice = this;
      if (widget.beforePlay != null) await widget.beforePlay!();

      if (!listened && !widget.message.mine) {
        listened = true;
        widget.message.playedByMe = true;
        widget.onListened?.call();
        unawaited(widget.api.markVoicePlayed(widget.message.id).catchError((_) {}));
      }
      if (player.processingState == ProcessingState.completed) {
        await player.seek(Duration.zero);
      }
      unawaited(_playToEnd());
      if (mounted) setState(() {});
    } catch (e) {
      if (activeVoice == this) activeVoice = null;
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
      final currentSeconds = position.inSeconds.clamp(0, totalSeconds);
      final heard = widget.message.mine
          ? widget.message.playedByOther
          : (listened || widget.message.playedByMe);
      final dark = Theme.of(context).brightness == Brightness.dark;
      final playColor = widget.message.mine
          ? Colors.white
          : (heard ? const Color(0xFF22A487) : const Color(0xFF118B78));
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
            color: heard && !widget.message.mine
                ? const Color(0x24118B78)
                : Colors.transparent,
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
                    currentSeconds > 0 && player.processingState != ProcessingState.completed
                        ? '${_voiceDuration(currentSeconds)} / ${_voiceDuration(totalSeconds)}'
                        : _voiceDuration(totalSeconds),
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

class _VoiceWavePainter'''
if not voice_pattern.search(c):
    raise SystemExit('patch anchor missing: voice bubble class')
c = voice_pattern.sub(voice_replacement, c, count=1)

CHAT.write_text(c, encoding='utf-8')

m = MODELS.read_text(encoding='utf-8')
m = replace_once(
    m,
    "  final bool playedByMe, encrypted;\n  bool playedByOther;",
    "  final bool encrypted;\n  bool playedByMe, playedByOther;",
    'mutable playedByMe',
)
MODELS.write_text(m, encoding='utf-8')

p = PUBSPEC.read_text(encoding='utf-8')
p = replace_once(p, 'version: 2.5.0+250', 'version: 2.6.0+260', 'pubspec version')
PUBSPEC.write_text(p, encoding='utf-8')

print('v2.6 deep chat audit patch applied')
