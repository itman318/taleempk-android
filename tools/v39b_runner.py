from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
source_path = ROOT / 'tools/v39_identity_speed_verification.py'
source = source_path.read_text(encoding='utf-8')

start_marker = '# Include timezone metadata on authentication calls. The server still uses the\n'
end_marker = '# Apply a realistic Android browser-style UA before the shared website\n'
start = source.find(start_marker)
end = source.find(end_marker, start)
if start < 0 or end < 0:
    raise RuntimeError('v3.9b could not locate authentication metadata transform')

replacement = r'''# Canonicalize authentication requests instead of depending on the formatting
# produced by earlier transformations. This guarantees that both password login
# and 2FA send the real native device label plus app/timezone metadata.
login_pattern = r"  Future<AuthResult> login\(String identifier, String password\) async \{.*?\n  \}\n\n  Future<AuthResult> verifyTwoFactor"
login_replacement = """  Future<AuthResult> login(String identifier, String password) async {
    final data = await _request({
      'action': 'login',
      'identifier': identifier.trim(),
      'password': password,
      'device': await NativeBridge.deviceName(),
      'client': 'TaleemPK Android app',
      'tz_offset': '${DateTime.now().timeZoneOffset.inMinutes}',
      'tz_name': DateTime.now().timeZoneName,
    }, authenticated: false);
    return _authResult(data);
  }

  Future<AuthResult> verifyTwoFactor"""
text, login_count = re.subn(login_pattern, login_replacement, text, count=1, flags=re.S)
if login_count != 1:
    raise RuntimeError('v3.9 login method boundary missing')

verify_pattern = r"  Future<AuthResult> verifyTwoFactor\(String challenge, String code\) async \{.*?\n  \}\n\n  Future<String> forgotPassword"
verify_replacement = """  Future<AuthResult> verifyTwoFactor(String challenge, String code) async {
    final data = await _request({
      'action': 'verify_2fa',
      'challenge': challenge,
      'code': code.trim(),
      'device': await NativeBridge.deviceName(),
      'client': 'TaleemPK Android app',
      'tz_offset': '${DateTime.now().timeZoneOffset.inMinutes}',
      'tz_name': DateTime.now().timeZoneName,
    }, authenticated: false);
    return _authResult(data);
  }

  Future<String> forgotPassword"""
text, verify_count = re.subn(verify_pattern, verify_replacement, text, count=1, flags=re.S)
if verify_count != 1:
    raise RuntimeError('v3.9 verifyTwoFactor method boundary missing')
w(path, text)

'''
source = source[:start] + replacement + source[end:]

# Replace the original compact assertion/readback block with explicit
# diagnostics below. The original block starts at its first final readback.
validation_start = source.find("api = r('flutter/lib/core/api_client.dart')")
if validation_start < 0:
    raise RuntimeError('v3.9b final validation block missing')
source = source[:validation_start] + "print('TaleemPK v3.9 transform generation finished')\n"

exec(
    compile(source, str(source_path), 'exec'),
    {'__file__': str(source_path), '__name__': '__main__'},
)

checks = {
    'api': (ROOT / 'flutter/lib/core/api_client.dart').read_text(encoding='utf-8'),
    'common': (ROOT / 'flutter/lib/widgets/common.dart').read_text(encoding='utf-8'),
    'verification': (ROOT / 'flutter/lib/screens/verification_screen.dart').read_text(encoding='utf-8'),
    'security': (ROOT / 'flutter/lib/screens/security_screen.dart').read_text(encoding='utf-8'),
    'mobile': (ROOT / 'backend/api/mobile.php').read_text(encoding='utf-8'),
    'pubspec': (ROOT / 'flutter/pubspec.yaml').read_text(encoding='utf-8'),
}
api = checks['api']
if api.count("'client': 'TaleemPK Android app'") < 2:
    raise RuntimeError('v3.9b authentication client metadata was not generated')
if api.count("'device': await NativeBridge.deviceName()") < 2:
    raise RuntimeError('v3.9b native device metadata was not generated')
if api.count("'tz_offset':") < 2 or api.count("'tz_name':") < 2:
    raise RuntimeError('v3.9b authentication timezone metadata was not generated')
if "'User-Agent': 'TaleemPKAndroid/3.9'" not in api:
    raise RuntimeError('v3.9b native User-Agent header missing')
if 'PageRoute<T> premiumRoute<T>' not in checks['common']:
    raise RuntimeError('v3.9b premium fast route helper missing')
if 'Something needs attention' not in checks['common']:
    raise RuntimeError('v3.9b polished global error view missing')
if '_VerificationStep' not in checks['verification'] or 'AB1234567' not in checks['verification']:
    raise RuntimeError('v3.9b verification form polish missing')
if 'Enter your teaching role or designation.' not in checks['verification']:
    raise RuntimeError('v3.9b verification role validation missing')
if 'network/IP area' not in checks['security']:
    raise RuntimeError('v3.9b security location accuracy copy missing')
if 'TaleemPKAndroid/3.9' not in checks['mobile']:
    raise RuntimeError('v3.9b server native User-Agent identity hook missing')
if "$signin['device'] = $safeDevice;" not in checks['mobile']:
    raise RuntimeError('v3.9b server device alert override missing')
if "$signin['browser'] = 'TaleemPK Android app';" not in checks['mobile']:
    raise RuntimeError('v3.9b server browser alert override missing')
if "'api_version' => '3.9'" not in checks['mobile']:
    raise RuntimeError('v3.9b server API version missing')
if 'version: 3.9.0+390' not in checks['pubspec']:
    raise RuntimeError('v3.9b release version missing')
print('TaleemPK v3.9 explicit regression diagnostics passed successfully')
