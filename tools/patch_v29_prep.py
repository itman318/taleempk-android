from pathlib import Path
import re

path = Path(__file__).resolve().parents[1] / 'flutter/lib/screens/module_screen.dart'
text = path.read_text()
replacement = r'''  Future<void> _open(ModuleItem item) async {
    if (item.kind == 'task') {
      try {
        await AppScope.of(context).api.moduleAction('toggle_task', id: item.id);
        _load();
      } catch (e) {
        showMessage(context, apiMessage(e));
      }
      return;
    }
    if (item.kind == 'setting') {
      try {
        if (item.id == 2) {
          await AppScope.of(context).api.moduleAction('cycle_privacy');
        } else if (item.id == 3) {
          await AppScope.of(context).api.moduleAction('toggle_online');
        } else {
          showMessage(context, 'Two-step verification is managed from the TaleemPK website.');
          return;
        }
        _load();
      } catch (e) {
        showMessage(context, apiMessage(e));
      }
      return;
    }
    if (item.kind == 'notification') {
      try {
        await AppScope.of(context).api.moduleAction('read_notification', id: item.id);
        _load();
      } catch (e) {
        showMessage(context, apiMessage(e));
      }
      return;
    }
    final route = switch (item.kind) {
      'resource' => 'resource.php?id=${item.id}',
      'quiz' => 'quiz-take.php?id=${item.id}',
      'group' => 'group.php?id=${item.id}',
      'board' => 'results.php?board=${item.id}',
      'ticket' => 'support.php?id=${item.id}',
      _ => '',
    };
    if (route.isNotEmpty) {
      final uri = Uri.parse('https://taleempk.online/$route');
      final opened = await launchUrl(uri, mode: LaunchMode.externalApplication);
      if (!opened && mounted) showMessage(context, 'Could not open this item.');
    }
  }
'''
new, count = re.subn(
    r"  Future<void> _open\(ModuleItem item\) async \{.*?\n  \}\n\n  Future<void> _newTicket",
    lambda _: replacement + "\n  Future<void> _newTicket",
    text,
    count=1,
    flags=re.S,
)
if count != 1:
    raise RuntimeError(f'module prep expected one match, got {count}')
path.write_text(new)
print('module route normalized for v2.9 patch')
