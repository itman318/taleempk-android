from pathlib import Path
p=Path('flutter/lib/screens/chat_screen.dart')
t=p.read_text(encoding='utf-8')
s=t.find('  Future<void> _reviewImages(')
e=t.find('  Future<String?> _editPhoto(',s)
r=t[s:e]
lines=r.splitlines()
print('REVIEW_SECTION_START')
for no,line in enumerate(lines,1):
    if any(k in line for k in ['editAt(', 'itemBuilder', 'onTap:', 'paths[i]', 'selected = i', 'AnimatedContainer', 'ListView.separated']):
        start=max(1,no-4); end=min(len(lines),no+7)
        print(f'--- lines {start}-{end} around {no} ---')
        for idx in range(start,end+1):
            print(f'{idx:04d}: {lines[idx-1]}')
print('REVIEW_SECTION_END')
