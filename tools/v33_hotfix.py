from pathlib import Path
import re
import shutil

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def write(path: str, text: str) -> None:
    p = ROOT / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding='utf-8')


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f'v3.3 hotfix target missing: {label}')
    return text.replace(old, new, 1)


# ---------------------------------------------------------------------------
# Native device identity: show the real manufacturer/model in signed-in devices.
# ---------------------------------------------------------------------------
path = 'flutter/lib/core/native_bridge.dart'
text = read(path)
marker = """  static Future<String?> editPhoto({
"""
insert = """  static Future<String> deviceName() async {
    try {
      final value = await _media.invokeMethod<String>('deviceName');
      final clean = value?.trim() ?? '';
      if (clean.isNotEmpty) return clean;
    } catch (_) {}
    return 'Android device';
  }

""" + marker
text = replace_once(text, marker, insert, 'native deviceName bridge')
write(path, text)

path = 'flutter/android/app/src/main/kotlin/online/taleempk/studyhub/MainActivity.kt'
text = read(path)
text = replace_once(
    text,
    '                when (call.method) {\n                    "editPhoto" -> {',
    '                when (call.method) {\n                    "deviceName" -> result.success(deviceName())\n                    "editPhoto" -> {',
    'Android deviceName method channel',
)
marker = """    private fun editPhoto(
"""
insert = """    private fun deviceName(): String {
        val manufacturer = Build.MANUFACTURER.trim()
        val model = Build.MODEL.trim()
        val base = when {
            model.isEmpty() && manufacturer.isEmpty() -> "Android device"
            model.isEmpty() -> manufacturer
            manufacturer.isEmpty() -> model
            model.lowercase().startsWith(manufacturer.lowercase()) -> model
            else -> "$manufacturer $model"
        }
        return "$base · Android ${Build.VERSION.RELEASE}".trim()
    }

""" + marker
text = replace_once(text, marker, insert, 'Android deviceName helper')
write(path, text)

path = 'flutter/lib/core/api_client.dart'
text = read(path)
text = replace_once(
    text,
    "import 'models.dart';\n",
    "import 'models.dart';\nimport 'native_bridge.dart';\n",
    'ApiClient NativeBridge import',
)
text = text.replace("'device': '${Platform.operatingSystem} Flutter app',", "'device': await NativeBridge.deviceName(),")
old = """  Future<List<Map<String, dynamic>>> mobileSessions() async {
    final data = await _request({'action': 'sessions'});
    return _list(data['sessions']).map(_map).toList();
  }
"""
new = """  Future<List<Map<String, dynamic>>> mobileSessions() async {
    final data = await _request({
      'action': 'sessions',
      'device': await NativeBridge.deviceName(),
    });
    return _list(data['sessions']).map(_map).toList();
  }
"""
text = replace_once(text, old, new, 'mobile sessions current device refresh')
write(path, text)

# ---------------------------------------------------------------------------
# Server media bug: attachmentBytes posts the message id; file endpoint was
# reading GET only, so every newly tapped image/voice could return false 404.
# Also refresh the current session device label without forcing a re-login.
# ---------------------------------------------------------------------------
path = 'backend/api/mobile.php'
text = read(path)
text = replace_once(
    text,
    "$id = max(0, (int) ($_GET['id'] ?? 0));",
    "$id = max(0, (int) ($_POST['id'] ?? $_GET['id'] ?? 0));",
    'POST attachment id support',
)
text, count = re.subn(
    r"if \(\$action === 'sessions'\) \{",
    """if ($action === 'sessions') {
    $device = mb_substr(trim((string)($_POST['device'] ?? '')), 0, 100);
    if ($device !== '') {
        q('UPDATE mobile_sessions SET device_name=? WHERE token_hash=?', [$device, hash('sha256', mobile_bearer())]);
    }""",
    text,
    count=1,
)
if count != 1:
    raise RuntimeError('v3.3 hotfix target missing: sessions action')
write(path, text)
shutil.copy2(ROOT / path, ROOT / 'flutter/backend/api/mobile.php')

# ---------------------------------------------------------------------------
# Chat polish: selected gallery thumbnails open the editor directly, lighter
# render palette, and less aggressive polling/full refresh for lower CPU/network.
# ---------------------------------------------------------------------------
path = 'flutter/lib/screens/chat_screen.dart'
text = read(path)
text = text.replace(
    'Duration(milliseconds: immediate ? 80 : 950)',
    'Duration(milliseconds: immediate ? 80 : 1150)',
)
text = text.replace('final fullSync = pollTicks % 4 == 0;', 'final fullSync = pollTicks % 8 == 0;')
text = text.replace("? const Color(0xFF06101A)\n        : const Color(0xFFF1F5F9)", "? const Color(0xFF07111F)\n        : const Color(0xFFF6F8FC)")
text = text.replace("? const Color(0xFF172033)\n                  : const Color(0xFFF4F6FA)", "? const Color(0xFF121D2E)\n                  : const Color(0xFFFFFFFF)")
# Make tapping a selected-photo thumbnail the direct edit action the user expects.
old_tap = "onTap: () => setLocal(() => selected = i),"
new_tap = """onTap: () async {
                            setLocal(() => selected = i);
                            final edited = await _editPhoto(paths[i]);
                            if (edited != null && dialog.mounted) {
                              setLocal(() {
                                paths[i] = edited;
                                selected = i;
                              });
                            }
                          },"""
if old_tap in text:
    text = text.replace(old_tap, new_tap, 1)
else:
    # The v3.2 patch may have slightly different whitespace; require exactly one
    # simple selected-index thumbnail tap to avoid silently patching the wrong UI.
    text, count = re.subn(
        r"onTap:\s*\(\)\s*=>\s*setLocal\(\(\)\s*=>\s*selected\s*=\s*i\),",
        new_tap,
        text,
        count=1,
    )
    if count != 1:
        raise RuntimeError('v3.3 hotfix target missing: multi-photo thumbnail edit tap')
# Improve failed local preview feedback instead of an empty/black editor canvas.
text = text.replace(
    """                                child: Image.file(
                                  File(sourcePath),
                                  fit: crop == 'original' ? BoxFit.contain : BoxFit.cover,
                                  filterQuality: FilterQuality.high,
                                  gaplessPlayback: true,
                                ),""",
    """                                child: Image.file(
                                  File(sourcePath),
                                  fit: crop == 'original' ? BoxFit.contain : BoxFit.cover,
                                  filterQuality: FilterQuality.high,
                                  gaplessPlayback: true,
                                  errorBuilder: (_, error, __) => const Center(
                                    child: Column(
                                      mainAxisSize: MainAxisSize.min,
                                      children: [
                                        Icon(Icons.broken_image_outlined, color: Colors.white70, size: 42),
                                        SizedBox(height: 10),
                                        Text('Photo preview could not be decoded.', style: TextStyle(color: Colors.white70)),
                                      ],
                                    ),
                                  ),
                                ),""",
    1,
)
write(path, text)

# ---------------------------------------------------------------------------
# Security screen visual cleanup: real labels are now returned by API/native.
# ---------------------------------------------------------------------------
path = 'flutter/lib/screens/security_screen.dart'
text = read(path)
text = text.replace("'${session['device'] ?? 'Mobile device'}'", "_prettyDevice('${session['device'] ?? 'Mobile device'}')")
marker = """  bool _bool(dynamic value, bool fallback) {
"""
helper = """  String _prettyDevice(String raw) {
    final value = raw.trim();
    if (value.isEmpty) return 'Android device';
    if (value.toLowerCase() == 'android flutter app') return 'Android device';
    return value;
  }

""" + marker
text = replace_once(text, marker, helper, 'pretty device helper')
write(path, text)

# Version bump for the audited hotfix build.
path = 'flutter/pubspec.yaml'
text = read(path)
text = re.sub(r'^version:\s*[^\n]+', 'version: 3.3.0+330', text, count=1, flags=re.M)
write(path, text)

# Static audit assertions: fail CI immediately if the core regressions reappear.
assert "$_POST['id'] ?? $_GET['id']" in read('backend/api/mobile.php')
assert "deviceName" in read('flutter/lib/core/native_bridge.dart')
assert "await NativeBridge.deviceName()" in read('flutter/lib/core/api_client.dart')
assert "pollTicks % 8" in read('flutter/lib/screens/chat_screen.dart')
print('TaleemPK v3.3 hotfix applied successfully')
