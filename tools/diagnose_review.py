from pathlib import Path
p=Path('flutter/lib/screens/chat_screen.dart')
t=p.read_text(encoding='utf-8')
s=t.find('  Future<void> _reviewImages(')
e=t.find('  Future<String?> _editPhoto(',s)
r=t[s:e]
i=r.find('selected = i')
print('REVIEW_SELECTED_INDEX',i)
print('REVIEW_SNIPPET_START')
print(r[max(0,i-700):i+900])
print('REVIEW_SNIPPET_END')
