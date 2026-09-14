from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / 'flutter/lib/screens/chat_screen.dart'
text = path.read_text(encoding='utf-8')
lines = text.splitlines()
out = []
found = {'suggestions': False, 'insert': False}
for line in lines:
    stripped = line.strip()
    if '_mentionSuggestions(' in stripped and stripped.endswith('{') and not found['suggestions']:
        out.append('  // ignore: unused_element -- kept for group @mention support')
        found['suggestions'] = True
    if '_insertMention(' in stripped and stripped.endswith('{') and not found['insert']:
        out.append('  // ignore: unused_element -- kept for group @mention support')
        found['insert'] = True
    out.append(line)
if not all(found.values()):
    raise RuntimeError(f'v3.7c mention helper declarations not found: {found}')
path.write_text('\n'.join(out) + '\n', encoding='utf-8')
print('TaleemPK v3.7 analyzer cleanup applied successfully')
