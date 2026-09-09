import 'dart:async';
import 'dart:io';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:just_audio/just_audio.dart';
import 'package:path_provider/path_provider.dart';
import 'package:record/record.dart';

import '../core/app_state.dart';
import '../core/models.dart';
import '../core/theme.dart';
import '../widgets/common.dart';

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
  bool loading = true, sending = false, recording = false, showEmoji = false;
  int recordSeconds = 0;
  String? error, recordPath;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    textController.addListener(_typing);
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
      error = null;
      _schedulePoll();
      _toBottom();
    } catch (e) {
      error = apiMessage(e);
    }
    if (mounted) setState(() => loading = false);
  }

  void _schedulePoll() {
    poll?.cancel();
    poll = Timer(const Duration(milliseconds: 1900), _poll);
  }

  Future<void> _poll() async {
    if (!mounted) return;
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
    } catch (_) {}
    _schedulePoll();
  }

  void _typing() {
    presenceDebounce?.cancel();
    if (textController.text.trim().isNotEmpty)
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
    presenceDebounce = Timer(
      const Duration(seconds: 2),
      () => AppScope.of(context).api.presence(widget.conversation.id, ''),
    );
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    backgroundColor: const Color(0xFFF0F3F9),
    appBar: AppBar(
      toolbarHeight: 68,
      backgroundColor: Colors.white,
      surfaceTintColor: Colors.transparent,
      titleSpacing: 0,
      title: Row(
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
                  style: const TextStyle(
                    fontSize: 17,
                    fontWeight: FontWeight.w800,
                    color: AppColors.ink,
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
        IconButton(
          onPressed: () => showMessage(
            context,
            'Audio and video calls follow your website privacy settings.',
          ),
          icon: const Icon(Icons.call_outlined),
        ),
        PopupMenuButton<String>(
          itemBuilder: (_) => const [
            PopupMenuItem(value: 'search', child: Text('Search messages')),
            PopupMenuItem(value: 'mute', child: Text('Mute notifications')),
          ],
          onSelected: (v) => showMessage(
            context,
            v == 'search'
                ? 'Message search is available from the conversation menu.'
                : 'Conversation notification setting updated.',
          ),
        ),
      ],
    ),
    body: SafeArea(
      top: false,
      child: Column(
        children: [
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
          if (reply != null) _replyBar(),
          _composer(),
          if (showEmoji) _emojiPanel(),
        ],
      ),
    ),
  );

  Widget _messageList() => ListView.builder(
    controller: scroll,
    padding: const EdgeInsets.fromLTRB(12, 16, 12, 14),
    itemCount: messages.length,
    itemBuilder: (_, i) {
      final m = messages[i],
          showDate = i == 0 || messages[i - 1].dateLabel != m.dateLabel;
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

  Widget _bubble(ChatMessage m) => Align(
    alignment: m.mine ? Alignment.centerRight : Alignment.centerLeft,
    child: GestureDetector(
      onLongPress: () => _messageActions(m),
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
          maxWidth: MediaQuery.sizeOf(context).width * .79,
        ),
        margin: const EdgeInsets.only(bottom: 7),
        padding: const EdgeInsets.fromLTRB(13, 10, 11, 7),
        decoration: BoxDecoration(
          gradient: m.mine
              ? const LinearGradient(
                  colors: [AppColors.blue, Color(0xFF5C48E8)],
                )
              : null,
          color: m.mine ? null : Colors.white,
          borderRadius: BorderRadius.only(
            topLeft: const Radius.circular(18),
            topRight: const Radius.circular(18),
            bottomLeft: Radius.circular(m.mine ? 18 : 5),
            bottomRight: Radius.circular(m.mine ? 5 : 18),
          ),
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
            if (m.voiceSeconds > 0 && !m.deleted)
              VoiceBubble(
                message: m,
                headers: AppScope.of(context).api.authHeaders,
              )
            else if (m.attachmentUrl != null && !m.deleted)
              _attachment(m)
            else
              Text(
                m.content,
                style: TextStyle(
                  color: m.mine ? Colors.white : AppColors.ink,
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
                              color: m.mine ? Colors.white : AppColors.ink,
                            ),
                          ),
                        ),
                      )
                      .toList(),
                ),
              ),
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
  Widget _attachment(ChatMessage m) => InkWell(
    onTap: () => showMessage(
      context,
      'Secure attachment: ${m.attachmentName ?? 'File'}',
    ),
    child: Row(
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
        Flexible(
          child: Text(
            m.attachmentName ?? 'Attachment',
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
            style: TextStyle(
              color: m.mine ? Colors.white : AppColors.ink,
              fontWeight: FontWeight.w700,
            ),
          ),
        ),
      ],
    ),
  );

  Widget _replyBar() => Container(
    color: Colors.white,
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
    color: Colors.white,
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
            onTap: () => setState(() => showEmoji = false),
            decoration: InputDecoration(
              hintText: 'Message',
              isDense: true,
              fillColor: const Color(0xFFF4F6FA),
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
      '😀',
      '😃',
      '😄',
      '😁',
      '😂',
      '🤣',
      '😊',
      '😍',
      '🥰',
      '😘',
      '😎',
      '🤓',
      '🤔',
      '🙌',
      '👏',
      '👍',
      '👎',
      '❤️',
      '🔥',
      '🎉',
      '✅',
      '💯',
      '📚',
      '✏️',
      '🧠',
      '🏆',
      '🇵🇰',
      '🙏',
      '🌟',
      '💡',
      '❓',
      '🚀',
    ];
    return Container(
      height: 210,
      color: Colors.white,
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
    color: const Color(0xFFFFF1F2),
    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
    child: Row(
      children: [
        const _PulseDot(),
        const SizedBox(width: 10),
        Text(
          'Recording ${_duration(recordSeconds)}',
          style: const TextStyle(
            color: AppColors.danger,
            fontWeight: FontWeight.w800,
          ),
        ),
        const Spacer(),
        TextButton(onPressed: _cancelRecording, child: const Text('Cancel')),
      ],
    ),
  );

  Future<void> _sendText() async {
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
    setState(() => sending = true);
    try {
      await AppScope.of(context).api
          .sendFile(widget.conversation.id, path, replyTo: reply?.id);
      reply = null;
      await _load();
    } catch (e) {
      if (mounted) showMessage(context, apiMessage(e));
    }
    if (mounted) setState(() => sending = false);
  }

  Future<void> _toggleRecording() async {
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
        '${dir.path}/studyhub_${DateTime.now().millisecondsSinceEpoch}.m4a';
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
    setState(() {});
    AppScope.of(context).api.presence(widget.conversation.id, 'voice');
    recordTimer = Timer.periodic(const Duration(seconds: 1), (_) {
      if (!mounted) return;
      setState(() => recordSeconds++);
      AppScope.of(context).api.presence(widget.conversation.id, 'voice');
      if (recordSeconds >= 120) _finishRecording();
    });
  }

  Future<void> _finishRecording() async {
    recordTimer?.cancel();
    final path = await recorder.stop();
    setState(() => recording = false);
    AppScope.of(context).api.presence(widget.conversation.id, '');
    if (path == null || recordSeconds < 1) return;
    setState(() => sending = true);
    try {
      await AppScope.of(context).api.sendFile(
        widget.conversation.id,
        path,
        field: 'voice',
        voiceSeconds: recordSeconds,
        replyTo: reply?.id,
      );
      reply = null;
      await _load();
    } catch (e) {
      if (mounted) showMessage(context, apiMessage(e));
    } finally {
      try {
        File(path).deleteSync();
      } catch (_) {}
      if (mounted) setState(() => sending = false);
    }
  }

  Future<void> _cancelRecording() async {
    recordTimer?.cancel();
    await recorder.cancel();
    if (mounted)
      setState(() {
        recording = false;
        recordSeconds = 0;
      });
    AppScope.of(context).api.presence(widget.conversation.id, '');
  }

  Future<void> _messageActions(ChatMessage m) async {
    await showModalBottomSheet<void>(
      context: context,
      builder: (sheet) => SafeArea(
        child: Wrap(
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
                    text: m.content.isNotEmpty ? m.content : 'Attachment',
                  ),
                );
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

  Future<void> _quickReaction(ChatMessage m) async {
    const values = ['❤️', '👍', '😂', '😮', '😢', '🙏'];
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
  String _duration(int seconds) =>
      '${(seconds ~/ 60).toString().padLeft(2, '0')}:${(seconds % 60).toString().padLeft(2, '0')}';
}

class VoiceBubble extends StatefulWidget {
  const VoiceBubble({super.key, required this.message, required this.headers});
  final ChatMessage message;
  final Map<String, String> headers;
  @override
  State<VoiceBubble> createState() => _VoiceBubbleState();
}

class _VoiceBubbleState extends State<VoiceBubble> {
  final player = AudioPlayer();
  bool ready = false;
  @override
  void dispose() {
    player.dispose();
    super.dispose();
  }

  Future<void> _toggle() async {
    try {
      if (!ready) {
        await player.setAudioSource(
          AudioSource.uri(
            Uri.parse(widget.message.attachmentUrl!),
            headers: widget.headers,
          ),
        );
        ready = true;
      }
      player.playing ? await player.pause() : await player.play();
      setState(() {});
    } catch (_) {}
  }

  @override
  Widget build(BuildContext context) => StreamBuilder<Duration>(
    stream: player.positionStream,
    builder: (_, snap) {
      final position = snap.data ?? Duration.zero,
          total = Duration(seconds: widget.message.voiceSeconds);
      return Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          IconButton(
            onPressed: _toggle,
            icon: StreamBuilder<bool>(
              stream: player.playingStream,
              builder: (_, s) => Icon(
                s.data == true ? Icons.pause_rounded : Icons.play_arrow_rounded,
                color: widget.message.mine ? Colors.white : AppColors.blue,
              ),
            ),
          ),
          SizedBox(
            width: 125,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                LinearProgressIndicator(
                  value: total.inMilliseconds == 0
                      ? 0
                      : (position.inMilliseconds / total.inMilliseconds).clamp(
                          0,
                          1,
                        ),
                  backgroundColor: Colors.white24,
                  color: widget.message.mine ? Colors.white : AppColors.blue,
                ),
                const SizedBox(height: 5),
                Text(
                  _voiceDuration(
                    position.inSeconds > 0
                        ? position.inSeconds
                        : widget.message.voiceSeconds,
                  ),
                  style: TextStyle(
                    fontSize: 10,
                    color: widget.message.mine
                        ? Colors.white70
                        : AppColors.muted,
                  ),
                ),
              ],
            ),
          ),
        ],
      );
    },
  );
  String _voiceDuration(int s) =>
      '${s ~/ 60}:${(s % 60).toString().padLeft(2, '0')}';
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
