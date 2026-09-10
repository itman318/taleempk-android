import 'dart:async';
import 'dart:io';
import 'dart:typed_data';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:image_picker/image_picker.dart';
import 'package:just_audio/just_audio.dart';
import 'package:path_provider/path_provider.dart';
import 'package:record/record.dart';
import 'package:url_launcher/url_launcher.dart';

import '../core/app_state.dart';
import '../core/api_client.dart';
import '../core/models.dart';
import '../core/theme.dart';
import '../widgets/common.dart';
import 'call_screen.dart';

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
  Timer? poll, recordTimer, presenceDebounce;
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
      historyDone = false;
  int recordSeconds = 0;
  double? uploadProgress;
  String? error, recordPath;
  String searchQuery = '';
  final selectedIds = <int>{};
  List<Map<String, dynamic>> pinnedMessages = const [];

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    textController.addListener(_typing);
    selfBlocked = widget.conversation.selfBlocked;
    muted = widget.conversation.muted;
    scroll.addListener(_historyListener);
    _load();
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    poll?.cancel();
    recordTimer?.cancel();
    presenceDebounce?.cancel();
    recorder.dispose();
    textController.dispose();
    scroll.dispose();
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) _poll();
  }

  Future<void> _load() async {
    try {
      final fresh = await AppScope.of(context).api
          .messages(widget.conversation.id);
      messages
        ..clear()
        ..addAll(fresh);
      pinnedMessages =
          await AppScope.of(context).api.pinnedMessages(widget.conversation.id);
      historyDone = fresh.length < 150;
      error = null;
      _schedulePoll();
      _toBottom();
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
      );
      if (older.isEmpty) {
        historyDone = true;
      } else {
        final unique = older
            .where((m) => messages.every((old) => old.id != m.id))
            .toList();
        messages.insertAll(0, unique);
        if (older.length < 150) historyDone = true;
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

  void _schedulePoll() {
    poll?.cancel();
    if (mounted) poll = Timer(const Duration(milliseconds: 2100), _poll);
  }

  Future<void> _poll() async {
    if (!mounted || polling) return;
    polling = true;
    try {
      final after = messages.isEmpty ? 0 : messages.last.id;
      final fresh = await AppScope.of(context).api
          .messages(widget.conversation.id, afterId: after);
      final p = await AppScope.of(context).api
          .presence(widget.conversation.id, '');
      for (final message in messages) {
        if (message.mine && message.id <= p.readThrough) message.read = true;
      }
      if (fresh.isNotEmpty) {
        messages.addAll(
          fresh.where((m) => messages.every((old) => old.id != m.id)),
        );
        _toBottom();
      }
      if (mounted) setState(() => presence = p);
    } catch (_) {
      // A transient poll failure must not erase already loaded messages.
    } finally {
      polling = false;
    }
    _schedulePoll();
  }

  void _typing() {
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

  @override
  Widget build(BuildContext context) => Scaffold(
    backgroundColor: Theme.of(context).brightness == Brightness.dark
        ? const Color(0xFF08111F)
        : const Color(0xFFF2F5FA),
    appBar: AppBar(
      toolbarHeight: 68,
      backgroundColor: Theme.of(context).colorScheme.surface,
      surfaceTintColor: Colors.transparent,
      titleSpacing: 0,
      title: searching
          ? TextField(
              autofocus: true,
              onChanged: (value) => setState(() => searchQuery = value),
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
                                  ? '${presence!.name} is recording…'
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
          if (recording) _recordingBar(),
          if (uploadProgress != null) _uploadBar(),
          if (reply != null && !_chatBlocked && selectedIds.isEmpty) _replyBar(),
          if (selectedIds.isNotEmpty)
            _selectionBar()
          else if (_chatBlocked)
            _blockedBanner()
          else
            _composer(),
          if (showEmoji && !_chatBlocked && selectedIds.isEmpty) _emojiPanel(),
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
        return Column(
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
        if (d.primaryVelocity!.abs() > 280)
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
      child: Container(
        constraints: BoxConstraints(
          maxWidth: MediaQuery.sizeOf(context).width *
              (m.voiceSeconds > 0 ? .86 : .79),
        ),
        margin: const EdgeInsets.only(bottom: 7),
        padding: const EdgeInsets.fromLTRB(13, 10, 11, 7),
        decoration: BoxDecoration(
          gradient: m.mine && m.voiceSeconds == 0
              ? const LinearGradient(
                  colors: [Color(0xFF2459D7), Color(0xFF5545D9)],
                )
              : null,
          color: m.voiceSeconds > 0
              ? (m.mine
                    ? const Color(0xFF172B4D)
                    : (Theme.of(context).brightness == Brightness.dark
                          ? const Color(0xFF152133)
                          : Colors.white))
              : (m.mine
                    ? null
                    : (Theme.of(context).brightness == Brightness.dark
                          ? const Color(0xFF141F32)
                          : Colors.white)),
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
            if (m.poll != null && !m.deleted)
              _pollBubble(m)
            else if (m.voiceSeconds > 0 && !m.deleted)
              VoiceBubble(message: m, api: AppScope.of(context).api)
            else if (m.attachmentUrl != null && !m.deleted)
              _attachment(m)
            else
              Text(
                m.content,
                style: TextStyle(
                  color: m.mine ? Colors.white : Theme.of(context).colorScheme.onSurface,
                  height: 1.35,
                  fontStyle: m.deleted ? FontStyle.italic : null,
                ),
              ),
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
                      ? (message.mine ? Colors.white18 : AppColors.blue.withValues(alpha: .12))
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

  Widget _emojiPanel() {
    const emoji = [
      '😀','😃','😄','😁','😆','😅','😂','🤣','😊','😇','🙂','🙃','😉','😌',
      '😍','🥰','😘','😗','😙','😚','😋','😛','😝','😜','🤪','🤨','🧐','🤓',
      '😎','🥳','😏','😒','😞','😔','😟','😕','🙁','☹️','😣','😖','😫','😩',
      '🥺','😢','😭','😤','😠','😡','🤬','🤯','😳','🥵','🥶','😱','😨','😰',
      '😥','😓','🤗','🤔','🫡','🤭','🫢','🤫','🤥','😶','😐','😑','😬','🙄',
      '😯','😦','😧','😮','😲','🥱','😴','🤤','😪','😵','🤐','🤢','🤮','🤧',
      '😷','🤒','🤕','👍','👎','👌','🤌','🤏','✌️','🤞','🫰','🤟','🤘','🤙',
      '👈','👉','👆','👇','☝️','✋','🤚','🖐️','🖖','👋','🤝','👏','🙌','🫶',
      '🙏','✍️','💪','🧠','👀','👁️','❤️','🩷','🧡','💛','💚','💙','🩵','💜',
      '🖤','🤍','🤎','💔','❤️‍🔥','❤️‍🩹','❣️','💕','💞','💓','💗','💖','💘',
      '💝','💟','🔥','✨','⭐','🌟','💫','💥','💯','✅','❌','⚠️','❓','❗',
      '🎉','🎊','🏆','🥇','📚','📖','✏️','📝','🎓','💡','🚀','🇵🇰'
    ];
    return Container(
      height: 210,
      color: Theme.of(context).colorScheme.surface,
      padding: const EdgeInsets.all(12),
      child: GridView.count(
        crossAxisCount: 8,
        children: emoji
            .map(
              (e) => InkWell(
                onTap: () {
                  textController.text += e;
                  textController.selection = TextSelection.collapsed(
                    offset: textController.text.length,
                  );
                },
                child: Center(
                  child: Text(e, style: const TextStyle(fontSize: 25)),
                ),
              ),
            )
            .toList(),
      ),
    );
  }

  Widget _recordingBar() => Container(
    color: Theme.of(context).brightness == Brightness.dark
        ? const Color(0xFF26151D)
        : const Color(0xFFFFF1F2),
    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
    child: Row(
      children: [
        if (recordingPaused)
          const Icon(Icons.pause_circle_filled_rounded, color: AppColors.violet)
        else
          const _PulseDot(),
        const SizedBox(width: 9),
        Expanded(
          child: Text(
            recordingPaused
                ? 'Paused · ${_duration(recordSeconds)}'
                : 'Recording · ${_duration(recordSeconds)}',
            style: TextStyle(
              color: recordingPaused
                  ? AppColors.violet
                  : AppColors.danger,
              fontWeight: FontWeight.w800,
            ),
          ),
        ),
        IconButton(
          tooltip: recordingPaused ? 'Resume recording' : 'Pause recording',
          onPressed: _pauseResumeRecording,
          icon: Icon(
            recordingPaused
                ? Icons.mic_rounded
                : Icons.pause_rounded,
          ),
        ),
        IconButton(
          tooltip: 'Delete recording',
          onPressed: _cancelRecording,
          icon: const Icon(Icons.delete_outline_rounded),
        ),
        IconButton.filled(
          tooltip: 'Send voice note',
          onPressed: _finishRecording,
          icon: const Icon(Icons.send_rounded),
        ),
      ],
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
      await _load();
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
              title: const Text('Photo or image'),
              onTap: () async {
                Navigator.pop(sheet);
                final image = await ImagePicker().pickImage(
                  source: ImageSource.gallery,
                  imageQuality: 88,
                  maxWidth: 2200,
                );
                if (image != null) _upload(image.path);
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
                if (image != null) _upload(image.path);
              },
            ),
          ],
        ),
      ),
    );
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
      await _load();
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

  Future<void> _toggleRecording() async {
    if (_chatBlocked) return;
    if (recording) {
      await _finishRecording();
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
    recording = true;
    recordingPaused = false;
    setState(() {});
    AppScope.of(context).api.presence(widget.conversation.id, 'voice');
    recordTimer = Timer.periodic(const Duration(seconds: 1), (_) {
      if (!mounted) return;
      if (recordingPaused) return;
      setState(() => recordSeconds++);
      if (recordSeconds % 3 == 0) {
        AppScope.of(context).api.presence(widget.conversation.id, 'voice');
      }
      if (recordSeconds >= 120) _finishRecording();
    });
  }

  Future<void> _pauseResumeRecording() async {
    try {
      if (recordingPaused) {
        await recorder.resume();
        recordingPaused = false;
        AppScope.of(context).api.presence(widget.conversation.id, 'voice');
      } else {
        await recorder.pause();
        recordingPaused = true;
        AppScope.of(context).api.presence(widget.conversation.id, '');
      }
      if (mounted) setState(() {});
    } catch (e) {
      if (mounted) showMessage(context, apiMessage(e));
    }
  }

  Future<void> _finishRecording() async {
    recordTimer?.cancel();
    final path = await recorder.stop();
    setState(() {
      recording = false;
      recordingPaused = false;
    });
    AppScope.of(context).api.presence(widget.conversation.id, '');
    if (path == null || recordSeconds < 1) return;
    setState(() {
      sending = true;
      uploadProgress = 0;
    });
    try {
      await AppScope.of(context).api.sendFile(
        widget.conversation.id,
        path,
        field: 'voice',
        voiceSeconds: recordSeconds,
        replyTo: reply?.id,
        onProgress: (value) {
          if (mounted) setState(() => uploadProgress = value);
        },
      );
      reply = null;
      await _load();
    } catch (e) {
      if (mounted) showMessage(context, apiMessage(e));
    } finally {
      try {
        File(path).deleteSync();
      } catch (_) {}
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
    await recorder.cancel();
    if (mounted)
      setState(() {
        recording = false;
        recordingPaused = false;
        recordSeconds = 0;
      });
    AppScope.of(context).api.presence(widget.conversation.id, '');
  }

  Widget _blockedBanner() => Container(
    margin: const EdgeInsets.fromLTRB(12, 8, 12, 10),
    padding: const EdgeInsets.fromLTRB(16, 12, 12, 12),
    decoration: BoxDecoration(
      color: Theme.of(context).colorScheme.surface,
      borderRadius: BorderRadius.circular(22),
      border: Border.all(color: Theme.of(context).dividerColor),
    ),
    child: Row(
      children: [
        const Icon(Icons.lock_outline_rounded, color: AppColors.muted),
        const SizedBox(width: 12),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                selfBlocked
                    ? 'You blocked ${widget.conversation.title}'
                    : 'Messaging is unavailable',
                style: TextStyle(
                  fontWeight: FontWeight.w800,
                  color: Theme.of(context).colorScheme.onSurface,
                ),
              ),
              const SizedBox(height: 2),
              Text(
                selfBlocked
                    ? 'You can’t send or receive new messages from this person.'
                    : 'This person has blocked this conversation.',
                style: const TextStyle(fontSize: 12, color: AppColors.muted),
              ),
            ],
          ),
        ),
        if (selfBlocked)
          FilledButton(
            onPressed: _toggleBlock,
            child: const Text('Unblock'),
          ),
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
      } else if (mounted) {
        showMessage(context, 'Date found. Loading that part of chat is next.');
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
      builder: (sheet) => SafeArea(
        child: Wrap(
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(14, 6, 14, 8),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceAround,
                children: ['👍','❤️','😂','😮','😢','🔥']
                    .map(
                      (emoji) => InkWell(
                        borderRadius: BorderRadius.circular(30),
                        onTap: () {
                          Navigator.pop(sheet);
                          _reactWith(m, emoji);
                        },
                        child: Padding(
                          padding: const EdgeInsets.all(7),
                          child: Text(
                            emoji,
                            style: const TextStyle(fontSize: 28),
                          ),
                        ),
                      ),
                    )
                    .toList(),
              ),
            ),
            const Divider(height: 1),
            ListTile(
              leading: const Icon(Icons.reply_rounded),
              title: const Text('Reply'),
              onTap: () {
                Navigator.pop(sheet);
                setState(
                  () => reply = ReplyPreview(
                    id: m.id,
                    sender: m.sender,
                    text: m.content.isNotEmpty ? m.content : 'Attachment',
                  ),
                );
              },
            ),
            if (m.content.isNotEmpty && !m.deleted)
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
              leading: const Icon(Icons.add_reaction_outlined),
              title: const Text('React'),
              onTap: () {
                Navigator.pop(sheet);
                _quickReaction(m);
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
            if (m.canEdit)
              ListTile(
                leading: const Icon(Icons.edit_outlined),
                title: const Text('Edit'),
                onTap: () {
                  Navigator.pop(sheet);
                  _edit(m);
                },
              ),
            if (m.mine)
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

  Future<void> _quickReaction(ChatMessage m) async {
    const values = ['❤️', '👍', '😂', '😮', '😢', '🔥'];
    await showDialog<void>(
      context: context,
      builder: (d) => AlertDialog(
        contentPadding: const EdgeInsets.all(12),
        content: Row(
          mainAxisSize: MainAxisSize.min,
          children: values
              .map(
                (e) => IconButton(
                  onPressed: () async {
                    Navigator.pop(d);
                    await AppScope.of(context).api.react(m.id, e);
                    _load();
                  },
                  icon: Text(e, style: const TextStyle(fontSize: 25)),
                ),
              )
              .toList(),
        ),
      ),
    );
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
  const VoiceBubble({super.key, required this.message, required this.api});
  final ChatMessage message;
  final ApiClient api;

  @override
  State<VoiceBubble> createState() => _VoiceBubbleState();
}

class _VoiceBubbleState extends State<VoiceBubble> {
  final player = AudioPlayer();
  bool ready = false, listened = false, loading = false;
  String? localPath;
  double speed = 1.0;

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
      player.playing ? await player.pause() : await player.play();
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
    if (ready) await player.setSpeed(speed);
    if (mounted) setState(() {});
  }

  Future<void> _seek(double fraction) async {
    await _prepare();
    if (!ready) return;
    final total = player.duration ?? Duration(seconds: widget.message.voiceSeconds);
    final ms = (total.inMilliseconds * fraction.clamp(0.0, 1.0)).round();
    await player.seek(Duration(milliseconds: ms));
  }

  @override
  Widget build(BuildContext context) => StreamBuilder<Duration>(
    stream: player.positionStream,
    builder: (_, snap) {
      final position = snap.data ?? Duration.zero;
      final knownTotal = player.duration ?? Duration(seconds: widget.message.voiceSeconds);
      final totalMs = knownTotal.inMilliseconds > 0
          ? knownTotal.inMilliseconds
          : 1;
      final progress =
          (position.inMilliseconds / totalMs).clamp(0.0, 1.0).toDouble();
      final heard = widget.message.mine
          ? widget.message.playedByOther
          : listened;
      final accent = heard
          ? const Color(0xFF17A873)
          : (widget.message.mine ? const Color(0xFFDAFF61) : const Color(0xFF128C7E));
      final inactive = widget.message.mine
          ? Colors.white30
          : (Theme.of(context).brightness == Brightness.dark
                ? const Color(0xFF566174)
                : const Color(0xFFCFD5DC));

      return ConstrainedBox(
        constraints: const BoxConstraints(minWidth: 220, maxWidth: 270),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            SizedBox(
              width: 44,
              height: 44,
              child: IconButton.filled(
                style: IconButton.styleFrom(
                  backgroundColor: widget.message.mine
                      ? Colors.white
                      : const Color(0xFF128C7E),
                  foregroundColor: widget.message.mine
                      ? AppColors.navy
                      : Colors.white,
                  padding: EdgeInsets.zero,
                ),
                onPressed: loading ? null : _toggle,
                icon: loading
                    ? const SizedBox(
                        width: 18,
                        height: 18,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : StreamBuilder<bool>(
                        stream: player.playingStream,
                        builder: (_, s) => Icon(
                          s.data == true
                              ? Icons.pause_rounded
                              : Icons.play_arrow_rounded,
                          size: 29,
                        ),
                      ),
              ),
            ),
            const SizedBox(width: 8),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  GestureDetector(
                    behavior: HitTestBehavior.opaque,
                    onTapDown: (d) {
                      final box = context.findRenderObject();
                      if (box is! RenderBox) return;
                      final local = box.globalToLocal(d.globalPosition);
                      final fraction = (local.dx / 150).clamp(0.0, 1.0);
                      _seek(fraction);
                    },
                    onHorizontalDragUpdate: (d) {
                      final box = context.findRenderObject();
                      if (box is! RenderBox) return;
                      final local = box.globalToLocal(d.globalPosition);
                      final fraction = (local.dx / 150).clamp(0.0, 1.0);
                      _seek(fraction);
                    },
                    child: SizedBox(
                      height: 31,
                      child: CustomPaint(
                        painter: _VoiceWavePainter(
                          progress: progress,
                          active: accent,
                          inactive: inactive,
                          seed: widget.message.id,
                          wave: widget.message.voiceWave,
                        ),
                        child: const SizedBox.expand(),
                      ),
                    ),
                  ),
                  Row(
                    children: [
                      Icon(
                        heard
                            ? Icons.graphic_eq_rounded
                            : Icons.mic_none_rounded,
                        size: 14,
                        color: accent,
                      ),
                      const SizedBox(width: 4),
                      Text(
                        _voiceDuration(
                          position.inSeconds > 0
                              ? position.inSeconds
                              : widget.message.voiceSeconds,
                        ),
                        style: TextStyle(
                          fontSize: 10.5,
                          fontWeight: FontWeight.w800,
                          color: accent,
                        ),
                      ),
                      if (heard) ...[
                        const SizedBox(width: 6),
                        Text(
                          'played',
                          style: TextStyle(
                            fontSize: 9.5,
                            fontWeight: FontWeight.w800,
                            color: accent,
                          ),
                        ),
                      ],
                      const Spacer(),
                      Text(
                        widget.message.time,
                        style: TextStyle(
                          fontSize: 10,
                          fontWeight: FontWeight.w600,
                          color: widget.message.mine
                              ? Colors.white70
                              : AppColors.muted,
                        ),
                      ),
                      if (widget.message.mine) ...[
                        const SizedBox(width: 4),
                        Icon(
                          widget.message.read
                              ? Icons.done_all_rounded
                              : Icons.check_rounded,
                          size: 15,
                          color: widget.message.read
                              ? const Color(0xFF7CE8FF)
                              : Colors.white70,
                        ),
                      ],
                      const SizedBox(width: 7),
                      InkWell(
                        borderRadius: BorderRadius.circular(18),
                        onTap: _cycleSpeed,
                        child: Container(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 8,
                            vertical: 3,
                          ),
                          decoration: BoxDecoration(
                            border: Border.all(
                              color: accent.withValues(alpha: .55),
                            ),
                            borderRadius: BorderRadius.circular(18),
                          ),
                          child: Text(
                            '${speed.toStringAsFixed(speed == 1.0 ? 0 : 1)}×',
                            style: TextStyle(
                              fontSize: 10,
                              fontWeight: FontWeight.w900,
                              color: accent,
                            ),
                          ),
                        ),
                      ),
                    ],
                  ),
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
  }

  @override
  bool shouldRepaint(covariant _VoiceWavePainter oldDelegate) =>
      oldDelegate.progress != progress ||
      oldDelegate.active != active ||
      oldDelegate.inactive != inactive ||
      oldDelegate.seed != seed ||
      oldDelegate.wave != wave;
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
