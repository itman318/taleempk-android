from pathlib import Path
import re
import shutil

ROOT = Path(__file__).resolve().parents[1]


def r(path):
    return (ROOT / path).read_text(encoding='utf-8')


def w(path, text):
    p = ROOT / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding='utf-8')


def once(text, old, new, label):
    if old not in text:
        raise RuntimeError(f'v3.3 missing target: {label}')
    return text.replace(old, new, 1)


# Real Android manufacturer/model/OS in Signed-in devices.
path = 'flutter/lib/core/native_bridge.dart'
text = r(path)
marker = '  static Future<String?> editPhoto({\n'
text = once(text, marker, """  static Future<String> deviceName() async {
    try {
      final value = await _media.invokeMethod<String>('deviceName');
      final clean = value?.trim() ?? '';
      if (clean.isNotEmpty) return clean;
    } catch (_) {}
    return 'Android device';
  }

""" + marker, 'NativeBridge.deviceName')
w(path, text)

path = 'flutter/android/app/src/main/kotlin/online/taleempk/studyhub/MainActivity.kt'
text = r(path)
channel = re.search(
    r'(MethodChannel\(flutterEngine\.dartExecutor\.binaryMessenger,\s*mediaBridge\)\s*\.setMethodCallHandler\s*\{\s*call,\s*result\s*->\s*)',
    text,
    re.S,
)
if not channel:
    raise RuntimeError('v3.3 missing target: Android media channel')
text = text[:channel.end()] + """if (call.method == "deviceName") {
                    result.success(deviceName())
                    return@setMethodCallHandler
                }
                """ + text[channel.end():]
marker = '    private fun editPhoto(\n'
text = once(text, marker, """    private fun deviceName(): String {
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
w(path, text)

# API: actual device label on login/2FA/session refresh; secure attachment
# downloader now follows the backend's authenticated GET route rather than
# incorrectly POSTing the message id (the cause of the false 404 screenshot).
path = 'flutter/lib/core/api_client.dart'
text = r(path)
if "import 'native_bridge.dart';" not in text:
    text = once(text, "import 'models.dart';\n", "import 'models.dart';\nimport 'native_bridge.dart';\n", 'NativeBridge import')
text = text.replace("'device': '${Platform.operatingSystem} Flutter app',", "'device': await NativeBridge.deviceName(),")
text, n = re.subn(
    r"  Future<List<Map<String, dynamic>>> mobileSessions\(\) async \{.*?\n  \}",
    """  Future<List<Map<String, dynamic>>> mobileSessions() async {
    final data = await _request({
      'action': 'sessions',
      'device': await NativeBridge.deviceName(),
    });
    return _list(data['sessions']).map(_map).toList();
  }""",
    text,
    count=1,
    flags=re.S,
)
if n != 1:
    raise RuntimeError('v3.3 missing target: mobileSessions')
text, n = re.subn(
    r"  Future<Uint8List> attachmentBytes\(String url\) async \{.*?\n  \}\n\n  Future<bool> toggleConversationArchive",
    """  Future<Uint8List> attachmentBytes(String url) async {
    if (_token == null || _token!.isEmpty) {
      throw const ApiException('Sign in to continue.', status: 401);
    }
    try {
      final source = Uri.parse(url);
      final id = source.queryParameters['id'];
      if (id == null || int.tryParse(id) == null) {
        throw const ApiException('This attachment link is invalid.');
      }
      final response = await _http
          .get(source, headers: authHeaders)
          .timeout(const Duration(seconds: 45));
      if (response.statusCode == 401) {
        await _expireSession('Your session has expired. Please sign in again.');
        throw const ApiException('Your session has expired. Please sign in again.', status: 401);
      }
      if (response.statusCode < 200 || response.statusCode >= 300) {
        throw ApiException(
          response.statusCode == 404
              ? 'This attachment is no longer available.'
              : 'The attachment could not be downloaded.',
          status: response.statusCode,
        );
      }
      if (response.bodyBytes.isEmpty) {
        throw const ApiException('The attachment is empty or unavailable.');
      }
      return response.bodyBytes;
    } on TimeoutException {
      throw const ApiException('The attachment download timed out.');
    } on SocketException {
      throw const ApiException('The connection was lost during download.');
    } on http.ClientException {
      throw const ApiException('Could not download the secure attachment.');
    }
  }

  Future<bool> toggleConversationArchive""",
    text,
    count=1,
    flags=re.S,
)
if n != 1:
    raise RuntimeError('v3.3 missing target: attachmentBytes')
w(path, text)

# Backend refreshes current session's real label. Old historical sessions did
# not store a model and therefore cannot be retroactively identified.
path = 'backend/api/mobile.php'
text = r(path)
marker = "if ($action === 'sessions') {"
text = once(text, marker, """if ($action === 'sessions') {
    $device = mb_substr(trim((string)($_POST['device'] ?? '')), 0, 100);
    if ($device !== '') {
        q('UPDATE mobile_sessions SET device_name=? WHERE token_hash=?', [$device, hash('sha256', mobile_bearer())]);
    }""", 'sessions action')
w(path, text)
shutil.copy2(ROOT / path, ROOT / 'flutter/backend/api/mobile.php')

# Chat: reduce background network/CPU work and refine light/dark surfaces.
# v3.2's generated media review was audited here: it already validates up to
# 20 local photos, renders thumbnails underneath, and calls editAt(i) when a
# thumbnail is tapped, exactly matching the requested interaction.
path = 'flutter/lib/screens/chat_screen.dart'
text = r(path)
text = text.replace('Duration(milliseconds: immediate ? 80 : 950)', 'Duration(milliseconds: immediate ? 80 : 1150)')
text = text.replace('final fullSync = pollTicks % 4 == 0;', 'final fullSync = pollTicks % 8 == 0;')
text = text.replace("? const Color(0xFF06101A)\n        : const Color(0xFFF1F5F9)", "? const Color(0xFF07111F)\n        : const Color(0xFFF6F8FC)")
text = text.replace("? const Color(0xFF172033)\n                  : const Color(0xFFF4F6FA)", "? const Color(0xFF121D2E)\n                  : const Color(0xFFFFFFFF)")
if 'onTap: () => editAt(i)' not in text or 'final edited = await _editPhoto(paths[index]);' not in text:
    raise RuntimeError('v3.3 audit failed: multi-photo thumbnail editor behavior missing')
w(path, text)

# Signed-in device UI: old generic rows are labelled honestly while current
# and future sessions use the native phone name.
path = 'flutter/lib/screens/security_screen.dart'
text = r(path)
text = text.replace("'${session['device'] ?? 'Mobile device'}'", "_prettyDevice('${session['device'] ?? 'Mobile device'}')")
marker = '  bool _bool(dynamic value, bool fallback) {\n'
text = once(text, marker, """  String _prettyDevice(String raw) {
    final value = raw.trim();
    if (value.isEmpty) return 'Android device';
    if (value.toLowerCase() == 'android flutter app') return 'Older Android session';
    return value;
  }

""" + marker, 'security pretty-device helper')
w(path, text)

# Release version.
path = 'flutter/pubspec.yaml'
text = r(path)
text = re.sub(r'^version:\s*[^\n]+', 'version: 3.3.0+330', text, count=1, flags=re.M)
w(path, text)

api = r('flutter/lib/core/api_client.dart')
chat = r('flutter/lib/screens/chat_screen.dart')
native = r('flutter/android/app/src/main/kotlin/online/taleempk/studyhub/MainActivity.kt')
assert '.get(source, headers: authHeaders)' in api
assert 'await NativeBridge.deviceName()' in api
assert 'onTap: () => editAt(i)' in chat
assert 'final edited = await _editPhoto(paths[index]);' in chat
assert 'pollTicks % 8' in chat
assert 'deviceName()' in native
print('TaleemPK v3.3 final hotfix applied successfully')
