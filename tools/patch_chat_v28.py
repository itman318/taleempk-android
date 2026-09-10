from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
CHAT = ROOT / 'flutter/lib/screens/chat_screen.dart'
AUTH = ROOT / 'flutter/lib/screens/auth_screen.dart'
CONV = ROOT / 'flutter/lib/screens/conversations_screen.dart'
PUB = ROOT / 'flutter/pubspec.yaml'


def sub_once(text: str, pattern: str, replacement: str, label: str) -> str:
    updated, count = re.subn(pattern, lambda _: replacement, text, count=1, flags=re.S)
    if count != 1:
        raise RuntimeError(f'{label}: expected one match, got {count}')
    return updated


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f'{label}: anchor missing')
    return text.replace(old, new, 1)


# ---------------- Chat / media ----------------
chat = CHAT.read_text()

photo_processor = r'''Uint8List _processOutgoingPhoto(Map<String, dynamic> args) {
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
'''
chat = sub_once(
    chat,
    r"Uint8List _processOutgoingPhoto\(Map<String, dynamic> args\) \{.*?\n\}\n(?=\nclass ChatScreen)",
    photo_processor,
    'photo processor',
)
chat = replace_once(chat, "String searchQuery = '';", "String searchQuery = '', emojiCategory = 'Recent';", 'emoji state')

# More refined chat canvas and bubbles.
chat = chat.replace("? const Color(0xFF07111D)\n        : const Color(0xFFEEF3F8)", "? const Color(0xFF07101B)\n        : const Color(0xFFF3F6FA)", 1)
chat = chat.replace("const Color(0xFF0D675A)", "const Color(0xFF0C5D58)", 1)
chat = chat.replace("const Color(0xFF193A64)", "const Color(0xFF183B63)", 1)
chat = chat.replace("const Color(0xFFD8F3EB)", "const Color(0xFFDCF6EF)", 1)
chat = chat.replace("const Color(0xFF132236)", "const Color(0xFF142236)", 1)

emoji_method = r'''  Widget _emojiPanel() {
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
'''
chat = sub_once(
    chat,
    r"  Widget _emojiPanel\(\) \{.*?\n  Widget _recordingBar\(\)",
    emoji_method + "\n  Widget _recordingBar()",
    'emoji panel',
)

photo_editor = r'''  Future<String?> _editPhoto(String sourcePath) async {
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
'''
chat = sub_once(
    chat,
    r"  Future<String\?> _editPhoto\(String sourcePath\) async \{.*?\n  Future<void> _uploadManyImages",
    photo_editor + "\n  Future<void> _uploadManyImages",
    'photo editor',
)

# Compact, more deliberate long-press action sheet with a preview header.
chat = replace_once(chat, 'heightFactor: .86,', 'heightFactor: .76,', 'action sheet height')
action_anchor = """        child: Column(\n          children: [\n            Padding(\n              padding: const EdgeInsets.fromLTRB(14, 2, 14, 10),\n"""
action_header = """        child: Column(\n          children: [\n            Padding(\n              padding: const EdgeInsets.fromLTRB(16, 0, 8, 8),\n              child: Row(\n                children: [\n                  Container(\n                    width: 38,\n                    height: 38,\n                    decoration: BoxDecoration(\n                      color: AppColors.blue.withValues(alpha: .10),\n                      borderRadius: BorderRadius.circular(12),\n                    ),\n                    child: const Icon(Icons.chat_bubble_outline_rounded, color: AppColors.blue, size: 20),\n                  ),\n                  const SizedBox(width: 10),\n                  Expanded(\n                    child: Column(\n                      crossAxisAlignment: CrossAxisAlignment.start,\n                      children: [\n                        const Text('Message actions', style: TextStyle(fontSize: 15, fontWeight: FontWeight.w900)),\n                        Text(\n                          m.content.trim().isNotEmpty\n                              ? m.content.trim()\n                              : (m.voiceSeconds > 0 ? 'Voice message' : (m.attachmentName ?? 'Attachment')),\n                          maxLines: 1,\n                          overflow: TextOverflow.ellipsis,\n                          style: const TextStyle(fontSize: 11, color: AppColors.muted),\n                        ),\n                      ],\n                    ),\n                  ),\n                  IconButton(\n                    tooltip: 'Close',\n                    onPressed: () => Navigator.pop(sheet),\n                    icon: const Icon(Icons.close_rounded),\n                  ),\n                ],\n              ),\n            ),\n            const Divider(height: 1),\n            Padding(\n              padding: const EdgeInsets.fromLTRB(14, 10, 14, 10),\n"""
chat = replace_once(chat, action_anchor, action_header, 'action sheet header')

# Voice listened/read palette: keep the whole sent voice note readable once played.
old_voice_palette = r'''      final playColor = widget.message.mine
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
'''
new_voice_palette = r'''      final playColor = widget.message.mine
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
'''
chat = replace_once(chat, old_voice_palette, new_voice_palette, 'voice palette')
chat = chat.replace(
    "color: heard && !widget.message.mine\n                ? const Color(0x24118B78)\n                : Colors.transparent,",
    "color: heard\n                ? (widget.message.mine ? Colors.white12 : const Color(0x24118B78))\n                : Colors.transparent,",
    1,
)
chat = chat.replace("'played',", "'Played',", 1)

CHAT.write_text(chat)

# ---------------- Authentication / email code ----------------
auth = AUTH.read_text()
auth = replace_once(auth, "import 'package:flutter/material.dart';", "import 'package:flutter/material.dart';\nimport 'package:flutter/services.dart';", 'auth services import')

two_factor = r'''  Future<void> _showTwoFactor(String challenge) async {
    final code = TextEditingController();
    var verifying = false;
    String? inlineError;

    Future<void> submit(StateSetter setLocal, BuildContext sheetContext) async {
      final value = code.text.trim();
      if (value.length != 6) {
        setLocal(() => inlineError = 'Enter the complete 6-digit security code.');
        return;
      }
      FocusManager.instance.primaryFocus?.unfocus();
      setLocal(() {
        verifying = true;
        inlineError = null;
      });
      try {
        await AppScope.of(context).finishTwoFactor(challenge, value);
        if (sheetContext.mounted) Navigator.of(sheetContext).pop();
      } on ApiException catch (e) {
        if (sheetContext.mounted) {
          setLocal(() {
            verifying = false;
            inlineError = e.message;
          });
        }
      } catch (_) {
        if (sheetContext.mounted) {
          setLocal(() {
            verifying = false;
            inlineError = 'Verification could not be completed. Check your connection and try again.';
          });
        }
      }
    }

    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      isDismissible: true,
      enableDrag: true,
      showDragHandle: true,
      builder: (sheetContext) => StatefulBuilder(
        builder: (context, setLocal) => Padding(
          padding: EdgeInsets.fromLTRB(
            24,
            10,
            24,
            MediaQuery.viewInsetsOf(sheetContext).bottom + 24,
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Align(
                alignment: Alignment.center,
                child: Container(
                  width: 64,
                  height: 64,
                  decoration: BoxDecoration(
                    color: AppColors.blue.withValues(alpha: .10),
                    shape: BoxShape.circle,
                  ),
                  child: const Icon(Icons.verified_user_rounded, size: 34, color: AppColors.blue),
                ),
              ),
              const SizedBox(height: 16),
              Text(
                'Verify it’s you',
                textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w900),
              ),
              const SizedBox(height: 7),
              const Text(
                'Enter the 6-digit security code sent to your email. The code expires in 10 minutes.',
                textAlign: TextAlign.center,
                style: TextStyle(color: AppColors.muted, height: 1.4),
              ),
              const SizedBox(height: 20),
              TextField(
                controller: code,
                keyboardType: TextInputType.number,
                textInputAction: TextInputAction.done,
                inputFormatters: const [FilteringTextInputFormatter.digitsOnly],
                autofillHints: const [AutofillHints.oneTimeCode],
                enableSuggestions: false,
                autocorrect: false,
                maxLength: 6,
                autofocus: true,
                onChanged: (_) => setLocal(() => inlineError = null),
                onSubmitted: (_) {
                  if (!verifying && code.text.trim().length == 6) {
                    submit(setLocal, sheetContext);
                  }
                },
                decoration: InputDecoration(
                  labelText: '6-digit code',
                  hintText: '000000',
                  prefixIcon: const Icon(Icons.password_rounded),
                  errorText: inlineError,
                  suffixIcon: IconButton(
                    tooltip: 'Paste code',
                    onPressed: verifying
                        ? null
                        : () async {
                            final data = await Clipboard.getData('text/plain');
                            final digits = (data?.text ?? '').replaceAll(RegExp(r'\D'), '');
                            if (digits.length >= 6) {
                              code.text = digits.substring(0, 6);
                              code.selection = TextSelection.collapsed(offset: code.text.length);
                              if (sheetContext.mounted) setLocal(() => inlineError = null);
                            }
                          },
                    icon: const Icon(Icons.content_paste_rounded),
                  ),
                ),
              ),
              if (verifying) ...[
                const SizedBox(height: 4),
                const LinearProgressIndicator(minHeight: 2),
                const SizedBox(height: 8),
                const Text(
                  'Verifying securely…',
                  textAlign: TextAlign.center,
                  style: TextStyle(fontSize: 11.5, color: AppColors.muted),
                ),
              ],
              const SizedBox(height: 12),
              FilledButton.icon(
                onPressed: verifying || code.text.trim().length != 6
                    ? null
                    : () => submit(setLocal, sheetContext),
                icon: verifying
                    ? const SizedBox(
                        width: 18,
                        height: 18,
                        child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                      )
                    : const Icon(Icons.shield_rounded),
                label: Text(verifying ? 'Verifying…' : 'Verify and continue'),
              ),
              const SizedBox(height: 6),
              const Text(
                'For your security, only the newest email code should be used.',
                textAlign: TextAlign.center,
                style: TextStyle(fontSize: 10.5, color: AppColors.muted),
              ),
            ],
          ),
        ),
      ),
    );
    code.dispose();
  }
'''
auth = sub_once(
    auth,
    r"  Future<void> _showTwoFactor\(String challenge\) async \{.*?\n  \}\n(?=\}\n\nclass _StudyBackdrop)",
    two_factor,
    'two factor sheet',
)
AUTH.write_text(auth)

# ---------------- Conversations / inbox ----------------
conv = CONV.read_text()
conv = replace_once(
    conv,
    ": 'Fast, private conversations',",
    ": 'Private messages, groups and study conversations',",
    'messages subtitle',
)
conv = replace_once(
    conv,
    "return Scaffold(\n      appBar:",
    "return Scaffold(\n      backgroundColor: Theme.of(context).brightness == Brightness.dark\n          ? const Color(0xFF08111D)\n          : const Color(0xFFF6F8FC),\n      appBar:",
    'inbox background',
)
old_search = r'''              decoration: const InputDecoration(
                hintText: 'Search conversations',
                prefixIcon: Icon(Icons.search_rounded),
                isDense: true,
              ),'''
new_search = r'''              decoration: InputDecoration(
                hintText: 'Search conversations',
                prefixIcon: const Icon(Icons.search_rounded),
                suffixIcon: query.isEmpty
                    ? null
                    : IconButton(
                        tooltip: 'Clear search',
                        onPressed: () => setState(() => query = ''),
                        icon: const Icon(Icons.close_rounded),
                      ),
                isDense: true,
                filled: true,
                fillColor: Theme.of(context).brightness == Brightness.dark
                    ? const Color(0xFF111C2C)
                    : Colors.white,
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(18),
                  borderSide: BorderSide.none,
                ),
              ),'''
conv = replace_once(conv, old_search, new_search, 'inbox search')
conv = conv.replace(
    "separatorBuilder: (_, __) =>\n                          const Divider(indent: 78, height: 1),",
    "separatorBuilder: (_, __) => const SizedBox(height: 8),",
    1,
)

row_widget = r'''  Widget _row(Conversation c) => Padding(
    padding: const EdgeInsets.symmetric(horizontal: 2),
    child: Material(
      color: Theme.of(context).brightness == Brightness.dark
          ? const Color(0xFF101A2A)
          : Colors.white,
      borderRadius: BorderRadius.circular(20),
      child: InkWell(
        borderRadius: BorderRadius.circular(20),
        onTap: () async {
          await Navigator.push(
            context,
            MaterialPageRoute(builder: (_) => ChatScreen(conversation: c)),
          );
          if (mounted) _load();
        },
        child: Container(
          padding: const EdgeInsets.fromLTRB(12, 11, 8, 11),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(20),
            border: Border.all(
              color: c.unread > 0
                  ? AppColors.blue.withValues(alpha: .28)
                  : Theme.of(context).colorScheme.outlineVariant.withValues(alpha: .55),
            ),
            boxShadow: Theme.of(context).brightness == Brightness.dark
                ? null
                : const [
                    BoxShadow(
                      color: Color(0x0C08142F),
                      blurRadius: 12,
                      offset: Offset(0, 4),
                    ),
                  ],
          ),
          child: Row(
            children: [
              UserAvatar(
                url: c.avatar,
                name: c.title,
                radius: 27,
                online: c.online,
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        if (c.isGroup) ...[
                          const Icon(Icons.groups_rounded, size: 16, color: AppColors.violet),
                          const SizedBox(width: 5),
                        ],
                        Expanded(
                          child: Text(
                            c.title,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: TextStyle(
                              fontSize: 15.5,
                              fontWeight: c.unread > 0 ? FontWeight.w900 : FontWeight.w800,
                              color: Theme.of(context).colorScheme.onSurface,
                            ),
                          ),
                        ),
                        const SizedBox(width: 8),
                        Text(
                          c.lastActivity,
                          style: TextStyle(
                            fontSize: 10.5,
                            fontWeight: c.unread > 0 ? FontWeight.w800 : FontWeight.w600,
                            color: c.unread > 0 ? AppColors.blue : AppColors.muted,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 6),
                    Row(
                      children: [
                        if (c.muted) ...[
                          const Icon(Icons.volume_off_rounded, size: 14, color: AppColors.muted),
                          const SizedBox(width: 5),
                        ],
                        Expanded(
                          child: Text(
                            c.lastMessage.isEmpty ? c.statusText : c.lastMessage,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: TextStyle(
                              fontSize: 13,
                              height: 1.2,
                              color: c.unread > 0
                                  ? Theme.of(context).colorScheme.onSurface
                                  : Theme.of(context).colorScheme.onSurfaceVariant,
                              fontWeight: c.unread > 0 ? FontWeight.w700 : FontWeight.w400,
                            ),
                          ),
                        ),
                        if (c.unread > 0) ...[
                          const SizedBox(width: 8),
                          Container(
                            constraints: const BoxConstraints(minWidth: 24, minHeight: 24),
                            alignment: Alignment.center,
                            padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 3),
                            decoration: BoxDecoration(
                              color: AppColors.blue,
                              borderRadius: BorderRadius.circular(14),
                            ),
                            child: Text(
                              c.unread > 99 ? '99+' : '${c.unread}',
                              style: const TextStyle(
                                color: Colors.white,
                                fontSize: 10,
                                fontWeight: FontWeight.w900,
                              ),
                            ),
                          ),
                        ],
                      ],
                    ),
                  ],
                ),
              ),
              PopupMenuButton<String>(
                tooltip: 'Conversation options',
                padding: EdgeInsets.zero,
                onSelected: (value) => _conversationAction(c, value),
                itemBuilder: (_) => [
                  PopupMenuItem(
                    value: 'mute',
                    child: ListTile(
                      contentPadding: EdgeInsets.zero,
                      leading: Icon(c.muted ? Icons.volume_up_rounded : Icons.volume_off_rounded),
                      title: Text(c.muted ? 'Unmute notifications' : 'Mute notifications'),
                    ),
                  ),
                  PopupMenuItem(
                    value: 'archive',
                    child: ListTile(
                      contentPadding: EdgeInsets.zero,
                      leading: Icon(archivedMode ? Icons.unarchive_rounded : Icons.archive_rounded),
                      title: Text(archivedMode ? 'Unarchive' : 'Archive'),
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    ),
  );
'''
conv = sub_once(
    conv,
    r"  Widget _row\(Conversation c\) => ListTile\(.*?\n  Future<void> _conversationAction",
    row_widget + "\n  Future<void> _conversationAction",
    'conversation row',
)
CONV.write_text(conv)

# Version marker for this audit build.
pub = PUB.read_text()
pub = re.sub(r'version:\s*[0-9.]+\+\d+', 'version: 2.8.0+280', pub, count=1)
PUB.write_text(pub)

print('v2.8 chat/auth/inbox audit patch applied')
