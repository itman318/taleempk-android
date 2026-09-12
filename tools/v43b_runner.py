from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
script_path = ROOT / 'tools' / 'v43_chat_stability.py'
source = script_path.read_text(encoding='utf-8')

old = "cs, ce = function_bounds(text, '  Widget _composer() => Container(')"
new = "cs, ce = function_bounds(text, '  Widget _composer() {')"
if old not in source:
    raise RuntimeError('v4.3b composer compatibility marker missing')
source = source.replace(old, new, 1)

code = compile(source, str(script_path), 'exec')
exec(code, {'__name__': '__main__', '__file__': str(script_path)})
print('TaleemPK v4.3 generated composer compatibility runner applied successfully')
