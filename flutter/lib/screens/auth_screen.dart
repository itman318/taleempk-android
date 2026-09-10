import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

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
                        if (!register)
                          Align(
                            alignment: Alignment.centerRight,
                            child: TextButton.icon(
                              onPressed: busy ? null : _forgotPassword,
                              icon: const Icon(Icons.key_rounded, size: 17),
                              label: const Text('Forgot password?'),
                            ),
                          ),
                        const SizedBox(height: 10),
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

  Future<void> _forgotPassword() async {
    final controller = TextEditingController(text: identifier.text.trim());
    final value = await showModalBottomSheet<String>(
      context: context,
      isScrollControlled: true,
      builder: (sheet) => Padding(
        padding: EdgeInsets.fromLTRB(
          24,
          26,
          24,
          MediaQuery.viewInsetsOf(sheet).bottom + 26,
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Icon(Icons.lock_reset_rounded, size: 48, color: AppColors.blue),
            const SizedBox(height: 14),
            Text(
              'Reset your password',
              style: Theme.of(sheet).textTheme.headlineSmall?.copyWith(
                    fontWeight: FontWeight.w800,
                  ),
            ),
            const SizedBox(height: 8),
            const Text(
              'Enter the email address linked to your TaleemPK account.',
              style: TextStyle(color: AppColors.muted),
            ),
            const SizedBox(height: 18),
            TextField(
              controller: controller,
              keyboardType: TextInputType.emailAddress,
              autofocus: true,
              decoration: const InputDecoration(
                labelText: 'Email address',
                prefixIcon: Icon(Icons.mail_outline_rounded),
              ),
            ),
            const SizedBox(height: 14),
            FilledButton(
              onPressed: () => Navigator.pop(sheet, controller.text.trim()),
              child: const Text('Send reset link'),
            ),
          ],
        ),
      ),
    );
    controller.dispose();
    if (value == null || value.isEmpty || !mounted) return;
    setState(() => busy = true);
    try {
      final message = await AppScope.of(context).api.forgotPassword(value);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(message)),
        );
      }
    } on ApiException catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(e.message)),
        );
      }
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

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
    var verifying = false;
    String? inlineError;

    Future<void> submit(StateSetter setLocal, BuildContext sheetContext) async {
      final value = code.text.trim();
      if (value.length != 6) {
        setLocal(() => inlineError = 'Enter the complete 6-digit security code.');
        return;
      }
      FocusManager.instance.primaryFocus?.unfocus();
      setLocal(() {
        verifying = true;
        inlineError = null;
      });
      try {
        await AppScope.of(context).finishTwoFactor(challenge, value);
        if (sheetContext.mounted) Navigator.of(sheetContext).pop();
      } on ApiException catch (e) {
        if (sheetContext.mounted) {
          setLocal(() {
            verifying = false;
            inlineError = e.message;
          });
        }
      } catch (_) {
        if (sheetContext.mounted) {
          setLocal(() {
            verifying = false;
            inlineError = 'Verification could not be completed. Check your connection and try again.';
          });
        }
      }
    }

    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      isDismissible: true,
      enableDrag: true,
      showDragHandle: true,
      builder: (sheetContext) => StatefulBuilder(
        builder: (context, setLocal) => Padding(
          padding: EdgeInsets.fromLTRB(
            24,
            10,
            24,
            MediaQuery.viewInsetsOf(sheetContext).bottom + 24,
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Align(
                alignment: Alignment.center,
                child: Container(
                  width: 64,
                  height: 64,
                  decoration: BoxDecoration(
                    color: AppColors.blue.withValues(alpha: .10),
                    shape: BoxShape.circle,
                  ),
                  child: const Icon(Icons.verified_user_rounded, size: 34, color: AppColors.blue),
                ),
              ),
              const SizedBox(height: 16),
              Text(
                'Verify it’s you',
                textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w900),
              ),
              const SizedBox(height: 7),
              const Text(
                'Enter the 6-digit security code sent to your email. The code expires in 10 minutes.',
                textAlign: TextAlign.center,
                style: TextStyle(color: AppColors.muted, height: 1.4),
              ),
              const SizedBox(height: 20),
              TextField(
                controller: code,
                keyboardType: TextInputType.number,
                textInputAction: TextInputAction.done,
                inputFormatters: const [FilteringTextInputFormatter.digitsOnly],
                autofillHints: const [AutofillHints.oneTimeCode],
                enableSuggestions: false,
                autocorrect: false,
                maxLength: 6,
                autofocus: true,
                onChanged: (_) => setLocal(() => inlineError = null),
                onSubmitted: (_) {
                  if (!verifying && code.text.trim().length == 6) {
                    submit(setLocal, sheetContext);
                  }
                },
                decoration: InputDecoration(
                  labelText: '6-digit code',
                  hintText: '000000',
                  prefixIcon: const Icon(Icons.password_rounded),
                  errorText: inlineError,
                  suffixIcon: IconButton(
                    tooltip: 'Paste code',
                    onPressed: verifying
                        ? null
                        : () async {
                            final data = await Clipboard.getData('text/plain');
                            final digits = (data?.text ?? '').replaceAll(RegExp(r'\D'), '');
                            if (digits.length >= 6) {
                              code.text = digits.substring(0, 6);
                              code.selection = TextSelection.collapsed(offset: code.text.length);
                              if (sheetContext.mounted) setLocal(() => inlineError = null);
                            }
                          },
                    icon: const Icon(Icons.content_paste_rounded),
                  ),
                ),
              ),
              if (verifying) ...[
                const SizedBox(height: 4),
                const LinearProgressIndicator(minHeight: 2),
                const SizedBox(height: 8),
                const Text(
                  'Verifying securely…',
                  textAlign: TextAlign.center,
                  style: TextStyle(fontSize: 11.5, color: AppColors.muted),
                ),
              ],
              const SizedBox(height: 12),
              FilledButton.icon(
                onPressed: verifying || code.text.trim().length != 6
                    ? null
                    : () => submit(setLocal, sheetContext),
                icon: verifying
                    ? const SizedBox(
                        width: 18,
                        height: 18,
                        child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                      )
                    : const Icon(Icons.shield_rounded),
                label: Text(verifying ? 'Verifying…' : 'Verify and continue'),
              ),
              const SizedBox(height: 6),
              const Text(
                'For your security, only the newest email code should be used.',
                textAlign: TextAlign.center,
                style: TextStyle(fontSize: 10.5, color: AppColors.muted),
              ),
            ],
          ),
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
