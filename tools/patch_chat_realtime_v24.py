from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
p = ROOT / 'flutter/lib/screens/chat_screen.dart'
c = p.read_text(encoding='utf-8')


def once(old, new, label):
    global c
    if old not in c:
        raise SystemExit(f'patch anchor missing: {label}')
    c = c.replace(old, new, 1)


once(
    "  int recordSeconds = 0;\n",
    "  int recordSeconds = 0, pollTicks = 0;\n",
    'poll tick state',
)

old_poll = """  Future<void> _poll() async {
    if (!mounted || polling) return;
    polling = true;
    try {
      final after = messages.isEmpty ? 0 : messages.last.id;
      final fresh = await AppScope.of(context).api
          .messages(widget.conversation.id, afterId: after);
      final p = await AppScope.of(context).api
          .presence(widget.conversation.id);
      final played = p.playedIds.toSet();
      for (final message in messages) {
        if (message.mine && message.id <= p.readThrough) message.read = true;
        if (message.mine &&
            message.voiceSeconds > 0 &&
            played.contains(message.id)) {
          message.playedByOther = true;
        }
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
"""
new_poll = """  Future<void> _poll() async {
    if (!mounted || polling) return;
    polling = true;
    try {
      pollTicks++;
      final fullSync = pollTicks % 4 == 0;
      final after = messages.isEmpty ? 0 : messages.last.id;
      final fresh = await AppScope.of(context).api.messages(
        widget.conversation.id,
        afterId: fullSync ? 0 : after,
      );
      final p = await AppScope.of(context).api
          .presence(widget.conversation.id);
      final played = p.playedIds.toSet();
      for (final message in messages) {
        if (message.mine && message.id <= p.readThrough) message.read = true;
        if (message.mine &&
            message.voiceSeconds > 0 &&
            played.contains(message.id)) {
          message.playedByOther = true;
        }
      }

      var addedNew = false;
      if (fullSync) {
        /* The incremental poll is perfect for new messages but cannot see an
           old bubble that was edited, deleted, reacted to, pinned, or whose
           poll results changed. Reconcile the recent window periodically
           without discarding older history the user already loaded. */
        for (final candidate in fresh) {
          final index = messages.indexWhere((m) => m.id == candidate.id);
          if (index >= 0) {
            final old = messages[index];
            if (old.mine && old.read) candidate.read = true;
            if (old.mine && old.playedByOther) {
              candidate.playedByOther = true;
            }
            messages[index] = candidate;
          } else {
            messages.add(candidate);
            addedNew = true;
          }
        }
        messages.sort((a, b) => a.id.compareTo(b.id));
        pinnedMessages = await AppScope.of(context).api
            .pinnedMessages(widget.conversation.id);
      } else if (fresh.isNotEmpty) {
        final unseen = fresh
            .where((m) => messages.every((old) => old.id != m.id))
            .toList();
        if (unseen.isNotEmpty) {
          messages.addAll(unseen);
          addedNew = true;
        }
      }

      if (addedNew) _toBottom();
      if (mounted) setState(() => presence = p);
    } catch (_) {
      // A transient poll failure must not erase already loaded messages.
    } finally {
      polling = false;
    }
    _schedulePoll();
  }
"""
once(old_poll, new_poll, 'realtime poll reconciliation')

# Polls only exist in group chats. Do not offer a button that the server must
# reject in private conversations.
once(
    """            ListTile(
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
""",
    """            if (widget.conversation.isGroup)
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
""",
    'group-only poll action',
)

# Preview clock starts at 0:00 and advances while listening, instead of showing
# the total duration before playback has even started.
once(
    "_duration(position.inSeconds > 0 ? position.inSeconds : recordSeconds)",
    "_duration(position.inSeconds)",
    'preview current clock',
)

p.write_text(c, encoding='utf-8')
print('Realtime chat reconciliation patch applied.')
