from pathlib import Path

script = Path(__file__).with_name('v44_realtime_push.py')
code = script.read_text(encoding='utf-8')

old = '''# Healthy WebSocket receives immediate invalidations; keep a slightly slower
# fallback poll for web/older clients and transient socket misses.
text, count = re.subn(
    r'Duration\\(milliseconds: immediate \\? 80 : \\d+\\)',
    "Duration(\\n        milliseconds: immediate\\n            ? 80\\n            : (RealtimeService.instance.connected ? 1400 : 950),\\n      )",
    text,
    count=1,
)
if count == 0 and 'RealtimeService.instance.connected ? 1400 : 950' not in text:
    raise RuntimeError('v4.4 chat poll duration marker missing')
w(path, text)
'''

new = '''# Healthy WebSocket receives immediate invalidations; keep a polling fallback
# for web/older clients and transient socket misses. Replace the whole function
# because earlier release transforms intentionally changed its timing shape.
schedule_poll = r\'''  void _schedulePoll({bool immediate = false}) {
    poll?.cancel();
    if (!mounted || !foreground) return;
    poll = Timer(
      Duration(
        milliseconds: immediate
            ? 70
            : (RealtimeService.instance.connected ? 1800 : 950),
      ),
      _poll,
    );
  }\'''
text = replace_function(text, '  void _schedulePoll(', schedule_poll)
w(path, text)
'''

if old not in code:
    raise RuntimeError('v4.4 compatibility target missing')
code = code.replace(old, new, 1)
exec(compile(code, str(script), 'exec'), {'__name__': '__main__', '__file__': str(script)})
print('TaleemPK v4.4 compatibility runner applied successfully')
