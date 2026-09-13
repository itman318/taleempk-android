import 'package:flutter/material.dart';

import '../core/app_state.dart';
import '../core/theme.dart';
import '../widgets/common.dart';
import 'home_shell.dart';

class SecurityScreen extends StatefulWidget {
  const SecurityScreen({super.key});

  @override
  State<SecurityScreen> createState() => _SecurityScreenState();
}

class _SecurityScreenState extends State<SecurityScreen> {
  Map<String, dynamic>? settings;
  List<Map<String, dynamic>> sessions = const [];
  bool loading = true, saving = false;
  String? error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    if (mounted) {
      setState(() {
        loading = true;
        error = null;
      });
    }
    try {
      final api = AppScope.of(context).api;
      final result = await Future.wait<Object>([
        api.privacySettings(),
        api.mobileSessions(),
      ]);
      settings = (result[0] as Map<String, dynamic>);
      sessions = (result[1] as List<Map<String, dynamic>>);
    } catch (e) {
      error = apiMessage(e);
    }
    if (mounted) setState(() => loading = false);
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: PremiumAppBar(
          title: 'Privacy & security',
          subtitle: 'Control who can reach you and protect your account',
          actions: [
            IconButton(
              tooltip: 'Refresh',
              onPressed: loading ? null : _load,
              icon: const Icon(Icons.refresh_rounded),
            ),
            const SizedBox(width: 6),
          ],
        ),
        body: loading
            ? const Center(child: CircularProgressIndicator())
            : error != null
                ? ErrorView(message: error!, retry: _load)
                : RefreshIndicator(
                    onRefresh: _load,
                    child: ListView(
                      padding: const EdgeInsets.fromLTRB(16, 8, 16, 30),
                      children: [
                        _privacyCard(),
                        const SizedBox(height: 16),
                        _sessionsCard(),
                        const SizedBox(height: 16),
                        _passwordCard(),
                        const SizedBox(height: 18),
                        _securityNote(),
                      ],
                    ),
                  ),
      );

  Widget _privacyCard() {
    final s = settings ?? const <String, dynamic>{};
    return Card(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const _SectionTitle(
              icon: Icons.tune_rounded,
              title: 'Privacy controls',
              subtitle: 'These settings sync with TaleemPK on the web.',
            ),
            const SizedBox(height: 14),
            _choice(
              label: 'Profile visibility',
              value: '${s['profile_privacy'] ?? 'public'}',
              values: const {
                'public': 'Public',
                'members': 'Members only',
                'private': 'Private',
              },
              onChanged: (v) => _savePrivacy('profile_privacy', v),
            ),
            _choice(
              label: 'Who can message you',
              value: '${s['allow_dm'] ?? 'everyone'}',
              values: const {
                'everyone': 'Everyone',
                'following': 'People you follow',
                'nobody': 'Nobody',
              },
              onChanged: (v) => _savePrivacy('allow_dm', v),
            ),
            _choice(
              label: 'Who can call you',
              value: '${s['allow_calls'] ?? 'everyone'}',
              values: const {
                'everyone': 'Everyone',
                'following': 'People you follow',
                'nobody': 'Nobody',
              },
              onChanged: (v) => _savePrivacy('allow_calls', v),
            ),
            _choice(
              label: 'Who can comment',
              value: '${s['allow_comments'] ?? 'everyone'}',
              values: const {
                'everyone': 'Everyone',
                'followers': 'Followers',
                'nobody': 'Nobody',
              },
              onChanged: (v) => _savePrivacy('allow_comments', v),
            ),
            SwitchListTile.adaptive(
              contentPadding: EdgeInsets.zero,
              value: _bool(s['show_online'], true),
              onChanged: saving ? null : (v) => _savePrivacy('show_online', v ? '1' : '0'),
              title: const Text('Show online status'),
              subtitle: const Text('Let others see when you are active.'),
            ),
            SwitchListTile.adaptive(
              contentPadding: EdgeInsets.zero,
              value: _bool(s['searchable'], true),
              onChanged: saving ? null : (v) => _savePrivacy('searchable', v ? '1' : '0'),
              title: const Text('Searchable profile'),
              subtitle: const Text('Allow your profile to appear in people search.'),
            ),
            SwitchListTile.adaptive(
              contentPadding: EdgeInsets.zero,
              value: _bool(s['show_receipts'], true),
              onChanged: saving ? null : (v) => _savePrivacy('show_receipts', v ? '1' : '0'),
              title: const Text('Read & played receipts'),
              subtitle: const Text('Share message read and voice played status.'),
            ),
            SwitchListTile.adaptive(
              contentPadding: EdgeInsets.zero,
              value: _bool(s['show_typing'], true),
              onChanged: saving ? null : (v) => _savePrivacy('show_typing', v ? '1' : '0'),
              title: const Text('Typing & recording indicators'),
              subtitle: const Text('Share live typing and voice-recording presence.'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _sessionsCard() => Card(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(16, 16, 16, 10),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const _SectionTitle(
                icon: Icons.devices_rounded,
                title: 'Signed-in devices',
                subtitle: 'Review and revoke mobile sessions you no longer use.',
              ),
              const SizedBox(height: 10),
              if (sessions.isEmpty)
                const Padding(
                  padding: EdgeInsets.symmetric(vertical: 16),
                  child: Text(
                    'No mobile sessions were returned.',
                    style: TextStyle(color: AppColors.muted),
                  ),
                )
              else
                for (final session in sessions) ...[
                  ListTile(
                    contentPadding: EdgeInsets.zero,
                    leading: Container(
                      width: 42,
                      height: 42,
                      decoration: BoxDecoration(
                        color: AppColors.blue.withValues(alpha: .10),
                        borderRadius: BorderRadius.circular(13),
                      ),
                      child: Icon(
                        session['current'] == true
                            ? Icons.smartphone_rounded
                            : Icons.devices_other_rounded,
                        color: session['current'] == true
                            ? AppColors.success
                            : AppColors.blue,
                      ),
                    ),
                    title: Text(
                      '${session['device'] ?? 'Mobile device'}',
                      style: const TextStyle(fontWeight: FontWeight.w800),
                    ),
                    subtitle: Text(
                      session['current'] == true
                          ? 'This device · active now'
                          : 'Last active ${session['last_seen'] ?? 'recently'}',
                    ),
                    trailing: session['current'] == true
                        ? const Chip(label: Text('Current'))
                        : IconButton(
                            tooltip: 'Sign out this device',
                            onPressed: () => _revokeSession('${session['session_id'] ?? ''}'),
                            icon: const Icon(
                              Icons.logout_rounded,
                              color: AppColors.danger,
                            ),
                          ),
                  ),
                  if (session != sessions.last) const Divider(height: 1),
                ],
            ],
          ),
        ),
      );

  Widget _passwordCard() => Card(
        child: ListTile(
          contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 9),
          leading: Container(
            width: 42,
            height: 42,
            decoration: BoxDecoration(
              color: AppColors.violet.withValues(alpha: .10),
              borderRadius: BorderRadius.circular(13),
            ),
            child: const Icon(Icons.password_rounded, color: AppColors.violet),
          ),
          title: const Text(
            'Change password',
            style: TextStyle(fontWeight: FontWeight.w800),
          ),
          subtitle: const Text('Update your password and sign out other devices.'),
          trailing: const Icon(Icons.chevron_right_rounded),
          onTap: _changePassword,
        ),
      );

  Widget _securityNote() => Container(
        padding: const EdgeInsets.all(15),
        decoration: BoxDecoration(
          color: AppColors.success.withValues(alpha: .08),
          borderRadius: BorderRadius.circular(18),
          border: Border.all(color: AppColors.success.withValues(alpha: .18)),
        ),
        child: const Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(Icons.shield_outlined, color: AppColors.success),
            SizedBox(width: 10),
            Expanded(
              child: Text(
                'Your mobile token is stored in Android secure storage. Changing your password can revoke every other mobile session without affecting this device.',
                style: TextStyle(height: 1.45),
              ),
            ),
          ],
        ),
      );

  Widget _choice({
    required String label,
    required String value,
    required Map<String, String> values,
    required ValueChanged<String> onChanged,
  }) {
    final safeValue = values.containsKey(value) ? value : values.keys.first;
    return ListTile(
      contentPadding: EdgeInsets.zero,
      title: Text(label),
      trailing: DropdownButton<String>(
        value: safeValue,
        underline: const SizedBox.shrink(),
        items: values.entries
            .map((entry) => DropdownMenuItem(
                  value: entry.key,
                  child: Text(entry.value),
                ))
            .toList(),
        onChanged: saving
            ? null
            : (next) {
                if (next != null) onChanged(next);
              },
      ),
    );
  }

  Future<void> _savePrivacy(String key, String value) async {
    if (saving) return;
    setState(() => saving = true);
    try {
      final next = await AppScope.of(context).api.updatePrivacySetting(key, value);
      settings = next;
    } catch (e) {
      if (mounted) showMessage(context, apiMessage(e));
    }
    if (mounted) setState(() => saving = false);
  }

  Future<void> _revokeSession(String sessionId) async {
    if (sessionId.length != 64) return;
    final yes = await showDialog<bool>(
          context: context,
          builder: (dialog) => AlertDialog(
            title: const Text('Sign out this device?'),
            content: const Text(
              'That device will need your password to sign in again.',
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(dialog, false),
                child: const Text('Cancel'),
              ),
              FilledButton(
                onPressed: () => Navigator.pop(dialog, true),
                child: const Text('Sign out'),
              ),
            ],
          ),
        ) ??
        false;
    if (!yes || !mounted) return;
    try {
      await AppScope.of(context).api.revokeMobileSession(sessionId);
      await _load();
    } catch (e) {
      if (mounted) showMessage(context, apiMessage(e));
    }
  }

  Future<void> _changePassword() async {
    final current = TextEditingController();
    final next = TextEditingController();
    final confirm = TextEditingController();
    var hideCurrent = true;
    var hideNext = true;
    var signOutOthers = true;
    final submitted = await showModalBottomSheet<bool>(
          context: context,
          isScrollControlled: true,
          showDragHandle: true,
          builder: (sheet) => StatefulBuilder(
            builder: (context, setLocal) => Padding(
              padding: EdgeInsets.fromLTRB(
                18,
                4,
                18,
                MediaQuery.viewInsetsOf(context).bottom + 22,
              ),
              child: SingleChildScrollView(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Text(
                      'Change password',
                      style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                            fontWeight: FontWeight.w900,
                          ),
                    ),
                    const SizedBox(height: 16),
                    TextField(
                      controller: current,
                      obscureText: hideCurrent,
                      autofillHints: const [AutofillHints.password],
                      decoration: InputDecoration(
                        labelText: 'Current password',
                        suffixIcon: IconButton(
                          onPressed: () => setLocal(() => hideCurrent = !hideCurrent),
                          icon: Icon(hideCurrent
                              ? Icons.visibility_outlined
                              : Icons.visibility_off_outlined),
                        ),
                      ),
                    ),
                    const SizedBox(height: 12),
                    TextField(
                      controller: next,
                      obscureText: hideNext,
                      autofillHints: const [AutofillHints.newPassword],
                      decoration: InputDecoration(
                        labelText: 'New password',
                        suffixIcon: IconButton(
                          onPressed: () => setLocal(() => hideNext = !hideNext),
                          icon: Icon(hideNext
                              ? Icons.visibility_outlined
                              : Icons.visibility_off_outlined),
                        ),
                      ),
                    ),
                    const SizedBox(height: 12),
                    TextField(
                      controller: confirm,
                      obscureText: true,
                      autofillHints: const [AutofillHints.newPassword],
                      decoration: const InputDecoration(
                        labelText: 'Confirm new password',
                      ),
                    ),
                    CheckboxListTile(
                      contentPadding: EdgeInsets.zero,
                      value: signOutOthers,
                      onChanged: (value) =>
                          setLocal(() => signOutOthers = value ?? true),
                      title: const Text('Sign out other mobile devices'),
                    ),
                    const SizedBox(height: 8),
                    FilledButton.icon(
                      onPressed: () {
                        if (next.text != confirm.text) {
                          showMessage(sheet, 'The new passwords do not match.');
                          return;
                        }
                        Navigator.pop(sheet, true);
                      },
                      icon: const Icon(Icons.lock_reset_rounded),
                      label: const Text('Update password'),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ) ??
        false;
    if (submitted && mounted) {
      try {
        await AppScope.of(context).api.changePassword(
              current.text,
              next.text,
              signOutOthers: signOutOthers,
            );
        if (mounted) {
          showMessage(context, 'Password updated securely.');
          await _load();
        }
      } catch (e) {
        if (mounted) showMessage(context, apiMessage(e));
      }
    }
    current.dispose();
    next.dispose();
    confirm.dispose();
  }

  bool _bool(dynamic value, bool fallback) {
    if (value is bool) return value;
    if (value is int) return value != 0;
    final text = '$value'.toLowerCase();
    if (text == '1' || text == 'true') return true;
    if (text == '0' || text == 'false') return false;
    return fallback;
  }

  int _int(dynamic value) => value is int ? value : int.tryParse('$value') ?? 0;
}

class _SectionTitle extends StatelessWidget {
  const _SectionTitle({
    required this.icon,
    required this.title,
    required this.subtitle,
  });

  final IconData icon;
  final String title, subtitle;

  @override
  Widget build(BuildContext context) => Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 42,
            height: 42,
            decoration: BoxDecoration(
              color: AppColors.blue.withValues(alpha: .10),
              borderRadius: BorderRadius.circular(13),
            ),
            child: Icon(icon, color: AppColors.blue),
          ),
          const SizedBox(width: 11),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: const TextStyle(fontWeight: FontWeight.w900),
                ),
                const SizedBox(height: 2),
                Text(
                  subtitle,
                  style: const TextStyle(
                    fontSize: 12,
                    height: 1.35,
                    color: AppColors.muted,
                  ),
                ),
              ],
            ),
          ),
        ],
      );
}
