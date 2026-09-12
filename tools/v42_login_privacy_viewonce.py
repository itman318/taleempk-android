from pathlib import Path
import re
import shutil

ROOT = Path(__file__).resolve().parents[1]


def r(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def w(path: str, text: str) -> None:
    p = ROOT / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding='utf-8')


def function_bounds(text: str, signature: str):
    start = text.find(signature)
    if start < 0:
        raise RuntimeError(f'v4.2 missing function: {signature}')
    brace = text.find('{', start)
    if brace < 0:
        raise RuntimeError(f'v4.2 malformed function: {signature}')
    depth = 0
    quote = None
    escape = False
    for i in range(brace, len(text)):
        ch = text[i]
        if quote is not None:
            if escape:
                escape = False
            elif ch == '\\':
                escape = True
            elif ch == quote:
                quote = None
            continue
        if ch in ("'", '"'):
            quote = ch
            continue
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                return start, i + 1
    raise RuntimeError(f'v4.2 unterminated function: {signature}')


def replace_function(text: str, signature: str, replacement: str) -> str:
    s, e = function_bounds(text, signature)
    return text[:s] + replacement + text[e:]


# ---------------------------------------------------------------------------
# 1) Login compatibility: broken/slow Android keystores must not prevent a
# valid account from signing in. Secure storage stays primary; app-private
# SharedPreferences is only a compatibility fallback and is migrated back to
# secure storage whenever possible.
# ---------------------------------------------------------------------------
path = 'flutter/lib/core/api_client.dart'
text = r(path)
if "import 'package:shared_preferences/shared_preferences.dart';" not in text:
    text = text.replace(
        "import 'package:http/http.dart' as http;\n",
        "import 'package:http/http.dart' as http;\nimport 'package:shared_preferences/shared_preferences.dart';\n",
        1,
    )
if "static const _compatTokenKey" not in text:
    text = text.replace(
        "  static const _legacyTokenKey = 'studyhub_mobile_token';\n",
        "  static const _legacyTokenKey = 'studyhub_mobile_token';\n  static const _compatTokenKey = 'taleempk_mobile_token_compat';\n",
        1,
    )

restore = r'''  Future<bool> restoreSession() async {
    String? secureValue;
    try {
      secureValue = await _storage
          .read(key: _tokenKey)
          .timeout(const Duration(seconds: 3));
      if (secureValue == null || secureValue.isEmpty) {
        secureValue = await _storage
            .read(key: _legacyTokenKey)
            .timeout(const Duration(seconds: 3));
        if (secureValue != null && secureValue.isNotEmpty) {
          try {
            await _storage
                .write(key: _tokenKey, value: secureValue)
                .timeout(const Duration(seconds: 3));
            await _storage
                .delete(key: _legacyTokenKey)
                .timeout(const Duration(seconds: 2));
          } catch (_) {}
        }
      }
    } catch (_) {
      secureValue = null;
    }

    if (secureValue != null && secureValue.isNotEmpty) {
      _token = secureValue;
      try {
        final prefs = await SharedPreferences.getInstance()
            .timeout(const Duration(seconds: 3));
        await prefs.remove(_compatTokenKey);
      } catch (_) {}
      return true;
    }

    try {
      final prefs = await SharedPreferences.getInstance()
          .timeout(const Duration(seconds: 3));
      final fallback = prefs.getString(_compatTokenKey)?.trim() ?? '';
      if (fallback.isNotEmpty) {
        _token = fallback;
        try {
          await _storage
              .write(key: _tokenKey, value: fallback)
              .timeout(const Duration(seconds: 3));
          await prefs.remove(_compatTokenKey);
        } catch (_) {}
        return true;
      }
    } catch (_) {}

    _token = null;
    return false;
  }'''
text = replace_function(text, '  Future<bool> restoreSession() async {', restore)

save = r'''  Future<void> saveToken(String value) async {
    _token = value;
    var secureSaved = false;
    try {
      await _storage
          .write(key: _tokenKey, value: value)
          .timeout(const Duration(seconds: 4));
      secureSaved = true;
    } catch (_) {
      // Some vendor keystores fail despite a healthy app/network. Keep the
      // already-issued revocable session usable via an app-private fallback.
    }

    try {
      final prefs = await SharedPreferences.getInstance()
          .timeout(const Duration(seconds: 3));
      if (secureSaved) {
        await prefs.remove(_compatTokenKey);
      } else {
        await prefs.setString(_compatTokenKey, value);
      }
    } catch (_) {
      // Memory session still works for this app run even if persistence fails.
    }
  }'''
text = replace_function(text, '  Future<void> saveToken(String value) async {', save)

clear = r'''  Future<void> clearToken() async {
    _token = null;
    try {
      await _storage.delete(key: _tokenKey).timeout(const Duration(seconds: 2));
    } catch (_) {}
    try {
      await _storage.delete(key: _legacyTokenKey).timeout(const Duration(seconds: 2));
    } catch (_) {}
    try {
      final prefs = await SharedPreferences.getInstance()
          .timeout(const Duration(seconds: 2));
      await prefs.remove(_compatTokenKey);
    } catch (_) {}
  }'''
text = replace_function(text, '  Future<void> clearToken() async {', clear)

# Add a two-attempt authentication request. A fresh attempt helps on carrier
# proxies/older Android TLS stacks that occasionally drop the first POST.
login_sig = '  Future<AuthResult> login(String identifier, String password) async {'
login_pos = text.find(login_sig)
if login_pos < 0:
    raise RuntimeError('v4.2 login method missing')
helper = r'''  Future<Map<String, dynamic>> _authRequestWithRetry(
    Map<String, String> fields,
  ) async {
    ApiException? last;
    for (var attempt = 0; attempt < 2; attempt++) {
      try {
        return await _request(fields, authenticated: false).timeout(
          const Duration(seconds: 20),
          onTimeout: () => throw const ApiException(
            'Sign-in is taking too long. Check your connection and try again.',
          ),
        );
      } on ApiException catch (e) {
        last = e;
        final clientError = e.status >= 400 && e.status < 500;
        if (clientError || attempt == 1) rethrow;
      } catch (_) {
        last = const ApiException(
          'This phone could not complete the secure sign-in request. Please try again.',
        );
        if (attempt == 1) throw last;
      }
      await Future<void>.delayed(const Duration(milliseconds: 300));
    }
    throw last ?? const ApiException('Could not sign in. Please try again.');
  }

'''
if '_authRequestWithRetry(' not in text:
    text = text[:login_pos] + helper + text[login_pos:]

login = r'''  Future<AuthResult> login(String identifier, String password) async {
    final device = await NativeBridge.deviceName();
    final data = await _authRequestWithRetry({
      'action': 'login',
      'identifier': identifier.trim(),
      'password': password,
      'device': device,
      'client': 'TaleemPK Android app',
      'tz_offset': '${DateTime.now().timeZoneOffset.inMinutes}',
      'tz_name': DateTime.now().timeZoneName,
    });
    return _authResult(data);
  }'''
text = replace_function(text, login_sig, login)

verify = r'''  Future<AuthResult> verifyTwoFactor(String challenge, String code) async {
    final device = await NativeBridge.deviceName();
    final data = await _authRequestWithRetry({
      'action': 'verify_2fa',
      'challenge': challenge,
      'code': code.trim(),
      'device': device,
      'client': 'TaleemPK Android app',
      'tz_offset': '${DateTime.now().timeZoneOffset.inMinutes}',
      'tz_name': DateTime.now().timeZoneName,
    });
    return _authResult(data);
  }'''
text = replace_function(text, '  Future<AuthResult> verifyTwoFactor(String challenge, String code) async {', verify)

# Surface TLS/vendor transport failures as useful errors rather than the generic
# catch-all from AppState. This also makes field reports diagnosable.
rs, re_ = function_bounds(text, '  Future<Map<String, dynamic>> _request(')
request_chunk = text[rs:re_]
needle = """    } on http.ClientException {
      throw const ApiException('Could not connect securely to TaleemPK.');
    }
"""
replacement = """    } on HandshakeException {
      throw const ApiException(
        'This phone could not establish a secure connection to TaleemPK. Check date/time, network or VPN and try again.',
      );
    } on TlsException {
      throw const ApiException(
        'Secure connection failed on this phone. Try another network or update Android security components.',
      );
    } on http.ClientException {
      throw const ApiException('Could not connect securely to TaleemPK.');
    } on FormatException {
      throw const ApiException('The server response could not be read on this phone. Please try again.');
    } catch (_) {
      throw const ApiException(
        'The sign-in connection was interrupted on this phone. Please try again.',
      );
    }
"""
if needle not in request_chunk:
    raise RuntimeError('v4.2 request transport catch marker missing')
request_chunk = request_chunk.replace(needle, replacement, 1)
text = text[:rs] + request_chunk + text[re_:]
w(path, text)


# ---------------------------------------------------------------------------
# 2) Do not throw away a valid login merely because the first home/bootstrap
# refresh fails on a specific phone/network. Seed the signed-in shell from the
# login response and refresh full account data quietly in the background.
# ---------------------------------------------------------------------------
path = 'flutter/lib/core/app_state.dart'
text = r(path)
login_pos = text.find('  Future<AuthResult> login(String identifier, String password) async {')
if login_pos < 0:
    raise RuntimeError('v4.2 AppState login missing')
recovery = r'''  void _recoverBootstrapInBackground() {
    Future<void>.delayed(const Duration(milliseconds: 700), () async {
      if (status != AppStatus.signedIn || api.token == null) return;
      try {
        final fresh = await _bootstrapAfterAuth();
        if (status == AppStatus.signedIn && api.token != null) {
          bootstrap = fresh;
          error = null;
          notifyListeners();
        }
      } catch (_) {
        // Keep the authenticated shell usable; the next normal refresh retries.
      }
    });
  }

'''
if '_recoverBootstrapInBackground()' not in text:
    text = text[:login_pos] + recovery + text[login_pos:]

login_state = r'''  Future<AuthResult> login(String identifier, String password) async {
    try {
      final result = await api.login(identifier, password);
      if (result.token != null) {
        await api.saveToken(result.token!);
        if (result.user != null) {
          bootstrap = BootstrapData(
            user: result.user!,
            stats: const Stats(),
            shortcuts: const <Shortcut>[],
          );
          error = null;
          status = AppStatus.signedIn;
          notifyListeners();
        }
        try {
          bootstrap = await _bootstrapAfterAuth();
          error = null;
          status = AppStatus.signedIn;
          notifyListeners();
        } on ApiException catch (e) {
          if (e.status == 401) {
            await api.clearToken();
            bootstrap = null;
            status = AppStatus.signedOut;
            notifyListeners();
            rethrow;
          }
          if (result.user == null) rethrow;
          error = e.message;
          _recoverBootstrapInBackground();
        }
      }
      return result;
    } on ApiException {
      rethrow;
    } catch (_) {
      throw const ApiException(
        'Sign-in could not finish on this phone. Please restart the app and try again.',
      );
    }
  }'''
text = replace_function(text, '  Future<AuthResult> login(String identifier, String password) async {', login_state)

# Two-factor gets the same resilience when user data is available in the result.
twofa_state = r'''  Future<void> finishTwoFactor(String challenge, String code) async {
    try {
      final result = await api.verifyTwoFactor(challenge, code);
      if (result.token == null) {
        throw const ApiException('Verification did not complete.');
      }
      await api.saveToken(result.token!);
      if (result.user != null) {
        bootstrap = BootstrapData(
          user: result.user!,
          stats: const Stats(),
          shortcuts: const <Shortcut>[],
        );
        error = null;
        status = AppStatus.signedIn;
        notifyListeners();
      }
      try {
        bootstrap = await _bootstrapAfterAuth();
        error = null;
        status = AppStatus.signedIn;
        notifyListeners();
      } on ApiException catch (e) {
        if (e.status == 401) {
          await api.clearToken();
          bootstrap = null;
          status = AppStatus.signedOut;
          notifyListeners();
          rethrow;
        }
        if (result.user == null) rethrow;
        error = e.message;
        _recoverBootstrapInBackground();
      }
    } on ApiException {
      rethrow;
    } catch (_) {
      throw const ApiException(
        'Verification could not finish on this phone. Please try again.',
      );
    }
  }'''
text = replace_function(text, '  Future<void> finishTwoFactor(String challenge, String code) async {', twofa_state)
w(path, text)


# ---------------------------------------------------------------------------
# 3) Android FLAG_SECURE bridge. View-once media cannot be captured by normal
# Android screenshots/screen recording while it is visible/playing.
# ---------------------------------------------------------------------------
path = 'flutter/lib/core/native_bridge.dart'
text = r(path)
if 'setSecureScreen(bool enabled)' not in text:
    marker = '  static Future<String> deviceName() async {'
    idx = text.find(marker)
    if idx < 0:
        raise RuntimeError('v4.2 NativeBridge deviceName marker missing')
    secure_method = r'''  static Future<void> setSecureScreen(bool enabled) async {
    try {
      await _media.invokeMethod<void>('setSecureScreen', {'enabled': enabled});
    } catch (_) {
      // Privacy protection is best-effort on vendor-modified Android builds.
    }
  }

'''
    text = text[:idx] + secure_method + text[idx:]
w(path, text)

path = 'flutter/android/app/src/main/kotlin/online/taleempk/studyhub/MainActivity.kt'
text = r(path)
if 'import android.view.WindowManager' not in text:
    text = text.replace('import android.util.Base64\n', 'import android.util.Base64\nimport android.view.WindowManager\n', 1)
if 'call.method == "setSecureScreen"' not in text:
    marker = 'if (call.method == "deviceName") {'
    idx = text.find(marker)
    if idx < 0:
        raise RuntimeError('v4.2 Android deviceName handler missing')
    native_secure = '''if (call.method == "setSecureScreen") {
                    val enabled = call.argument<Boolean>("enabled") ?: false
                    runOnUiThread {
                        if (enabled) {
                            window.addFlags(WindowManager.LayoutParams.FLAG_SECURE)
                        } else {
                            window.clearFlags(WindowManager.LayoutParams.FLAG_SECURE)
                        }
                        result.success(null)
                    }
                    return@setMethodCallHandler
                }
                '''
    text = text[:idx] + native_secure + text[idx:]
w(path, text)


# ---------------------------------------------------------------------------
# 4) Professional media privacy selector. One-time photo is no longer a
# separate bulky action: choose Standard / 1× once at the top, then pick photo
# or camera and send. Standard mode keeps direct multi-photo sending.
# ---------------------------------------------------------------------------
path = 'flutter/lib/screens/chat_screen.dart'
text = r(path)
picker = r'''  Future<void> _pickAttachment() async {
    if (_chatBlocked || sending) return;
    var viewOnce = false;
    await showModalBottomSheet<void>(
      context: context,
      useSafeArea: true,
      showDragHandle: true,
      builder: (sheet) => StatefulBuilder(
        builder: (context, setSheet) => SafeArea(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
                child: Row(
                  children: [
                    Expanded(
                      child: Text(
                        'Send attachment',
                        style: Theme.of(sheet).textTheme.titleMedium?.copyWith(
                              fontWeight: FontWeight.w900,
                            ),
                      ),
                    ),
                    SegmentedButton<bool>(
                      segments: const [
                        ButtonSegment<bool>(
                          value: false,
                          icon: Icon(Icons.all_inclusive_rounded, size: 17),
                          label: Text('Standard'),
                        ),
                        ButtonSegment<bool>(
                          value: true,
                          icon: Icon(Icons.looks_one_rounded, size: 17),
                          label: Text('Once'),
                        ),
                      ],
                      selected: <bool>{viewOnce},
                      showSelectedIcon: false,
                      onSelectionChanged: (value) =>
                          setSheet(() => viewOnce = value.first),
                    ),
                  ],
                ),
              ),
              AnimatedSwitcher(
                duration: const Duration(milliseconds: 140),
                child: viewOnce
                    ? Container(
                        key: const ValueKey('once-note'),
                        margin: const EdgeInsets.fromLTRB(16, 0, 16, 8),
                        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 9),
                        decoration: BoxDecoration(
                          color: AppColors.success.withValues(alpha: .08),
                          borderRadius: BorderRadius.circular(14),
                        ),
                        child: const Row(
                          children: [
                            Icon(Icons.shield_outlined, size: 18, color: AppColors.success),
                            SizedBox(width: 8),
                            Expanded(
                              child: Text(
                                'One photo · opens once · screenshots/screen recording blocked while open',
                                style: TextStyle(fontSize: 11.5, fontWeight: FontWeight.w700),
                              ),
                            ),
                          ],
                        ),
                      )
                    : const SizedBox.shrink(key: ValueKey('standard-note')),
              ),
              ListTile(
                leading: const Icon(Icons.photo_library_outlined, color: AppColors.blue),
                title: Text(viewOnce ? 'Choose one photo' : 'Photos or images'),
                subtitle: Text(viewOnce
                    ? 'Select and send as one-time media'
                    : 'Select one or many · send directly in chat'),
                onTap: () async {
                  Navigator.pop(sheet);
                  if (viewOnce) {
                    final image = await ImagePicker().pickImage(
                      source: ImageSource.gallery,
                      imageQuality: 92,
                      maxWidth: 2600,
                      maxHeight: 2600,
                    );
                    if (image != null && mounted) {
                      await _uploadManyImages([image.path], viewOnce: true);
                    }
                  } else {
                    final images = await ImagePicker().pickMultiImage(
                      imageQuality: 92,
                      maxWidth: 2600,
                      maxHeight: 2600,
                    );
                    if (images.isNotEmpty && mounted) {
                      await _uploadManyImages(images.map((e) => e.path).toList());
                    }
                  }
                },
              ),
              ListTile(
                leading: const Icon(Icons.camera_alt_outlined, color: AppColors.success),
                title: const Text('Camera'),
                subtitle: Text(viewOnce ? 'Capture and send once' : 'Capture and send directly'),
                onTap: () async {
                  Navigator.pop(sheet);
                  final image = await ImagePicker().pickImage(
                    source: ImageSource.camera,
                    imageQuality: 92,
                    maxWidth: 2600,
                    maxHeight: 2600,
                  );
                  if (image != null && mounted) {
                    await _uploadManyImages([image.path], viewOnce: viewOnce);
                  }
                },
              ),
              if (!viewOnce)
                ListTile(
                  leading: const Icon(Icons.tune_rounded, color: AppColors.violet),
                  title: const Text('Edit before sending'),
                  subtitle: const Text('Crop, rotate, hide details or review multiple photos'),
                  onTap: () async {
                    Navigator.pop(sheet);
                    final images = await ImagePicker().pickMultiImage(
                      imageQuality: 92,
                      maxWidth: 2600,
                      maxHeight: 2600,
                    );
                    if (images.isNotEmpty && mounted) {
                      await _reviewImages(images.map((e) => e.path).toList());
                    }
                  },
                ),
              if (!viewOnce)
                ListTile(
                  leading: const Icon(Icons.attach_file_rounded, color: AppColors.violet),
                  title: const Text('Document or file'),
                  onTap: () async {
                    Navigator.pop(sheet);
                    final file = await FilePicker.pickFile();
                    final filePath = file?.path;
                    if (filePath != null && mounted) await _upload(filePath);
                  },
                ),
              if (!viewOnce && widget.conversation.isGroup)
                ListTile(
                  leading: const Icon(Icons.poll_outlined, color: AppColors.violet),
                  title: const Text('Create poll'),
                  onTap: () {
                    Navigator.pop(sheet);
                    _createPoll();
                  },
                ),
              const SizedBox(height: 6),
            ],
          ),
        ),
      ),
    );
  }'''
text = replace_function(text, '  Future<void> _pickAttachment() async {', picker)

# Protect one-time image viewer with FLAG_SECURE for the complete dialog life.
os, oe = function_bounds(text, '  Future<void> _openAttachment(ChatMessage m) async {')
open_chunk = text[os:oe]
if 'final viewOnce = _isViewOnceAttachmentName(m.attachmentName);' not in open_chunk:
    raise RuntimeError('v4.2 expected v4.1 view-once image logic missing')
if 'NativeBridge.setSecureScreen(true)' not in open_chunk:
    open_chunk = open_chunk.replace(
        '    try {\n',
        '    if (viewOnce) await NativeBridge.setSecureScreen(true);\n    try {\n',
        1,
    )
    tail = """    } catch (e) {
      if (mounted) showMessage(context, apiMessage(e));
    }
"""
    if tail not in open_chunk:
        raise RuntimeError('v4.2 attachment catch tail missing')
    open_chunk = open_chunk.replace(
        tail,
        """    } catch (e) {
      if (mounted) showMessage(context, apiMessage(e));
    } finally {
      if (viewOnce) await NativeBridge.setSecureScreen(false);
    }
""",
        1,
    )
text = text[:os] + open_chunk + text[oe:]

# Secure one-time voice playback. Pause/completion/dispose all clear FLAG_SECURE.
vs = text.find('class _VoiceBubbleState extends State<VoiceBubble> {')
ve = text.find('\nclass ', vs + 10)
if vs < 0:
    raise RuntimeError('v4.2 voice bubble missing')
if ve < 0:
    ve = len(text)
voice = text[vs:ve]
if 'bool secureViewOnceActive = false;' not in voice:
    voice = voice.replace(
        '  String? localPath;\n',
        '  String? localPath;\n  bool secureViewOnceActive = false;\n',
        1,
    )
    helper_marker = '  Future<void> _downloadFresh(File file) async {'
    helper_code = r'''  bool get _protectedViewOnceVoice =>
      _isViewOnceAttachmentName(widget.message.attachmentName) &&
      !widget.message.mine;

  Future<void> _setSecureViewOnce(bool enabled) async {
    if (!_protectedViewOnceVoice && enabled) return;
    if (secureViewOnceActive == enabled) return;
    secureViewOnceActive = enabled;
    await NativeBridge.setSecureScreen(enabled);
  }

'''
    if helper_marker not in voice:
        raise RuntimeError('v4.2 voice helper insertion marker missing')
    voice = voice.replace(helper_marker, helper_code + helper_marker, 1)

    # Dispose safety.
    voice = voice.replace(
        '    player.dispose();\n    super.dispose();',
        '    player.dispose();\n    if (secureViewOnceActive) {\n      unawaited(NativeBridge.setSecureScreen(false));\n    }\n    super.dispose();',
        1,
    )

    # Pausing for another note clears protection.
    ps, pe = function_bounds(voice, '  Future<void> _pauseForAnotherVoice() async {')
    pause_chunk = voice[ps:pe]
    pause_chunk = pause_chunk.replace(
        '    if (mounted) setState(() {});',
        '    await _setSecureViewOnce(false);\n    if (mounted) setState(() {});',
        1,
    )
    voice = voice[:ps] + pause_chunk + voice[pe:]

    # Toggle: clear on manual pause, enable immediately before playback.
    ts, te = function_bounds(voice, '  Future<void> _toggle({bool autoStart = false}) async {')
    toggle = voice[ts:te]
    toggle = toggle.replace(
        '        if (activeVoice == this) activeVoice = null;\n        if (mounted) setState(() {});\n        return;',
        '        if (activeVoice == this) activeVoice = null;\n        await _setSecureViewOnce(false);\n        if (mounted) setState(() {});\n        return;',
        1,
    )
    toggle = toggle.replace(
        '      unawaited(_playToEnd());',
        '      await _setSecureViewOnce(true);\n      unawaited(_playToEnd());',
        1,
    )
    toggle = toggle.replace(
        '    } catch (e) {\n      if (activeVoice == this) activeVoice = null;',
        '    } catch (e) {\n      if (activeVoice == this) activeVoice = null;\n      await _setSecureViewOnce(false);',
        1,
    )
    voice = voice[:ts] + toggle + voice[te:]

    hs, he = function_bounds(voice, '  Future<void> _handleCompleted() async {')
    complete = voice[hs:he]
    finally_marker = '    } finally {\n      handlingCompletion = false;'
    if finally_marker not in complete:
        raise RuntimeError('v4.2 voice completion finally marker missing')
    complete = complete.replace(
        finally_marker,
        '    } finally {\n      await _setSecureViewOnce(false);\n      handlingCompletion = false;',
        1,
    )
    voice = voice[:hs] + complete + voice[he:]

text = text[:vs] + voice + text[ve:]
w(path, text)


# ---------------------------------------------------------------------------
# 5) Server: consuming view-once media removes the underlying attachment and
# marks the message deleted for everyone. The sender therefore also sees that
# the one-time media has expired after the recipient opens/listens once.
# ---------------------------------------------------------------------------
for path in ['backend/api/mobile.php', 'flutter/backend/api/mobile.php']:
    text = r(path)

    start = text.find("if ($action === 'mark_view_once') {")
    end = text.find("if ($action === 'mark_voice_played') {", start)
    if start < 0 or end < 0:
        raise RuntimeError(f'v4.2 view-once backend action missing: {path}')
    view_action = r'''if ($action === 'mark_view_once') {
    $mid = max(0, (int)($_POST['message_id'] ?? 0));
    $m = fetch_one("SELECT m.id,m.sender_id,m.attachment,m.attachment_name
                      FROM messages m
                      JOIN conversation_members cm ON cm.conversation_id=m.conversation_id AND cm.user_id=?
                     WHERE m.id=? AND m.status='sent' LIMIT 1", [$uid,$mid]);
    $name = (string)($m['attachment_name'] ?? '');
    if (!$m || (int)$m['sender_id']===$uid || strncmp($name, 'once__', 6)!==0) {
        mobile_error('That view once media is not available.', 404);
    }
    if (table_exists('message_plays')) {
        q('INSERT IGNORE INTO message_plays (message_id,user_id) VALUES (?,?)', [$mid,$uid]);
    }
    $base = realpath(UPLOAD_PATH . '/chat');
    $file = !empty($m['attachment']) ? realpath(UPLOAD_PATH . '/' . ltrim((string)$m['attachment'],'/')) : false;
    if ($base && $file && strpos($file,$base.DIRECTORY_SEPARATOR)===0 && is_file($file)) {
        @unlink($file);
    }
    q("UPDATE messages SET status='deleted' WHERE id=? AND status='sent'", [$mid]);
    mobile_out(['consumed'=>true,'deleted'=>true]);
}

'''
    text = text[:start] + view_action + text[end:]

    # Extend voice receipt query so one-time voice can self-delete on completion.
    voice_start = text.find("if ($action === 'mark_voice_played') {")
    voice_end = text.find("if ($action === 'pinned_messages') {", voice_start)
    if voice_start < 0 or voice_end < 0:
        raise RuntimeError(f'v4.2 voice receipt action missing: {path}')
    voice_action = r'''if ($action === 'mark_voice_played') {
    $mid = max(0, (int)($_POST['message_id'] ?? 0));
    $m = fetch_one("SELECT m.id,m.sender_id,m.voice_seconds,m.attachment,m.attachment_name
                      FROM messages m
                      JOIN conversation_members cm ON cm.conversation_id=m.conversation_id AND cm.user_id=?
                     WHERE m.id=? AND m.status='sent' LIMIT 1", [$uid,$mid]);
    if (!$m || (int)$m['voice_seconds']<=0 || (int)$m['sender_id']===$uid) {
        mobile_error('That voice message is not available.', 404);
    }
    if (table_exists('message_plays') && (int)($u['show_receipts'] ?? 1)===1) {
        q('INSERT IGNORE INTO message_plays (message_id,user_id) VALUES (?,?)', [$mid,$uid]);
    }
    $name = (string)($m['attachment_name'] ?? '');
    $viewOnce = strncmp($name, 'once__', 6) === 0;
    if ($viewOnce) {
        $base = realpath(UPLOAD_PATH . '/chat');
        $file = !empty($m['attachment']) ? realpath(UPLOAD_PATH . '/' . ltrim((string)$m['attachment'],'/')) : false;
        if ($base && $file && strpos($file,$base.DIRECTORY_SEPARATOR)===0 && is_file($file)) {
            @unlink($file);
        }
        q("UPDATE messages SET status='deleted' WHERE id=? AND status='sent'", [$mid]);
    }
    mobile_out(['played'=>true,'deleted'=>$viewOnce]);
}

'''
    text = text[:voice_start] + voice_action + text[voice_end:]
    w(path, text)

# Keep mirrors identical.
if r('backend/api/mobile.php') != r('flutter/backend/api/mobile.php'):
    shutil.copy2(ROOT / 'backend/api/mobile.php', ROOT / 'flutter/backend/api/mobile.php')


# Version.
path = 'flutter/pubspec.yaml'
text = r(path)
text = re.sub(r'^version:\s*[^\n]+', 'version: 4.2.0+420', text, count=1, flags=re.M)
w(path, text)

# Assertions.
api = r('flutter/lib/core/api_client.dart')
state = r('flutter/lib/core/app_state.dart')
chat = r('flutter/lib/screens/chat_screen.dart')
native_bridge = r('flutter/lib/core/native_bridge.dart')
native = r('flutter/android/app/src/main/kotlin/online/taleempk/studyhub/MainActivity.kt')
mobile = r('backend/api/mobile.php')
pubspec = r('flutter/pubspec.yaml')
assert '_compatTokenKey' in api and 'SharedPreferences.getInstance()' in api
assert '_authRequestWithRetry' in api and 'HandshakeException' in api
assert '_recoverBootstrapInBackground' in state and 'stats: const Stats()' in state
assert 'setSecureScreen(bool enabled)' in native_bridge
assert 'WindowManager.LayoutParams.FLAG_SECURE' in native
assert "label: Text('Once')" in chat and 'viewOnce: viewOnce' in chat
assert 'await NativeBridge.setSecureScreen(true)' in chat
assert '_setSecureViewOnce(true)' in chat and '_setSecureViewOnce(false)' in chat
assert "UPDATE messages SET status='deleted'" in mobile and "@unlink($file)" in mobile
assert 'version: 4.2.0+420' in pubspec
print('TaleemPK v4.2 login/privacy/view-once hardening applied successfully')
