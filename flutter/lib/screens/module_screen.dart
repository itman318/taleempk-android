import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import '../core/app_state.dart';
import '../core/models.dart';
import '../core/theme.dart';
import '../widgets/common.dart';
import 'home_shell.dart';

class ModuleScreen extends StatefulWidget {
  const ModuleScreen({super.key, required this.module});
  final String module;
  @override
  State<ModuleScreen> createState() => _ModuleScreenState();
}

class _ModuleScreenState extends State<ModuleScreen> {
  ModuleData? data;
  String? error;
  bool loading = true;
  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      loading = true;
      error = null;
    });
    try {
      data = await AppScope.of(context).api.module(widget.module);
    } catch (e) {
      error = apiMessage(e);
    }
    if (mounted) setState(() => loading = false);
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: PremiumAppBar(
      title: data?.title ?? _fallbackTitle(),
      subtitle: data?.subtitle,
      actions: [
        IconButton(onPressed: _load, icon: const Icon(Icons.refresh_rounded)),
        const SizedBox(width: 8),
      ],
    ),
    body: loading
        ? const Center(child: CircularProgressIndicator())
        : error != null
        ? ErrorView(message: error!, retry: _load)
        : data!.items.isEmpty
        ? EmptyView(
            icon: _icon(widget.module),
            title: 'Nothing here yet',
            message: 'New items will appear here as they are added.',
          )
        : RefreshIndicator(
            onRefresh: _load,
            child: ListView.separated(
              padding: const EdgeInsets.fromLTRB(18, 8, 18, 28),
              itemCount: data!.items.length,
              separatorBuilder: (_, __) => const SizedBox(height: 10),
              itemBuilder: (_, i) => _item(data!.items[i]),
            ),
          ),
    floatingActionButton: widget.module == 'support'
        ? FloatingActionButton.extended(
            onPressed: _newTicket,
            icon: const Icon(Icons.add_comment_rounded),
            label: const Text('New request'),
          )
        : null,
  );

  Widget _item(ModuleItem item) => Card(
    child: InkWell(
      borderRadius: BorderRadius.circular(22),
      onTap: () => _open(item),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Row(
          children: [
            Container(
              width: 48,
              height: 48,
              decoration: BoxDecoration(
                color: item.done
                    ? const Color(0x1517A673)
                    : const Color(0x123157E8),
                borderRadius: BorderRadius.circular(15),
              ),
              child: Icon(
                item.done ? Icons.check_circle_rounded : _kindIcon(item.kind),
                color: item.done ? AppColors.success : AppColors.blue,
              ),
            ),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    item.title,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(fontWeight: FontWeight.w800),
                  ),
                  if (item.subtitle.isNotEmpty) ...[
                    const SizedBox(height: 4),
                    Text(
                      item.subtitle,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                        color: AppColors.muted,
                        fontSize: 13,
                      ),
                    ),
                  ],
                  if (item.meta.isNotEmpty) ...[
                    const SizedBox(height: 6),
                    Text(
                      item.meta,
                      style: const TextStyle(
                        color: AppColors.blue,
                        fontSize: 11.5,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ],
                ],
              ),
            ),
            const SizedBox(width: 8),
            const Icon(Icons.chevron_right_rounded, color: AppColors.muted),
          ],
        ),
      ),
    ),
  );

  Future<void> _open(ModuleItem item) async {
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

    if (item.kind == 'quiz' && item.route.isEmpty) {
      showMessage(
        context,
        'This quiz needs the latest TaleemPK mobile API. Update api/mobile.php, then refresh.',
      );
      return;
    }

    final route = item.route.isNotEmpty
        ? item.route
        : switch (item.kind) {
            'resource' => 'resource.php?id=${item.id}',
            'group' => 'group.php?id=${item.id}',
            'board' => 'results.php?board=${item.id}',
            'ticket' => 'support.php?id=${item.id}',
            _ => '',
          };
    if (route.isNotEmpty) {
      final uri = Uri.parse('https://taleempk.online/$route');
      final opened = await launchUrl(uri, mode: LaunchMode.externalApplication);
      if (!opened && mounted) {
        showMessage(context, 'Could not open this item.');
      }
    }
  }

  Future<void> _newTicket() async {
    final subject = TextEditingController(), body = TextEditingController();
    String topic = 'bug';
    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      builder: (c) => StatefulBuilder(
        builder: (c, setModal) => Padding(
          padding: EdgeInsets.fromLTRB(
            22,
            24,
            22,
            MediaQuery.viewInsetsOf(c).bottom + 24,
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text(
                'New support request',
                style: Theme.of(c).textTheme.headlineSmall
                    ?.copyWith(fontWeight: FontWeight.w800),
              ),
              const SizedBox(height: 18),
              DropdownButtonFormField<String>(
                initialValue: topic,
                items: const [
                  DropdownMenuItem(
                    value: 'bug',
                    child: Text('Technical issue'),
                  ),
                  DropdownMenuItem(
                    value: 'account',
                    child: Text('Account help'),
                  ),
                  DropdownMenuItem(value: 'appeal', child: Text('Appeal')),
                  DropdownMenuItem(value: 'other', child: Text('Other')),
                ],
                onChanged: (v) => setModal(() => topic = v ?? 'other'),
                decoration: const InputDecoration(labelText: 'Topic'),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: subject,
                decoration: const InputDecoration(labelText: 'Subject'),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: body,
                minLines: 4,
                maxLines: 7,
                decoration: const InputDecoration(
                  labelText: 'Describe how we can help',
                ),
              ),
              const SizedBox(height: 18),
              FilledButton(
                onPressed: () async {
                  try {
                    final m = await AppScope.of(context).api
                        .createTicket(topic, subject.text, body.text);
                    if (c.mounted) Navigator.pop(c);
                    if (mounted) {
                      showMessage(context, m);
                      _load();
                    }
                  } catch (e) {
                    if (c.mounted) showMessage(c, apiMessage(e));
                  }
                },
                child: const Text('Submit request'),
              ),
            ],
          ),
        ),
      ),
    );
    subject.dispose();
    body.dispose();
  }

  String _fallbackTitle() => widget.module.isEmpty
      ? 'TaleemPK'
      : '${widget.module[0].toUpperCase()}${widget.module.substring(1)}';
  IconData _icon(String key) => switch (key) {
    'library' => Icons.local_library_rounded,
    'quizzes' => Icons.quiz_rounded,
    'groups' => Icons.groups_rounded,
    'planner' => Icons.event_note_rounded,
    'results' => Icons.workspace_premium_rounded,
    'notifications' => Icons.notifications_rounded,
    'support' => Icons.support_agent_rounded,
    _ => Icons.school_rounded,
  };
  IconData _kindIcon(String key) => switch (key) {
    'resource' => Icons.description_rounded,
    'quiz' => Icons.quiz_rounded,
    'group' => Icons.groups_rounded,
    'board' => Icons.account_balance_rounded,
    'ticket' => Icons.support_agent_rounded,
    'notification' => Icons.notifications_rounded,
    _ => Icons.auto_stories_rounded,
  };
}
