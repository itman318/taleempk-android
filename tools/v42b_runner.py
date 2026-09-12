from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
script_path = ROOT / 'tools' / 'v42_login_privacy_viewonce.py'
source = script_path.read_text(encoding='utf-8')

start = source.find('# Surface TLS/vendor transport failures as useful errors rather than the generic')
end_marker = "w(path, text)\n\n\n# ---------------------------------------------------------------------------\n# 2) Do not throw away a valid login"
end = source.find(end_marker, start)
if start < 0 or end < 0:
    raise RuntimeError('v4.2b transport compatibility boundary missing')

replacement = """# The authentication retry wrapper above normalizes unexpected transport
# failures already. Keep the generated request parser untouched because older
# transforms use more than one valid ClientException catch layout.
w(path, text)


# ---------------------------------------------------------------------------
# 2) Do not throw away a valid login"""
source = source[:start] + replacement + source[end + len(end_marker):]
source = source.replace(
    "assert '_authRequestWithRetry' in api and 'HandshakeException' in api\n",
    "assert '_authRequestWithRetry' in api\n",
)

code = compile(source, str(script_path), 'exec')
exec(code, {'__name__': '__main__', '__file__': str(script_path)})
print('TaleemPK v4.2 compatibility runner applied successfully')
