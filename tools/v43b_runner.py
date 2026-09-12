from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
script_path = ROOT / 'tools' / 'v43_chat_stability.py'
source = script_path.read_text(encoding='utf-8')

old = "cs, ce = function_bounds(text, '  Widget _composer() => Container(')"
new = "cs, ce = function_bounds(text, '  Widget _composer() {')"
if old not in source:
    raise RuntimeError('v4.3b composer compatibility marker missing')
source = source.replace(old, new, 1)

# The original outbox helper is expression-bodied, so the replacement must
# retain its terminating semicolon or the rest of ChatScreen parses as members.
outbox_old = """        ),
      )'''\ntext = replace_function(text, '  Widget _outboxBar() => Container(', outbox_bar)"""
outbox_new = """        ),
      );'''\ntext = replace_function(text, '  Widget _outboxBar() => Container(', outbox_bar)"""
if outbox_old not in source:
    raise RuntimeError('v4.3b outbox terminator marker missing')
source = source.replace(outbox_old, outbox_new, 1)

code = compile(source, str(script_path), 'exec')
exec(code, {'__name__': '__main__', '__file__': str(script_path)})
print('TaleemPK v4.3 generated composer/outbox compatibility runner applied successfully')
