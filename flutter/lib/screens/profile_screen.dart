import 'package:flutter/material.dart';

import '../core/app_state.dart';
import '../core/models.dart';
import '../core/theme.dart';
import '../widgets/common.dart';
import 'home_shell.dart';
import 'module_screen.dart';

class ProfileScreen extends StatelessWidget {
  const ProfileScreen({super.key});
  @override
  Widget build(BuildContext context) {
    final state = AppScope.of(context), user = state.user!;
    return Scaffold(
      appBar: PremiumAppBar(
        title: 'Your profile',
        subtitle: 'Identity, privacy and support',
        actions: [
          IconButton(
            onPressed: state.toggleTheme,
            icon: Icon(
              state.darkMode
                  ? Icons.light_mode_outlined
                  : Icons.dark_mode_outlined,
            ),
          ),
          const SizedBox(width: 8),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(17, 8, 17, 28),
        children: [
          _profileCard(user),
          const SizedBox(height: 18),
          _section(context, 'Account', [
            _tile(
              Icons.manage_accounts_rounded,
              'Edit profile',
              'Name, headline, city and bio',
              () => _editProfile(context, user),
            ),
            _tile(
              Icons.verified_user_outlined,
              'Verification',
              user.verified
                  ? 'Your profile is verified'
                  : 'Build trust with a verified identity',
              () => showMessage(
                context,
                user.verified ? 'Your profile is already verified.' : 'Open Get Verified on the website to submit your documents.',
              ),
            ),
            _tile(
              Icons.notifications_active_outlined,
              'Notifications',
              'Your recent account activity',
              () => _open(context, 'notifications'),
            ),
          ]),
          const SizedBox(height: 14),
          _section(context, 'Privacy & help', [
            _tile(
              Icons.shield_outlined,
              'Privacy & security',
              'Control profile and online visibility',
              () => _privacy(context),
            ),
            _tile(
              Icons.support_agent_rounded,
              'Help & support',
              'Tickets, appeals and assistance',
              () => _open(context, 'support'),
            ),
          ]),
          const SizedBox(height: 18),
          OutlinedButton.icon(
            onPressed: () => _confirmLogout(context),
            icon: const Icon(Icons.logout_rounded, color: AppColors.danger),
            label: const Text(
              'Sign out',
              style: TextStyle(color: AppColors.danger),
            ),
            style: OutlinedButton.styleFrom(
              minimumSize: const Size.fromHeight(52),
              side: const BorderSide(color: Color(0x40E24B5B)),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(16),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _profileCard(User u) => Container(
    padding: const EdgeInsets.all(21),
    decoration: BoxDecoration(
      gradient: const LinearGradient(
        colors: [AppColors.navy, Color(0xFF193A78), Color(0xFF5939B1)],
        begin: Alignment.topLeft,
        end: Alignment.bottomRight,
      ),
      borderRadius: BorderRadius.circular(26),
      boxShadow: const [
        BoxShadow(
          color: Color(0x33264DD3),
          blurRadius: 25,
          offset: Offset(0, 12),
        ),
      ],
    ),
    child: Row(
      children: [
        Container(
          padding: const EdgeInsets.all(3),
          decoration: const BoxDecoration(
            shape: BoxShape.circle,
            gradient: LinearGradient(
              colors: [Color(0xFF64E6FF), Color(0xFFBDA9FF)],
            ),
          ),
          child: UserAvatar(url: u.avatar, name: u.name, radius: 34),
        ),
        const SizedBox(width: 16),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Flexible(
                    child: Text(
                      u.name,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                        color: Colors.white,
                        fontWeight: FontWeight.w900,
                        fontSize: 21,
                      ),
                    ),
                  ),
                  if (u.verified)
                    const Padding(
                      padding: EdgeInsets.only(left: 6),
                      child: Icon(
                        Icons.verified_rounded,
                        color: Color(0xFF61DBFF),
                        size: 20,
                      ),
                    ),
                ],
              ),
              const SizedBox(height: 4),
              Text(
                '@${u.username}',
                style: const TextStyle(color: Colors.white70),
              ),
              const SizedBox(height: 9),
              Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 10,
                  vertical: 5,
                ),
                decoration: BoxDecoration(
                  color: Colors.white.withValues(alpha: .13),
                  borderRadius: BorderRadius.circular(20),
                ),
                child: Text(
                  u.role.toUpperCase(),
                  style: const TextStyle(
                    color: Colors.white,
                    fontWeight: FontWeight.w800,
                    fontSize: 10,
                    letterSpacing: .7,
                  ),
                ),
              ),
            ],
          ),
        ),
      ],
    ),
  );

  Widget _section(BuildContext context, String title, List<Widget> items) =>
      Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.only(left: 4, bottom: 9),
            child: Text(
              title,
              style: const TextStyle(
                fontSize: 13,
                color: AppColors.muted,
                fontWeight: FontWeight.w800,
              ),
            ),
          ),
          Card(
            child: Column(
              children: [
                for (var i = 0; i < items.length; i++) ...[
                  items[i],
                  if (i < items.length - 1)
                    const Divider(indent: 64, height: 1),
                ],
              ],
            ),
          ),
        ],
      );
  Widget _tile(
    IconData icon,
    String title,
    String subtitle,
    VoidCallback tap,
  ) => ListTile(
    contentPadding: const EdgeInsets.symmetric(horizontal: 15, vertical: 5),
    leading: Container(
      width: 40,
      height: 40,
      decoration: BoxDecoration(
        color: const Color(0x123157E8),
        borderRadius: BorderRadius.circular(13),
      ),
      child: Icon(icon, color: AppColors.blue, size: 21),
    ),
    title: Text(title, style: const TextStyle(fontWeight: FontWeight.w700)),
    subtitle: Text(
      subtitle,
      maxLines: 1,
      overflow: TextOverflow.ellipsis,
      style: const TextStyle(fontSize: 12, color: AppColors.muted),
    ),
    trailing: const Icon(Icons.chevron_right_rounded, color: AppColors.muted),
    onTap: tap,
  );
  void _open(BuildContext context, String module) => Navigator.push(
    context,
    MaterialPageRoute(builder: (_) => ModuleScreen(module: module)),
  );

  Future<void> _editProfile(BuildContext context, User user) async {
    final name = TextEditingController(text: user.name),
        city = TextEditingController(),
        headline = TextEditingController(),
        bio = TextEditingController();
    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (sheet) => Padding(
        padding: EdgeInsets.fromLTRB(
          20,
          6,
          20,
          MediaQuery.viewInsetsOf(sheet).bottom + 22,
        ),
        child: SingleChildScrollView(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text(
                'Edit profile',
                style: Theme.of(sheet).textTheme.headlineSmall
                    ?.copyWith(fontWeight: FontWeight.w800),
              ),
              const SizedBox(height: 18),
              TextField(
                controller: name,
                decoration: const InputDecoration(labelText: 'Full name'),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: city,
                decoration: const InputDecoration(labelText: 'City'),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: headline,
                maxLength: 160,
                decoration: const InputDecoration(labelText: 'Headline'),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: bio,
                minLines: 4,
                maxLines: 7,
                maxLength: 480,
                decoration: const InputDecoration(labelText: 'About you'),
              ),
              const SizedBox(height: 10),
              FilledButton(
                onPressed: () async {
                  try {
                    await AppScope.of(context).api.updateProfile(
                      name.text.trim(),
                      city.text.trim(),
                      headline.text.trim(),
                      bio.text.trim(),
                    );
                    await AppScope.of(context).refreshSession();
                    if (sheet.mounted) Navigator.pop(sheet);
                  } catch (e) {
                    if (sheet.mounted) showMessage(sheet, apiMessage(e));
                  }
                },
                child: const Text('Save changes'),
              ),
            ],
          ),
        ),
      ),
    );
    name.dispose();
    city.dispose();
    headline.dispose();
    bio.dispose();
  }

  Future<void> _privacy(BuildContext context) async {
    await showModalBottomSheet<void>(
      context: context,
      showDragHandle: true,
      builder: (sheet) => SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(17, 4, 17, 18),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text(
                'Privacy & security',
                style: Theme.of(sheet).textTheme.headlineSmall
                    ?.copyWith(fontWeight: FontWeight.w800),
              ),
              const SizedBox(height: 12),
              ListTile(
                leading: const Icon(
                  Icons.visibility_outlined,
                  color: AppColors.blue,
                ),
                title: const Text('Profile privacy'),
                subtitle: const Text(
                  'Tap to cycle public, members and private',
                ),
                onTap: () async {
                  final data = await AppScope.of(context).api
                      .moduleAction('cycle_privacy');
                  if (sheet.mounted)
                    showMessage(
                      sheet,
                      'Profile visibility: ${data['privacy']}',
                    );
                },
              ),
              ListTile(
                leading: const Icon(
                  Icons.circle_outlined,
                  color: AppColors.success,
                ),
                title: const Text('Online status'),
                subtitle: const Text('Control whether others see you online'),
                onTap: () async {
                  final data = await AppScope.of(context).api
                      .moduleAction('toggle_online');
                  if (sheet.mounted)
                    showMessage(
                      sheet,
                      data['enabled'] == true
                          ? 'Online status is visible.'
                          : 'Online status is hidden.',
                    );
                },
              ),
              const ListTile(
                leading: Icon(Icons.key_rounded, color: AppColors.violet),
                title: Text('Secure device session'),
                subtitle: Text('Your password is never stored in this app.'),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Future<void> _confirmLogout(BuildContext context) async {
    final yes =
        await showDialog<bool>(
          context: context,
          builder: (d) => AlertDialog(
            title: const Text('Sign out?'),
            content: const Text(
              'This device session will be revoked. You can sign in again at any time.',
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(d, false),
                child: const Text('Cancel'),
              ),
              FilledButton(
                onPressed: () => Navigator.pop(d, true),
                child: const Text('Sign out'),
              ),
            ],
          ),
        ) ??
        false;
    if (yes && context.mounted) await AppScope.of(context).logout();
  }
}
