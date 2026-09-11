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


def require_replace(text, old, new, label):
    if old not in text:
        raise RuntimeError(f'v3.3 target missing: {label}')
    return text.replace(old, new, 1)


# Native bridge: phone manufacturer/model/Android version.
path = 'flutter/lib/core/native_bridge.dart'
text = read(path)
marker = '  static Future<String?> editPhoto({\n'
text = require_replace(text, marker, """  static Future<String> deviceName() async {
    try {
      final value = await _media.invokeMethod<String>('deviceName');
      final clean = value?.trim() ?? '';
      if (clean.isNotEmpty) return clean;
    } catch (_) {}
    return 'Android device';
  }

""" + marker, 'native device bridge')
write(path, text)

# Android bridge implementation.
path = 'flutter/android/app/src/main/kotlin/online/taleempk/studyhub/MainActivity.kt'
text = read(path)
media = re.compile(r'(MethodChannel\(flutterEngine\.dartExecutor\.binaryMessenger,\s*mediaBridge\)\s*\.setMethodCallHandler\s*\{\s*call,\s*result\s*->\s*)', re.S)
m = media.search(text)
if not m:
    raise RuntimeError('v3.3 target missing: Android media channel')
text = text[:m.end()] + """if (call.method == "deviceName") {
                    result.success(deviceName())
                    return@setMethodCallHandler
                }
                """ + text[m.end():]
marker = '    private fun editPhoto(\n'
text = require_replace(text, marker, """    private fun deviceName(): String {
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

""" + marker, 'Android device helper')
write(path, text)

# API client: actual device name on login/2FA and current-session refresh.
path = 'flutter/lib/core/api_client.dart'
text = read(path)
if "import 'native_bridge.dart';" not in text:
    text = require_replace(text, "import 'models.dart';\n", "import 'models.dart';\nimport 'native_bridge.dart';\n", 'native bridge import')
text = text.replace("'device': '${Platform.operatingSystem} Flutter app',", "'device': await NativeBridge.deviceName(),")
pattern = re.compile(r"  Future<List<Map<String, dynamic>>> mobileSessions\(\) async \{.*?\n  \}", re.S)
replacement = """  Future<List<Map<String, dynamic>>> mobileSessions() async {
    final data = await _request({
      'action': 'sessions',
      'device': await NativeBridge.deviceName(),
    });
    return _list(data['sessions']).map(_map).toList();
  }"""
text, count = pattern.subn(replacement, text, count=1)
if count != 1:
    raise RuntimeError('v3.3 target missing: mobileSessions')
if 'await NativeBridge.deviceName()' not in text:
    raise RuntimeError('v3.3 failed to add real device name')
write(path, text)

# Server: fix secure attachment POST id bug and refresh current session name.
path = 'backend/api/mobile.php'
text = read(path)
text = require_replace(text,
    "$id = max(0, (int) ($_GET['id'] ?? 0));",
    "$id = max(0, (int) ($_POST['id'] ?? $_GET['id'] ?? 0));",
    'attachment POST id')
session_marker = "if ($action === 'sessions') {"
text = require_replace(text, session_marker, """if ($action === 'sessions') {
    $device = mb_substr(trim((string)($_POST['device'] ?? '')), 0, 100);
    if ($device !== '') {
        q('UPDATE mobile_sessions SET device_name=? WHERE token_hash=?', [$device, hash('sha256', mobile_bearer())]);
    }""", 'sessions action')
write(path, text)
shutil.copy2(ROOT / path, ROOT / 'flutter/backend/api/mobile.php')

# Chat: lower background work, premium surfaces, thumbnail-tap editor, explicit
# editor decode feedback. Existing v3.2 encrypted-media changes remain intact.
path = 'flutter/lib/screens/chat_screen.dart'
text = read(path)
text = text.replace('Duration(milliseconds: immediate ? 80 : 950)', 'Duration(milliseconds: immediate ? 80 : 1150)')
text = text.replace('final fullSync = pollTicks % 4 == 0;', 'final fullSync = pollTicks % 8 == 0;')
text = text.replace("? const Color(0xFF06101A)\n        : const Color(0xFFF1F5F9)", "? const Color(0xFF07111F)\n        : const Color(0xFFF6F8FC)")
text = text.replace("? const Color(0xFF172033)\n                  : const Color(0xFFF4F6FA)", "? const Color(0xFF121D2E)\n                  : const Color(0xFFFFFFFF)")
thumb = re.compile(r"onTap:\s*\(\)\s*=>\s*setLocal\(\(\)\s*=>\s*selected\s*=\s*i\),")
thumb_repl = """onTap: () async {
                            setLocal(() => selected = i);
                            final edited = await _editPhoto(paths[i]);
                            if (edited != null && dialog.mounted) {
                              setLocal(() {
                                paths[i] = edited;
                                selected = i;
                              });
                            }
                          },"""
text, count = thumb.subn(thumb_repl, text, count=1)
if count != 1:
    raise RuntimeError('v3.3 target missing: photo thumbnail tap')
preview = """                                child: Image.file(
                                  File(sourcePath),
                                  fit: crop == 'original' ? BoxFit.contain : BoxFit.cover,
                                  filterQuality: FilterQuality.high,
                                  gaplessPlayback: true,
                                ),"""
preview2 = """                                child: Image.file(
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
                                ),"""
text = require_replace(text, preview, preview2, 'editor image preview')
write(path, text)

# Signed-in devices UI: stale historic generic sessions get a clean fallback;
# current session receives real phone model from native bridge/server refresh.
path = 'flutter/lib/screens/security_screen.dart'
text = read(path)
text = text.replace("'${session['device'] ?? 'Mobile device'}'", "_prettyDevice('${session['device'] ?? 'Mobile device'}')")
marker = '  bool _bool(dynamic value, bool fallback) {\n'
text = require_replace(text, marker, """  String _prettyDevice(String raw) {
    final value = raw.trim();
    if (value.isEmpty) return 'Android device';
    if (value.toLowerCase() == 'android flutter app') return 'Older Android session';
    return value;
  }

""" + marker, 'security device pretty label')
write(path, text)

# Release version.
path = 'flutter/pubspec.yaml'
text = read(path)
text = re.sub(r'^version:\s*[^\n]+', 'version: 3.3.0+330', text, count=1, flags=re.M)
write(path, text)

# Fail fast if critical regressions are absent from generated source.
assert "$_POST['id'] ?? $_GET['id']" in read('backend/api/mobile.php')
assert 'await NativeBridge.deviceName()' in read('flutter/lib/core/api_client.dart')
assert 'pollTicks % 8' in read('flutter/lib/screens/chat_screen.dart')
assert 'deviceName()' in read('flutter/android/app/src/main/kotlin/online/taleempk/studyhub/MainActivity.kt')
print('TaleemPK v3.3 runtime hotfix applied')
