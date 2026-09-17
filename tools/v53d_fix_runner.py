from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
script_path = ROOT / 'tools' / 'v53d_ui_push_delivery_audit.py'
source = script_path.read_text(encoding='utf-8')

old = r'''old_tick = """                  Icon(
                    m.read ? Icons.done_all_rounded : Icons.check_rounded,
                    size: 15,
                    color: m.read ? const Color(0xFF75E9FF) : Colors.white70,
                  ),"""
new_tick = """                  Icon(
                    (m.read || m.delivered) ? Icons.done_all_rounded : Icons.check_rounded,
                    size: 15,
                    color: m.read ? const Color(0xFF75E9FF) : Colors.white70,
                  ),"""
text = once(text, old_tick, new_tick, 'three-state message tick')
w(path, text)'''
new = r'''tick_expr = 'm.read ? Icons.done_all_rounded : Icons.check_rounded'
if tick_expr not in text:
    raise RuntimeError('v5.3d missing three-state message tick expression')
text = text.replace(
    tick_expr,
    '(m.read || m.delivered) ? Icons.done_all_rounded : Icons.check_rounded',
    1,
)
w(path, text)'''

if old not in source:
    raise RuntimeError('v5.3d runner patch marker missing')
source = source.replace(old, new, 1)
code = compile(source, str(script_path), 'exec')
exec(code, {'__name__': '__main__', '__file__': str(script_path)})
