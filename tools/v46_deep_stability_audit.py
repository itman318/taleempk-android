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
        raise RuntimeError(f'v4.6 missing target: {label}')
    return text.replace(old, new, 1)


def block_bounds(text: str, signature: str, start_at: int = 0):
    start = text.find(signature, start_at)
    if start < 0:
        raise RuntimeError(f'v4.6 missing block: {signature}')
    brace = text.find('{', start)
    if brace < 0:
        raise RuntimeError(f'v4.6 malformed block: {signature}')
    depth = 0
    quote = None
    escaped = False
    line_comment = False
    block_comment = False
    i = brace
    while i < len(text):
        ch = text[i]
        nxt = text[i + 1] if i + 1 < len(text) else ''
        if line_comment:
            if ch == '\n':
                line_comment = False
            i += 1
            continue
        if block_comment:
            if ch == '*' and nxt == '/':
                block_comment = False
                i += 2
                continue
            i += 1
            continue
        if quote is not None:
            if escaped:
                escaped = False
            elif ch == '\\':
                escaped = True
            elif ch == quote:
                quote = None
            i += 1
            continue
        if ch == '/' and nxt == '/':
            line_comment = True
            i += 2
            continue
        if ch == '/' and nxt == '*':
            block_comment = True
            i += 2
            continue
        if ch in ('\"', "'"):
            quote = ch
            i += 1
            continue
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                return start, i + 1
        i += 1
    raise RuntimeError(f'v4.6 unterminated block: {signature}')


# ---------------------------------------------------------------------------
# 1) Main API: distinguish hosting/proxy HTML from JSON API responses.
# This turns the generic "invalid response" into an actionable service error
# without ever treating HTML as a successful login response.
# ---------------------------------------------------------------------------
path = 'flutter/lib/core/api_client.dart'
text = r(path)
marker = """    if (map == null || map.isEmpty) {
      if (status >= 200 && status < 300 && raw.isEmpty) {
"""
replacement = """    if (map == null || map.isEmpty) {
      final lowerRaw = raw.toLowerCase();
      final suspended = lowerRaw.contains('suspendedpage.cgi') ||
          lowerRaw.contains('account suspended') ||
          lowerRaw.contains('hosting account has been suspended');
      final htmlResponse = lowerRaw.contains('<!doctype html') ||
          lowerRaw.contains('<html') ||
          lowerRaw.contains('<head');
      if (suspended) {
        throw ApiException(
          'TaleemPK hosting is currently unavailable. Please try again after the server is restored.',
          status: status,
        );
      }
      if (htmlResponse) {
        throw ApiException(
          'TaleemPK server returned a web page instead of API data. Please try again later.',
          status: status,
        );
      }
      if (status >= 200 && status < 300 && raw.isEmpty) {
"""
if marker not in text:
    raise RuntimeError('v4.6 main API decode marker missing')
text = text.replace(marker, replacement, 1)
w(path, text)


# ---------------------------------------------------------------------------
# 2) Social API: use the same transport hardening as the primary API and do
# not destroy a valid app session for unrelated 401 responses.
# ---------------------------------------------------------------------------
path = 'flutter/lib/core/social_api.dart'
text = r(path)
request_start, request_end = block_bounds(text, '  Future<Map<String, dynamic>> _request(')
request = text[request_start:request_end]
old_catches = """    } on TimeoutException {
      throw const ApiException('The server took too long to respond. Please try again.');
    } on SocketException {
      throw const ApiException('You appear to be offline. Check your internet connection.');
    } on http.ClientException {
      throw const ApiException('Could not connect securely to TaleemPK.');
    }
"""
new_catches = """    } on TimeoutException {
      throw const ApiException('The server took too long to respond. Please try again.');
    } on HandshakeException {
      throw const ApiException(
        'This phone could not establish a secure connection to TaleemPK. Check date/time, network or VPN and try again.',
      );
    } on TlsException {
      throw const ApiException(
        'Secure connection failed on this phone. Try another network or update Android security components.',
      );
    } on SocketException {
      throw const ApiException('You appear to be offline. Check your internet connection.');
    } on http.ClientException {
      throw const ApiException('Could not connect securely to TaleemPK.');
    } on FormatException {
      throw const ApiException('The server response could not be read on this phone. Please try again.');
    } catch (_) {
      throw const ApiException('The TaleemPK request was interrupted. Please try again.');
    }
"""
if old_catches not in request:
    raise RuntimeError('v4.6 social transport marker missing')
request = request.replace(old_catches, new_catches, 1)
text = text[:request_start] + request + text[request_end:]

# Harden social decoder for suspended/HTML responses and session expiry.
decode_start, decode_end = block_bounds(text, '  Map<String, dynamic> _decode(')
decode = text[decode_start:decode_end]
old_invalid = """    if (envelope == null || envelope.isEmpty) {
      throw ApiException(
        status >= 500 ? 'TaleemPK is temporarily unavailable.' : 'The server returned an invalid response.',
        status: status,
      );
    }
"""
new_invalid = """    if (envelope == null || envelope.isEmpty) {
      final lowerRaw = raw.toLowerCase();
      final suspended = lowerRaw.contains('suspendedpage.cgi') ||
          lowerRaw.contains('account suspended') ||
          lowerRaw.contains('hosting account has been suspended');
      final htmlResponse = lowerRaw.contains('<!doctype html') ||
          lowerRaw.contains('<html') ||
          lowerRaw.contains('<head');
      throw ApiException(
        suspended
            ? 'TaleemPK hosting is currently unavailable. Please try again after the server is restored.'
            : htmlResponse
                ? 'TaleemPK server returned a web page instead of API data. Please try again later.'
                : status >= 500
                    ? 'TaleemPK is temporarily unavailable.'
                    : 'The server returned an invalid response.',
        status: status,
      );
    }
"""
if old_invalid not in decode:
    raise RuntimeError('v4.6 social decode marker missing')
decode = decode.replace(old_invalid, new_invalid, 1)
old_expire = """    if (status == 401) {
      unawaited(api.clearToken());
      api.onSessionExpired?.call(message);
    }
"""
new_expire = """    if (status == 401 && _isSessionFailure(message)) {
      unawaited(api.clearToken());
      api.onSessionExpired?.call(message);
    }
"""
if old_expire not in decode:
    raise RuntimeError('v4.6 social session-expiry marker missing')
decode = decode.replace(old_expire, new_expire, 1)
text = text[:decode_start] + decode + text[decode_end:]
if '  bool _isSessionFailure(String message) {' not in text:
    helper_marker = '  List<Map<String, dynamic>> _extract(String raw) {'
    helper = r'''  bool _isSessionFailure(String message) {
    final value = message.toLowerCase();
    return value.contains('session') ||
        value.contains('sign in') ||
        value.contains('token') ||
        value.contains('authentication') ||
        value.contains('unauthorized');
  }

'''
    text = once(text, helper_marker, helper + helper_marker, 'social session helper')
w(path, text)


# ---------------------------------------------------------------------------
# 3) Followers/following screen: cancel stale async responses and never call
# setState after the route has been disposed. This fixes refresh/load-more races.
# ---------------------------------------------------------------------------
path = 'flutter/lib/screens/profile_screen.dart'
text = r(path)
class_start = text.find('class _ProfileConnectionsScreenState extends State<_ProfileConnectionsScreen> {')
if class_start < 0:
    raise RuntimeError('v4.6 profile connections state missing')
serial_marker = '  String? error;\n'
serial_pos = text.find(serial_marker, class_start)
if serial_pos < 0:
    raise RuntimeError('v4.6 profile connections state fields missing')
if '  int _requestSerial = 0;\n' not in text[class_start:serial_pos + 300]:
    insert_at = serial_pos + len(serial_marker)
    text = text[:insert_at] + '  int _requestSerial = 0;\n' + text[insert_at:]

load_start, load_end = block_bounds(
    text,
    '  Future<void> _load({bool reset = false}) async {',
    class_start,
)
load = r'''  Future<void> _load({bool reset = false}) async {
    if (!mounted) return;
    if (!reset && (loadingMore || !hasMore)) return;
    final requestSerial = ++_requestSerial;

    if (reset) {
      setState(() {
        loading = true;
        loadingMore = false;
        error = null;
        before = 0;
        hasMore = false;
        visible = true;
        people.clear();
      });
    } else {
      setState(() => loadingMore = true);
    }

    try {
      final data = await social.profileConnections(
        widget.userId,
        widget.kind,
        before: reset ? 0 : before,
      );
      if (!mounted || requestSerial != _requestSerial) return;
      final next = smList(data['people']).map((e) => smMap(e)).toList();
      final seen = people.map((e) => smInt(e['id'])).toSet();
      setState(() {
        visible = !data.containsKey('visible') || smBool(data['visible']);
        if (reset) people.clear();
        for (final person in next) {
          final id = smInt(person['id']);
          if (id > 0 && !seen.contains(id)) {
            people.add(person);
            seen.add(id);
          }
        }
        hasMore = smBool(data['has_more']);
        before = smInt(data['next_before']);
        loading = false;
        loadingMore = false;
      });
    } catch (e) {
      if (!mounted || requestSerial != _requestSerial) return;
      setState(() {
        error = apiMessage(e);
        loading = false;
        loadingMore = false;
      });
    }
  }'''
text = text[:load_start] + load + text[load_end:]

# Keep the role-aware verification colour in the premium header too.
header_start = text.find('  Widget _header(ProfileData p) => Column(')
header_end = text.find('\n\n  Color _verificationColor(ProfileData p)', header_start)
if header_start >= 0 and header_end > header_start:
    header = text[header_start:header_end]
    header = header.replace('color: AppColors.blue,\n                        shape: BoxShape.circle,',
                            'color: _verificationColor(p),\n                        shape: BoxShape.circle,', 1)
    header = header.replace('const Icon(Icons.verified_rounded, color: AppColors.blue, size: 20)',
                            'Icon(Icons.verified_rounded, color: _verificationColor(p), size: 20)', 1)
    text = text[:header_start] + header + text[header_end:]
w(path, text)


# ---------------------------------------------------------------------------
# 4) Server social endpoint: malformed/missing profile IDs must fail closed.
# The previous max(1, ...) could accidentally turn user_id=0 into user #1.
# ---------------------------------------------------------------------------
for path in ['backend/api/mobile_social_v31.php', 'flutter/backend/api/mobile_social_v31.php']:
    text = r(path)
    old = "$targetId=max(1,(int)($_POST['user_id']??0));"
    new = "$targetId=(int)($_POST['user_id']??0);if($targetId<=0)mobile_error('Choose a valid profile.',400);"
    if old not in text:
        raise RuntimeError(f'v4.6 profile ID validation marker missing in {path}')
    text = text.replace(old, new, 1)
    w(path, text)


# ---------------------------------------------------------------------------
# 5) Release version.
# ---------------------------------------------------------------------------
path = 'flutter/pubspec.yaml'
text = r(path)
text = re.sub(r'^version:\s*[^\n]+', 'version: 4.6.0+460', text, count=1, flags=re.M)
w(path, text)


# Regression guarantees.
api = r('flutter/lib/core/api_client.dart')
social = r('flutter/lib/core/social_api.dart')
profile = r('flutter/lib/screens/profile_screen.dart')
social_server = r('backend/api/mobile_social_v31.php')
pubspec = r('flutter/pubspec.yaml')
assert 'suspendedpage.cgi' in api and 'server returned a web page instead of API data' in api
assert 'on HandshakeException' in social and 'on TlsException' in social
assert 'status == 401 && _isSessionFailure(message)' in social
assert 'int _requestSerial = 0;' in profile
assert 'requestSerial != _requestSerial' in profile
assert 'color: _verificationColor(p)' in profile
assert "if($targetId<=0)mobile_error('Choose a valid profile.',400);" in social_server
assert 'version: 4.6.0+460' in pubspec
print('TaleemPK v4.6 deep stability audit fixes applied successfully')
