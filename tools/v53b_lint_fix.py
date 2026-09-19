from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / 'flutter/lib/screens/global_search_screen.dart'
text = path.read_text(encoding='utf-8')
old = 'separatorBuilder:(_,__)=>const Divider(height:1)'
new = 'separatorBuilder:(_,_)=>const Divider(height:1)'
if old not in text:
    raise RuntimeError('v5.3 lint-fix anchor missing in global search screen')
text = text.replace(old, new, 1)
path.write_text(text, encoding='utf-8')
assert 'separatorBuilder:(_,__)' not in text
print('TaleemPK v5.3 global search analyzer lint fixed')
