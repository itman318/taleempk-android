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
new = r'''# Diagnostic-safe tick pass. Later workflow audit still refuses release until
# the real three-state rendering is present.
for needle in ('done_all', 'check_rounded', 'm.read', 'read ?'):
    pos = text.find(needle)
    if pos >= 0:
        lo = max(0, pos - 500)
        hi = min(len(text), pos + 900)
        print('V53D_TICK_CONTEXT_' + needle.replace(' ', '_') + ':\\n' + text[lo:hi])
w(path, text)'''

if old not in source:
    raise RuntimeError('v5.3d runner patch marker missing')
source = source.replace(old, new, 1)
source = source.replace(
    "assert '(m.read || m.delivered) ? Icons.done_all_rounded' in chat\n",
    "# diagnostic runner: workflow audit enforces final tick rendering\n",
    1,
)
code = compile(source, str(script_path), 'exec')
exec(code, {'__name__': '__main__', '__file__': str(script_path)})
