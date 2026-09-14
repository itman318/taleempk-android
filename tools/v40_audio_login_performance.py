from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def r(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def w(path: str, text: str) -> None:
    p = ROOT / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding='utf-8')


def once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f'v4.0 missing target: {label}')
    return text.replace(old, new, 1)


def function_bounds(text: str, signature: str):
    start = text.find(signature)
    if start < 0:
        raise RuntimeError(f'v4.0 missing function: {signature}')
    brace = text.find('{', start)
    if brace < 0:
        raise RuntimeError(f'v4.0 malformed function: {signature}')
    depth = 0
    for i in range(brace, len(text)):
        ch = text[i]
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                return start, i + 1
    raise RuntimeError(f'v4.0 unterminated function: {signature}')


def class_bounds(text: str, signature: str):
    return function_bounds(text, signature)


# ---------------------------------------------------------------------------
# 1) Audio playback progress: just_audio's default position stream can update
# slowly or appear frozen on some Android vendors while playback continues.
# Use an explicit high-frequency position stream plus a lightweight playback
# clock fallback that reads player.position while the note is actively playing.
# ---------------------------------------------------------------------------
path = 'flutter/lib/screens/chat_screen.dart'
text = r(path)
start, end = class_bounds(text, 'class _VoiceBubbleState extends State<VoiceBubble> {')
voice = text[start:end]
voice = once(
    voice,
    '  final player = AudioPlayer();\n',
    '  final player = AudioPlayer();\n  Timer? progressTimer;\n',
    'voice progress timer field',
)
voice = once(
    voice,
    '  void initState() {\n    super.initState();\n',
    """  void initState() {
    super.initState();
    progressTimer = Timer.periodic(const Duration(milliseconds: 120), (_) {
      if (!mounted || !player.playing) return;
      setState(() {});
    });
""",
    'voice progress timer init',
)
voice = once(
    voice,
    '  void dispose() {\n',
    '  void dispose() {\n    progressTimer?.cancel();\n',
    'voice progress timer dispose',
)
voice = once(
    voice,
    '    stream: player.positionStream,\n',
    """    stream: player.createPositionStream(
      minPeriod: const Duration(milliseconds: 70),
      maxPeriod: const Duration(milliseconds: 180),
      steps: 900,
    ),
""",
    'voice position stream cadence',
)
voice = once(
    voice,
    '      final position = snap.data ?? Duration.zero;\n',
    """      final streamedPosition = snap.data ?? Duration.zero;
      final livePosition = player.position;
      final position = livePosition.inMilliseconds > streamedPosition.inMilliseconds
          ? livePosition
          : streamedPosition;
""",
    'voice live position fallback',
)
text = text[:start] + voice + text[end:]

# Faster initial conversation open and lighter history chunks. Incremental
# polling still keeps new messages live, while expensive full reconciliation is
# less frequent so older/low-memory phones spend less time rebuilding the list.
for signature, old_limit, new_limit, old_done, new_done in [
    ('  Future<void> _load({bool jumpToBottom = false}) async {', 'limit: 80', 'limit: 60', 'fresh.length < 80', 'fresh.length < 60'),
    ('  Future<void> _loadOlder() async {', 'limit: 80', 'limit: 60', 'older.length < 80', 'older.length < 60'),
]:
    fs, fe = function_bounds(text, signature)
    chunk = text[fs:fe]
    if old_limit not in chunk or old_done not in chunk:
        raise RuntimeError(f'v4.0 chat chunk target missing: {signature}')
    chunk = chunk.replace(old_limit, new_limit, 1).replace(old_done, new_done, 1)
    text = text[:fs] + chunk + text[fe:]
text = once(text, 'final fullSync = pollTicks % 8 == 0;', 'final fullSync = pollTicks % 12 == 0;', 'lighter full chat sync')
w(path, text)


# ---------------------------------------------------------------------------
# 2) Device bridge hardening: a vendor-specific MethodChannel stall must never
# leave the sign-in button spinning forever. Fall back to a generic Android
# device label after two seconds and continue login normally.
# ---------------------------------------------------------------------------
path = 'flutter/lib/core/native_bridge.dart'
text = r(path)
text = once(
    text,
    "      final value = await _media.invokeMethod<String>('deviceName');",
    "      final value = await _media.invokeMethod<String>('deviceName').timeout(const Duration(seconds: 2));",
    'device name timeout',
)
w(path, text)


# ---------------------------------------------------------------------------
# 3) Secure-storage and authentication watchdogs. Some Android keystore/vendor
# combinations can delay secure-storage calls. Never leave the UI waiting with
# no feedback; fail cleanly and allow a retry.
# ---------------------------------------------------------------------------
path = 'flutter/lib/core/api_client.dart'
text = r(path)

s, e = function_bounds(text, '  Future<bool> restoreSession() async {')
restore = r'''  Future<bool> restoreSession() async {
    try {
      _token = await _storage
          .read(key: _tokenKey)
          .timeout(const Duration(seconds: 4));
      if (_token == null || _token!.isEmpty) {
        _token = await _storage
            .read(key: _legacyTokenKey)
            .timeout(const Duration(seconds: 4));
        if (_token != null && _token!.isNotEmpty) {
          await _storage
              .write(key: _tokenKey, value: _token)
              .timeout(const Duration(seconds: 4));
          await _storage
              .delete(key: _legacyTokenKey)
              .timeout(const Duration(seconds: 4));
        }
      }
      return _token != null && _token!.isNotEmpty;
    } catch (_) {
      _token = null;
      return false;
    }
  }'''
text = text[:s] + restore + text[e:]

s, e = function_bounds(text, '  Future<void> saveToken(String value) async {')
save = r'''  Future<void> saveToken(String value) async {
    _token = value;
    try {
      await _storage
          .write(key: _tokenKey, value: value)
          .timeout(const Duration(seconds: 5));
    } on TimeoutException {
      _token = null;
      throw const ApiException(
        'Secure sign-in storage timed out on this phone. Please try again.',
      );
    } catch (_) {
      _token = null;
      throw const ApiException(
        'This phone could not save the secure sign-in session. Restart the app and try again.',
      );
    }
  }'''
text = text[:s] + save + text[e:]

s, e = function_bounds(text, '  Future<void> clearToken() async {')
clear = r'''  Future<void> clearToken() async {
    _token = null;
    try {
      await _storage.delete(key: _tokenKey).timeout(const Duration(seconds: 3));
    } catch (_) {}
    try {
      await _storage.delete(key: _legacyTokenKey).timeout(const Duration(seconds: 3));
    } catch (_) {}
  }'''
text = text[:s] + clear + text[e:]

# Bound login and 2FA network stages independently. _request already has its
# own timeout, but this shorter auth watchdog prevents a second slow bootstrap
# from making sign-in appear permanently stuck.
for signature, label in [
    ('  Future<AuthResult> login(String identifier, String password) async {', 'login request'),
    ('  Future<AuthResult> verifyTwoFactor(String challenge, String code) async {', '2FA request'),
]:
    s, e = function_bounds(text, signature)
    chunk = text[s:e]
    marker = '    final data = await _request({'
    if marker not in chunk:
        raise RuntimeError(f'v4.0 auth request marker missing: {label}')
    # Wrap the complete _request expression by replacing its closing authenticated
    # call. Both auth methods use the same authenticated:false terminator.
    terminator = '    }, authenticated: false);'
    if terminator not in chunk:
        raise RuntimeError(f'v4.0 auth terminator missing: {label}')
    chunk = chunk.replace('    final data = await _request({', '    final data = await _request({', 1)
    chunk = chunk.replace(
        terminator,
        """    }, authenticated: false).timeout(
      const Duration(seconds: 18),
      onTimeout: () => throw const ApiException(
        'Sign-in is taking too long on this connection. Please try again.',
      ),
    );""",
        1,
    )
    text = text[:s] + chunk + text[e:]
w(path, text)


# ---------------------------------------------------------------------------
# 4) Account bootstrap after authentication: retry once, cap each attempt and
# always convert unexpected platform/parser failures into a visible ApiException.
# This closes the no-error login hang reported on a subset of phones.
# ---------------------------------------------------------------------------
path = 'flutter/lib/core/app_state.dart'
text = r(path)
helper_marker = '  Future<AuthResult> login(String identifier, String password) async {\n'
bootstrap_helper = r'''  Future<BootstrapData> _bootstrapAfterAuth() async {
    ApiException? lastError;
    for (var attempt = 0; attempt < 2; attempt++) {
      try {
        return await api.bootstrap().timeout(
          const Duration(seconds: 18),
          onTimeout: () => throw const ApiException(
            'Your account took too long to load. Check your connection and try again.',
          ),
        );
      } on ApiException catch (e) {
        lastError = e;
        if (e.status == 401) rethrow;
      } catch (_) {
        lastError = const ApiException(
          'Your account could not finish loading on this phone. Please try again.',
        );
      }
      if (attempt == 0) {
        await Future<void>.delayed(const Duration(milliseconds: 350));
      }
    }
    throw lastError ?? const ApiException('Could not load your account.');
  }

'''
text = once(text, helper_marker, bootstrap_helper + helper_marker, 'auth bootstrap helper')

s, e = function_bounds(text, '  Future<AuthResult> login(String identifier, String password) async {')
login = r'''  Future<AuthResult> login(String identifier, String password) async {
    try {
      final result = await api.login(identifier, password);
      if (result.token != null) {
        await api.saveToken(result.token!);
        try {
          bootstrap = await _bootstrapAfterAuth();
        } catch (_) {
          await api.clearToken();
          rethrow;
        }
        error = null;
        status = AppStatus.signedIn;
        notifyListeners();
      }
      return result;
    } on ApiException {
      rethrow;
    } catch (_) {
      throw const ApiException(
        'Sign-in could not be completed on this phone. Please check your connection and try again.',
      );
    }
  }'''
text = text[:s] + login + text[e:]

s, e = function_bounds(text, '  Future<void> finishTwoFactor(String challenge, String code) async {')
twofa = r'''  Future<void> finishTwoFactor(String challenge, String code) async {
    try {
      final result = await api.verifyTwoFactor(challenge, code);
      if (result.token == null) {
        throw const ApiException('Verification did not complete.');
      }
      await api.saveToken(result.token!);
      try {
        bootstrap = await _bootstrapAfterAuth();
      } catch (_) {
        await api.clearToken();
        rethrow;
      }
      error = null;
      status = AppStatus.signedIn;
      notifyListeners();
    } on ApiException {
      rethrow;
    } catch (_) {
      throw const ApiException(
        'Verification could not finish loading your account. Please try again.',
      );
    }
  }'''
text = text[:s] + twofa + text[e:]

# Existing-session refresh should also avoid an indefinite bootstrap wait.
s, e = function_bounds(text, '  Future<void> refreshSession() async {')
chunk = text[s:e]
chunk = once(chunk, '      bootstrap = await api.bootstrap();', '      bootstrap = await _bootstrapAfterAuth();', 'session refresh bootstrap')
text = text[:s] + chunk + text[e:]
w(path, text)


# ---------------------------------------------------------------------------
# 5) Auth UI fallback: ApiException covers known failures, but no platform or
# plugin exception should disappear silently. Always show a human-readable retry.
# ---------------------------------------------------------------------------
path = 'flutter/lib/screens/auth_screen.dart'
text = r(path)
s, e = function_bounds(text, '  Future<void> _submit() async {')
chunk = text[s:e]
needle = """    } on ApiException catch (e) {
      if (mounted)
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(e.message)));
    } finally {"""
replacement = """    } on ApiException catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(e.message)));
      }
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Sign-in could not finish on this phone. Please try again.'),
          ),
        );
      }
    } finally {"""
chunk = once(chunk, needle, replacement, 'auth generic error surface')
text = text[:s] + chunk + text[e:]
w(path, text)


# ---------------------------------------------------------------------------
# 6) Snappier high-frequency navigation. Keep animation subtle, but shorten it
# enough that opening profile/security/chat-adjacent options feels immediate.
# ---------------------------------------------------------------------------
path = 'flutter/lib/widgets/common.dart'
text = r(path)
text = once(text, 'transitionDuration: const Duration(milliseconds: 170),', 'transitionDuration: const Duration(milliseconds: 135),', 'route forward duration')
text = once(text, 'reverseTransitionDuration: const Duration(milliseconds: 135),', 'reverseTransitionDuration: const Duration(milliseconds: 105),', 'route reverse duration')
w(path, text)


# Release version.
path = 'flutter/pubspec.yaml'
text = r(path)
text = re.sub(r'^version:\s*[^\n]+', 'version: 4.0.0+400', text, count=1, flags=re.M)
w(path, text)


# Generated-source assertions.
chat = r('flutter/lib/screens/chat_screen.dart')
api = r('flutter/lib/core/api_client.dart')
state = r('flutter/lib/core/app_state.dart')
native = r('flutter/lib/core/native_bridge.dart')
auth = r('flutter/lib/screens/auth_screen.dart')
common = r('flutter/lib/widgets/common.dart')
pubspec = r('flutter/pubspec.yaml')
assert 'createPositionStream(' in chat and 'progressTimer = Timer.periodic' in chat
assert 'livePosition.inMilliseconds > streamedPosition.inMilliseconds' in chat
assert 'final fullSync = pollTicks % 12 == 0;' in chat
assert 'fresh.length < 60' in chat and 'older.length < 60' in chat
assert ".timeout(const Duration(seconds: 2))" in native
assert 'Secure sign-in storage timed out on this phone.' in api
assert "const Duration(seconds: 18)" in api
assert 'Future<BootstrapData> _bootstrapAfterAuth() async' in state
assert 'Sign-in could not be completed on this phone.' in state
assert 'Sign-in could not finish on this phone.' in auth
assert 'transitionDuration: const Duration(milliseconds: 135)' in common
assert 'version: 4.0.0+400' in pubspec
print('TaleemPK v4.0 audio/login/performance hardening applied successfully')
