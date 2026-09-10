import 'dart:async';
import 'dart:io';
import 'dart:typed_data';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:image/image.dart' as img;
import 'package:image_picker/image_picker.dart';
import 'package:just_audio/just_audio.dart';
import 'package:path_provider/path_provider.dart';
import 'package:record/record.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:url_launcher/url_launcher.dart';

import '../core/app_state.dart';
import '../core/api_client.dart';
import '../core/models.dart';
import '../core/theme.dart';
import '../widgets/common.dart';
import 'call_screen.dart';

Uint8List _processOutgoingPhoto(Map<String, dynamic> args) {
  final bytes = args['bytes'] as Uint8List;
  final turns = (args['turns'] as int?) ?? 0;
  final crop = '${args['crop'] ?? 'original'}';
  final flip = args['flip'] == true;
  var image = img.decodeImage(bytes);
  if (image == null) {
    throw StateError('This image format cannot be edited on this device.');
  }

  final normalizedTurns = ((turns % 4) + 4) % 4;
  if (normalizedTurns != 0) {
    image = img.copyRotate(image, angle: 90 * normalizedTurns);
  }
  if (flip) image = img.flipHorizontal(image);

  double? targetRatio;
  if (crop == 'square') targetRatio = 1;
  if (crop == 'portrait') targetRatio = 4 / 5;
  if (crop == 'landscape') targetRatio = 16 / 9;
  if (targetRatio != null) {
    final current = image.width / image.height;
    if (current > targetRatio) {
      final width = (image.height * targetRatio).round().clamp(1, image.width).toInt();
      image = img.copyCrop(
        image,
        x: (image.width - width) ~/ 2,
        y: 0,
        width: width,
        height: image.height,
      );
    } else if (current < targetRatio) {
      final height = (image.width / targetRatio).round().clamp(1, image.height).toInt();
      image = img.copyCrop(
        image,
        x: 0,
        y: (image.height - height) ~/ 2,
        width: image.width,
        height: height,
      );
    }
  }

  return Uint8List.fromList(img.encodeJpg(image, quality: 93));
}

class ChatScreen extends StatefulWidget {
  const ChatScreen({super.key, required this.conversation});
  final Conversation conversation;
  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> with WidgetsBindingObserver {
  final messages = <ChatMessage>[];
  final textController = TextEditingController(), scroll = ScrollController();
  final recorder = AudioRecorder();
  final voicePreviewPlayer = AudioPlayer();
  Timer? poll, recordTimer, waveTimer, presenceDebounce, typingHeartbeat, voiceHeartbeat;
  ChatPresence? presence;
  ReplyPreview? reply;
  bool loading = true,
      sending = false,
      recording = false,
      recordingPaused = false,
      showEmoji = false,
      polling = false,
      typingSent = false,
      searching = false,
      selfBlocked = false,
      muted = false,
      loadingOlder = false,
      historyDone = false,
      foreground = true;
  int recordSeconds = 0, pollTicks = 0;
  double? uploadProgress;
  String? error, recordPath, voicePreviewPath;
  String searchQuery = '', emojiCategory = 'Recent';
  final selectedIds = <int>{};
  final voiceLevels = <double>[];
  List<String> recentEmojis = <String>[];
  List<Map<String, dynamic>> pinnedMessages = const [];

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    textController.addListener(_typing);
    selfBlocked = widget.conversation.selfBlocked;
    muted = widget.conversation.muted;
    scroll.addListener(_historyListener);
    _loadRecentEmojis();
    _load(jumpToBottom: true);
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    poll?.cancel();
    recordTimer?.cancel();
    waveTimer?.cancel();
    presenceDebounce?.cancel();
    typingHeartbeat?.cancel();
    voiceHeartbeat?.cancel();
    recorder.dispose();
    voicePreviewPlayer.dispose();
    final preview = voicePreviewPath;
    if (preview != null) {
      try {
        File(preview).deleteSync();
      } catch (_) {}
    }
    textController.dispose();
    scroll.dispose();
    super.dispose();
  }

  @override
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

  Future<void> _load({bool jumpToBottom = false}) async {
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

  void _historyListener() {
    if (!scroll.hasClients || loading || loadingOlder || historyDone) return;
    if (scroll.position.pixels < 180) _loadOlder();
  }

  Future<void> _loadOlder() async {
    if (messages.isEmpty || loadingOlder || historyDone) return;
    loadingOlder = true;
    if (mounted) setState(() {});
    final before = messages.first.id;
    final oldExtent = scroll.hasClients ? scroll.position.maxScrollExtent : 0.0;
    try {
      final older = await AppScope.of(context).api.messages(
        widget.conversation.id,
        beforeId: before,
        limit: 80,
      );
      if (older.isEmpty) {
        historyDone = true;
      } else {
        final unique = older
            .where((m) => messages.every((old) => old.id != m.id))
            .toList();
        messages.insertAll(0, unique);
        if (older.length < 80) historyDone = true;
        WidgetsBinding.instance.addPostFrameCallback((_) {
          if (!scroll.hasClients) return;
          final gained = scroll.position.maxScrollExtent - oldExtent;
          scroll.jumpTo((scroll.position.pixels + gained).clamp(
            scroll.position.minScrollExtent,
            scroll.position.maxScrollExtent,
          ));
        });
      }
    } catch (_) {
      // Older history is optional; keep the current thread usable.
    } finally {
      loadingOlder = false;
      if (mounted) setState(() {});
    }
  }

  void _schedulePoll({bool immediate = false}) {
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
            if (!old.mine && old.playedByMe) {
              candidate.playedByMe = true;
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

  void _typing() {
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

  @override
  Widget build(BuildContext context) => Scaffold(
    backgroundColor: Theme.of(context).brightness == Brightness.dark
        ? const Color(0xFF07101B)
        : const Color(0xFFF3F6FA),
    appBar: AppBar(
      toolbarHeight: 68,
      backgroundColor: Theme.of(context).colorScheme.surface,
      surfaceTintColor: Colors.transparent,
      titleSpacing: 0,
      title: searching
          ? TextField(
              autofocus: true,
              textInputAction: TextInputAction.search,
              onChanged: (value) => setState(() => searchQuery = value),
              onSubmitted: _serverFindInConversation,
              decoration: const InputDecoration(
                hintText: 'Search this conversation',
                border: InputBorder.none,
                filled: false,
              ),
            )
          : Row(
              children: [
                UserAvatar(
                  url: widget.conversation.avatar,
                  name: widget.conversation.title,
                  radius: 20,
                  online: widget.conversation.online,
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        widget.conversation.title,
                        overflow: TextOverflow.ellipsis,
                        style: TextStyle(
                          fontSize: 17,
                          fontWeight: FontWeight.w800,
                          color: Theme.of(context).colorScheme.onSurface,
                        ),
                      ),
                      Text(
                        presence?.active == true
                            ? (presence!.kind == 'voice'
                                  ? '${presence!.name} is recording voice…'
                                  : '${presence!.name} is typing…')
                            : widget.conversation.statusText,
                        style: TextStyle(
                          fontSize: 11.5,
                          color: presence?.active == true
                              ? AppColors.success
                              : AppColors.muted,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
      actions: [
        if (!widget.conversation.isGroup &&
            widget.conversation.callsEnabled &&
            !_chatBlocked)
          IconButton(
            tooltip: 'Voice call',
            onPressed: () => _startCall(false),
            icon: const Icon(Icons.call_outlined),
          ),
        if (!widget.conversation.isGroup &&
            widget.conversation.videoCallsEnabled &&
            !_chatBlocked)
          IconButton(
            tooltip: 'Video call',
            onPressed: () => _startCall(true),
            icon: const Icon(Icons.videocam_outlined),
          ),
        IconButton(
          tooltip: searching ? 'Close search' : 'Search messages',
          onPressed: () => setState(() {
            searching = !searching;
            if (!searching) searchQuery = '';
          }),
          icon: Icon(searching ? Icons.close_rounded : Icons.search_rounded),
        ),
        IconButton(
          tooltip: 'Conversation options',
          onPressed: _conversationMenu,
          icon: const Icon(Icons.more_vert_rounded),
        ),
      ],
    ),
    body: SafeArea(
      top: false,
      child: Column(
        children: [
          if (pinnedMessages.isNotEmpty) _pinnedBar(),
          Expanded(
            child: loading
                ? const Center(child: CircularProgressIndicator())
                : error != null
                ? ErrorView(message: error!, retry: _load)
                : messages.isEmpty
                ? const EmptyView(
                    icon: Icons.waving_hand_rounded,
                    title: 'Start the conversation',
                    message: 'Send a message, photo, file or voice note.',
                  )
                : _messageList(),
          ),
          if (presence?.active == true)
            _ChatPresenceBubble(
              name: presence!.name,
              voice: presence!.kind == 'voice',
            ),
          if (recording)
            _recordingBar()
          else if (voicePreviewPath != null)
            _voicePreviewBar(),
          if (uploadProgress != null) _uploadBar(),
          if (reply != null &&
              !_chatBlocked &&
              selectedIds.isEmpty &&
              !recording &&
              voicePreviewPath == null)
            _replyBar(),
          if (selectedIds.isNotEmpty)
            _selectionBar()
          else if (_chatBlocked)
            _blockedBanner()
          else if (!recording && voicePreviewPath == null)
            _composer(),
          if (showEmoji &&
              !_chatBlocked &&
              selectedIds.isEmpty &&
              !recording &&
              voicePreviewPath == null)
            _emojiPanel(),
        ],
      ),
    ),
  );

  Widget _messageList() {
    final needle = searchQuery.trim().toLowerCase();
    final visible = needle.isEmpty
        ? messages
        : messages
              .where(
                (m) =>
                    m.content.toLowerCase().contains(needle) ||
                    m.sender.toLowerCase().contains(needle) ||
                    (m.attachmentName?.toLowerCase().contains(needle) ?? false),
              )
              .toList();
    if (visible.isEmpty && needle.isNotEmpty) {
      return const EmptyView(
        icon: Icons.search_off_rounded,
        title: 'No matching messages',
        message: 'Try a different word or name.',
      );
    }
    return ListView.builder(
      controller: scroll,
      padding: const EdgeInsets.fromLTRB(12, 8, 12, 14),
      itemCount: visible.length + (loadingOlder ? 1 : 0),
      itemBuilder: (_, i) {
        if (loadingOlder && i == 0) {
          return const Padding(
            padding: EdgeInsets.symmetric(vertical: 12),
            child: Center(
              child: SizedBox(
                width: 22,
                height: 22,
                child: CircularProgressIndicator(strokeWidth: 2),
              ),
            ),
          );
        }
        final index = loadingOlder ? i - 1 : i;
        final m = visible[index],
            showDate = index == 0 ||
                visible[index - 1].dateLabel != m.dateLabel;
        return KeyedSubtree(
          key: ValueKey<int>(m.id),
          child: Column(
            children: [
            if (showDate)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 12),
                child: Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 12,
                    vertical: 6,
                  ),
                  decoration: BoxDecoration(
                    color: const Color(0x1908142F),
                    borderRadius: BorderRadius.circular(20),
                  ),
                  child: Text(
                    m.dateLabel,
                    style: const TextStyle(
                      fontSize: 11,
                      color: AppColors.muted,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ),
              ),
            _bubble(m),
            ],
          ),
        );
      },
    );
  }

  Widget _bubble(ChatMessage m) => Align(
    alignment: m.mine ? Alignment.centerRight : Alignment.centerLeft,
    child: GestureDetector(
      onTap: selectedIds.isNotEmpty ? () => _toggleSelected(m.id) : null,
      onLongPress: () => selectedIds.isNotEmpty
          ? _toggleSelected(m.id)
          : _messageActions(m),
      onHorizontalDragEnd: (d) {
        final velocity = d.primaryVelocity ?? 0;
        if (velocity.abs() > 280)
          setState(
            () => reply = ReplyPreview(
              id: m.id,
              sender: m.sender,
              text: m.content.isNotEmpty
                  ? m.content
                  : (m.voiceSeconds > 0
                        ? 'Voice message'
                        : m.attachmentName ?? 'Attachment'),
            ),
          );
      },
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 220),
        curve: Curves.easeOut,
        constraints: BoxConstraints(
          maxWidth: MediaQuery.sizeOf(context).width *
              (m.voiceSeconds > 0 ? .86 : .79),
        ),
        margin: const EdgeInsets.only(bottom: 7),
        padding: const EdgeInsets.fromLTRB(13, 10, 11, 7),
        decoration: BoxDecoration(
          gradient: m.mine && m.voiceSeconds == 0
              ? const LinearGradient(
                  colors: [Color(0xFF245FD3), Color(0xFF5146D8)],
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                )
              : null,
          color: m.voiceSeconds > 0
              ? (m.mine
                    ? (m.playedByOther
                          ? const Color(0xFF0C5D58)
                          : const Color(0xFF183B63))
                    : (m.playedByMe
                          ? (Theme.of(context).brightness == Brightness.dark
                                ? const Color(0xFF103C35)
                                : const Color(0xFFDCF6EF))
                          : (Theme.of(context).brightness == Brightness.dark
                                ? const Color(0xFF142236)
                                : const Color(0xFFFFFFFF))))
              : (m.mine
                    ? null
                    : (Theme.of(context).brightness == Brightness.dark
                          ? const Color(0xFF132033)
                          : const Color(0xFFFFFFFF))),
          borderRadius: BorderRadius.only(
            topLeft: const Radius.circular(18),
            topRight: const Radius.circular(18),
            bottomLeft: Radius.circular(m.mine ? 18 : 5),
            bottomRight: Radius.circular(m.mine ? 5 : 18),
          ),
          border: selectedIds.contains(m.id)
              ? Border.all(color: AppColors.success, width: 2.2)
              : null,
          boxShadow: const [
            BoxShadow(
              color: Color(0x1008142F),
              blurRadius: 10,
              offset: Offset(0, 3),
            ),
          ],
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (!m.mine && widget.conversation.isGroup)
              Padding(
                padding: const EdgeInsets.only(bottom: 5),
                child: Text(
                  m.sender,
                  style: const TextStyle(
                    color: AppColors.violet,
                    fontSize: 12,
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ),
            if (m.forwarded)
              _metaLine(Icons.forward_rounded, 'Forwarded', m.mine),
            if (m.reply != null) _quoted(m.reply!, m.mine),
            if (m.encrypted && !m.deleted)
              _encryptedBubble(m)
            else if (m.poll != null && !m.deleted)
              _pollBubble(m)
            else if (m.voiceSeconds > 0 && !m.deleted)
              VoiceBubble(
                key: ValueKey<String>('voice-${m.id}'),
                message: m,
                api: AppScope.of(context).api,
                beforePlay: () async {
                  if (voicePreviewPlayer.playing) {
                    await voicePreviewPlayer.pause();
                  }
                },
                onListened: () {
                  if (!m.playedByMe && mounted) {
                    setState(() => m.playedByMe = true);
                  }
                },
                onCompleted: () => _playNextVoice(m.id),
              )
            else if (m.attachmentUrl != null && !m.deleted)
              _attachment(m)
            else
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
              ),
            if (m.linkPreview != null && !m.deleted && !m.encrypted)
              _linkPreview(m.linkPreview!, m.mine),
            if (m.reactions.isNotEmpty)
              Padding(
                padding: const EdgeInsets.only(top: 7),
                child: Wrap(
                  spacing: 5,
                  children: m.reactions
                      .map(
                        (r) => Container(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 7,
                            vertical: 3,
                          ),
                          decoration: BoxDecoration(
                            color: (m.mine ? Colors.white : AppColors.blue)
                                .withValues(alpha: .14),
                            borderRadius: BorderRadius.circular(15),
                          ),
                          child: Text(
                            '${r.emoji} ${r.count}',
                            style: TextStyle(
                              fontSize: 12,
                              color: m.mine ? Colors.white : Theme.of(context).colorScheme.onSurface,
                            ),
                          ),
                        ),
                      )
                      .toList(),
                ),
              ),
            if (m.voiceSeconds == 0) ...[
              const SizedBox(height: 3),
              Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                if (m.edited)
                  Text(
                    'edited · ',
                    style: TextStyle(
                      fontSize: 9.5,
                      color: (m.mine ? Colors.white : AppColors.muted)
                          .withValues(alpha: .75),
                    ),
                  ),
                Text(
                  m.time,
                  style: TextStyle(
                    fontSize: 9.5,
                    color: (m.mine ? Colors.white : AppColors.muted).withValues(
                      alpha: .78,
                    ),
                  ),
                ),
                if (m.mine) ...[
                  const SizedBox(width: 4),
                  Icon(
                    m.read ? Icons.done_all_rounded : Icons.check_rounded,
                    size: 15,
                    color: m.read ? const Color(0xFF75E9FF) : Colors.white70,
                  ),
                ],
              ],
            ),
            ],
          ],
        ),
      ),
    ),
  );

  Widget _quoted(ReplyPreview r, bool mine) => Container(
    margin: const EdgeInsets.only(bottom: 7),
    padding: const EdgeInsets.all(9),
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
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          r.sender,
          style: TextStyle(
            fontSize: 11,
            fontWeight: FontWeight.w800,
            color: mine ? Colors.white : AppColors.blue,
          ),
        ),
        Text(
          r.text,
          maxLines: 2,
          overflow: TextOverflow.ellipsis,
          style: TextStyle(
            fontSize: 11,
            color: mine ? Colors.white70 : AppColors.muted,
          ),
        ),
      ],
    ),
  );
  Widget _metaLine(IconData icon, String text, bool mine) => Padding(
    padding: const EdgeInsets.only(bottom: 5),
    child: Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, size: 12, color: mine ? Colors.white70 : AppColors.muted),
        const SizedBox(width: 4),
        Text(
          text,
          style: TextStyle(
            fontSize: 10,
            color: mine ? Colors.white70 : AppColors.muted,
          ),
        ),
      ],
    ),
  );
  Widget _attachment(ChatMessage m) {
    final image = _isImage(m.attachmentType);
    return InkWell(
      onTap: () => _openAttachment(m),
      borderRadius: BorderRadius.circular(14),
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 260),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (image)
              ClipRRect(
                borderRadius: BorderRadius.circular(13),
                child: SecureChatImage(
                  api: AppScope.of(context).api,
                  url: m.attachmentUrl!,
                  mine: m.mine,
                ),
              )
            else
              Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Container(
                    padding: const EdgeInsets.all(10),
                    decoration: BoxDecoration(
                      color: Colors.white.withValues(alpha: .16),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Icon(
                      _fileIcon(m.attachmentType),
                      color: m.mine ? Colors.white : AppColors.blue,
                    ),
                  ),
                  const SizedBox(width: 9),
                  const Icon(Icons.download_rounded, size: 19),
                ],
              ),
            const SizedBox(height: 6),
            Text(
              m.attachmentName ?? 'Attachment',
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              style: TextStyle(
                color: m.mine ? Colors.white : Theme.of(context).colorScheme.onSurface,
                fontWeight: FontWeight.w700,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _openAttachment(ChatMessage m) async {
    try {
      final bytes = await AppScope.of(context).api
          .attachmentBytes(m.attachmentUrl!);
      if (!mounted) return;
      if (_isImage(m.attachmentType)) {
        await showDialog<void>(
          context: context,
          builder: (dialogContext) => Dialog.fullscreen(
            backgroundColor: Colors.black,
            child: Stack(
              children: [
                Center(
                  child: InteractiveViewer(
                    minScale: .7,
                    maxScale: 5,
                    child: Image.memory(bytes, fit: BoxFit.contain),
                  ),
                ),
                SafeArea(
                  child: IconButton.filledTonal(
                    onPressed: () => Navigator.pop(dialogContext),
                    icon: const Icon(Icons.close_rounded),
                  ),
                ),
              ],
            ),
          ),
        );
        return;
      }
      final saved = await FilePicker.saveFile(
        dialogTitle: 'Save secure attachment',
        fileName: m.attachmentName ?? 'TaleemPK-file',
        bytes: bytes,
      );
      if (mounted && saved != null) showMessage(context, 'Attachment saved.');
    } catch (e) {
      if (mounted) showMessage(context, apiMessage(e));
    }
  }

  Widget _encryptedBubble(ChatMessage message) => InkWell(
    borderRadius: BorderRadius.circular(12),
    onTap: _encryptionInfo,
    child: Container(
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: (message.mine ? Colors.white : AppColors.success)
            .withValues(alpha: .12),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(
            Icons.lock_rounded,
            size: 18,
            color: message.mine ? Colors.white : AppColors.success,
          ),
          const SizedBox(width: 8),
          Flexible(
            child: Text(
              'End-to-end encrypted message · open the web chat with your encryption key to read it',
              style: TextStyle(
                fontSize: 12,
                height: 1.35,
                color: message.mine
                    ? Colors.white
                    : Theme.of(context).colorScheme.onSurface,
              ),
            ),
          ),
        ],
      ),
    ),
  );

  Widget _linkPreview(ChatLinkPreview preview, bool mine) {
    if (preview.url.isEmpty) return const SizedBox.shrink();
    final uri = Uri.tryParse(preview.url);
    return Padding(
      padding: const EdgeInsets.only(top: 8),
      child: InkWell(
        borderRadius: BorderRadius.circular(12),
        onTap: uri == null
            ? null
            : () => launchUrl(uri, mode: LaunchMode.externalApplication),
        child: Container(
          constraints: const BoxConstraints(maxWidth: 260),
          padding: const EdgeInsets.all(9),
          decoration: BoxDecoration(
            color: (mine ? Colors.white : AppColors.blue)
                .withValues(alpha: .11),
            borderRadius: BorderRadius.circular(12),
            border: Border.all(
              color: (mine ? Colors.white : AppColors.blue)
                  .withValues(alpha: .18),
            ),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              if (preview.title.isNotEmpty)
                Text(
                  preview.title,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.w900,
                    color: mine
                        ? Colors.white
                        : Theme.of(context).colorScheme.onSurface,
                  ),
                ),
              if (preview.description.isNotEmpty) ...[
                const SizedBox(height: 3),
                Text(
                  preview.description,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(
                    fontSize: 10.5,
                    color: mine ? Colors.white70 : AppColors.muted,
                  ),
                ),
              ],
              const SizedBox(height: 4),
              Text(
                uri?.host.isNotEmpty == true ? uri!.host : preview.url,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: TextStyle(
                  fontSize: 9.5,
                  fontWeight: FontWeight.w700,
                  color: mine ? Colors.white70 : AppColors.blue,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _pinnedBar() => Container(
    margin: const EdgeInsets.fromLTRB(10, 8, 10, 2),
    decoration: BoxDecoration(
      color: Theme.of(context).colorScheme.surface,
      borderRadius: BorderRadius.circular(16),
      border: Border.all(color: Theme.of(context).dividerColor),
    ),
    child: SizedBox(
      height: 54,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 7),
        itemCount: pinnedMessages.length,
        separatorBuilder: (_, _) => const SizedBox(width: 8),
        itemBuilder: (_, i) {
          final p = pinnedMessages[i];
          return InkWell(
            borderRadius: BorderRadius.circular(12),
            onTap: () => _jumpToMessage(_asInt(p['id'])),
            child: Container(
              constraints: const BoxConstraints(maxWidth: 230),
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
              decoration: BoxDecoration(
                color: AppColors.blue.withValues(alpha: .08),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Icon(Icons.push_pin_rounded, size: 15, color: AppColors.blue),
                  const SizedBox(width: 6),
                  Flexible(
                    child: Text(
                      '${p['sender']}: ${p['text']}',
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(fontSize: 11.5, fontWeight: FontWeight.w700),
                    ),
                  ),
                ],
              ),
            ),
          );
        },
      ),
    ),
  );

  Future<void> _jumpToMessage(int id) async {
    if (id <= 0) return;
    for (var attempt = 0; attempt < 6; attempt++) {
      final index = messages.indexWhere((m) => m.id == id);
      if (index >= 0) {
        if (!scroll.hasClients) return;
        final target = (index * 82.0).clamp(
          scroll.position.minScrollExtent,
          scroll.position.maxScrollExtent,
        );
        await scroll.animateTo(
          target,
          duration: const Duration(milliseconds: 320),
          curve: Curves.easeOut,
        );
        return;
      }
      if (historyDone) break;
      await _loadOlder();
    }
    if (mounted) showMessage(context, 'That pinned message is not in the loaded history.');
  }

  Widget _pollBubble(ChatMessage message) {
    final poll = message.poll!;
    final totalVotes = poll.options.fold<int>(0, (sum, o) => sum + o.votes);
    final colors = Theme.of(context).colorScheme;
    return ConstrainedBox(
      constraints: const BoxConstraints(minWidth: 230, maxWidth: 285),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            poll.question,
            style: TextStyle(
              fontSize: 15,
              fontWeight: FontWeight.w900,
              color: message.mine ? Colors.white : colors.onSurface,
            ),
          ),
          const SizedBox(height: 10),
          for (final option in poll.options) ...[
            InkWell(
              borderRadius: BorderRadius.circular(12),
              onTap: poll.closed ? null : () => _votePoll(poll.id, option.id),
              child: Container(
                padding: const EdgeInsets.fromLTRB(10, 8, 10, 8),
                decoration: BoxDecoration(
                  color: option.mine
                      ? (message.mine ? Colors.white.withValues(alpha: .18) : AppColors.blue.withValues(alpha: .12))
                      : Colors.transparent,
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(
                    color: option.mine
                        ? (message.mine ? Colors.white70 : AppColors.blue)
                        : (message.mine ? Colors.white24 : colors.outlineVariant),
                  ),
                ),
                child: Row(
                  children: [
                    Icon(
                      option.mine
                          ? Icons.check_circle_rounded
                          : Icons.radio_button_unchecked_rounded,
                      size: 18,
                      color: option.mine
                          ? (message.mine ? Colors.white : AppColors.blue)
                          : (message.mine ? Colors.white70 : AppColors.muted),
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        option.label,
                        style: TextStyle(
                          fontWeight: FontWeight.w700,
                          color: message.mine ? Colors.white : colors.onSurface,
                        ),
                      ),
                    ),
                    Text(
                      totalVotes == 0
                          ? '0%'
                          : '${((option.votes / totalVotes) * 100).round()}%',
                      style: TextStyle(
                        fontSize: 11,
                        fontWeight: FontWeight.w800,
                        color: message.mine ? Colors.white70 : AppColors.muted,
                      ),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 6),
          ],
          Row(
            children: [
              Text(
                '${poll.voters} voter${poll.voters == 1 ? '' : 's'}${poll.closed ? ' · closed' : ''}',
                style: TextStyle(
                  fontSize: 10.5,
                  color: message.mine ? Colors.white70 : AppColors.muted,
                ),
              ),
              const Spacer(),
              if (poll.mine)
                InkWell(
                  onTap: () => _togglePollClosed(poll.id, !poll.closed),
                  child: Text(
                    poll.closed ? 'Reopen' : 'Close poll',
                    style: TextStyle(
                      fontSize: 10.5,
                      fontWeight: FontWeight.w800,
                      color: message.mine ? Colors.white : AppColors.blue,
                    ),
                  ),
                ),
            ],
          ),
        ],
      ),
    );
  }

  Future<void> _votePoll(int pollId, int optionId) async {
    try {
      await AppScope.of(context).api.votePoll(pollId, optionId);
      await _load();
    } catch (e) {
      if (mounted) showMessage(context, apiMessage(e));
    }
  }

  Future<void> _togglePollClosed(int pollId, bool closed) async {
    try {
      await AppScope.of(context).api.setPollClosed(pollId, closed);
      await _load();
    } catch (e) {
      if (mounted) showMessage(context, apiMessage(e));
    }
  }

  Future<void> _createPoll() async {
    final question = TextEditingController();
    final options = List.generate(4, (_) => TextEditingController());
    var multi = false;
    final send = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (sheet) => StatefulBuilder(
        builder: (context, setLocal) => Padding(
          padding: EdgeInsets.fromLTRB(
            20,
            4,
            20,
            MediaQuery.viewInsetsOf(context).bottom + 20,
          ),
          child: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  'Create poll',
                  style: Theme.of(context).textTheme.titleLarge,
                ),
                const SizedBox(height: 14),
                TextField(
                  controller: question,
                  maxLength: 240,
                  decoration: const InputDecoration(labelText: 'Question'),
                ),
                for (var i = 0; i < options.length; i++) ...[
                  const SizedBox(height: 8),
                  TextField(
                    controller: options[i],
                    maxLength: 120,
                    decoration: InputDecoration(labelText: 'Option ${i + 1}'),
                  ),
                ],
                SwitchListTile(
                  contentPadding: EdgeInsets.zero,
                  value: multi,
                  onChanged: (v) => setLocal(() => multi = v),
                  title: const Text('Allow multiple answers'),
                ),
                const SizedBox(height: 8),
                FilledButton.icon(
                  onPressed: () => Navigator.pop(sheet, true),
                  icon: const Icon(Icons.send_rounded),
                  label: const Text('Send poll'),
                ),
              ],
            ),
          ),
        ),
      ),
    );
    if (send == true && mounted) {
      final values = options
          .map((e) => e.text.trim())
          .where((e) => e.isNotEmpty)
          .toList();
      if (question.text.trim().length < 2 || values.length < 2) {
        showMessage(context, 'Add a question and at least two options.');
      } else {
        try {
          await AppScope.of(context).api.createPoll(
            widget.conversation.id,
            question.text.trim(),
            values,
            multi: multi,
          );
          await _load();
        } catch (e) {
          if (mounted) showMessage(context, apiMessage(e));
        }
      }
    }
    question.dispose();
    for (final controller in options) {
      controller.dispose();
    }
  }

  Widget _replyBar() => Container(
    color: Theme.of(context).colorScheme.surface,
    padding: const EdgeInsets.fromLTRB(14, 8, 8, 7),
    child: Row(
      children: [
        const Icon(Icons.reply_rounded, color: AppColors.blue),
        const SizedBox(width: 10),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Reply to ${reply!.sender}',
                style: const TextStyle(
                  fontSize: 12,
                  color: AppColors.blue,
                  fontWeight: FontWeight.w800,
                ),
              ),
              Text(
                reply!.text,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(fontSize: 12, color: AppColors.muted),
              ),
            ],
          ),
        ),
        IconButton(
          onPressed: () => setState(() => reply = null),
          icon: const Icon(Icons.close_rounded),
        ),
      ],
    ),
  );

  Widget _composer() => Container(
    color: Theme.of(context).colorScheme.surface,
    padding: const EdgeInsets.fromLTRB(8, 7, 8, 9),
    child: Row(
      crossAxisAlignment: CrossAxisAlignment.end,
      children: [
        IconButton(
          onPressed: _pickAttachment,
          icon: const Icon(
            Icons.add_circle_outline_rounded,
            color: AppColors.blue,
          ),
        ),
        Expanded(
          child: TextField(
            controller: textController,
            minLines: 1,
            maxLines: 5,
            maxLength: 4000,
            buildCounter: (
              _, {
              required currentLength,
              required isFocused,
              maxLength,
            }) => null,
            onTap: () => setState(() => showEmoji = false),
            decoration: InputDecoration(
              hintText: 'Message',
              isDense: true,
              fillColor: Theme.of(context).brightness == Brightness.dark
                  ? const Color(0xFF172033)
                  : const Color(0xFFF4F6FA),
              suffixIcon: IconButton(
                onPressed: () => setState(() => showEmoji = !showEmoji),
                icon: const Icon(Icons.emoji_emotions_outlined),
              ),
            ),
          ),
        ),
        const SizedBox(width: 7),
        IconButton.filled(
          onPressed: sending
              ? null
              : (textController.text.trim().isEmpty
                    ? _toggleRecording
                    : _sendText),
          icon: Icon(
            textController.text.trim().isEmpty
                ? (recording ? Icons.stop_rounded : Icons.mic_rounded)
                : Icons.send_rounded,
          ),
        ),
      ],
    ),
  );

  Future<void> _loadRecentEmojis() async {
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
    final groups = <String, List<String>>{
      'Recent': recentEmojis,
      'Smileys': const [
        '😀','😃','😄','😁','😆','😅','😂','🤣','🥲','☺️','😊','😇','🙂','🙃','😉','😌',
        '😍','🥰','😘','😗','😙','😚','😋','😛','😝','😜','🤪','🤨','🧐','🤓','😎','🥸','🤩','🥳',
        '😏','😒','😞','😔','😟','😕','🙁','☹️','😣','😖','😫','😩','🥺','😢','😭','😤','😠','😡','🤬',
        '🤯','😳','🥵','🥶','😱','😨','😰','😥','😓','🤗','🤔','🫡','🤭','🫢','🫣','🤫','🤥','😶','🫥',
        '😐','🫤','😑','😬','🙄','😯','😦','😧','😮','😲','🥱','😴','🤤','😪','😵','😵‍💫','🤐','🥴',
        '🤢','🤮','🤧','😷','🤒','🤕','🤑','🤠','😈','👿','👹','👺','🤡','💩','👻','💀','☠️','👽','👾','🤖'
      ],
      'People': const [
        '👍','👎','👌','🤌','🤏','✌️','🤞','🫰','🤟','🤘','🤙','👈','👉','👆','👇','☝️','✋','🤚','🖐️',
        '🖖','👋','🤝','👏','🙌','🫶','👐','🤲','🙏','✍️','💅','🤳','💪','🦾','🦵','🦶','👂','👃','🧠','🫀',
        '🫁','🦷','🦴','👀','👁️','👅','👄','🫦','👶','🧒','👦','👧','🧑','👱','👨','🧔','👩','🧓','👴','👵'
      ],
      'Hearts': const [
        '❤️','🩷','🧡','💛','💚','💙','🩵','💜','🤎','🖤','🩶','🤍','💔','❤️‍🔥','❤️‍🩹','❣️','💕','💞','💓',
        '💗','💖','💘','💝','💟','💋','💌','💢','💥','💫','💦','💨','💬','🗨️','🗯️','💭','💤','✨','⭐','🌟','⚡'
      ],
      'Activities': const [
        '🎉','🎊','🎈','🎁','🎀','🏆','🥇','🥈','🥉','⚽','🏏','🏀','🏐','🎾','🏸','🎯','🎮','🎲','♟️','🎵','🎶',
        '🚀','✈️','🚗','🏠','🏢','🏫','🏥','🕌','🌍','🌎','🌏','📷','🎥','🎙️','📱','💻','⌚','⏰','🔔','✅','❌'
      ],
      'Study': const [
        '📚','📖','📕','📗','📘','📙','📓','📔','📒','📝','✏️','🖊️','🖋️','📌','📍','📎','📐','📏','🎓','💡','🔬',
        '🧪','🧬','🔭','🧮','📊','📈','📉','🗂️','📂','🗒️','✅','❓','❗','💯','🔒','🔓','🔐','🔑','🛡️'
      ],
      'Nature': const [
        '🔥','☀️','🌤️','⛅','🌥️','☁️','🌧️','⛈️','🌩️','🌨️','❄️','☃️','🌈','☔','💧','🌊','💐','🌹','🌷','🌸',
        '🌺','🌻','🌼','🍀','🌿','🐶','🐱','🐭','🐹','🐰','🦊','🐻','🐼','🐨','🐯','🦁','🐮','🐷','🐸','🐵','🦋'
      ],
      'Food': const [
        '🍎','🍏','🍊','🍋','🍌','🍉','🍇','🍓','🫐','🍒','🥭','🍍','🥝','🍅','🥑','🥕','🌽','🍞','🥐','🍕','🍔',
        '🍟','🍗','🍚','🍜','🍰','🎂','🍫','🍪','☕','🫖','🥤','🧃','🍯','🥛','🍿','🍩','🍨','🍦','🥗','🥪'
      ],
      'Flags': const [
        '🇵🇰','🇦🇪','🇦🇺','🇬🇧','🇺🇸','🇨🇦','🇸🇦','🇹🇷','🇶🇦','🇯🇵','🇰🇷','🇨🇳','🇩🇪','🇫🇷','🇮🇹','🇪🇸',
        '🇮🇳','🇧🇩','🇱🇰','🇳🇿','🇲🇾','🇸🇬','🇮🇩','🇿🇦','🇳🇴','🇸🇪','🇨🇭','🇳🇱','🇧🇪','🇧🇷','🇦🇷','🇲🇽'
      ],
    };
    final activeCategory = emojiCategory == 'Recent' && recentEmojis.isEmpty
        ? 'Smileys'
        : emojiCategory;
    final items = groups[activeCategory] ?? groups['Smileys']!;
    final dark = Theme.of(context).brightness == Brightness.dark;

    Widget emojiButton(String e) => Material(
      color: Colors.transparent,
      child: InkWell(
        borderRadius: BorderRadius.circular(14),
        onTap: () => _insertEmoji(e),
        child: Center(child: Text(e, style: const TextStyle(fontSize: 27))),
      ),
    );

    return Container(
      height: 318,
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surface,
        border: Border(
          top: BorderSide(color: Theme.of(context).dividerColor.withValues(alpha: .65)),
        ),
      ),
      padding: const EdgeInsets.fromLTRB(10, 9, 10, 8),
      child: Column(
        children: [
          Row(
            children: [
              Container(
                width: 34,
                height: 34,
                decoration: BoxDecoration(
                  color: AppColors.blue.withValues(alpha: .10),
                  borderRadius: BorderRadius.circular(11),
                ),
                child: Icon(
                  activeCategory == 'Recent' ? Icons.history_rounded : Icons.emoji_emotions_rounded,
                  size: 19,
                  color: AppColors.blue,
                ),
              ),
              const SizedBox(width: 9),
              Expanded(
                child: Text(
                  activeCategory == 'Recent' ? 'Recently used' : activeCategory,
                  style: TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.w900,
                    color: Theme.of(context).colorScheme.onSurface,
                  ),
                ),
              ),
              if (activeCategory == 'Recent' && recentEmojis.isNotEmpty)
                TextButton(
                  onPressed: () async {
                    setState(() => recentEmojis = <String>[]);
                    try {
                      final prefs = await SharedPreferences.getInstance();
                      await prefs.remove('chat_recent_emojis');
                    } catch (_) {}
                  },
                  child: const Text('Clear'),
                ),
            ],
          ),
          const SizedBox(height: 7),
          SizedBox(
            height: 38,
            child: ListView.separated(
              scrollDirection: Axis.horizontal,
              itemCount: groups.keys.length,
              separatorBuilder: (_, _) => const SizedBox(width: 6),
              itemBuilder: (_, i) {
                final name = groups.keys.elementAt(i);
                final selected = name == activeCategory;
                return ChoiceChip(
                  selected: selected,
                  showCheckmark: false,
                  visualDensity: VisualDensity.compact,
                  label: Text(name),
                  onSelected: (_) => setState(() => emojiCategory = name),
                );
              },
            ),
          ),
          const SizedBox(height: 7),
          Expanded(
            child: items.isEmpty
                ? Center(
                    child: Text(
                      'Use an emoji and it will appear here.',
                      style: TextStyle(
                        color: Theme.of(context).colorScheme.onSurfaceVariant,
                      ),
                    ),
                  )
                : Container(
                    decoration: BoxDecoration(
                      color: dark ? const Color(0xFF101A2A) : const Color(0xFFF7F9FC),
                      borderRadius: BorderRadius.circular(18),
                    ),
                    padding: const EdgeInsets.all(7),
                    child: GridView.builder(
                      padding: EdgeInsets.zero,
                      gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                        crossAxisCount: 8,
                        mainAxisSpacing: 2,
                        crossAxisSpacing: 2,
                      ),
                      itemCount: items.length,
                      itemBuilder: (_, i) => emojiButton(items[i]),
                    ),
                  ),
          ),
        ],
      ),
    );
  }

  Widget _recordingBar() {
    final wave = _encodedVoiceWave();
    return Container(
      color: Theme.of(context).colorScheme.surface,
      padding: const EdgeInsets.fromLTRB(12, 10, 12, 10),
      child: Column(
        children: [
          Row(
            children: [
              Text(
                _duration(recordSeconds),
                style: TextStyle(
                  fontSize: 15,
                  fontWeight: FontWeight.w900,
                  color: recordingPaused ? AppColors.violet : AppColors.danger,
                ),
              ),
              if (recordingPaused) ...[
                const SizedBox(width: 7),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 3),
                  decoration: BoxDecoration(
                    color: AppColors.violet.withValues(alpha: .12),
                    borderRadius: BorderRadius.circular(20),
                  ),
                  child: const Text(
                    'Paused',
                    style: TextStyle(
                      fontSize: 10,
                      fontWeight: FontWeight.w800,
                      color: AppColors.violet,
                    ),
                  ),
                ),
              ],
              const SizedBox(width: 10),
              Expanded(
                child: SizedBox(
                  height: 34,
                  child: CustomPaint(
                    painter: _VoiceWavePainter(
                      progress: 1,
                      active: recordingPaused ? AppColors.violet : AppColors.danger,
                      inactive: Theme.of(context).dividerColor,
                      seed: recordSeconds + 17,
                      wave: wave,
                    ),
                    child: const SizedBox.expand(),
                  ),
                ),
              ),
              const SizedBox(width: 8),
              Text(
                '/ 2:00',
                style: TextStyle(
                  fontSize: 10.5,
                  color: Theme.of(context).colorScheme.onSurfaceVariant,
                ),
              ),
            ],
          ),
          const SizedBox(height: 9),
          Row(
            children: [
              IconButton.filledTonal(
                tooltip: 'Discard recording',
                onPressed: _cancelRecording,
                icon: const Icon(Icons.delete_outline_rounded, color: AppColors.danger),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: FilledButton.tonalIcon(
                  onPressed: _pauseResumeRecording,
                  icon: Icon(
                    recordingPaused ? Icons.play_arrow_rounded : Icons.pause_rounded,
                  ),
                  label: Text(recordingPaused ? 'Resume' : 'Pause'),
                  style: FilledButton.styleFrom(
                    minimumSize: const Size.fromHeight(48),
                  ),
                ),
              ),
              const SizedBox(width: 10),
              IconButton.filled(
                tooltip: 'Done — review recording',
                onPressed: _stopRecordingForPreview,
                icon: const Icon(Icons.check_rounded),
              ),
            ],
          ),
          const SizedBox(height: 4),
          Align(
            alignment: Alignment.centerLeft,
            child: Text(
              recordingPaused ? 'Recording paused' : 'Recording…',
              style: TextStyle(
                fontSize: 10.5,
                color: Theme.of(context).colorScheme.onSurfaceVariant,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _voicePreviewBar() => Container(
    color: Theme.of(context).colorScheme.surface,
    padding: const EdgeInsets.fromLTRB(10, 9, 10, 10),
    child: StreamBuilder<Duration>(
      stream: voicePreviewPlayer.positionStream,
      builder: (context, snap) {
        final position = snap.data ?? Duration.zero;
        final decodedMs = voicePreviewPlayer.duration?.inMilliseconds ?? 0;
        final recordedMs = recordSeconds * 1000;
        final totalMs = decodedMs > recordedMs ? decodedMs : (recordedMs > 0 ? recordedMs : 1);
        var progress =
            (position.inMilliseconds / totalMs).clamp(0.0, 1.0).toDouble();
        if (voicePreviewPlayer.processingState != ProcessingState.completed &&
            progress >= .995) {
          progress = .985;
        }
        return Row(
          children: [
            IconButton.filledTonal(
              tooltip: 'Delete recording',
              onPressed: _discardVoicePreview,
              icon: const Icon(Icons.delete_outline_rounded, color: AppColors.danger),
            ),
            const SizedBox(width: 7),
            Expanded(
              child: Container(
                padding: const EdgeInsets.fromLTRB(8, 7, 8, 7),
                decoration: BoxDecoration(
                  color: Theme.of(context).brightness == Brightness.dark
                      ? const Color(0xFF172033)
                      : const Color(0xFFF4F7FA),
                  borderRadius: BorderRadius.circular(18),
                ),
                child: Row(
                  children: [
                    SizedBox(
                      width: 40,
                      height: 40,
                      child: IconButton.filled(
                        style: IconButton.styleFrom(
                          backgroundColor: const Color(0xFF118B78),
                          foregroundColor: Colors.white,
                        ),
                        onPressed: _toggleVoicePreviewPlayback,
                        icon: StreamBuilder<bool>(
                          stream: voicePreviewPlayer.playingStream,
                          builder: (_, playing) => Icon(
                            playing.data == true
                                ? Icons.pause_rounded
                                : Icons.play_arrow_rounded,
                          ),
                        ),
                      ),
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: LayoutBuilder(
                        builder: (_, constraints) => GestureDetector(
                          behavior: HitTestBehavior.opaque,
                          onTapDown: (d) => _seekVoicePreview(
                            d.localPosition.dx / constraints.maxWidth,
                          ),
                          onHorizontalDragUpdate: (d) => _seekVoicePreview(
                            d.localPosition.dx / constraints.maxWidth,
                          ),
                          child: SizedBox(
                            height: 30,
                            child: CustomPaint(
                              painter: _VoiceWavePainter(
                                progress: progress,
                                active: const Color(0xFF118B78),
                                inactive: Theme.of(context).brightness == Brightness.dark
                                    ? const Color(0xFF526274)
                                    : const Color(0xFFBBDDD8),
                                seed: recordSeconds + 41,
                                wave: _encodedVoiceWave(),
                              ),
                              child: const SizedBox.expand(),
                            ),
                          ),
                        ),
                      ),
                    ),
                    const SizedBox(width: 8),
                    Text(
                      _duration(position.inSeconds),
                      style: const TextStyle(
                        fontSize: 11,
                        fontWeight: FontWeight.w800,
                        color: Color(0xFF118B78),
                      ),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(width: 8),
            IconButton.filled(
              tooltip: 'Send voice message',
              onPressed: sending ? null : _sendVoicePreview,
              icon: const Icon(Icons.send_rounded),
            ),
          ],
        );
      },
    ),
  );

  Widget _uploadBar() => Container(
    color: Theme.of(context).colorScheme.surface,
    padding: const EdgeInsets.fromLTRB(16, 10, 16, 8),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            const Icon(
              Icons.cloud_upload_outlined,
              size: 18,
              color: AppColors.blue,
            ),
            const SizedBox(width: 8),
            Text(
              'Sending attachment ${(uploadProgress! * 100).round()}%',
              style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w800),
            ),
          ],
        ),
        const SizedBox(height: 7),
        LinearProgressIndicator(value: uploadProgress),
      ],
    ),
  );

  bool get _chatBlocked => selfBlocked || widget.conversation.blockedByOther;

  Future<void> _sendText() async {
    if (_chatBlocked) return;
    final text = textController.text.trim();
    if (text.isEmpty) return;
    final currentReply = reply;
    setState(() => sending = true);
    textController.clear();
    setState(() => reply = null);
    try {
      await AppScope.of(context).api
          .sendText(widget.conversation.id, text, replyTo: currentReply?.id);
      await _load(jumpToBottom: true);
    } catch (e) {
      textController.text = text;
      if (mounted) showMessage(context, apiMessage(e));
    }
    if (mounted) setState(() => sending = false);
  }

  Future<void> _pickAttachment() async {
    if (_chatBlocked) return;
    showModalBottomSheet<void>(
      context: context,
      builder: (sheet) => SafeArea(
        child: Wrap(
          children: [
            ListTile(
              leading: const Icon(Icons.photo_outlined, color: AppColors.blue),
              title: const Text('Photos or images'),
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
              },
            ),
            ListTile(
              leading: const Icon(
                Icons.attach_file_rounded,
                color: AppColors.violet,
              ),
              title: const Text('Document or file'),
              onTap: () async {
                Navigator.pop(sheet);
                final file = await FilePicker.pickFile();
                final path = file?.path;
                if (path != null) _upload(path);
              },
            ),
            if (widget.conversation.isGroup)
              ListTile(
                leading: const Icon(
                  Icons.poll_outlined,
                  color: AppColors.violet,
                ),
                title: const Text('Create poll'),
                onTap: () {
                  Navigator.pop(sheet);
                  _createPoll();
                },
              ),
            ListTile(
              leading: const Icon(
                Icons.camera_alt_outlined,
                color: AppColors.success,
              ),
              title: const Text('Take a photo'),
              onTap: () async {
                Navigator.pop(sheet);
                final image = await ImagePicker().pickImage(
                  source: ImageSource.camera,
                  imageQuality: 88,
                  maxWidth: 2200,
                );
                if (image != null && mounted) {
                  await _reviewImages([image.path]);
                }
              },
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _reviewImages(List<String> initialPaths) async {
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
    var flip = false;
    var crop = 'original';

    double ratioFor(String mode) {
      if (mode == 'square') return 1;
      if (mode == 'portrait') return 4 / 5;
      if (mode == 'landscape') return 16 / 9;
      return 4 / 5;
    }

    final apply = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      backgroundColor: const Color(0xFF08111D),
      builder: (sheet) => StatefulBuilder(
        builder: (context, setLocal) => SizedBox(
          height: MediaQuery.sizeOf(context).height * .90,
          child: Column(
            children: [
              Padding(
                padding: const EdgeInsets.fromLTRB(8, 8, 8, 4),
                child: Row(
                  children: [
                    IconButton(
                      onPressed: () => Navigator.pop(sheet, false),
                      icon: const Icon(Icons.close_rounded, color: Colors.white),
                    ),
                    const Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            'Edit photo',
                            style: TextStyle(
                              color: Colors.white,
                              fontSize: 18,
                              fontWeight: FontWeight.w900,
                            ),
                          ),
                          Text(
                            'Crop, rotate or flip before sending',
                            style: TextStyle(color: Colors.white60, fontSize: 11),
                          ),
                        ],
                      ),
                    ),
                    TextButton(
                      onPressed: () => setLocal(() {
                        turns = 0;
                        flip = false;
                        crop = 'original';
                      }),
                      child: const Text('Reset'),
                    ),
                  ],
                ),
              ),
              const Divider(height: 1, color: Color(0x334B5870)),
              Expanded(
                child: Padding(
                  padding: const EdgeInsets.all(14),
                  child: Center(
                    child: AnimatedContainer(
                      duration: const Duration(milliseconds: 180),
                      constraints: const BoxConstraints(maxWidth: 520, maxHeight: 560),
                      child: AspectRatio(
                        aspectRatio: ratioFor(crop),
                        child: ClipRRect(
                          borderRadius: BorderRadius.circular(20),
                          child: ColoredBox(
                            color: Colors.black,
                            child: Transform.flip(
                              flipX: flip,
                              child: RotatedBox(
                                quarterTurns: turns,
                                child: Image.file(
                                  File(sourcePath),
                                  fit: crop == 'original' ? BoxFit.contain : BoxFit.cover,
                                  filterQuality: FilterQuality.high,
                                  gaplessPlayback: true,
                                ),
                              ),
                            ),
                          ),
                        ),
                      ),
                    ),
                  ),
                ),
              ),
              Container(
                width: double.infinity,
                padding: const EdgeInsets.fromLTRB(12, 10, 12, 8),
                decoration: const BoxDecoration(
                  color: Color(0xFF0D1828),
                  border: Border(top: BorderSide(color: Color(0x334B5870))),
                ),
                child: Column(
                  children: [
                    SingleChildScrollView(
                      scrollDirection: Axis.horizontal,
                      child: Row(
                        children: [
                          for (final entry in const <String, String>{
                            'original': 'Original',
                            'square': 'Square',
                            'portrait': '4:5',
                            'landscape': '16:9',
                          }.entries) ...[
                            ChoiceChip(
                              selected: crop == entry.key,
                              showCheckmark: false,
                              label: Text(entry.value),
                              onSelected: (_) => setLocal(() => crop = entry.key),
                            ),
                            const SizedBox(width: 7),
                          ],
                        ],
                      ),
                    ),
                    const SizedBox(height: 10),
                    Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        IconButton.filledTonal(
                          tooltip: 'Rotate left',
                          onPressed: () => setLocal(() => turns = (turns + 3) % 4),
                          icon: const Icon(Icons.rotate_left_rounded),
                        ),
                        const SizedBox(width: 10),
                        IconButton.filledTonal(
                          tooltip: 'Rotate right',
                          onPressed: () => setLocal(() => turns = (turns + 1) % 4),
                          icon: const Icon(Icons.rotate_right_rounded),
                        ),
                        const SizedBox(width: 10),
                        IconButton.filledTonal(
                          tooltip: 'Flip horizontal',
                          onPressed: () => setLocal(() => flip = !flip),
                          icon: Icon(flip ? Icons.flip_rounded : Icons.flip_outlined),
                        ),
                        const Spacer(),
                        FilledButton.icon(
                          onPressed: () => Navigator.pop(sheet, true),
                          icon: const Icon(Icons.check_rounded),
                          label: const Text('Apply'),
                        ),
                      ],
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
    if (turns == 0 && !flip && crop == 'original') return sourcePath;
    try {
      final bytes = await File(sourcePath).readAsBytes();
      final edited = await compute(_processOutgoingPhoto, <String, dynamic>{
        'bytes': bytes,
        'turns': turns,
        'flip': flip,
        'crop': crop,
      });
      final dir = await getTemporaryDirectory();
      final output = '${dir.path}/taleempk_photo_${DateTime.now().microsecondsSinceEpoch}.jpg';
      final file = File(output);
      await file.writeAsBytes(edited, flush: true);
      if (!await file.exists() || await file.length() < 256) {
        throw StateError('Edited photo output is empty.');
      }
      return output;
    } catch (e) {
      if (mounted) {
        showMessage(context, 'Photo edit failed. The original photo is still selected.');
      }
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

  void _startVoicePresenceHeartbeat() {
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

  Future<void> _toggleRecording() async {
    if (_chatBlocked) return;
    if (recording) {
      await _stopRecordingForPreview();
      return;
    }
    if (!await recorder.hasPermission()) {
      if (mounted)
        showMessage(
          context,
          'Microphone permission is needed for voice notes.',
        );
      return;
    }
    await VoiceBubble.pauseActivePlayback();
    await voicePreviewPlayer.stop();
    final dir = await getTemporaryDirectory();
    recordPath =
        '${dir.path}/taleempk_${DateTime.now().millisecondsSinceEpoch}.m4a';
    await recorder.start(
      const RecordConfig(
        encoder: AudioEncoder.aacLc,
        bitRate: 96000,
        sampleRate: 44100,
      ),
      path: recordPath!,
    );
    recordSeconds = 0;
    voiceLevels.clear();
    recording = true;
    recordingPaused = false;
    setState(() {});
    typingHeartbeat?.cancel();
    typingHeartbeat = null;
    presenceDebounce?.cancel();
    typingSent = false;
    _startVoicePresenceHeartbeat();
    waveTimer?.cancel();
    waveTimer = Timer.periodic(const Duration(milliseconds: 120), (_) async {
      if (!mounted || recordingPaused || !recording) return;
      try {
        final amp = await recorder.getAmplitude();
        final db = amp.current;
        final normalized = ((db + 60) / 60).clamp(0.05, 1.0).toDouble();
        if (voiceLevels.length < 1600) voiceLevels.add(normalized);
      } catch (_) {}
    });
    recordTimer = Timer.periodic(const Duration(seconds: 1), (_) {
      if (!mounted) return;
      if (recordingPaused) return;
      setState(() => recordSeconds++);
      if (recordSeconds >= 120) _stopRecordingForPreview();
    });
  }

  Future<void> _pauseResumeRecording() async {
    try {
      if (recordingPaused) {
        await recorder.resume();
        recordingPaused = false;
        _startVoicePresenceHeartbeat();
      } else {
        await recorder.pause();
        recordingPaused = true;
        _stopVoicePresenceHeartbeat();
      }
      if (mounted) setState(() {});
    } catch (e) {
      if (mounted) showMessage(context, apiMessage(e));
    }
  }

  Future<void> _stopRecordingForPreview() async {
    if (!recording) return;
    recordTimer?.cancel();
    waveTimer?.cancel();
    final path = await recorder.stop();
    _stopVoicePresenceHeartbeat();
    if (!mounted) return;
    setState(() {
      recording = false;
      recordingPaused = false;
      voicePreviewPath = path;
    });
    if (path == null || recordSeconds < 1) {
      await _discardVoicePreview();
      return;
    }
    try {
      await voicePreviewPlayer.stop();
      await voicePreviewPlayer.setFilePath(path);
    } catch (e) {
      if (mounted) showMessage(context, 'The recording could not be previewed. Please record it again.');
    }
  }

  Future<void> _toggleVoicePreviewPlayback() async {
    if (voicePreviewPath == null) return;
    try {
      if (voicePreviewPlayer.processingState == ProcessingState.completed) {
        await voicePreviewPlayer.seek(Duration.zero);
      }
      if (voicePreviewPlayer.playing) {
        await voicePreviewPlayer.pause();
      } else {
        await VoiceBubble.pauseActivePlayback();
        await voicePreviewPlayer.play();
      }
    } catch (e) {
      if (mounted) showMessage(context, apiMessage(e));
    }
  }

  Future<void> _seekVoicePreview(double fraction) async {
    final total = voicePreviewPlayer.duration ?? Duration(seconds: recordSeconds);
    if (total.inMilliseconds <= 0) return;
    await voicePreviewPlayer.seek(
      Duration(
        milliseconds: (total.inMilliseconds * fraction.clamp(0.0, 1.0)).round(),
      ),
    );
  }

  Future<void> _discardVoicePreview() async {
    await voicePreviewPlayer.stop();
    final path = voicePreviewPath;
    if (path != null) {
      try {
        File(path).deleteSync();
      } catch (_) {}
    }
    if (mounted) {
      setState(() {
        voicePreviewPath = null;
        recordPath = null;
        recordSeconds = 0;
        voiceLevels.clear();
      });
    }
  }

  Future<void> _sendVoicePreview() async {
    final path = voicePreviewPath;
    if (path == null || sending || recordSeconds < 1) return;
    final wave = _encodedVoiceWave();
    final seconds = recordSeconds;
    setState(() {
      sending = true;
      uploadProgress = 0;
    });
    await voicePreviewPlayer.pause();
    try {
      await AppScope.of(context).api.sendFile(
        widget.conversation.id,
        path,
        field: 'voice',
        voiceSeconds: seconds,
        voiceWave: wave,
        replyTo: reply?.id,
        onProgress: (value) {
          if (mounted) setState(() => uploadProgress = value);
        },
      );
      reply = null;
      await _discardVoicePreview();
      await _load(jumpToBottom: true);
    } catch (e) {
      if (mounted) showMessage(context, apiMessage(e));
    } finally {
      if (mounted) {
        setState(() {
          sending = false;
          uploadProgress = null;
        });
      }
    }
  }

  Future<void> _cancelRecording() async {
    recordTimer?.cancel();
    waveTimer?.cancel();
    await recorder.cancel();
    if (mounted)
      setState(() {
        recording = false;
        recordingPaused = false;
        recordSeconds = 0;
        voiceLevels.clear();
      });
    _stopVoicePresenceHeartbeat();
  }

  Widget _blockedBanner() => Container(
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

  Future<void> _startCall(bool video) async {
    if (_chatBlocked || widget.conversation.isGroup) return;
    await Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => CallScreen(
          conversation: widget.conversation,
          video: video,
        ),
      ),
    );
    if (mounted) _load();
  }

  Future<void> _conversationMenu() async {
    await showModalBottomSheet<void>(
      context: context,
      showDragHandle: true,
      builder: (sheet) => SafeArea(
        child: Wrap(
          children: [
            if (!widget.conversation.isGroup &&
                widget.conversation.otherUsername.isNotEmpty)
              ListTile(
                leading: const Icon(Icons.person_outline_rounded),
                title: const Text('View profile'),
                onTap: () {
                  Navigator.pop(sheet);
                  _openProfile();
                },
              ),
            if (widget.conversation.isGroup)
              ListTile(
                leading: const Icon(Icons.group_outlined),
                title: const Text('Group members & settings'),
                onTap: () {
                  Navigator.pop(sheet);
                  _groupManagement();
                },
              ),
            ListTile(
              leading: const Icon(Icons.calendar_month_outlined),
              title: const Text('Jump to date'),
              onTap: () {
                Navigator.pop(sheet);
                _jumpToDate();
              },
            ),
            ListTile(
              leading: const Icon(Icons.lock_outline_rounded),
              title: const Text('Encryption'),
              onTap: () {
                Navigator.pop(sheet);
                _encryptionInfo();
              },
            ),
            if (!widget.conversation.isGroup &&
                widget.conversation.otherId > 0)
              ListTile(
                leading: Icon(
                  selfBlocked
                      ? Icons.lock_open_rounded
                      : Icons.block_rounded,
                  color: selfBlocked ? AppColors.success : AppColors.danger,
                ),
                title: Text(selfBlocked ? 'Unblock' : 'Block'),
                onTap: () {
                  Navigator.pop(sheet);
                  _toggleBlock();
                },
              ),
            ListTile(
              leading: Icon(
                widget.conversation.archived
                    ? Icons.unarchive_outlined
                    : Icons.archive_outlined,
              ),
              title: Text(
                widget.conversation.archived ? 'Unarchive chat' : 'Archive chat',
              ),
              onTap: () {
                Navigator.pop(sheet);
                _toggleArchive();
              },
            ),
            ListTile(
              leading: Icon(
                muted
                    ? Icons.notifications_active_outlined
                    : Icons.notifications_off_outlined,
              ),
              title: Text(
                muted ? 'Unmute notifications' : 'Mute notifications',
              ),
              onTap: () {
                Navigator.pop(sheet);
                _toggleMute();
              },
            ),
            if (!widget.conversation.isGroup &&
                widget.conversation.otherId > 0)
              ListTile(
                leading: const Icon(
                  Icons.flag_outlined,
                  color: AppColors.danger,
                ),
                title: const Text(
                  'Report',
                  style: TextStyle(color: AppColors.danger),
                ),
                onTap: () {
                  Navigator.pop(sheet);
                  _reportUser();
                },
              ),
          ],
        ),
      ),
    );
  }

  Future<void> _toggleArchive() async {
    try {
      final archived = await AppScope.of(context).api
          .toggleConversationArchive(widget.conversation.id);
      if (!mounted) return;
      showMessage(context, archived ? 'Chat archived.' : 'Chat restored.');
      Navigator.pop(context);
    } catch (e) {
      if (mounted) showMessage(context, apiMessage(e));
    }
  }

  Future<void> _groupManagement() async {
    try {
      var data = await AppScope.of(context).api.groupMembers(widget.conversation.id);
      if (!mounted) return;
      await showModalBottomSheet<void>(
        context: context,
        isScrollControlled: true,
        showDragHandle: true,
        builder: (sheet) => StatefulBuilder(
          builder: (context, setLocal) {
            final role = '${data['role'] ?? ''}';
            final members = (data['members'] is List)
                ? (data['members'] as List)
                    .whereType<Map>()
                    .map((e) => e.cast<String, dynamic>())
                    .toList()
                : <Map<String, dynamic>>[];
            return SizedBox(
              height: MediaQuery.sizeOf(context).height * .78,
              child: Column(
                children: [
                  ListTile(
                    leading: const Icon(Icons.groups_rounded, color: AppColors.blue),
                    title: Text(
                      widget.conversation.title,
                      style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w900),
                    ),
                    subtitle: Text('${members.length} members · ${role.isEmpty ? 'member' : role}'),
                    trailing: role == 'admin'
                        ? IconButton(
                            tooltip: 'Rename group',
                            onPressed: () async {
                              final value = await _renameGroup();
                              if (value != null && sheet.mounted) {
                                setLocal(() {});
                              }
                            },
                            icon: const Icon(Icons.edit_outlined),
                          )
                        : null,
                  ),
                  if (role == 'admin')
                    ListTile(
                      leading: const Icon(Icons.person_add_alt_1_rounded),
                      title: const Text('Add member'),
                      onTap: () async {
                        await _addGroupMember();
                        data = await AppScope.of(context).api
                            .groupMembers(widget.conversation.id);
                        if (sheet.mounted) setLocal(() {});
                      },
                    ),
                  const Divider(height: 1),
                  Expanded(
                    child: ListView.separated(
                      itemCount: members.length,
                      separatorBuilder: (_, _) => const Divider(height: 1, indent: 70),
                      itemBuilder: (_, i) {
                        final member = members[i];
                        final id = _asInt(member['id']);
                        final memberRole = '${member['role'] ?? ''}';
                        return ListTile(
                          leading: UserAvatar(
                            url: member['avatar']?.toString(),
                            name: '${member['name'] ?? ''}',
                            radius: 20,
                          ),
                          title: Text('${member['name'] ?? ''}'),
                          subtitle: Text(
                            '@${member['username'] ?? ''}${memberRole == 'admin' ? ' · admin' : ''}',
                          ),
                          trailing: role == 'admin' &&
                                  id != AppScope.of(context).user?.id
                              ? IconButton(
                                  tooltip: 'Remove member',
                                  onPressed: () async {
                                    final yes = await showDialog<bool>(
                                          context: context,
                                          builder: (d) => AlertDialog(
                                            title: const Text('Remove member?'),
                                            content: Text(
                                              'Remove ${member['name']} from this group?',
                                            ),
                                            actions: [
                                              TextButton(
                                                onPressed: () => Navigator.pop(d, false),
                                                child: const Text('Cancel'),
                                              ),
                                              FilledButton(
                                                onPressed: () => Navigator.pop(d, true),
                                                child: const Text('Remove'),
                                              ),
                                            ],
                                          ),
                                        ) ??
                                        false;
                                    if (!yes) return;
                                    await AppScope.of(context).api.groupAction(
                                      'remove',
                                      conversationId: widget.conversation.id,
                                      userId: id,
                                    );
                                    data = await AppScope.of(context).api
                                        .groupMembers(widget.conversation.id);
                                    if (sheet.mounted) setLocal(() {});
                                  },
                                  icon: const Icon(
                                    Icons.person_remove_outlined,
                                    color: AppColors.danger,
                                  ),
                                )
                              : null,
                        );
                      },
                    ),
                  ),
                  SafeArea(
                    top: false,
                    child: Padding(
                      padding: const EdgeInsets.fromLTRB(16, 8, 16, 14),
                      child: OutlinedButton.icon(
                        onPressed: () async {
                          final yes = await showDialog<bool>(
                                context: context,
                                builder: (d) => AlertDialog(
                                  title: const Text('Leave group?'),
                                  content: const Text(
                                    'You will stop receiving messages from this group.',
                                  ),
                                  actions: [
                                    TextButton(
                                      onPressed: () => Navigator.pop(d, false),
                                      child: const Text('Cancel'),
                                    ),
                                    FilledButton(
                                      onPressed: () => Navigator.pop(d, true),
                                      child: const Text('Leave'),
                                    ),
                                  ],
                                ),
                              ) ??
                              false;
                          if (!yes) return;
                          await AppScope.of(context).api.groupAction(
                            'leave',
                            conversationId: widget.conversation.id,
                          );
                          if (sheet.mounted) Navigator.pop(sheet);
                          if (mounted) Navigator.pop(context);
                        },
                        icon: const Icon(Icons.logout_rounded, color: AppColors.danger),
                        label: const Text(
                          'Leave group',
                          style: TextStyle(color: AppColors.danger),
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            );
          },
        ),
      );
    } catch (e) {
      if (mounted) showMessage(context, apiMessage(e));
    }
  }

  Future<String?> _renameGroup() async {
    final controller = TextEditingController(text: widget.conversation.title);
    final value = await showDialog<String>(
      context: context,
      builder: (d) => AlertDialog(
        title: const Text('Rename group'),
        content: TextField(
          controller: controller,
          autofocus: true,
          maxLength: 120,
          decoration: const InputDecoration(labelText: 'Group name'),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(d),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(d, controller.text.trim()),
            child: const Text('Save'),
          ),
        ],
      ),
    );
    controller.dispose();
    if (value == null || value.length < 2 || !mounted) return null;
    try {
      await AppScope.of(context).api.groupAction(
        'rename',
        conversationId: widget.conversation.id,
        title: value,
      );
      showMessage(context, 'Group renamed.');
      return value;
    } catch (e) {
      showMessage(context, apiMessage(e));
      return null;
    }
  }

  Future<void> _addGroupMember() async {
    final controller = TextEditingController();
    List<Map<String, dynamic>> results = const [];
    int selected = 0;
    final add = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (sheet) => StatefulBuilder(
        builder: (context, setLocal) => SizedBox(
          height: MediaQuery.sizeOf(context).height * .62,
          child: Column(
            children: [
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 4, 16, 10),
                child: TextField(
                  controller: controller,
                  autofocus: true,
                  decoration: InputDecoration(
                    hintText: 'Search people',
                    prefixIcon: const Icon(Icons.person_search_rounded),
                    suffixIcon: IconButton(
                      onPressed: () async {
                        if (controller.text.trim().length < 2) return;
                        results = await AppScope.of(context).api
                            .searchPeople(controller.text.trim());
                        if (sheet.mounted) setLocal(() {});
                      },
                      icon: const Icon(Icons.search_rounded),
                    ),
                  ),
                  onSubmitted: (_) async {
                    if (controller.text.trim().length < 2) return;
                    results = await AppScope.of(context).api
                        .searchPeople(controller.text.trim());
                    if (sheet.mounted) setLocal(() {});
                  },
                ),
              ),
              Expanded(
                child: ListView.builder(
                  itemCount: results.length,
                  itemBuilder: (_, i) {
                    final p = results[i];
                    final id = _asInt(p['id']);
                    return RadioListTile<int>(
                      value: id,
                      groupValue: selected,
                      onChanged: (v) => setLocal(() => selected = v ?? 0),
                      title: Text('${p['name'] ?? ''}'),
                      subtitle: Text('@${p['username'] ?? ''}'),
                    );
                  },
                ),
              ),
              Padding(
                padding: const EdgeInsets.all(14),
                child: FilledButton(
                  onPressed: selected > 0
                      ? () => Navigator.pop(sheet, true)
                      : null,
                  child: const Text('Add member'),
                ),
              ),
            ],
          ),
        ),
      ),
    );
    controller.dispose();
    if (add != true || selected <= 0 || !mounted) return;
    try {
      await AppScope.of(context).api.groupAction(
        'add',
        conversationId: widget.conversation.id,
        userId: selected,
      );
      showMessage(context, 'Member added.');
    } catch (e) {
      showMessage(context, apiMessage(e));
    }
  }

  Future<void> _openProfile() async {
    final username = widget.conversation.otherUsername;
    if (username.isEmpty) return;
    final uri = Uri.parse(
      'https://taleempk.online/profile.php?u=${Uri.encodeQueryComponent(username)}',
    );
    if (!await launchUrl(uri, mode: LaunchMode.externalApplication) && mounted) {
      showMessage(context, 'Profile could not be opened.');
    }
  }

  Future<void> _toggleMute() async {
    try {
      final next = await AppScope.of(context).api
          .toggleConversationMute(widget.conversation.id);
      if (mounted) {
        setState(() => muted = next);
        showMessage(
          context,
          next ? 'Notifications muted.' : 'Notifications unmuted.',
        );
      }
    } catch (e) {
      if (mounted) showMessage(context, apiMessage(e));
    }
  }

  Future<void> _toggleBlock() async {
    if (widget.conversation.otherId <= 0) return;
    if (!selfBlocked) {
      final confirm = await showDialog<bool>(
            context: context,
            builder: (d) => AlertDialog(
              title: Text('Block ${widget.conversation.title}?'),
              content: const Text(
                'You won’t be able to send or receive messages from this person until you unblock them.',
              ),
              actions: [
                TextButton(
                  onPressed: () => Navigator.pop(d, false),
                  child: const Text('Cancel'),
                ),
                FilledButton(
                  onPressed: () => Navigator.pop(d, true),
                  child: const Text('Block'),
                ),
              ],
            ),
          ) ??
          false;
      if (!confirm) return;
    }
    try {
      final data = await AppScope.of(context).api
          .toggleBlock(widget.conversation.otherId);
      final blocked = data['blocked'] == true;
      if (mounted) {
        setState(() {
          selfBlocked = blocked;
          if (blocked) {
            reply = null;
            showEmoji = false;
          }
        });
        showMessage(
          context,
          '${data['message'] ?? (blocked ? 'Blocked.' : 'Unblocked.')}',
        );
      }
    } catch (e) {
      if (mounted) showMessage(context, apiMessage(e));
    }
  }

  Future<void> _serverFindInConversation(String query) async {
    final q = query.trim();
    if (q.length < 2) return;
    try {
      final results = await AppScope.of(context).api.searchMessages(q);
      final scoped = results
          .where((r) => _asInt(r['conversation_id']) == widget.conversation.id)
          .toList();
      if (!mounted) return;
      if (scoped.isEmpty) {
        showMessage(context, 'No matching messages in this conversation.');
        return;
      }
      final selected = await showModalBottomSheet<Map<String, dynamic>>(
        context: context,
        showDragHandle: true,
        builder: (sheet) => SafeArea(
          child: ConstrainedBox(
            constraints: BoxConstraints(
              maxHeight: MediaQuery.sizeOf(sheet).height * .62,
            ),
            child: ListView.separated(
              shrinkWrap: true,
              itemCount: scoped.length,
              separatorBuilder: (_, _) => const Divider(height: 1),
              itemBuilder: (_, i) {
                final item = scoped[i];
                return ListTile(
                  leading: const Icon(Icons.search_rounded),
                  title: Text(
                    '${item['sender'] ?? ''}',
                    style: const TextStyle(fontWeight: FontWeight.w800),
                  ),
                  subtitle: Text(
                    '${item['text'] ?? ''}',
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                  trailing: Text(
                    '${item['time'] ?? ''}',
                    style: const TextStyle(fontSize: 10, color: AppColors.muted),
                  ),
                  onTap: () => Navigator.pop(sheet, item),
                );
              },
            ),
          ),
        ),
      );
      if (selected != null) {
        await _jumpToMessage(_asInt(selected['id']));
      }
    } catch (e) {
      if (mounted) showMessage(context, apiMessage(e));
    }
  }

  Future<void> _jumpToDate() async {
    final picked = await showDatePicker(
      context: context,
      firstDate: DateTime(2020),
      lastDate: DateTime.now(),
      initialDate: DateTime.now(),
    );
    if (picked == null || !mounted) return;
    final date =
        '${picked.year.toString().padLeft(4, '0')}-${picked.month.toString().padLeft(2, '0')}-${picked.day.toString().padLeft(2, '0')}';
    try {
      final data = await AppScope.of(context).api
          .jumpToDate(widget.conversation.id, date);
      final anchor = _asInt(data['anchor_id']);
      if (anchor <= 0) {
        if (mounted) {
          showMessage(
            context,
            '${data['message'] ?? 'No messages near that date.'}',
          );
        }
        return;
      }
      final index = messages.indexWhere((m) => m.id == anchor);
      if (index >= 0 && scroll.hasClients) {
        final target = (index * 76.0).clamp(
          0.0,
          scroll.position.maxScrollExtent,
        );
        await scroll.animateTo(
          target,
          duration: const Duration(milliseconds: 320),
          curve: Curves.easeOut,
        );
      } else {
        await _jumpToMessage(anchor);
      }
    } catch (e) {
      if (mounted) showMessage(context, apiMessage(e));
    }
  }

  Future<void> _encryptionInfo() async {
    await showDialog<void>(
      context: context,
      builder: (d) => AlertDialog(
        icon: const Icon(Icons.lock_rounded, color: AppColors.success),
        title: const Text('Private and encrypted in transit'),
        content: const Text(
          'TaleemPK protects app traffic with HTTPS and secure account sessions. End-to-end encrypted web conversations remain protected on the website; native end-to-end key sync is not enabled yet.',
        ),
        actions: [
          FilledButton(
            onPressed: () => Navigator.pop(d),
            child: const Text('Got it'),
          ),
        ],
      ),
    );
  }

  Future<void> _reportUser() async {
    const reasons = <String, String>{
      'spam': 'Spam or scam',
      'harassment': 'Harassment',
      'inappropriate': 'Inappropriate content',
      'impersonation': 'Impersonation',
      'other': 'Other',
    };
    String selected = 'spam';
    final details = TextEditingController();
    final submit = await showDialog<bool>(
          context: context,
          builder: (d) => StatefulBuilder(
            builder: (context, setLocal) => AlertDialog(
              title: Text('Report ${widget.conversation.title}'),
              content: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  DropdownButtonFormField<String>(
                    initialValue: selected,
                    items: reasons.entries
                        .map(
                          (e) => DropdownMenuItem(
                            value: e.key,
                            child: Text(e.value),
                          ),
                        )
                        .toList(),
                    onChanged: (value) {
                      if (value != null) setLocal(() => selected = value);
                    },
                    decoration: const InputDecoration(labelText: 'Reason'),
                  ),
                  const SizedBox(height: 12),
                  TextField(
                    controller: details,
                    minLines: 2,
                    maxLines: 4,
                    decoration: const InputDecoration(
                      labelText: 'Details (optional)',
                    ),
                  ),
                ],
              ),
              actions: [
                TextButton(
                  onPressed: () => Navigator.pop(d, false),
                  child: const Text('Cancel'),
                ),
                FilledButton(
                  onPressed: () => Navigator.pop(d, true),
                  child: const Text('Submit report'),
                ),
              ],
            ),
          ),
        ) ??
        false;
    if (!submit || !mounted) {
      details.dispose();
      return;
    }
    try {
      final data = await AppScope.of(context).api.reportUser(
        widget.conversation.otherId,
        reason: selected,
        details: details.text.trim(),
      );
      if (mounted) {
        showMessage(context, '${data['message'] ?? 'Report submitted.'}');
      }
    } catch (e) {
      if (mounted) showMessage(context, apiMessage(e));
    } finally {
      details.dispose();
    }
  }

  int _asInt(dynamic value) =>
      value is int ? value : int.tryParse('$value') ?? 0;

  void _toggleSelected(int id) {
    setState(() {
      if (!selectedIds.add(id)) selectedIds.remove(id);
    });
  }

  Widget _selectionBar() => Container(
    color: Theme.of(context).colorScheme.surface,
    padding: const EdgeInsets.fromLTRB(10, 8, 10, 10),
    child: Row(
      children: [
        IconButton(
          tooltip: 'Cancel selection',
          onPressed: () => setState(selectedIds.clear),
          icon: const Icon(Icons.close_rounded),
        ),
        Text(
          '${selectedIds.length} selected',
          style: const TextStyle(fontWeight: FontWeight.w800),
        ),
        const Spacer(),
        IconButton(
          tooltip: 'Copy selected text',
          onPressed: _copySelected,
          icon: const Icon(Icons.copy_rounded),
        ),
        IconButton(
          tooltip: 'Forward selected',
          onPressed: _forwardSelected,
          icon: const Icon(Icons.forward_rounded),
        ),
        IconButton(
          tooltip: 'Delete selected',
          onPressed: _deleteSelected,
          icon: const Icon(Icons.delete_outline_rounded, color: AppColors.danger),
        ),
      ],
    ),
  );

  Future<void> _copySelected() async {
    final text = messages
        .where((m) => selectedIds.contains(m.id) && m.content.isNotEmpty)
        .map((m) => m.content)
        .join('\n');
    if (text.isEmpty) {
      showMessage(context, 'Selected messages have no text to copy.');
      return;
    }
    await Clipboard.setData(ClipboardData(text: text));
    if (mounted) showMessage(context, 'Selected messages copied.');
  }

  Future<void> _forwardSelected() async {
    final chosen = messages.where((m) => selectedIds.contains(m.id)).toList();
    if (chosen.isEmpty) return;
    try {
      final chats = await AppScope.of(context).api.conversations();
      if (!mounted) return;
      final target = await showModalBottomSheet<Conversation>(
        context: context,
        isScrollControlled: true,
        showDragHandle: true,
        builder: (sheet) => SizedBox(
          height: MediaQuery.sizeOf(sheet).height * .65,
          child: ListView(
            children: [
              const ListTile(
                leading: Icon(Icons.forward_rounded, color: AppColors.blue),
                title: Text(
                  'Forward selected messages',
                  style: TextStyle(fontWeight: FontWeight.w900),
                ),
              ),
              ...chats
                  .where((chat) => chat.id != widget.conversation.id)
                  .map(
                    (chat) => ListTile(
                      leading: UserAvatar(
                        url: chat.avatar,
                        name: chat.title,
                        radius: 20,
                      ),
                      title: Text(chat.title),
                      subtitle: Text(chat.statusText),
                      onTap: () => Navigator.pop(sheet, chat),
                    ),
                  ),
            ],
          ),
        ),
      );
      if (target == null || !mounted) return;
      for (final message in chosen) {
        await AppScope.of(context).api.forwardMessage(message.id, target.id);
      }
      selectedIds.clear();
      setState(() {});
      showMessage(context, '${chosen.length} message${chosen.length == 1 ? '' : 's'} forwarded.');
    } catch (e) {
      if (mounted) showMessage(context, apiMessage(e));
    }
  }

  Future<void> _deleteSelected() async {
    final chosen = messages.where((m) => selectedIds.contains(m.id)).toList();
    if (chosen.isEmpty) return;
    final canDeleteForAll = chosen.every((m) => m.mine);
    final everyone = canDeleteForAll
        ? await showDialog<bool>(
              context: context,
              builder: (d) => AlertDialog(
                title: Text('Delete ${chosen.length} messages?'),
                content: const Text(
                  'Choose whether to remove them only for you or for everyone.',
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
            )
        : false;
    try {
      await AppScope.of(context).api.deleteMessages(
        chosen.map((m) => m.id).toList(),
        everyone: everyone == true,
      );
      selectedIds.clear();
      await _load();
    } catch (e) {
      if (mounted) showMessage(context, apiMessage(e));
    }
  }

  Future<void> _reactWith(ChatMessage m, String emoji) async {
    try {
      await AppScope.of(context).api.react(m.id, emoji);
      await _load();
    } catch (e) {
      if (mounted) showMessage(context, apiMessage(e));
    }
  }

  Future<void> _reportMessage(ChatMessage m) async {
    final details = TextEditingController();
    final ok = await showDialog<bool>(
          context: context,
          builder: (d) => AlertDialog(
            title: const Text('Report message'),
            content: TextField(
              controller: details,
              maxLines: 4,
              decoration: const InputDecoration(
                hintText: 'Tell us what is wrong with this message',
              ),
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(d, false),
                child: const Text('Cancel'),
              ),
              FilledButton(
                onPressed: () => Navigator.pop(d, true),
                child: const Text('Report'),
              ),
            ],
          ),
        ) ??
        false;
    if (!ok || !mounted) {
      details.dispose();
      return;
    }
    try {
      final data = await AppScope.of(context).api.reportMessage(
        m.id,
        details: details.text.trim(),
      );
      if (mounted) {
        showMessage(context, '${data['message'] ?? 'Message reported.'}');
      }
    } catch (e) {
      if (mounted) showMessage(context, apiMessage(e));
    } finally {
      details.dispose();
    }
  }

  Future<void> _messageActions(ChatMessage m) async {
    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      showDragHandle: true,
      builder: (sheet) => FractionallySizedBox(
        heightFactor: .76,
        child: Column(
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 0, 8, 8),
              child: Row(
                children: [
                  Container(
                    width: 38,
                    height: 38,
                    decoration: BoxDecoration(
                      color: AppColors.blue.withValues(alpha: .10),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: const Icon(Icons.chat_bubble_outline_rounded, color: AppColors.blue, size: 20),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text('Message actions', style: TextStyle(fontSize: 15, fontWeight: FontWeight.w900)),
                        Text(
                          m.content.trim().isNotEmpty
                              ? m.content.trim()
                              : (m.voiceSeconds > 0 ? 'Voice message' : (m.attachmentName ?? 'Attachment')),
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(fontSize: 11, color: AppColors.muted),
                        ),
                      ],
                    ),
                  ),
                  IconButton(
                    tooltip: 'Close',
                    onPressed: () => Navigator.pop(sheet),
                    icon: const Icon(Icons.close_rounded),
                  ),
                ],
              ),
            ),
            const Divider(height: 1),
            Padding(
              padding: const EdgeInsets.fromLTRB(14, 10, 14, 10),
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

  Future<void> _forward(ChatMessage message) async {
    try {
      final chats = await AppScope.of(context).api.conversations();
      if (!mounted) return;
      final target = await showModalBottomSheet<Conversation>(
        context: context,
        isScrollControlled: true,
        builder: (sheet) => SafeArea(
          child: SizedBox(
            height: MediaQuery.sizeOf(sheet).height * .62,
            child: Column(
              children: [
                const Padding(
                  padding: EdgeInsets.fromLTRB(20, 18, 20, 10),
                  child: Row(
                    children: [
                      Icon(Icons.forward_rounded, color: AppColors.blue),
                      SizedBox(width: 10),
                      Text(
                        'Forward message',
                        style: TextStyle(
                          fontSize: 18,
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                    ],
                  ),
                ),
                Expanded(
                  child: ListView(
                    children: chats
                        .where((chat) => chat.id != widget.conversation.id)
                        .map(
                          (chat) => ListTile(
                            leading: UserAvatar(
                              url: chat.avatar,
                              name: chat.title,
                              radius: 20,
                              online: chat.online,
                            ),
                            title: Text(chat.title),
                            subtitle: Text(
                              chat.statusText,
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                            ),
                            onTap: () => Navigator.pop(sheet, chat),
                          ),
                        )
                        .toList(),
                  ),
                ),
              ],
            ),
          ),
        ),
      );
      if (target == null || !mounted) return;
      await AppScope.of(context).api.forwardMessage(message.id, target.id);
      if (mounted) showMessage(context, 'Message forwarded to ${target.title}.');
    } catch (e) {
      if (mounted) showMessage(context, apiMessage(e));
    }
  }

  Future<void> _showEditHistory(ChatMessage m) async {
    try {
      final history = await AppScope.of(context).api.editHistory(m.id);
      if (!mounted) return;
      await showModalBottomSheet<void>(
        context: context,
        showDragHandle: true,
        builder: (sheet) => SafeArea(
          child: ConstrainedBox(
            constraints: BoxConstraints(
              maxHeight: MediaQuery.sizeOf(sheet).height * .65,
            ),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const ListTile(
                  leading: Icon(Icons.history_rounded, color: AppColors.blue),
                  title: Text(
                    'Edit history',
                    style: TextStyle(fontWeight: FontWeight.w900),
                  ),
                ),
                Flexible(
                  child: history.isEmpty
                      ? const Padding(
                          padding: EdgeInsets.all(24),
                          child: Text('No earlier version is available.'),
                        )
                      : ListView.separated(
                          shrinkWrap: true,
                          itemCount: history.length,
                          separatorBuilder: (_, _) => const Divider(height: 1),
                          itemBuilder: (_, i) {
                            final h = history[i];
                            return ListTile(
                              title: Text('${h['content'] ?? ''}'),
                              subtitle: Text('${h['edited_at'] ?? ''}'),
                            );
                          },
                        ),
                ),
              ],
            ),
          ),
        ),
      );
    } catch (e) {
      if (mounted) showMessage(context, apiMessage(e));
    }
  }

  Future<void> _edit(ChatMessage m) async {
    final c = TextEditingController(text: m.content);
    await showDialog<void>(
      context: context,
      builder: (d) => AlertDialog(
        title: const Text('Edit message'),
        content: TextField(controller: c, autofocus: true, maxLines: 5),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(d),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () async {
              await AppScope.of(context).api.editMessage(m.id, c.text.trim());
              if (d.mounted) Navigator.pop(d);
              _load();
            },
            child: const Text('Save'),
          ),
        ],
      ),
    );
    c.dispose();
  }

  Future<void> _delete(ChatMessage m) async {
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

  Future<void> _playNextVoice(int currentId) async {
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

  void _toBottom() => WidgetsBinding.instance.addPostFrameCallback((_) {
    if (scroll.hasClients)
      scroll.animateTo(
        scroll.position.maxScrollExtent,
        duration: const Duration(milliseconds: 240),
        curve: Curves.easeOut,
      );
  });
  IconData _fileIcon(String? type) =>
      ['jpg', 'jpeg', 'png', 'gif', 'webp'].contains(type)
      ? Icons.image_rounded
      : type == 'pdf'
      ? Icons.picture_as_pdf_rounded
      : Icons.description_rounded;
  bool _isImage(String? type) =>
      ['jpg', 'jpeg', 'png', 'gif', 'webp'].contains(type?.toLowerCase());
  String _encodedVoiceWave() {
    if (voiceLevels.isEmpty) return '';
    const bars = 48;
    final out = StringBuffer();
    for (var i = 0; i < bars; i++) {
      final start = (i * voiceLevels.length / bars).floor();
      final end = (((i + 1) * voiceLevels.length / bars).ceil())
          .clamp(start + 1, voiceLevels.length);
      var peak = 0.0;
      for (var j = start; j < end; j++) {
        if (voiceLevels[j] > peak) peak = voiceLevels[j];
      }
      out.write((peak * 15).round().clamp(1, 15).toRadixString(16));
    }
    return out.toString();
  }

  String _duration(int seconds) =>
      '${(seconds ~/ 60).toString().padLeft(2, '0')}:${(seconds % 60).toString().padLeft(2, '0')}';
}

class SecureChatImage extends StatefulWidget {
  const SecureChatImage({
    super.key,
    required this.api,
    required this.url,
    required this.mine,
  });
  final ApiClient api;
  final String url;
  final bool mine;

  @override
  State<SecureChatImage> createState() => _SecureChatImageState();
}

class _SecureChatImageState extends State<SecureChatImage> {
  late final Future<Uint8List> bytes = widget.api.attachmentBytes(widget.url);

  @override
  Widget build(BuildContext context) => FutureBuilder<Uint8List>(
    future: bytes,
    builder: (context, snapshot) {
      if (snapshot.hasData) {
        return Image.memory(
          snapshot.data!,
          width: 240,
          height: 190,
          fit: BoxFit.cover,
          gaplessPlayback: true,
        );
      }
      if (snapshot.hasError) {
        return Container(
          width: 240,
          height: 120,
          alignment: Alignment.center,
          color: widget.mine ? Colors.white12 : const Color(0xFFF2F4F8),
          child: const Icon(
            Icons.broken_image_outlined,
            color: AppColors.muted,
          ),
        );
      }
      return Container(
        width: 240,
        height: 150,
        alignment: Alignment.center,
        color: widget.mine ? Colors.white12 : const Color(0xFFF2F4F8),
        child: const SizedBox(
          width: 24,
          height: 24,
          child: CircularProgressIndicator(strokeWidth: 2),
        ),
      );
    },
  );
}

class VoiceBubble extends StatefulWidget {
  const VoiceBubble({
    super.key,
    required this.message,
    required this.api,
    this.onListened,
    this.beforePlay,
    this.onCompleted,
  });
  final ChatMessage message;
  final ApiClient api;
  final VoidCallback? onListened;
  final Future<void> Function()? beforePlay;
  final Future<void> Function()? onCompleted;

  static Future<void> pauseActivePlayback() async {
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

  @override
  State<VoiceBubble> createState() => _VoiceBubbleState();
}

class _VoiceBubbleState extends State<VoiceBubble> {
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
      handlingCompletion = false;
  String? localPath;
  Duration? decodedDuration;
  late double speed = rememberedSpeed;

  @override
  void initState() {
    super.initState();
    listened = widget.message.playedByMe;
    instances[widget.message.id] = this;
    durationSub = player.durationStream.listen((value) {
      if (value != null && value.inMilliseconds > 0 && mounted) {
        decodedDuration = value;
        setState(() {});
      }
    });
    stateSub = player.playerStateStream.listen((state) {
      if (state.processingState == ProcessingState.completed) {
        unawaited(_handleCompleted());
      }
    });
  }

  @override
  void didUpdateWidget(covariant VoiceBubble oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.message.id != widget.message.id) {
      if (instances[oldWidget.message.id] == this) {
        instances.remove(oldWidget.message.id);
      }
      instances[widget.message.id] = this;
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
    if (instances[widget.message.id] == this) {
      instances.remove(widget.message.id);
    }
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

  Future<void> _toggle({bool autoStart = false}) async {
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

      if (activeVoice == this) return;

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
          : (heard ? const Color(0xFF0E8B76) : const Color(0xFF118B78));
      final playIcon = widget.message.mine
          ? (heard ? const Color(0xFF0C5D58) : const Color(0xFF17345B))
          : Colors.white;
      final active = widget.message.mine
          ? (heard ? const Color(0xFFC9FFF3) : const Color(0xFFD8EC72))
          : (heard ? const Color(0xFF0E806D) : const Color(0xFF4FAF9F));
      final inactive = widget.message.mine
          ? (heard ? const Color(0x668BE5D2) : const Color(0x668AA05D))
          : (dark ? const Color(0xFF526274) : const Color(0xFFBBDDD8));
      final meta = widget.message.mine
          ? (heard ? const Color(0xFFD8F8F1) : Colors.white70)
          : AppColors.muted;

      Widget rateChip() => InkWell(
        borderRadius: BorderRadius.circular(18),
        onTap: _cycleSpeed,
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
          decoration: BoxDecoration(
            color: heard
                ? (widget.message.mine ? Colors.white12 : const Color(0x24118B78))
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
                        onPressed: loading ? null : () => _toggle(),
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
                      'Played',
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

class _VoiceWavePainter extends CustomPainter {
  const _VoiceWavePainter({
    required this.progress,
    required this.active,
    required this.inactive,
    required this.seed,
    required this.wave,
  });

  final double progress;
  final Color active, inactive;
  final int seed;
  final String wave;

  @override
  void paint(Canvas canvas, Size size) {
    const gap = 3.0;
    const width = 2.4;
    final count = (size.width / (width + gap)).floor().clamp(18, 54);
    final activeUntil = (count * progress).round();
    for (var i = 0; i < count; i++) {
      final clean = wave.replaceAll(RegExp(r'[^0-9a-fA-F]'), '');
      final raw = clean.isNotEmpty
          ? (int.tryParse(clean[i % clean.length], radix: 16) ?? 7) / 15.0
          : ((i * 37 + seed * 11) % 17) / 16.0;
      final height = 7.0 + raw * (size.height - 9.0);
      final x = i * (width + gap) + width / 2;
      final y1 = (size.height - height) / 2;
      final y2 = y1 + height;
      final paint = Paint()
        ..color = i < activeUntil ? active : inactive
        ..strokeWidth = width
        ..strokeCap = StrokeCap.round;
      canvas.drawLine(Offset(x, y1), Offset(x, y2), paint);
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

  @override
  bool shouldRepaint(covariant _VoiceWavePainter oldDelegate) =>
      oldDelegate.progress != progress ||
      oldDelegate.active != active ||
      oldDelegate.inactive != inactive ||
      oldDelegate.seed != seed ||
      oldDelegate.wave != wave;
}

class _ChatPresenceBubble extends StatefulWidget {
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

class _PulseDot extends StatefulWidget {
  const _PulseDot();
  @override
  State<_PulseDot> createState() => _PulseDotState();
}

class _PulseDotState extends State<_PulseDot>
    with SingleTickerProviderStateMixin {
  late final AnimationController c = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 760),
  )..repeat(reverse: true);
  @override
  void dispose() {
    c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => FadeTransition(
    opacity: Tween(begin: .35, end: 1.0).animate(c),
    child: const Icon(
      Icons.fiber_manual_record_rounded,
      color: AppColors.danger,
      size: 17,
    ),
  );
}
