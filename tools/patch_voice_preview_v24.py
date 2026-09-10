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
    "  final recorder = AudioRecorder();\n",
    "  final recorder = AudioRecorder();\n  final voicePreviewPlayer = AudioPlayer();\n",
    'preview player field',
)
once(
    "  String? error, recordPath;\n",
    "  String? error, recordPath, voicePreviewPath;\n",
    'preview path state',
)
once(
    """    recorder.dispose();
    textController.dispose();
""",
    """    recorder.dispose();
    voicePreviewPlayer.dispose();
    final preview = voicePreviewPath;
    if (preview != null) {
      try {
        File(preview).deleteSync();
      } catch (_) {}
    }
    textController.dispose();
""",
    'dispose preview',
)

# Recording / preview replaces the composer, matching the website.
once(
    """          if (recording) _recordingBar(),
          if (uploadProgress != null) _uploadBar(),
          if (reply != null && !_chatBlocked && selectedIds.isEmpty) _replyBar(),
          if (selectedIds.isNotEmpty)
            _selectionBar()
          else if (_chatBlocked)
            _blockedBanner()
          else
            _composer(),
          if (showEmoji && !_chatBlocked && selectedIds.isEmpty) _emojiPanel(),
""",
    """          if (recording)
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
""",
    'recording replaces composer',
)

# Replace the basic recorder row with a website-like two-row recorder and
# listen-back preview.
start = c.index('  Widget _recordingBar() => Container(')
end = c.index('  Widget _uploadBar() => Container(', start)
widgets = r'''  Widget _recordingBar() {
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
        final total = voicePreviewPlayer.duration ?? Duration(seconds: recordSeconds);
        final totalMs = total.inMilliseconds > 0 ? total.inMilliseconds : 1;
        final progress =
            (position.inMilliseconds / totalMs).clamp(0.0, 1.0).toDouble();
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
                      _duration(position.inSeconds > 0 ? position.inSeconds : recordSeconds),
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

'''
c = c[:start] + widgets + c[end:]

# Mic while already recording is no longer a send action; Done owns that job.
once(
    """    if (recording) {
      await _finishRecording();
      return;
    }
""",
    """    if (recording) {
      await _stopRecordingForPreview();
      return;
    }
""",
    'toggle recording done action',
)
c = c.replace('if (recordSeconds >= 120) _finishRecording();',
              'if (recordSeconds >= 120) _stopRecordingForPreview();', 1)

# Replace auto-send finish with two-stage preview/send lifecycle.
start = c.index('  Future<void> _finishRecording() async {')
end = c.index('  Future<void> _cancelRecording() async {', start)
methods = r'''  Future<void> _stopRecordingForPreview() async {
    if (!recording) return;
    recordTimer?.cancel();
    waveTimer?.cancel();
    final path = await recorder.stop();
    AppScope.of(context).api
        .presence(widget.conversation.id, clear: true)
        .catchError((_) => const ChatPresence(
              active: false,
              kind: '',
              name: '',
              readThrough: 0,
            ));
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
      await _load();
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

'''
c = c[:start] + methods + c[end:]

# Cancel should also clear any stale preview state.
once(
    """        recordSeconds = 0;
        voiceLevels.clear();
      });
""",
    """        recordSeconds = 0;
        recordPath = null;
        voicePreviewPath = null;
        voiceLevels.clear();
      });
""",
    'cancel clears preview state',
)

p.write_text(c, encoding='utf-8')
print('Website-style voice recording preview patch applied.')
