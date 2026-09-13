from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
script_path = ROOT / 'tools' / 'v40_audio_login_performance.py'
source = script_path.read_text(encoding='utf-8')

old = """for signature, old_limit, new_limit, old_done, new_done in [
    ('  Future<void> _load({bool jumpToBottom = false}) async {', 'limit: 80', 'limit: 60', 'fresh.length < 80', 'fresh.length < 60'),
    ('  Future<void> _loadOlder() async {', 'limit: 80', 'limit: 60', 'older.length < 80', 'older.length < 60'),
]:
    fs, fe = function_bounds(text, signature)
    chunk = text[fs:fe]
    if old_limit not in chunk or old_done not in chunk:
        raise RuntimeError(f'v4.0 chat chunk target missing: {signature}')
    chunk = chunk.replace(old_limit, new_limit, 1).replace(old_done, new_done, 1)
    text = text[:fs] + chunk + text[fe:]
"""
new = """for signature, old_limit, new_limit, old_done, new_done in [
    ('  Future<void> _load({bool jumpToBottom = false}) async {', 'limit: 80', 'limit: 60', 'fresh.length < 80', 'fresh.length < 60'),
    ('  Future<void> _loadOlder() async {', 'limit: 80', 'limit: 60', 'older.length < 80', 'older.length < 60'),
]:
    fs, fe = function_bounds(text, signature)
    chunk = text[fs:fe]
    # Later UI transforms may already use a lighter page size. Only lower the
    # cost when these legacy 80-message markers are still present.
    if old_limit in chunk:
        chunk = chunk.replace(old_limit, new_limit, 1)
    if old_done in chunk:
        chunk = chunk.replace(old_done, new_done, 1)
    text = text[:fs] + chunk + text[fe:]
"""
if old not in source:
    raise RuntimeError('v4 runner compatibility block not found')
source = source.replace(old, new, 1)
source = source.replace("assert 'fresh.length < 60' in chat and 'older.length < 60' in chat\n", "")

code = compile(source, str(script_path), 'exec')
exec(code, {'__name__': '__main__', '__file__': str(script_path)})
