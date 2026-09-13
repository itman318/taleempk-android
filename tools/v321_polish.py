from pathlib import Path
import re
import shutil

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return (ROOT / path).read_text(encoding='utf-8')


def write(path, text):
    p = ROOT / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding='utf-8')


def replace_once(text, old, new, label):
    if old not in text:
        raise RuntimeError(f'v3.2.1 polish target missing: {label}')
    return text.replace(old, new, 1)


def sub_once(text, pattern, replacement, label):
    out, count = re.subn(pattern, lambda _m: replacement, text, count=1, flags=re.S)
    if count != 1:
        raise RuntimeError(f'v3.2.1 polish target missing: {label}')
    return out


# ---------------------------------------------------------------------------
# Native device label, secure attachment GET + bounded memory cache.
# ---------------------------------------------------------------------------
path = 'flutter/lib/core/native_bridge.dart'
text = read(path)
marker = """  static Future<String?> editPhoto({
"""
device_method = """  static Future<String> deviceLabel() async {
    try {
      final value = await _media.invokeMethod<String>('deviceLabel');
      final label = value?.trim() ?? '';
      if (label.isNotEmpty) return label;
    } catch (_) {}
    return 'Android device';
  }

""" + marker
text = replace_once(text, marker, device_method, 'native device label')
write(path, text)

path = 'flutter/lib/core/api_client.dart'
text = read(path)
if "import 'native_bridge.dart';" not in text:
    text = replace_once(text, "import 'models.dart';\n", "import 'models.dart';\nimport 'native_bridge.dart';\n", 'native bridge import')
text = text.replace("'device': '${Platform.operatingSystem} Flutter app',", "'device': await NativeBridge.deviceLabel(),")
if text.count("'device': await NativeBridge.deviceLabel(),") < 2:
    raise RuntimeError('v3.2.1 polish target missing: login device labels')
text = replace_once(
    text,
    """  Future<List<Map<String, dynamic>>> mobileSessions() async {
    final data = await _request({'action': 'sessions'});
    return _list(data['sessions']).map(_map).toList();
  }
""",
    """  Future<List<Map<String, dynamic>>> mobileSessions() async {
    final data = await _request({
      'action': 'sessions',
      'device': await NativeBridge.deviceLabel(),
    });
    return _list(data['sessions']).map(_map).toList();
  }
""",
    'mobile sessions device refresh',
)
text = replace_once(
    text,
    """  static const _legacyTokenKey = 'studyhub_mobile_token';
  final http.Client _http;
""",
    """  static const _legacyTokenKey = 'studyhub_mobile_token';
  static final Map<String, Uint8List> _attachmentCache = <String, Uint8List>{};
  static int _attachmentCacheBytes = 0;
  static const int _attachmentCacheLimit = 24 * 1024 * 1024;
  final http.Client _http;
""",
    'attachment cache fields',
)
text = replace_once(
    text,
    """  Future<void> clearToken() async {
    _token = null;
    await _storage.delete(key: _tokenKey);
    await _storage.delete(key: _legacyTokenKey);
  }
""",
    """  Future<void> clearToken() async {
    _token = null;
    _attachmentCache.clear();
    _attachmentCacheBytes = 0;
    await _storage.delete(key: _tokenKey);
    await _storage.delete(key: _legacyTokenKey);
  }
""",
    'clear attachment cache',
)
text = sub_once(
    text,
    r"  Future<Uint8List> attachmentBytes\(String url\) async \{.*?\n  \}\n\n  Future<bool> toggleConversationArchive",
    """  Future<Uint8List> attachmentBytes(String url) async {
    if (_token == null || _token!.isEmpty) {
      throw const ApiException('Sign in to continue.', status: 401);
    }
    try {
      final source = Uri.parse(url);
      final apiUri = Uri.parse(endpoint);
      final id = source.queryParameters['id'];
      if (id == null || int.tryParse(id) == null || source.host != apiUri.host) {
        throw const ApiException('This attachment link is invalid.');
      }
      final cached = _attachmentCache.remove(id);
      if (cached != null) {
        _attachmentCache[id] = cached;
        return cached;
      }
      final response = await _http
          .get(source, headers: authHeaders)
          .timeout(const Duration(seconds: 45));
      if (response.statusCode == 401) {
        await _expireSession('Your session has expired. Please sign in again.');
        throw const ApiException(
          'Your session has expired. Please sign in again.',
          status: 401,
        );
      }
      if (response.statusCode < 200 || response.statusCode >= 300) {
        throw ApiException(
          response.statusCode == 404
              ? 'This attachment is no longer available.'
              : 'The attachment could not be downloaded.',
          status: response.statusCode,
        );
      }
      final bytes = response.bodyBytes;
      if (bytes.isEmpty) throw const ApiException('The attachment is empty.');
      if (bytes.length <= 4 * 1024 * 1024) {
        while (_attachmentCacheBytes + bytes.length > _attachmentCacheLimit &&
            _attachmentCache.isNotEmpty) {
          final oldest = _attachmentCache.keys.first;
          final removed = _attachmentCache.remove(oldest);
          if (removed != null) _attachmentCacheBytes -= removed.length;
        }
        _attachmentCache[id] = bytes;
        _attachmentCacheBytes += bytes.length;
      }
      return bytes;
    } on TimeoutException {
      throw const ApiException('The attachment download timed out.');
    } on SocketException {
      throw const ApiException('The connection was lost during download.');
    } on http.ClientException {
      throw const ApiException('Could not download the secure attachment.');
    }
  }

  Future<bool> toggleConversationArchive""",
    'secure attachment GET',
)
write(path, text)


# ---------------------------------------------------------------------------
# Android model/manufacturer label without adding a dependency.
# ---------------------------------------------------------------------------
path = 'flutter/android/app/src/main/kotlin/online/taleempk/studyhub/MainActivity.kt'
text = read(path)
text = replace_once(
    text,
    """                when (call.method) {
                    "editPhoto" -> {
""",
    """                when (call.method) {
                    "deviceLabel" -> result.success(deviceLabel())
                    "editPhoto" -> {
""",
    'Android deviceLabel channel',
)
marker = """    private fun editPhoto(
"""
helper = """    private fun deviceLabel(): String {
        val makerRaw = Build.MANUFACTURER.trim()
        val maker = makerRaw.replaceFirstChar { if (it.isLowerCase()) it.titlecase() else it.toString() }
        val model = Build.MODEL.trim()
        val base = when {
            model.isEmpty() -> if (maker.isEmpty()) "Android device" else maker
            maker.isEmpty() -> model
            model.lowercase().startsWith(makerRaw.lowercase()) -> model
            else -> "$maker $model"
        }
        val release = Build.VERSION.RELEASE?.trim().orEmpty()
        return if (release.isEmpty()) base else "$base · Android $release"
    }

""" + marker
text = replace_once(text, marker, helper, 'Android deviceLabel helper')
write(path, text)


# ---------------------------------------------------------------------------
# Server: refresh current session label and accept attachment id on GET/POST.
# ---------------------------------------------------------------------------
path = 'backend/api/mobile.php'
text = read(path)
text = sub_once(
    text,
    r"if \(\$action === 'sessions'\) \{.*?mobile_out\(\['sessions' => \$sessions\]\);\n\}",
    """if ($action === 'sessions') {
    $currentHash = hash('sha256', mobile_bearer());
    $reportedDevice = trim((string) ($_POST['device'] ?? ''));
    if ($reportedDevice !== '') {
        $reportedDevice = preg_replace('/[\\x00-\\x1F\\x7F]+/u', ' ', $reportedDevice) ?: '';
        $reportedDevice = mb_substr(trim((string) preg_replace('/\\s+/u', ' ', $reportedDevice)), 0, 100);
        if ($reportedDevice !== '') {
            q('UPDATE mobile_sessions SET device_name=? WHERE token_hash=? AND user_id=?', [$reportedDevice,$currentHash,$uid]);
        }
    }
    $rows = fetch_all('SELECT token_hash,device_name,created_at,last_seen,expires_at FROM mobile_sessions WHERE user_id=? AND expires_at>NOW() ORDER BY created_at DESC LIMIT 20', [$uid]);
    $sessions = array_map(static function(array $row) use ($currentHash): array {
        $device = trim((string) ($row['device_name'] ?? ''));
        if ($device === '' || preg_match('/^android\\s+flutter\\s+app$/i', $device)) $device = 'Android device';
        return [
            'session_id' => (string) $row['token_hash'],
            'device' => $device,
            'created_at' => (string) ($row['created_at'] ?? ''),
            'last_seen' => (string) ($row['last_seen'] ?? $row['created_at'] ?? ''),
            'expires_at' => (string) ($row['expires_at'] ?? ''),
            'current' => hash_equals($currentHash, (string) $row['token_hash']),
        ];
    }, $rows);
    mobile_out(['sessions' => $sessions]);
}""",
    'server session labels',
)
text = replace_once(
    text,
    "$id = max(0, (int) ($_GET['id'] ?? 0));",
    "$id = max(0, (int) ($_GET['id'] ?? $_POST['id'] ?? 0));",
    'server attachment id fallback',
)
write(path, text)
shutil.copy2(ROOT / path, ROOT / 'flutter/backend/api/mobile.php')


# ---------------------------------------------------------------------------
# Chat media UX: reliable byte preview, bottom thumbnail tray, tap-to-edit.
# ---------------------------------------------------------------------------
path = 'flutter/lib/screens/chat_screen.dart'
text = read(path)
text = sub_once(
    text,
    r"Uint8List _processOutgoingPhoto\(Map<String, dynamic> args\) \{.*?\n\}\n\nclass ChatScreen",
    """Uint8List _processOutgoingPhoto(Map<String, dynamic> args) {
  final bytes = args['bytes'] as Uint8List;
  final turns = (args['turns'] as int?) ?? 0;
  final crop = '${args['crop'] ?? 'original'}';
  final flip = args['flip'] == true;
  final quality = (args['quality'] as int?) ?? 90;
  final maxDimension = (args['maxDimension'] as int?) ?? 1800;
  var image = img.decodeImage(bytes);
  if (image == null) {
    throw StateError('This image format cannot be edited on this device.');
  }
  image = img.bakeOrientation(image);
  final normalizedTurns = ((turns % 4) + 4) % 4;
  if (normalizedTurns != 0) image = img.copyRotate(image, angle: 90 * normalizedTurns);
  if (flip) image = img.flipHorizontal(image);
  double? targetRatio;
  if (crop == 'square') targetRatio = 1;
  if (crop == 'portrait') targetRatio = 4 / 5;
  if (crop == 'landscape') targetRatio = 16 / 9;
  if (targetRatio != null) {
    final current = image.width / image.height;
    if (current > targetRatio) {
      final width = (image.height * targetRatio).round().clamp(1, image.width).toInt();
      image = img.copyCrop(image, x: (image.width - width) ~/ 2, y: 0, width: width, height: image.height);
    } else if (current < targetRatio) {
      final height = (image.width / targetRatio).round().clamp(1, image.height).toInt();
      image = img.copyCrop(image, x: 0, y: (image.height - height) ~/ 2, width: image.width, height: height);
    }
  }
  final longest = image.width > image.height ? image.width : image.height;
  if (longest > maxDimension) {
    if (image.width >= image.height) {
      image = img.copyResize(image, width: maxDimension, interpolation: img.Interpolation.cubic);
    } else {
      image = img.copyResize(image, height: maxDimension, interpolation: img.Interpolation.cubic);
    }
  }
  return Uint8List.fromList(img.encodeJpg(image, quality: quality.clamp(65, 98)));
}

class ChatScreen""",
    'photo processor',
)

review_method = r'''  Future<void> _reviewImages(List<String> initialPaths) async {
    if (initialPaths.isEmpty || !mounted) return;
    final paths = <String>[];
    for (final value in initialPaths.take(20)) {
      final file = File(value);
      if (await file.exists() && await file.length() > 256) paths.add(value);
    }
    if (paths.isEmpty) {
      if (mounted) showMessage(context, 'Those photos are no longer available.');
      return;
    }
    var selected = 0;
    final send = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      backgroundColor: const Color(0xFF07131C),
      builder: (sheet) => StatefulBuilder(
        builder: (context, setLocal) {
          Future<void> editAt(int index) async {
            if (index < 0 || index >= paths.length) return;
            setLocal(() => selected = index);
            final edited = await _editPhoto(paths[index]);
            if (edited != null && context.mounted) {
              setLocal(() {
                paths[index] = edited;
                selected = index.clamp(0, paths.length - 1);
              });
            }
          }

          return SizedBox(
            height: MediaQuery.sizeOf(context).height * .94,
            child: Column(
              children: [
                Padding(
                  padding: const EdgeInsets.fromLTRB(10, 8, 8, 6),
                  child: Row(
                    children: [
                      IconButton(
                        onPressed: () => Navigator.pop(sheet, false),
                        icon: const Icon(Icons.close_rounded, color: Colors.white),
                      ),
                      Expanded(
                        child: Text(
                          '${paths.length} photo${paths.length == 1 ? '' : 's'} selected',
                          style: const TextStyle(color: Colors.white, fontSize: 17, fontWeight: FontWeight.w800),
                        ),
                      ),
                      IconButton(
                        tooltip: 'Edit selected photo',
                        onPressed: paths.isEmpty ? null : () => editAt(selected),
                        icon: const Icon(Icons.tune_rounded, color: Colors.white),
                      ),
                    ],
                  ),
                ),
                Expanded(
                  child: GestureDetector(
                    onTap: () => editAt(selected),
                    child: Container(
                      width: double.infinity,
                      margin: const EdgeInsets.symmetric(horizontal: 12),
                      decoration: BoxDecoration(color: Colors.black, borderRadius: BorderRadius.circular(24)),
                      clipBehavior: Clip.antiAlias,
                      child: InteractiveViewer(
                        minScale: .8,
                        maxScale: 4,
                        child: Center(
                          child: Image.file(
                            File(paths[selected]),
                            key: ValueKey(paths[selected]),
                            fit: BoxFit.contain,
                            gaplessPlayback: true,
                            errorBuilder: (_, _, _) => const Center(
                              child: Column(mainAxisSize: MainAxisSize.min, children: [
                                Icon(Icons.broken_image_outlined, color: Colors.white54, size: 48),
                                SizedBox(height: 8),
                                Text('Preview unavailable', style: TextStyle(color: Colors.white70)),
                              ]),
                            ),
                          ),
                        ),
                      ),
                    ),
                  ),
                ),
                Container(
                  padding: const EdgeInsets.fromLTRB(12, 12, 12, 8),
                  child: SizedBox(
                    height: 82,
                    child: ListView.separated(
                      scrollDirection: Axis.horizontal,
                      itemCount: paths.length,
                      separatorBuilder: (_, _) => const SizedBox(width: 8),
                      itemBuilder: (_, i) => InkWell(
                        onTap: () => editAt(i),
                        borderRadius: BorderRadius.circular(15),
                        child: Container(
                          width: 72,
                          decoration: BoxDecoration(
                            borderRadius: BorderRadius.circular(15),
                            border: Border.all(
                              color: i == selected ? const Color(0xFF4DD0E1) : const Color(0x445E6A80),
                              width: i == selected ? 2.5 : 1,
                            ),
                          ),
                          clipBehavior: Clip.antiAlias,
                          child: Image.file(
                            File(paths[i]),
                            fit: BoxFit.cover,
                            errorBuilder: (_, _, _) => const ColoredBox(
                              color: Color(0xFF132333),
                              child: Icon(Icons.broken_image_outlined, color: Colors.white54),
                            ),
                          ),
                        ),
                      ),
                    ),
                  ),
                ),
                Padding(
                  padding: const EdgeInsets.fromLTRB(12, 4, 12, 14),
                  child: Row(
                    children: [
                      OutlinedButton.icon(
                        onPressed: () async {
                          final more = await ImagePicker().pickMultiImage(imageQuality: 92, maxWidth: 2600, maxHeight: 2600);
                          if (more.isNotEmpty && context.mounted) {
                            setLocal(() {
                              paths.addAll(more.map((e) => e.path).take(20 - paths.length));
                              selected = paths.length - 1;
                            });
                          }
                        },
                        icon: const Icon(Icons.add_photo_alternate_outlined),
                        label: const Text('Add'),
                      ),
                      const SizedBox(width: 8),
                      IconButton.filledTonal(
                        tooltip: 'Remove selected',
                        onPressed: paths.length <= 1
                            ? null
                            : () => setLocal(() {
                                  paths.removeAt(selected);
                                  selected = selected.clamp(0, paths.length - 1);
                                }),
                        icon: const Icon(Icons.delete_outline_rounded),
                      ),
                      const Spacer(),
                      FilledButton.icon(
                        onPressed: () => Navigator.pop(sheet, true),
                        icon: const Icon(Icons.send_rounded),
                        label: Text('Send ${paths.length}'),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          );
        },
      ),
    );
    if (send == true && paths.isNotEmpty && mounted) await _uploadManyImages(paths);
  }

  Future<String?> _editPhoto'''
text = sub_once(
    text,
    r"  Future<void> _reviewImages\(List<String> initialPaths\) async \{.*?\n  Future<String\?> _editPhoto",
    review_method,
    'multi-photo review tray',
)

editor_method = r'''  Future<String?> _editPhoto(String sourcePath) async {
    if (!mounted) return null;
    final source = File(sourcePath);
    if (!await source.exists() || await source.length() < 256) {
      showMessage(context, 'That photo is no longer available.');
      return null;
    }
    final previewBytes = await source.readAsBytes();
    final decoded = img.decodeImage(previewBytes);
    final originalRatio = decoded == null || decoded.height == 0 ? 4 / 3 : decoded.width / decoded.height;
    var turns = 0;
    var flip = false;
    var crop = 'original';
    var brightness = 0.0;
    var contrast = 1.0;
    var hd = false;

    double ratioFor(String mode) {
      var ratio = mode == 'square'
          ? 1.0
          : mode == 'portrait'
              ? 4 / 5
              : mode == 'landscape'
                  ? 16 / 9
                  : originalRatio;
      if (turns.isOdd) ratio = 1 / ratio;
      return ratio.clamp(.55, 1.9);
    }

    ColorFilter previewFilter() {
      final shift = brightness * 255;
      final translate = (-0.5 * contrast + 0.5) * 255 + shift;
      return ColorFilter.matrix(<double>[
        contrast, 0, 0, 0, translate,
        0, contrast, 0, 0, translate,
        0, 0, contrast, 0, translate,
        0, 0, 0, 1, 0,
      ]);
    }

    final apply = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      backgroundColor: const Color(0xFF07131C),
      builder: (sheet) => StatefulBuilder(
        builder: (context, setLocal) => SizedBox(
          height: MediaQuery.sizeOf(context).height * .96,
          child: Column(
            children: [
              Padding(
                padding: const EdgeInsets.fromLTRB(8, 6, 8, 4),
                child: Row(children: [
                  IconButton(onPressed: () => Navigator.pop(sheet, false), icon: const Icon(Icons.close_rounded, color: Colors.white)),
                  const Expanded(child: Text('Edit photo', style: TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.w900))),
                  TextButton(
                    onPressed: () => setLocal(() {
                      turns = 0; flip = false; crop = 'original'; brightness = 0; contrast = 1; hd = false;
                    }),
                    child: const Text('Reset'),
                  ),
                ]),
              ),
              Expanded(
                child: Padding(
                  padding: const EdgeInsets.all(12),
                  child: Center(
                    child: AnimatedContainer(
                      duration: const Duration(milliseconds: 180),
                      constraints: const BoxConstraints(maxWidth: 560, maxHeight: 570),
                      child: AspectRatio(
                        aspectRatio: ratioFor(crop),
                        child: ClipRRect(
                          borderRadius: BorderRadius.circular(22),
                          child: ColoredBox(
                            color: Colors.black,
                            child: ColorFiltered(
                              colorFilter: previewFilter(),
                              child: Transform.flip(
                                flipX: flip,
                                child: RotatedBox(
                                  quarterTurns: turns,
                                  child: Image.memory(
                                    previewBytes,
                                    fit: crop == 'original' ? BoxFit.contain : BoxFit.cover,
                                    filterQuality: FilterQuality.medium,
                                    gaplessPlayback: true,
                                    errorBuilder: (_, _, _) => const Center(
                                      child: Text('This photo cannot be previewed.', style: TextStyle(color: Colors.white70)),
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
                ),
              ),
              Container(
                padding: const EdgeInsets.fromLTRB(14, 12, 14, 14),
                decoration: const BoxDecoration(
                  color: Color(0xFF0D1B28),
                  borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
                ),
                child: Column(children: [
                  SingleChildScrollView(
                    scrollDirection: Axis.horizontal,
                    child: Row(children: [
                      for (final entry in const {'original':'Original','square':'1:1','portrait':'4:5','landscape':'16:9'}.entries)
                        Padding(
                          padding: const EdgeInsets.only(right: 7),
                          child: ChoiceChip(
                            selected: crop == entry.key,
                            showCheckmark: false,
                            label: Text(entry.value),
                            onSelected: (_) => setLocal(() => crop = entry.key),
                          ),
                        ),
                    ]),
                  ),
                  Row(children: [
                    IconButton.filledTonal(onPressed: () => setLocal(() => turns = (turns + 3) % 4), icon: const Icon(Icons.rotate_left_rounded)),
                    const SizedBox(width: 6),
                    IconButton.filledTonal(onPressed: () => setLocal(() => turns = (turns + 1) % 4), icon: const Icon(Icons.rotate_right_rounded)),
                    const SizedBox(width: 6),
                    IconButton.filledTonal(onPressed: () => setLocal(() => flip = !flip), icon: const Icon(Icons.flip_rounded)),
                    const Spacer(),
                    FilterChip(
                      selected: hd,
                      onSelected: (value) => setLocal(() => hd = value),
                      avatar: const Icon(Icons.hd_rounded, size: 18),
                      label: Text(hd ? 'HD' : 'Standard'),
                    ),
                  ]),
                  Row(children: [
                    const SizedBox(width: 82, child: Text('Brightness', style: TextStyle(color: Colors.white70, fontSize: 12))),
                    Expanded(child: Slider(value: brightness, min: -.35, max: .35, divisions: 28, onChanged: (v) => setLocal(() => brightness = v))),
                  ]),
                  Row(children: [
                    const SizedBox(width: 82, child: Text('Contrast', style: TextStyle(color: Colors.white70, fontSize: 12))),
                    Expanded(child: Slider(value: contrast, min: .65, max: 1.45, divisions: 32, onChanged: (v) => setLocal(() => contrast = v))),
                  ]),
                  SizedBox(
                    width: double.infinity,
                    child: FilledButton.icon(
                      onPressed: () => Navigator.pop(sheet, true),
                      icon: const Icon(Icons.check_rounded),
                      label: const Text('Apply changes'),
                    ),
                  ),
                ]),
              ),
            ],
          ),
        ),
      ),
    );
    if (apply != true) return null;
    final quality = hd ? 96 : 89;
    final maxDimension = hd ? 3200 : 1800;
    try {
      final native = await NativeBridge.editPhoto(
        path: sourcePath,
        turns: turns,
        flip: flip,
        crop: crop,
        brightness: brightness,
        contrast: contrast,
        quality: quality,
        maxDimension: maxDimension,
      );
      if (native != null) {
        final file = File(native);
        if (await file.exists() && await file.length() > 256) {
          if (mounted) showMessage(context, 'Photo changes applied.');
          return native;
        }
      }
    } catch (_) {}
    try {
      final bytes = await compute(_processOutgoingPhoto, <String, dynamic>{
        'bytes': previewBytes,
        'turns': turns,
        'flip': flip,
        'crop': crop,
        'quality': quality,
        'maxDimension': maxDimension,
      });
      final dir = await getTemporaryDirectory();
      final output = File('${dir.path}/taleempk_edit_${DateTime.now().microsecondsSinceEpoch}.jpg');
      await output.writeAsBytes(bytes, flush: true);
      if (await output.length() < 256) throw StateError('empty output');
      if (mounted) showMessage(context, 'Photo changes applied.');
      return output.path;
    } catch (_) {
      if (mounted) showMessage(context, 'This photo format could not be edited. Try another image or take a new photo.');
      return null;
    }
  }

  Future<void> _uploadManyImages'''
text = sub_once(
    text,
    r"  Future<String\?> _editPhoto\(String sourcePath\) async \{.*?\n  Future<void> _uploadManyImages",
    editor_method,
    'reliable byte photo editor',
)

# Reduce expensive full synchronizations while retaining sub-second incremental chat.
text = text.replace('final fullSync = pollTicks % 4 == 0;', 'final fullSync = pollTicks % 8 == 0;')
old_pins = """        final pins = await api.pinnedMessages(widget.conversation.id);
        if (pins.toString() != pinnedMessages.toString()) {
          pinnedMessages = pins;
          changed = true;
        }
"""
new_pins = """        if (pollTicks % 24 == 0) {
          final pins = await api.pinnedMessages(widget.conversation.id);
          if (pins.toString() != pinnedMessages.toString()) {
            pinnedMessages = pins;
            changed = true;
          }
        }
"""
text = replace_once(text, old_pins, new_pins, 'slower pinned refresh')
text = text.replace("? const Color(0xFF06101A)\n        : const Color(0xFFF1F5F9)", "? const Color(0xFF07131C)\n        : const Color(0xFFF4F7FA)")
text = text.replace('colors: [Color(0xFF123B64), Color(0xFF285C8D)]', 'colors: [Color(0xFF0B4F6C), Color(0xFF176B87)]')
text = text.replace('const Color(0xFF0B665E)', 'const Color(0xFF0F766E)')
text = text.replace('const Color(0xFF173B63)', 'const Color(0xFF134E6F)')
write(path, text)


# Slightly calmer, higher-contrast surfaces.
path = 'flutter/lib/core/theme.dart'
text = read(path)
text = text.replace("static const bg = Color(0xFFF5F7FC);", "static const bg = Color(0xFFF4F7FB);")
text = text.replace("static const ink = Color(0xFF17213B);", "static const ink = Color(0xFF101828);")
write(path, text)


# Version + audit notes.
path = 'flutter/pubspec.yaml'
text = read(path)
text = re.sub(r'^version:\s*[^\n]+', 'version: 3.2.1+321', text, count=1, flags=re.M)
write(path, text)
write('flutter/V3.2.1.md', '''# TaleemPK Flutter v3.2.1\n\n- Fixed secure chat image/voice downloads by using the authenticated attachment URL directly.\n- Added a bounded in-memory media cache to reduce repeated image/audio downloads.\n- Signed-in devices now report the real Android manufacturer/model/version for the current device; historical generic sessions are labelled Android device.\n- Photo editor previews image bytes directly, adds reliable Standard/HD editing and retains native crop/rotate/flip/brightness/contrast.\n- Multi-photo review now keeps thumbnails at the bottom and tapping a thumbnail opens that photo in the editor.\n- Reduced expensive full chat/pin refresh frequency while retaining fast incremental message polling.\n- Refined chat/background colors and light-theme contrast.\n''')
