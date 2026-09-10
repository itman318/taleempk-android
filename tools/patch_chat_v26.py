from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHAT = ROOT / 'flutter/lib/screens/chat_screen.dart'
PUBSPEC = ROOT / 'flutter/pubspec.yaml'


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f'patch anchor missing: {label}')
    return text.replace(old, new, 1)


c = CHAT.read_text(encoding='utf-8')

# Never let a currently playing received voice note leak into a new recording.
c = replace_once(
    c,
    "    final dir = await getTemporaryDirectory();\n    recordPath =",
    "    await VoiceBubble.pauseActivePlayback();\n    await voicePreviewPlayer.stop();\n    final dir = await getTemporaryDirectory();\n    recordPath =",
    'pause playback before recording',
)

# Preview playback and received-message playback are mutually exclusive.
c = replace_once(
    c,
    "      if (voicePreviewPlayer.playing) {\n        await voicePreviewPlayer.pause();\n      } else {\n        await voicePreviewPlayer.play();\n      }",
    "      if (voicePreviewPlayer.playing) {\n        await voicePreviewPlayer.pause();\n      } else {\n        await VoiceBubble.pauseActivePlayback();\n        await voicePreviewPlayer.play();\n      }",
    'pause bubble before preview',
)

# Public coordinator hook for the recorder/preview in the same chat screen.
c = replace_once(
    c,
    "  final Future<void> Function()? beforePlay;\n\n  @override\n  State<VoiceBubble> createState() => _VoiceBubbleState();",
    "  final Future<void> Function()? beforePlay;\n\n  static Future<void> pauseActivePlayback() async {\n    final active = _VoiceBubbleState.activeVoice;\n    if (active != null) {\n      await active._pauseForAnotherVoice();\n    }\n  }\n\n  @override\n  State<VoiceBubble> createState() => _VoiceBubbleState();",
    'voice coordinator hook',
)

# A fast double tap can arrive before just_audio reports playing=true. The active
# token is set synchronously, so use it as the second guard against double start.
c = replace_once(
    c,
    "      final previous = activeVoice;\n      if (previous != null && previous != this) {",
    "      if (activeVoice == this) return;\n\n      final previous = activeVoice;\n      if (previous != null && previous != this) {",
    'double start guard',
)

c = replace_once(
    c,
    "  Future<void> _pauseForAnotherVoice() async {\n    if (player.playing) await player.pause();\n    if (mounted) setState(() {});\n  }",
    "  Future<void> _pauseForAnotherVoice() async {\n    if (player.playing) await player.pause();\n    if (activeVoice == this) activeVoice = null;\n    if (mounted) setState(() {});\n  }",
    'clear active voice on peer pause',
)

# Remove duplicate cleanup assignments found during the audit.
c = replace_once(
    c,
    "        voicePreviewPath = null;\n        recordPath = null;\n        recordSeconds = 0;\n        recordPath = null;\n        voicePreviewPath = null;\n        voiceLevels.clear();",
    "        voicePreviewPath = null;\n        recordPath = null;\n        recordSeconds = 0;\n        voiceLevels.clear();",
    'voice preview cleanup',
)

CHAT.write_text(c, encoding='utf-8')

p = PUBSPEC.read_text(encoding='utf-8')
p = replace_once(p, 'version: 2.6.0+260', 'version: 2.6.1+261', 'pubspec version')
PUBSPEC.write_text(p, encoding='utf-8')

print('v2.6.1 voice duplication hardening applied')
