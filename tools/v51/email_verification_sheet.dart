import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../core/api_client.dart';
import '../widgets/form_components.dart';

class EmailVerificationSheet extends StatefulWidget {
  const EmailVerificationSheet({super.key, required this.api, required this.identifier,
    required this.password, this.address, this.needsReview = false});
  final ApiClient api;
  final String identifier, password;
  final String? address;
  final bool needsReview;
  @override
  State<EmailVerificationSheet> createState() => _EmailVerificationSheetState();
}
class _EmailVerificationSheetState extends State<EmailVerificationSheet> {
  final code = TextEditingController();
  final form = GlobalKey<FormState>();
  bool busy = false, failed = false;
  String? notice;
  int seconds = 0;
  Timer? timer;
  @override
  void dispose() { timer?.cancel(); code.dispose(); super.dispose(); }
  Future<void> _submit({bool resend = false}) async {
    if (busy || (resend && seconds > 0)) return;
    if (!resend && !(form.currentState?.validate() ?? false)) return;
    FocusManager.instance.primaryFocus?.unfocus();
    setState(() { busy = true; notice = null; });
    try {
      final message = await widget.api.confirmEmail(identifier: widget.identifier,
        password: widget.password, code: resend ? null : code.text.trim());
      if (!mounted) return;
      if (!resend) { Navigator.pop(context, true); return; }
      setState(() { notice = message; failed = false; seconds = 60; });
      timer?.cancel();
      timer = Timer.periodic(const Duration(seconds: 1), (t) {
        if (!mounted) { t.cancel(); return; }
        setState(() => seconds--);
        if (seconds <= 0) t.cancel();
      });
    } on ApiException catch (e) {
      if (mounted) setState(() { notice = e.message; failed = true; });
    } catch (_) {
      if (mounted) setState(() { notice = 'Could not connect. Please try again.'; failed = true; });
    } finally { if (mounted) setState(() => busy = false); }
  }
  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    return PopScope(canPop: !busy, child: SingleChildScrollView(
      padding: EdgeInsets.fromLTRB(24, 24, 24, MediaQuery.viewInsetsOf(context).bottom + 24),
      child: Center(child: ConstrainedBox(constraints: const BoxConstraints(maxWidth: 480),
        child: Form(key: form, child: Column(crossAxisAlignment: CrossAxisAlignment.stretch,
          mainAxisSize: MainAxisSize.min, children: [
          Row(children: [CircleAvatar(radius: 28, backgroundColor: colors.primaryContainer,
            child: Icon(Icons.mark_email_read_outlined, color: colors.onPrimaryContainer, size: 28)),
            const Spacer(), IconButton(tooltip: 'Finish later', onPressed: busy ? null : () => Navigator.pop(context, false),
              icon: const Icon(Icons.close_rounded))]),
          const SizedBox(height: 20),
          Text('Verify your email', style: Theme.of(context).textTheme.headlineSmall),
          const SizedBox(height: 8),
          Text('Enter the 6-digit code sent to ${widget.address ?? widget.identifier}.',
            style: TextStyle(color: colors.onSurfaceVariant, height: 1.5)),
          const SizedBox(height: 22),
          if (notice != null) ...[FormNotice(notice!, isError: failed), const SizedBox(height: 16)],
          TextFormField(controller: code, enabled: !busy, keyboardType: TextInputType.number,
            textInputAction: TextInputAction.done, autofillHints: const [AutofillHints.oneTimeCode],
            inputFormatters: [FilteringTextInputFormatter.digitsOnly, LengthLimitingTextInputFormatter(6)],
            style: const TextStyle(fontSize: 26, fontWeight: FontWeight.w700, letterSpacing: 8),
            decoration: const InputDecoration(labelText: 'Email verification code', hintText: '000000'),
            validator: (v) => RegExp(r'^\d{6}$').hasMatch(v ?? '') ? null : 'Enter all 6 digits.',
            onFieldSubmitted: (_) => _submit()),
          const SizedBox(height: 20),
          PrimaryAction(label: 'Verify email', busy: busy, onPressed: () => _submit()),
          const SizedBox(height: 8),
          TextButton(onPressed: busy || seconds > 0 ? null : () => _submit(resend: true),
            child: Text(seconds > 0 ? 'Resend in ${seconds}s' : 'Resend code')),
          Text(widget.needsReview ? 'After email verification, your account still needs admin approval.'
            : 'No email? Check Spam or request a new code. You can return here by signing in.',
            textAlign: TextAlign.center, style: TextStyle(color: colors.onSurfaceVariant, fontSize: 13, height: 1.5)),
        ])),
      )),
    ));
  }
}
