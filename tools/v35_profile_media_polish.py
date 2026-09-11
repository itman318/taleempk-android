from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def r(path):
    return (ROOT / path).read_text(encoding='utf-8')


def w(path, text):
    p = ROOT / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding='utf-8')


def once(text, old, new, label):
    if old not in text:
        raise RuntimeError(f'v3.5 missing target: {label}')
    return text.replace(old, new, 1)


def replace_function(text, signature, replacement, label):
    start = text.find(signature)
    if start < 0:
        raise RuntimeError(f'v3.5 missing function: {label}')
    brace = text.find('{', start)
    if brace < 0:
        raise RuntimeError(f'v3.5 malformed function: {label}')
    depth = 0
    end = None
    for index in range(brace, len(text)):
        char = text[index]
        if char == '{':
            depth += 1
        elif char == '}':
            depth -= 1
            if depth == 0:
                end = index + 1
                break
    if end is None:
        raise RuntimeError(f'v3.5 unterminated function: {label}')
    return text[:start] + replacement + text[end:]


# ---------------------------------------------------------------------------
# Profile: compact actions, balanced hierarchy and premium segmented tabs.
# ---------------------------------------------------------------------------
path = 'flutter/lib/screens/profile_screen.dart'
text = r(path)
start = text.find('  Widget _actions(ProfileData p) => Padding(')
end = text.find('  Widget _activityList()', start)
if start < 0 or end < 0:
    raise RuntimeError('v3.5 profile action/tab block not found')
replacement = r'''  ButtonStyle _compactFilledStyle() => FilledButton.styleFrom(
        minimumSize: const Size(0, 44),
        maximumSize: const Size(double.infinity, 44),
        padding: const EdgeInsets.symmetric(horizontal: 12),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
        textStyle: const TextStyle(fontSize: 12.5, fontWeight: FontWeight.w800),
      );

  ButtonStyle _compactOutlinedStyle() => OutlinedButton.styleFrom(
        minimumSize: const Size(0, 44),
        maximumSize: const Size(double.infinity, 44),
        padding: const EdgeInsets.symmetric(horizontal: 10),
        side: BorderSide(color: Theme.of(context).colorScheme.outlineVariant),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
        textStyle: const TextStyle(fontSize: 12.2, fontWeight: FontWeight.w800),
      );

  Widget _actions(ProfileData p) => Padding(
        padding: const EdgeInsets.fromLTRB(18, 14, 18, 0),
        child: p.isMe
            ? DecoratedBox(
                decoration: BoxDecoration(
                  color: Theme.of(context).colorScheme.surface.withValues(alpha: .76),
                  borderRadius: BorderRadius.circular(18),
                  border: Border.all(color: Theme.of(context).colorScheme.outlineVariant.withValues(alpha: .65)),
                ),
                child: Padding(
                  padding: const EdgeInsets.all(8),
                  child: Column(
                    children: [
                      Row(
                        children: [
                          Expanded(
                            child: FilledButton.icon(
                              style: _compactFilledStyle(),
                              onPressed: () => _editProfile(p),
                              icon: const Icon(Icons.edit_outlined, size: 18),
                              label: const Text('Edit profile', maxLines: 1),
                            ),
                          ),
                          const SizedBox(width: 8),
                          Expanded(
                            child: OutlinedButton.icon(
                              style: _compactOutlinedStyle(),
                              onPressed: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const VerificationScreen())).then((_) => _load(refresh: true)),
                              icon: const Icon(Icons.verified_user_outlined, size: 18),
                              label: Text(p.verified ? 'Verification' : 'Get verified', maxLines: 1),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 8),
                      Row(
                        children: [
                          Expanded(
                            child: OutlinedButton.icon(
                              style: _compactOutlinedStyle(),
                              onPressed: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const SecurityScreen())),
                              icon: const Icon(Icons.shield_outlined, size: 18),
                              label: const FittedBox(fit: BoxFit.scaleDown, child: Text('Privacy & security')),
                            ),
                          ),
                          const SizedBox(width: 8),
                          Expanded(
                            child: OutlinedButton.icon(
                              style: _compactOutlinedStyle(),
                              onPressed: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const ModuleScreen(module: 'support'))),
                              icon: const Icon(Icons.support_agent_rounded, size: 18),
                              label: const Text('Support', maxLines: 1),
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
              )
            : Row(
                children: [
                  Expanded(
                    child: FilledButton.icon(
                      style: _compactFilledStyle(),
                      onPressed: actionBusy ? null : _toggleFollow,
                      icon: Icon(p.isFollowing ? Icons.person_remove_alt_1_outlined : Icons.person_add_alt_1_rounded, size: 18),
                      label: Text(p.isFollowing ? 'Following' : 'Follow'),
                    ),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: OutlinedButton.icon(
                      style: _compactOutlinedStyle(),
                      onPressed: actionBusy ? null : () => _report(p.id),
                      icon: const Icon(Icons.flag_outlined, size: 18),
                      label: const Text('Report'),
                    ),
                  ),
                ],
              ),
      );

  Widget _tabs() {
    const items = [('posts', 'Posts'), ('uploads', 'Uploads'), ('answers', 'Answers'), ('badges', 'Badges')];
    return Padding(
      padding: const EdgeInsets.fromLTRB(18, 16, 18, 8),
      child: Container(
        height: 44,
        padding: const EdgeInsets.all(4),
        decoration: BoxDecoration(
          color: Theme.of(context).colorScheme.surfaceContainerHighest.withValues(alpha: .55),
          borderRadius: BorderRadius.circular(15),
          border: Border.all(color: Theme.of(context).colorScheme.outlineVariant.withValues(alpha: .55)),
        ),
        child: Row(
          children: [
            for (final item in items)
              Expanded(
                child: Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 2),
                  child: Material(
                    color: tab == item.$1
                        ? Theme.of(context).colorScheme.primary.withValues(alpha: .12)
                        : Colors.transparent,
                    borderRadius: BorderRadius.circular(11),
                    child: InkWell(
                      borderRadius: BorderRadius.circular(11),
                      onTap: () {
                        if (tab == item.$1) return;
                        setState(() => tab = item.$1);
                        _loadActivity(reset: true);
                      },
                      child: Center(
                        child: FittedBox(
                          fit: BoxFit.scaleDown,
                          child: Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              if (tab == item.$1) ...[
                                Icon(Icons.check_rounded, size: 15, color: Theme.of(context).colorScheme.primary),
                                const SizedBox(width: 3),
                              ],
                              Text(
                                item.$2,
                                style: TextStyle(
                                  fontSize: 12,
                                  fontWeight: tab == item.$1 ? FontWeight.w900 : FontWeight.w700,
                                  color: tab == item.$1
                                      ? Theme.of(context).colorScheme.primary
                                      : Theme.of(context).colorScheme.onSurfaceVariant,
                                ),
                              ),
                            ],
                          ),
                        ),
                      ),
                    ),
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }

'''
text = text[:start] + replacement + text[end:]
w(path, text)

# ---------------------------------------------------------------------------
# Chat media review: validate files, cap at 20, and make add-more deterministic.
# ---------------------------------------------------------------------------
path = 'flutter/lib/screens/chat_screen.dart'
text = r(path)
if "import 'dart:ui' as ui;" not in text:
    text = once(text, "import 'dart:typed_data';\n", "import 'dart:typed_data';\nimport 'dart:ui' as ui;\n", 'dart ui import')
if "import 'package:flutter/rendering.dart';" not in text:
    text = once(text, "import 'package:flutter/material.dart';\n", "import 'package:flutter/material.dart';\nimport 'package:flutter/rendering.dart';\n", 'rendering import')

text = once(
    text,
    "    final paths = <String>[...initialPaths];\n    var selected = 0;\n",
    """    final paths = initialPaths
        .where((path) => path.trim().isNotEmpty && File(path).existsSync())
        .toSet()
        .take(20)
        .toList();
    if (paths.isEmpty) {
      showMessage(context, 'The selected photo is no longer available.');
      return;
    }
    var selected = 0;
""",
    'validated media review paths',
)
text = once(
    text,
    """                            setLocal(() {
                              paths.addAll(more.map((e) => e.path));
                              selected = paths.length - more.length;
                            });
""",
    """                            setLocal(() {
                              final oldLength = paths.length;
                              final additions = more
                                  .map((e) => e.path)
                                  .where((path) => !paths.contains(path) && File(path).existsSync())
                                  .take((20 - paths.length).clamp(0, 20))
                                  .toList();
                              paths.addAll(additions);
                              if (paths.length > oldLength) selected = oldLength;
                            });
                            if (paths.length >= 20 && dialog.mounted) {
                              showMessage(context, 'You can send up to 20 photos at once.');
                            }
""",
    'media review add-more cap',
)

# Replace the previous crop-only editor with a polished integrated editor.
new_editor = r'''  Future<String?> _editPhoto(String sourcePath) async {
    if (!mounted) return null;
    final source = File(sourcePath);
    if (!await source.exists()) {
      showMessage(context, 'This photo is no longer available.');
      return null;
    }

    var turns = 0;
    var flip = false;
    var crop = 'original';
    var brightness = 0.0;
    var contrast = 1.0;
    var tool = 'none';
    var saving = false;
    final strokes = <_PhotoStroke>[];
    final boundaryKey = GlobalKey();

    double ratioFor(String mode) {
      if (mode == 'square') return 1;
      if (mode == 'portrait') return 4 / 5;
      if (mode == 'landscape') return 16 / 9;
      if (mode == 'story') return 9 / 16;
      return 4 / 5;
    }

    ColorFilter adjustmentFilter() {
      final translate = (-.5 * contrast + .5) * 255 + brightness * 255;
      return ColorFilter.matrix(<double>[
        contrast, 0, 0, 0, translate,
        0, contrast, 0, 0, translate,
        0, 0, contrast, 0, translate,
        0, 0, 0, 1, 0,
      ]);
    }

    Future<String?> exportMarkup() async {
      await WidgetsBinding.instance.endOfFrame;
      final boundary = boundaryKey.currentContext?.findRenderObject() as RenderRepaintBoundary?;
      if (boundary == null) return null;
      final logical = boundary.size;
      final longest = logical.longestSide <= 0 ? 1.0 : logical.longestSide;
      final pixelRatio = (2560 / longest).clamp(1.5, 3.0).toDouble();
      final image = await boundary.toImage(pixelRatio: pixelRatio);
      final bytes = await image.toByteData(format: ui.ImageByteFormat.png);
      image.dispose();
      if (bytes == null) return null;
      final dir = await getTemporaryDirectory();
      final output = '${dir.path}/taleempk_markup_${DateTime.now().microsecondsSinceEpoch}.png';
      final file = File(output);
      await file.writeAsBytes(bytes.buffer.asUint8List(), flush: true);
      return await file.exists() && await file.length() >= 256 ? output : null;
    }

    Future<String?> exportNative() async {
      try {
        final output = await NativeBridge.editPhoto(
          path: sourcePath,
          turns: turns,
          flip: flip,
          crop: crop == 'story' ? 'portrait_story' : crop,
          brightness: brightness,
          contrast: contrast,
          quality: 93,
          maxDimension: 3072,
        );
        if (output != null) {
          final file = File(output);
          if (await file.exists() && await file.length() >= 256) return output;
        }
      } catch (_) {}
      return null;
    }

    final edited = await showModalBottomSheet<String?>(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      backgroundColor: const Color(0xFF08111D),
      builder: (sheet) => StatefulBuilder(
        builder: (context, setLocal) => SizedBox(
          height: MediaQuery.sizeOf(context).height * .94,
          child: Column(
            children: [
              Padding(
                padding: const EdgeInsets.fromLTRB(8, 6, 8, 4),
                child: Row(
                  children: [
                    IconButton(
                      tooltip: 'Cancel',
                      onPressed: saving ? null : () => Navigator.pop(sheet),
                      icon: const Icon(Icons.close_rounded, color: Colors.white),
                    ),
                    const Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text('Photo editor', style: TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.w900)),
                          Text('Crop · adjust · mark up · hide details', style: TextStyle(color: Colors.white60, fontSize: 11)),
                        ],
                      ),
                    ),
                    TextButton.icon(
                      onPressed: saving
                          ? null
                          : () => setLocal(() {
                                turns = 0;
                                flip = false;
                                crop = 'original';
                                brightness = 0;
                                contrast = 1;
                                tool = 'none';
                                strokes.clear();
                              }),
                      icon: const Icon(Icons.restart_alt_rounded, size: 18),
                      label: const Text('Reset'),
                    ),
                  ],
                ),
              ),
              const Divider(height: 1, color: Color(0x334B5870)),
              Expanded(
                child: Padding(
                  padding: const EdgeInsets.all(12),
                  child: Center(
                    child: AnimatedContainer(
                      duration: const Duration(milliseconds: 180),
                      constraints: const BoxConstraints(maxWidth: 540, maxHeight: 590),
                      child: AspectRatio(
                        aspectRatio: ratioFor(crop),
                        child: ClipRRect(
                          borderRadius: BorderRadius.circular(18),
                          child: GestureDetector(
                            behavior: HitTestBehavior.opaque,
                            onPanStart: tool == 'none'
                                ? null
                                : (details) => setLocal(() => strokes.add(_PhotoStroke(tool, <Offset>[details.localPosition]))),
                            onPanUpdate: tool == 'none'
                                ? null
                                : (details) => setLocal(() {
                                      if (strokes.isNotEmpty) strokes.last.points.add(details.localPosition);
                                    }),
                            child: RepaintBoundary(
                              key: boundaryKey,
                              child: Stack(
                                fit: StackFit.expand,
                                children: [
                                  const ColoredBox(color: Colors.black),
                                  ColorFiltered(
                                    colorFilter: adjustmentFilter(),
                                    child: Transform.flip(
                                      flipX: flip,
                                      child: RotatedBox(
                                        quarterTurns: turns,
                                        child: Image.file(
                                          source,
                                          fit: crop == 'original' ? BoxFit.contain : BoxFit.cover,
                                          filterQuality: FilterQuality.high,
                                          gaplessPlayback: true,
                                          errorBuilder: (_, _, _) => const Center(
                                            child: Icon(Icons.broken_image_outlined, color: Colors.white54, size: 54),
                                          ),
                                        ),
                                      ),
                                    ),
                                  ),
                                  Positioned.fill(
                                    child: IgnorePointer(
                                      child: CustomPaint(painter: _PhotoMarkupPainter(strokes)),
                                    ),
                                  ),
                                ],
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
                padding: const EdgeInsets.fromLTRB(12, 8, 12, 10),
                decoration: const BoxDecoration(
                  color: Color(0xFF0D1828),
                  border: Border(top: BorderSide(color: Color(0x334B5870))),
                ),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    SingleChildScrollView(
                      scrollDirection: Axis.horizontal,
                      child: Row(
                        children: [
                          for (final entry in const <String, String>{
                            'original': 'Original',
                            'square': '1:1',
                            'portrait': '4:5',
                            'landscape': '16:9',
                            'story': '9:16',
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
                    const SizedBox(height: 6),
                    Row(
                      children: [
                        const SizedBox(width: 2),
                        const Icon(Icons.brightness_6_outlined, color: Colors.white70, size: 18),
                        Expanded(
                          child: Slider(
                            value: brightness,
                            min: -.45,
                            max: .45,
                            onChanged: (v) => setLocal(() => brightness = v),
                          ),
                        ),
                        const Icon(Icons.contrast_rounded, color: Colors.white70, size: 18),
                        Expanded(
                          child: Slider(
                            value: contrast,
                            min: .65,
                            max: 1.45,
                            onChanged: (v) => setLocal(() => contrast = v),
                          ),
                        ),
                      ],
                    ),
                    SingleChildScrollView(
                      scrollDirection: Axis.horizontal,
                      child: Row(
                        children: [
                          _PhotoToolButton(
                            label: 'Rotate',
                            icon: Icons.rotate_right_rounded,
                            onTap: () => setLocal(() => turns = (turns + 1) % 4),
                          ),
                          _PhotoToolButton(
                            label: 'Flip',
                            icon: Icons.flip_rounded,
                            active: flip,
                            onTap: () => setLocal(() => flip = !flip),
                          ),
                          _PhotoToolButton(
                            label: 'Pen',
                            icon: Icons.edit_rounded,
                            active: tool == 'pen',
                            onTap: () => setLocal(() => tool = tool == 'pen' ? 'none' : 'pen'),
                          ),
                          _PhotoToolButton(
                            label: 'Highlight',
                            icon: Icons.border_color_rounded,
                            active: tool == 'highlight',
                            onTap: () => setLocal(() => tool = tool == 'highlight' ? 'none' : 'highlight'),
                          ),
                          _PhotoToolButton(
                            label: 'Hide',
                            icon: Icons.visibility_off_rounded,
                            active: tool == 'hide',
                            onTap: () => setLocal(() => tool = tool == 'hide' ? 'none' : 'hide'),
                          ),
                          _PhotoToolButton(
                            label: 'Undo',
                            icon: Icons.undo_rounded,
                            onTap: strokes.isEmpty ? null : () => setLocal(strokes.removeLast),
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(height: 8),
                    Row(
                      children: [
                        Text(
                          tool == 'none' ? 'Pinch/preview, then apply' : 'Drag on the photo to ${tool == 'hide' ? 'hide details' : tool}',
                          style: const TextStyle(color: Colors.white60, fontSize: 11),
                        ),
                        const Spacer(),
                        FilledButton.icon(
                          onPressed: saving
                              ? null
                              : () async {
                                  setLocal(() {
                                    saving = true;
                                    tool = 'none';
                                  });
                                  try {
                                    String? output;
                                    if (strokes.isEmpty) output = await exportNative();
                                    output ??= await exportMarkup();
                                    if (!sheet.mounted) return;
                                    if (output == null) {
                                      setLocal(() => saving = false);
                                      showMessage(context, 'Photo changes could not be saved. Try again.');
                                      return;
                                    }
                                    Navigator.pop(sheet, output);
                                  } catch (_) {
                                    if (sheet.mounted) {
                                      setLocal(() => saving = false);
                                      showMessage(context, 'Photo changes could not be saved. Try again.');
                                    }
                                  }
                                },
                          icon: saving
                              ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2))
                              : const Icon(Icons.check_rounded),
                          label: Text(saving ? 'Saving…' : 'Apply'),
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

    if (edited != null && mounted) showMessage(context, 'Photo changes applied.');
    return edited;
  }
'''
text = replace_function(text, '  Future<String?> _editPhoto(String sourcePath) async {', new_editor, 'integrated photo editor')

# Append compact editor support widgets once.
if 'class _PhotoStroke {' not in text:
    text += r'''

class _PhotoStroke {
  _PhotoStroke(this.tool, this.points);
  final String tool;
  final List<Offset> points;
}

class _PhotoMarkupPainter extends CustomPainter {
  const _PhotoMarkupPainter(this.strokes);
  final List<_PhotoStroke> strokes;

  @override
  void paint(Canvas canvas, Size size) {
    for (final stroke in strokes) {
      if (stroke.points.isEmpty) continue;
      final paint = Paint()
        ..style = PaintingStyle.stroke
        ..strokeCap = StrokeCap.round
        ..strokeJoin = StrokeJoin.round;
      if (stroke.tool == 'highlight') {
        paint
          ..color = const Color(0x99E8FF35)
          ..strokeWidth = 18;
      } else if (stroke.tool == 'hide') {
        paint
          ..color = const Color(0xFF111827)
          ..strokeWidth = 34;
      } else {
        paint
          ..color = const Color(0xFFFF4D67)
          ..strokeWidth = 4.5;
      }
      if (stroke.points.length == 1) {
        canvas.drawPoints(ui.PointMode.points, stroke.points, paint);
        continue;
      }
      final path = Path()..moveTo(stroke.points.first.dx, stroke.points.first.dy);
      for (final point in stroke.points.skip(1)) {
        path.lineTo(point.dx, point.dy);
      }
      canvas.drawPath(path, paint);
    }
  }

  @override
  bool shouldRepaint(covariant _PhotoMarkupPainter oldDelegate) => true;
}

class _PhotoToolButton extends StatelessWidget {
  const _PhotoToolButton({
    required this.label,
    required this.icon,
    required this.onTap,
    this.active = false,
  });

  final String label;
  final IconData icon;
  final VoidCallback? onTap;
  final bool active;

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.only(right: 7),
        child: Material(
          color: active ? const Color(0xFF2D5BEC) : const Color(0xFF162238),
          borderRadius: BorderRadius.circular(12),
          child: InkWell(
            onTap: onTap,
            borderRadius: BorderRadius.circular(12),
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 11, vertical: 8),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(icon, color: onTap == null ? Colors.white30 : Colors.white, size: 18),
                  const SizedBox(width: 6),
                  Text(
                    label,
                    style: TextStyle(
                      color: onTap == null ? Colors.white30 : Colors.white,
                      fontSize: 11.5,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      );
}
'''
w(path, text)

# Native Android editor: add the 9:16 crop mode used by the new UI.
path = 'flutter/android/app/src/main/kotlin/online/taleempk/studyhub/MainActivity.kt'
text = r(path)
text = once(
    text,
    '            "landscape" -> 16.0 / 9.0\n            else -> null\n',
    '            "landscape" -> 16.0 / 9.0\n            "portrait_story" -> 9.0 / 16.0\n            else -> null\n',
    'native story crop ratio',
)
w(path, text)

# Release version.
path = 'flutter/pubspec.yaml'
pubspec = r(path)
pubspec = re.sub(r'^version:\s*[^\n]+', 'version: 3.5.0+350', pubspec, count=1, flags=re.M)
w(path, pubspec)

# Deep generated-source regression assertions.
profile = r('flutter/lib/screens/profile_screen.dart')
chat = r('flutter/lib/screens/chat_screen.dart')
native = r('flutter/android/app/src/main/kotlin/online/taleempk/studyhub/MainActivity.kt')
assert 'maximumSize: const Size(double.infinity, 44)' in profile
assert 'Privacy & security' in profile and 'surfaceContainerHighest' in profile
assert "'story': '9:16'" in chat
assert "label: 'Highlight'" in chat and "label: 'Hide'" in chat and "label: 'Pen'" in chat
assert 'RenderRepaintBoundary' in chat and '_PhotoMarkupPainter' in chat
assert '.take(20)' in chat
assert 'portrait_story' in native
assert 'recordingPaused = true;' in chat and 'await recorder.resume();' in chat
assert 'Future<void> _syncAfterSend() async' in chat
print('TaleemPK v3.5 profile/media polish applied successfully')
