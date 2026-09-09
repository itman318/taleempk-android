import 'package:flutter/material.dart';

import '../core/api_client.dart';
import '../core/app_state.dart';
import '../core/theme.dart';

class AuthScreen extends StatefulWidget {
  const AuthScreen({super.key});
  @override
  State<AuthScreen> createState() => _AuthScreenState();
}

class _AuthScreenState extends State<AuthScreen> {
  bool register = false, busy = false, hidePassword = true;
  String role = 'student';
  final formKey = GlobalKey<FormState>();
  final identifier = TextEditingController(),
      password = TextEditingController(),
      name = TextEditingController(),
      username = TextEditingController(),
      email = TextEditingController(),
      phone = TextEditingController(),
      dob = TextEditingController();

  @override
  void dispose() {
    for (final c in [identifier, password, name, username, email, phone, dob]) {
      c.dispose();
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    body: Stack(
      children: [
        const _StudyBackdrop(),
        SafeArea(
          child: Center(
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(22),
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 480),
                child: Container(
                  padding: const EdgeInsets.fromLTRB(24, 28, 24, 24),
                  decoration: BoxDecoration(
                    color: Colors.white.withValues(alpha: .97),
                    borderRadius: BorderRadius.circular(30),
                    boxShadow: const [
                      BoxShadow(
                        color: Color(0x44000000),
                        blurRadius: 40,
                        offset: Offset(0, 18),
                      ),
                    ],
                  ),
                  child: Form(
                    key: formKey,
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        const Center(child: BrandMark(size: 54)),
                        const SizedBox(height: 24),
                        Text(
                          register ? 'Create your account' : 'Welcome back',
                          style: Theme.of(context).textTheme.headlineMedium,
                        ),
                        const SizedBox(height: 7),
                        Text(
                          register
                              ? 'Join students, teachers and institutes across Pakistan.'
                              : 'Continue your learning journey.',
                          style: const TextStyle(color: AppColors.muted),
                        ),
                        const SizedBox(height: 24),
                        if (register) ...[
                          SegmentedButton<String>(
                            segments: const [
                              ButtonSegment(
                                value: 'student',
                                label: Text('Student'),
                                icon: Icon(Icons.school_outlined),
                              ),
                              ButtonSegment(
                                value: 'teacher',
                                label: Text('Teacher'),
                                icon: Icon(Icons.co_present_outlined),
                              ),
                              ButtonSegment(
                                value: 'institute',
                                label: Text('Institute'),
                                icon: Icon(Icons.account_balance_outlined),
                              ),
                            ],
                            selected: {role},
                            onSelectionChanged: (v) =>
                                setState(() => role = v.first),
                            showSelectedIcon: false,
                          ),
                          const SizedBox(height: 16),
                          _field(name, 'Full name', Icons.badge_outlined),
                          const SizedBox(height: 12),
                          _field(
                            username,
                            'Username',
                            Icons.alternate_email_rounded,
                          ),
                          const SizedBox(height: 12),
                          _field(
                            email,
                            'Email address',
                            Icons.mail_outline_rounded,
                            type: TextInputType.emailAddress,
                          ),
                          const SizedBox(height: 12),
                          _field(
                            phone,
                            'Phone (if required)',
                            Icons.phone_outlined,
                            required: false,
                            type: TextInputType.phone,
                          ),
                          const SizedBox(height: 12),
                          _field(
                            dob,
                            'Date of birth (DD-MM-YYYY)',
                            Icons.calendar_today_outlined,
                          ),
                          const SizedBox(height: 12),
                        ] else ...[
                          _field(
                            identifier,
                            'Email or username',
                            Icons.person_outline_rounded,
                          ),
                          const SizedBox(height: 14),
                        ],
                        TextFormField(
                          controller: password,
                          obscureText: hidePassword,
                          validator: (v) => (v?.length ?? 0) < 8
                              ? 'Enter at least 8 characters.'
                              : null,
                          decoration: InputDecoration(
                            labelText: 'Password',
                            prefixIcon: const Icon(Icons.lock_outline_rounded),
                            suffixIcon: IconButton(
                              onPressed: () =>
                                  setState(() => hidePassword = !hidePassword),
                              icon: Icon(
                                hidePassword
                                    ? Icons.visibility_outlined
                                    : Icons.visibility_off_outlined,
                              ),
                            ),
                          ),
                        ),
                        const SizedBox(height: 22),
                        FilledButton(
                          onPressed: busy ? null : _submit,
                          child: busy
                              ? const SizedBox(
                                  width: 24,
                                  height: 24,
                                  child: CircularProgressIndicator(
                                    strokeWidth: 2,
                                    color: Colors.white,
                                  ),
                                )
                              : Text(
                                  register
                                      ? 'Create account'
                                      : 'Sign in securely',
                                ),
                        ),
                        const SizedBox(height: 10),
                        TextButton(
                          onPressed: busy
                              ? null
                              : () => setState(() => register = !register),
                          child: Text(
                            register
                                ? 'Already a member? Sign in'
                                : 'New to TaleemPK? Create account',
                          ),
                        ),
                        if (!register)
                          const Center(
                            child: Text(
                              'Protected by secure, revocable device access',
                              style: TextStyle(
                                fontSize: 12,
                                color: AppColors.muted,
                              ),
                            ),
                          ),
                      ],
                    ),
                  ),
                ),
              ),
            ),
          ),
        ),
      ],
    ),
  );

  Widget _field(
    TextEditingController controller,
    String label,
    IconData icon, {
    bool required = true,
    TextInputType? type,
  }) => TextFormField(
    controller: controller,
    keyboardType: type,
    validator: (v) => required && (v?.trim().isEmpty ?? true)
        ? 'This field is required.'
        : null,
    decoration: InputDecoration(labelText: label, prefixIcon: Icon(icon)),
  );

  Future<void> _submit() async {
    if (!formKey.currentState!.validate()) return;
    setState(() => busy = true);
    try {
      final state = AppScope.of(context);
      if (register) {
        final message = await state.api.register(
          role: role,
          name: name.text.trim(),
          username: username.text.trim(),
          email: email.text.trim(),
          phone: phone.text.trim(),
          dob: dob.text.trim(),
          password: password.text,
        );
        if (!mounted) return;
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(message)));
        setState(() {
          register = false;
          identifier.text = email.text;
        });
      } else {
        final result = await state.login(identifier.text, password.text);
        if (result.needsTwoFactor && result.challenge != null && mounted)
          await _showTwoFactor(result.challenge!);
      }
    } on ApiException catch (e) {
      if (mounted)
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(e.message)));
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> _showTwoFactor(String challenge) async {
    final code = TextEditingController();
    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      builder: (sheetContext) => Padding(
        padding: EdgeInsets.fromLTRB(
          24,
          28,
          24,
          MediaQuery.viewInsetsOf(sheetContext).bottom + 28,
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Icon(
              Icons.verified_user_rounded,
              size: 48,
              color: AppColors.blue,
            ),
            const SizedBox(height: 14),
            Text(
              'Verify it’s you',
              style: Theme.of(context).textTheme.headlineSmall
                  ?.copyWith(fontWeight: FontWeight.w800),
            ),
            const SizedBox(height: 8),
            const Text(
              'Enter the security code sent to your email.',
              style: TextStyle(color: AppColors.muted),
            ),
            const SizedBox(height: 20),
            TextField(
              controller: code,
              keyboardType: TextInputType.number,
              maxLength: 6,
              autofocus: true,
              decoration: const InputDecoration(
                labelText: '6-digit code',
                prefixIcon: Icon(Icons.password_rounded),
              ),
            ),
            const SizedBox(height: 10),
            FilledButton(
              onPressed: () async {
                try {
                  await AppScope.of(context)
                      .finishTwoFactor(challenge, code.text);
                  if (sheetContext.mounted) Navigator.pop(sheetContext);
                } on ApiException catch (e) {
                  if (sheetContext.mounted)
                    ScaffoldMessenger.of(sheetContext)
                        .showSnackBar(SnackBar(content: Text(e.message)));
                }
              },
              child: const Text('Verify and continue'),
            ),
          ],
        ),
      ),
    );
    code.dispose();
  }
}

class _StudyBackdrop extends StatelessWidget {
  const _StudyBackdrop();
  @override
  Widget build(BuildContext context) => Container(
    decoration: const BoxDecoration(
      gradient: LinearGradient(
        colors: [Color(0xFF06122C), Color(0xFF17346C), Color(0xFF5932B2)],
        begin: Alignment.topLeft,
        end: Alignment.bottomRight,
      ),
    ),
    child: Stack(
      children: [
        Positioned(
          top: 55,
          left: -12,
          child: _icon(Icons.menu_book_rounded, 72, .10),
        ),
        Positioned(
          top: 130,
          right: 12,
          child: _icon(Icons.science_rounded, 68, .12),
        ),
        Positioned(
          bottom: 70,
          left: 26,
          child: _icon(Icons.calculate_rounded, 74, .10),
        ),
        Positioned(
          bottom: 130,
          right: -8,
          child: _icon(Icons.language_rounded, 84, .12),
        ),
      ],
    ),
  );
  Widget _icon(IconData icon, double size, double opacity) => Icon(
    icon,
    size: size,
    color: Colors.white.withValues(alpha: opacity),
  );
}
