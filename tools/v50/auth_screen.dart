import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../core/api_client.dart';
import '../core/app_state.dart';
import '../core/form_rules.dart';
import '../core/theme.dart';
import '../widgets/form_components.dart';

class AuthScreen extends StatefulWidget {
  const AuthScreen({super.key});
  @override
  State<AuthScreen> createState() => _AuthScreenState();
}

class _AuthScreenState extends State<AuthScreen> {
  bool register = false, busy = false, hidden = true;
  int step = 0;
  String role = 'student';
  String? notice;
  bool failed = false;
  final formKey = GlobalKey<FormState>();
  final scroll = ScrollController();
  final identifier = TextEditingController(), password = TextEditingController(),
      confirm = TextEditingController(), name = TextEditingController(),
      username = TextEditingController(), email = TextEditingController(),
      phone = TextEditingController(), dob = TextEditingController();
  DateTime? birthday;

  @override
  void dispose() {
    for (final c in [identifier, password, confirm, name, username, email, phone, dob]) {
      c.dispose();
    }
    scroll.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    return Scaffold(body: Stack(children: [
      const ExcludeSemantics(child: _StudyBackdrop()),
      SafeArea(child: Center(child: SingleChildScrollView(controller: scroll,
        keyboardDismissBehavior: ScrollViewKeyboardDismissBehavior.onDrag,
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 28),
        child: ConstrainedBox(constraints: const BoxConstraints(maxWidth: 480),
          child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
            const Center(child: BrandMark(size: 44, light: true)),
            const SizedBox(height: 24),
            Container(padding: const EdgeInsets.all(22),
              decoration: BoxDecoration(color: colors.surface,
                borderRadius: BorderRadius.circular(28),
                border: Border.all(color: colors.outlineVariant.withValues(alpha: .6)),
                boxShadow: const [BoxShadow(color: Color(0x28000000), blurRadius: 32, offset: Offset(0, 14))]),
              child: AutofillGroup(child: Form(key: formKey,
                child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                  Text(register ? 'A place to grow.' : 'Welcome back.',
                    style: Theme.of(context).textTheme.headlineMedium),
                  const SizedBox(height: 8),
                  Text(register ? 'Create your TaleemPK account, one simple step at a time.'
                    : 'Your learning community is waiting for you.',
                    style: TextStyle(color: colors.onSurfaceVariant, height: 1.5)),
                  const SizedBox(height: 24),
                  if (register) ...[
                    FlowSteps(labels: const ['Profile', 'Contact', 'Security'], current: step),
                    const SizedBox(height: 24),
                  ],
                  if (notice != null) ...[
                    FormNotice(notice!, isError: failed), const SizedBox(height: 18),
                  ],
                  // Distinct keys prevent validators/autofill state leaking between steps.
                  KeyedSubtree(key: ValueKey('$register-$step'), child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: register ? _registrationFields() : [
                      _field(identifier, 'Email or username', Icons.person_outline,
                        validator: (v) => (v ?? '').trim().isEmpty ? 'Enter your email or username.' : null,
                        autofill: const [AutofillHints.username]),
                      _passwordField(),
                      Align(alignment: Alignment.centerRight, child: TextButton(
                        onPressed: busy ? null : _forgot, child: const Text('Forgot password?'))),
                    ],
                  )),
                  const SizedBox(height: 8),
                  PrimaryAction(label: busy ? (register ? 'Creating account…' : 'Signing in…')
                      : register ? (step < 2 ? 'Continue' : 'Create account') : 'Sign in',
                    busy: busy, onPressed: _next),
                  if (register && step > 0) TextButton.icon(
                    onPressed: busy ? null : () => _changeStep(step - 1),
                    icon: const Icon(Icons.arrow_back_rounded, size: 18), label: const Text('Previous step')),
                  const SizedBox(height: 10),
                  TextButton(onPressed: busy ? null : () {
                    FocusManager.instance.primaryFocus?.unfocus();
                    setState(() { register = !register; step = 0; notice = null; hidden = true; });
                  }, child: Text(register ? 'Already have an account? Sign in' : 'New here? Create an account',
                    textAlign: TextAlign.center)),
                ]))),
            ),
            const SizedBox(height: 20),
            const Text('Learn. Share. Move forward.', textAlign: TextAlign.center,
              style: TextStyle(color: Color(0xFFD3DEFA), fontSize: 13, letterSpacing: .3)),
          ])),
      ))),
    ]));
  }

  List<Widget> _registrationFields() {
    if (step == 0) { return [
      Text('I’m joining as', style: Theme.of(context).textTheme.titleMedium),
      const SizedBox(height: 12),
      RoleSelector(value: role, onChanged: busy ? null : (v) => setState(() => role = v)),
      const SizedBox(height: 10),
      _field(name, 'Full name', Icons.badge_outlined, validator: FormRules.name,
        autofill: const [AutofillHints.name], capitalization: TextCapitalization.words),
      _field(username, 'Username', Icons.alternate_email, validator: FormRules.username,
        helper: '3–30 letters, numbers or underscores', autofill: const [AutofillHints.newUsername]),
    ]; }
    if (step == 1) { return [
      _field(email, 'Email address', Icons.mail_outline, validator: FormRules.email,
        type: TextInputType.emailAddress, autofill: const [AutofillHints.email]),
      _field(phone, 'Phone (if required)', Icons.phone_outlined,
        type: TextInputType.phone, autofill: const [AutofillHints.telephoneNumber]),
      Padding(padding: const EdgeInsets.only(bottom: 16), child: TextFormField(
        controller: dob, readOnly: true, enabled: !busy,
        validator: (v) => birthday == null ? 'Select your date of birth.' : null,
        onTap: _pickBirthday,
        decoration: const InputDecoration(labelText: 'Date of birth', hintText: 'Choose a date',
          prefixIcon: Icon(Icons.calendar_today_outlined), suffixIcon: Icon(Icons.expand_more)))),
      const FormNotice('Use an email you can access for verification and account recovery.'),
      const SizedBox(height: 12),
    ]; }
    return [
      const FormNotice('Use at least 10 characters. Avoid common passwords and personal details.',
        icon: Icons.lock_outline_rounded),
      const SizedBox(height: 18),
      _passwordField(),
      _field(confirm, 'Confirm password', Icons.lock_outline,
        secret: true, validator: (v) => v != password.text ? 'The passwords do not match.' : null,
        autofill: const [AutofillHints.newPassword]),
      Text('Creating an account for ${email.text}', style: TextStyle(
        color: Theme.of(context).colorScheme.onSurfaceVariant, fontSize: 13)),
      const SizedBox(height: 12),
    ];
  }

  Widget _field(TextEditingController controller, String label, IconData icon, {
    String? Function(String?)? validator, TextInputType? type, String? helper,
    bool secret = false, Iterable<String>? autofill,
    TextCapitalization capitalization = TextCapitalization.none,
  }) => Padding(padding: const EdgeInsets.only(bottom: 16), child: TextFormField(
    controller: controller, enabled: !busy, validator: validator, keyboardType: type,
    obscureText: secret && hidden, autocorrect: false, enableSuggestions: !secret,
    textCapitalization: capitalization, autofillHints: autofill,
    textInputAction: TextInputAction.next,
    autovalidateMode: AutovalidateMode.onUserInteraction,
    decoration: InputDecoration(labelText: label, helperText: helper,
      helperMaxLines: 3, errorMaxLines: 3, prefixIcon: Icon(icon)),
  ));

  Widget _passwordField() => Padding(padding: const EdgeInsets.only(bottom: 16),
    child: TextFormField(controller: password, enabled: !busy, obscureText: hidden,
      autocorrect: false, enableSuggestions: false,
      autofillHints: [register ? AutofillHints.newPassword : AutofillHints.password],
      validator: (v) => FormRules.password(v, creating: register),
      textInputAction: register ? TextInputAction.next : TextInputAction.done,
      onFieldSubmitted: (_) { if (!register) _next(); },
      decoration: InputDecoration(labelText: 'Password', errorMaxLines: 3,
        prefixIcon: const Icon(Icons.lock_outline_rounded),
        suffixIcon: IconButton(tooltip: hidden ? 'Show password' : 'Hide password',
          onPressed: busy ? null : () => setState(() => hidden = !hidden),
          icon: Icon(hidden ? Icons.visibility_outlined : Icons.visibility_off_outlined))),
    ));

  Future<void> _pickBirthday() async {
    final now = DateTime.now();
    final chosen = await showDatePicker(context: context,
      initialDate: birthday ?? DateTime(now.year - 18, now.month, now.day),
      firstDate: DateTime(1900), lastDate: now, helpText: 'Select your date of birth');
    if (!mounted || chosen == null) return;
    setState(() { birthday = chosen; dob.text = FormRules.dateLabel(chosen); });
  }

  void _changeStep(int value) {
    FocusManager.instance.primaryFocus?.unfocus();
    setState(() { step = value; notice = null; });
    _showTop();
  }

  void _showTop() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted && scroll.hasClients) scroll.jumpTo(0);
    });
  }

  Future<void> _next() async {
    if (busy || !(formKey.currentState?.validate() ?? false)) return;
    if (register && step < 2) { _changeStep(step + 1); return; }
    FocusManager.instance.primaryFocus?.unfocus();
    final app = AppScope.of(context);
    setState(() { busy = true; notice = null; });
    try {
      if (register) {
        final message = await app.api.register(role: role, name: name.text.trim(),
          username: username.text.trim(), email: email.text.trim(), phone: phone.text.trim(),
          dob: dob.text, password: password.text);
        if (!mounted) return;
        setState(() { register = false; step = 0; identifier.text = email.text.trim();
          password.clear(); confirm.clear(); notice = message; failed = false; });
      } else {
        final result = await app.login(identifier.text.trim(), password.text);
        if (mounted && result.needsTwoFactor && result.challenge != null) {
          await showModalBottomSheet<void>(context: context, isScrollControlled: true,
            isDismissible: false, enableDrag: false, useSafeArea: true,
            builder: (_) => _AccountSheet(app: app, challenge: result.challenge));
        }
      }
    } on ApiException catch (e) {
      if (mounted) setState(() { notice = e.message; failed = true; });
    } catch (_) {
      if (mounted) setState(() { notice = 'We couldn’t complete this request. Check your connection and try again.'; failed = true; });
    } finally {
      if (mounted) { setState(() => busy = false); if (notice != null) _showTop(); }
    }
  }

  Future<void> _forgot() async {
    final app = AppScope.of(context);
    await showModalBottomSheet<void>(context: context, isScrollControlled: true,
      isDismissible: false, enableDrag: false, useSafeArea: true,
      builder: (_) => _AccountSheet(app: app, initialEmail: identifier.text.trim()));
  }
}

/// Owns its controllers until the modal's exit animation has finished.
class _AccountSheet extends StatefulWidget {
  const _AccountSheet({required this.app, this.challenge, this.initialEmail = ''});
  final AppState app;
  final String? challenge;
  final String initialEmail;
  @override
  State<_AccountSheet> createState() => _AccountSheetState();
}

class _AccountSheetState extends State<_AccountSheet> {
  late final input = TextEditingController(text: otp ? '' : widget.initialEmail);
  final key = GlobalKey<FormState>();
  bool busy = false, success = false;
  String? error, message;
  bool get otp => widget.challenge != null;
  @override
  void dispose() { input.dispose(); super.dispose(); }
  @override
  Widget build(BuildContext context) => PopScope(canPop: !busy,
    child: SingleChildScrollView(padding: EdgeInsets.fromLTRB(24, 12, 24,
      MediaQuery.viewInsetsOf(context).bottom + MediaQuery.paddingOf(context).bottom + 24),
      child: Form(key: key, child: Column(mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          Align(alignment: Alignment.centerRight, child: IconButton(tooltip: 'Close',
            onPressed: busy ? null : () => Navigator.pop(context), icon: const Icon(Icons.close))),
          Icon(otp ? Icons.verified_user_outlined : Icons.lock_reset_rounded,
            size: 44, color: Theme.of(context).colorScheme.primary),
          const SizedBox(height: 18),
          Text(otp ? 'Verify it’s you' : 'Reset your password',
            style: Theme.of(context).textTheme.headlineSmall, textAlign: TextAlign.center),
          const SizedBox(height: 10),
          Text(otp ? 'Enter the 6-digit code sent to your email. Check your spam folder too.'
            : 'We’ll email recovery instructions for your account.', textAlign: TextAlign.center),
          const SizedBox(height: 22),
          if (error != null) ...[FormNotice(error!, isError: true), const SizedBox(height: 14)],
          if (message != null) ...[FormNotice(message!), const SizedBox(height: 14)],
          if (!success) ...[
            TextFormField(controller: input, enabled: !busy,
              keyboardType: otp ? TextInputType.number : TextInputType.emailAddress,
              autocorrect: false, enableSuggestions: false,
              autofillHints: [otp ? AutofillHints.oneTimeCode : AutofillHints.email],
              inputFormatters: otp ? [FilteringTextInputFormatter.digitsOnly,
                LengthLimitingTextInputFormatter(6)] : null,
              validator: otp ? (v) => RegExp(r'^\d{6}$').hasMatch(v ?? '') ? null : 'Enter all 6 digits.' : FormRules.email,
              onFieldSubmitted: (_) => _submit(), textInputAction: TextInputAction.done,
              decoration: InputDecoration(labelText: otp ? '6-digit code' : 'Email address', errorMaxLines: 3,
                prefixIcon: Icon(otp ? Icons.password : Icons.mail_outline),
                suffixIcon: otp ? IconButton(tooltip: 'Paste code', onPressed: busy ? null : _paste,
                  icon: const Icon(Icons.content_paste_rounded)) : null)),
            const SizedBox(height: 18),
            PrimaryAction(label: busy ? 'Please wait…' : otp ? 'Verify and continue' : 'Send reset link',
              busy: busy, onPressed: _submit),
          ] else PrimaryAction(label: 'Back to sign in', onPressed: () => Navigator.pop(context)),
        ])),
    ));

  Future<void> _paste() async {
    final data = await Clipboard.getData('text/plain');
    if (!mounted || busy) return;
    final digits = (data?.text ?? '').replaceAll(RegExp(r'\D'), '');
    if (digits.length == 6) input.text = digits;
  }

  Future<void> _submit() async {
    if (busy || !(key.currentState?.validate() ?? false)) return;
    FocusManager.instance.primaryFocus?.unfocus();
    setState(() { busy = true; error = null; });
    try {
      if (otp) {
        await widget.app.finishTwoFactor(widget.challenge!, input.text.trim());
        if (mounted) Navigator.pop(context);
      } else {
        final result = await widget.app.api.forgotPassword(input.text.trim());
        if (mounted) setState(() { message = result; success = true; });
      }
    } on ApiException catch (e) {
      if (mounted) setState(() => error = e.message);
    } catch (_) {
      if (mounted) setState(() => error = 'Couldn’t connect. Please try again.');
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }
}
