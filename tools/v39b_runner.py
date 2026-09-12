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

replacement = r'''# Include timezone metadata on authentication calls. The server still uses the
# connection IP for the security alert's network area; timezone is a useful
# diagnostic hint but is not treated as a physical location. The first two
# NativeBridge.deviceName() fields belong to login and verify_2fa; use a
# line-level replacement so formatting changes from older transforms cannot
# silently skip the metadata.
device_line = "      'device': await NativeBridge.deviceName(),\n"
if text.count(device_line) < 2:
    raise RuntimeError('v3.9 authentication device fields missing')
auth_metadata = (
    device_line
    + "      'client': 'TaleemPK Android app',\n"
    + "      'tz_offset': '${DateTime.now().timeZoneOffset.inMinutes}',\n"
    + "      'tz_name': DateTime.now().timeZoneName,\n"
)
text = text.replace(device_line, auth_metadata, 2)
w(path, text)

'''
source = source[:start] + replacement + source[end:]

exec(
    compile(source, str(source_path), 'exec'),
    {'__file__': str(source_path), '__name__': '__main__'},
)

api = (ROOT / 'flutter/lib/core/api_client.dart').read_text(encoding='utf-8')
if api.count("'client': 'TaleemPK Android app'") < 2:
    raise RuntimeError('v3.9b authentication client metadata was not generated')
if api.count("'tz_offset':") < 2 or api.count("'tz_name':") < 2:
    raise RuntimeError('v3.9b authentication timezone metadata was not generated')
print('TaleemPK v3.9 authentication metadata fix applied successfully')
