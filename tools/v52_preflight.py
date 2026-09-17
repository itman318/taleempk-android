from pathlib import Path

path = Path('flutter/lib/screens/module_screen.dart')
text = path.read_text()
start_marker = "    if (item.kind == 'notification') {"
end_marker = "\n\n    final route = item.route.isNotEmpty"
start = text.find(start_marker)
end = text.find(end_marker, start)
if start < 0 or end < 0:
    raise SystemExit('Could not locate generated notification handler')
# Normalize the post-v5.1 handler to the v5.2 generator's expected input.
legacy = """    if (item.kind == 'notification') {
      try {
        await AppScope.of(context).api.moduleAction('read_notification', id: item.id);
        _load();
      } catch (e) {
        showMessage(context, apiMessage(e));
      }
      return;
    }"""
text = text[:start] + legacy + text[end:]
path.write_text(text)
print('v5.2 preflight compatibility applied')
