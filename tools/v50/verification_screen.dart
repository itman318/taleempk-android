import 'dart:io';
import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../core/app_state.dart';
import '../core/form_rules.dart';
import '../core/social_api.dart';
import '../core/social_models.dart';
import '../widgets/common.dart';
import '../widgets/form_components.dart';
import 'home_shell.dart';

class VerificationScreen extends StatefulWidget {
  const VerificationScreen({super.key});
  @override
  State<VerificationScreen> createState() => _VerificationScreenState();
}

class _VerificationScreenState extends State<VerificationScreen> {
  late final social = SocialApi(AppScope.of(context).api);
  VerificationState? state;
  bool loading = true, withdrawing = false;
  String? error;
  int serial = 0;
  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (serial == 0) _load();
  }

  Future<void> _load() async {
    final request = ++serial;
    setState(() { loading = true; error = null; });
    try {
      final result = await social.verificationStatus();
      if (mounted && request == serial) setState(() => state = result);
    } catch (e) {
      if (mounted && request == serial) setState(() => error = apiMessage(e));
    } finally {
      if (mounted && request == serial) setState(() => loading = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: const PremiumAppBar(title: 'Verification', subtitle: 'Your identity. Your community.'),
    body: loading ? const Center(child: CircularProgressIndicator())
      : error != null ? ErrorView(message: error!, retry: _load)
      : RefreshIndicator(onRefresh: _load, child: ListView(
          physics: const AlwaysScrollableScrollPhysics(),
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 32),
          children: [Center(child: ConstrainedBox(constraints: const BoxConstraints(maxWidth: 680),
            child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
              _hero(), const SizedBox(height: 20),
              if (!state!.emailVerified) ...[
                const FormNotice('Verify your email first, then return here to apply. Check the verification email in your inbox and spam folder.'),
                TextButton.icon(onPressed: _load, icon: const Icon(Icons.refresh),
                  label: const Text('I’ve verified my email')),
                const SizedBox(height: 12),
              ],
              if (state!.application != null) ...[_status(state!.application!), const SizedBox(height: 20)],
              FormSection(title: 'Before you begin', icon: Icons.fact_check_outlined,
                subtitle: 'A little preparation makes it easier.', children: const [
                  _ChecklistRow(icon: Icons.badge_outlined, title: 'Confirm your details',
                    detail: 'Your name and CNIC or B-Form number should match your documents.'),
                  _ChecklistRow(icon: Icons.upload_file_outlined, title: 'Prepare clear documents',
                    detail: 'Identity document required. Teachers and institutes also need proof of their role.'),
                  _ChecklistRow(icon: Icons.mark_email_read_outlined, title: 'Follow your application',
                    detail: 'Return here for your review status and any requests for more information.'),
                ]),
              const SizedBox(height: 20),
              if (state!.canApply && state!.emailVerified && !state!.verified)
                PrimaryAction(label: state!.application?.status == 'info'
                  ? 'Update application' : state!.application == null ? 'Start verification' : 'Apply again',
                  icon: Icons.arrow_forward_rounded, onPressed: _apply),
            ])))],
        )),
  );

  Widget _hero() {
    final verified = state!.verified;
    return Container(padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(borderRadius: BorderRadius.circular(26),
        gradient: const LinearGradient(colors: [Color(0xFF152D68), Color(0xFF4440A4)],
          begin: Alignment.topLeft, end: Alignment.bottomRight)),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Container(padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(color: Colors.white.withValues(alpha: .12),
            borderRadius: BorderRadius.circular(18)),
          child: Icon(verified ? Icons.verified_rounded : Icons.verified_user_outlined,
            color: const Color(0xFFDAE5FF), size: 32)),
        const SizedBox(height: 20),
        Text(verified ? 'Your profile is verified.' : 'Build trust in your profile.',
          style: const TextStyle(fontSize: 27, fontWeight: FontWeight.w800,
            color: Colors.white, height: 1.2, letterSpacing: -.5)),
        const SizedBox(height: 10),
        Text(verified ? 'Your verification status is up to date.'
          : 'Help others recognise the person or organisation behind your account.',
          style: const TextStyle(color: Color(0xFFDCE4FF), height: 1.5)),
      ]));
  }

  Widget _status(VerificationApplication a) {
    final (title, description, icon) = switch (a.status) {
      'pending' => ('Under review', 'Your application has been received. Check back here for an update.', Icons.hourglass_top_rounded),
      'info' => ('More information needed', 'Read the reviewer’s note and update your application.', Icons.edit_note_rounded),
      'approved' => ('Application approved', 'Your application was approved.', Icons.verified_rounded),
      'rejected' => ('Application not approved', 'Review the feedback before submitting a new application.', Icons.info_outline_rounded),
      'withdrawn' => ('Application withdrawn', 'You can start again when your documents are ready.', Icons.undo_rounded),
      'expired' => ('Application expired', 'Submit a new application with current documents.', Icons.history_rounded),
      _ => ('Application status', 'Refresh this page for the latest information.', Icons.info_outline),
    };
    return FormSection(title: title, icon: icon, children: [
      Text(description), const SizedBox(height: 12),
      if (a.caseId > 0) SelectableText('Reference SH-V${a.caseId.toString().padLeft(6, '0')}',
        style: TextStyle(color: Theme.of(context).colorScheme.onSurfaceVariant, fontSize: 12)),
      if (a.adminNote.trim().isNotEmpty) ...[const SizedBox(height: 14),
        FormNotice('Reviewer’s note\n${a.adminNote}', icon: Icons.chat_bubble_outline)],
      if (a.status == 'pending' || a.status == 'info') ...[
        const SizedBox(height: 14),
        OutlinedButton(onPressed: withdrawing ? null : _withdraw,
          child: Text(withdrawing ? 'Withdrawing…' : 'Withdraw application')),
      ],
    ]);
  }

  Future<void> _apply() async {
    final user = AppScope.of(context).user;
    final message = await Navigator.of(context).push<String>(MaterialPageRoute(
      builder: (_) => VerificationApplicationScreen(social: social,
        current: state!.application, initialName: user?.name ?? '')));
    if (!mounted || message == null) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(message)));
    await _load();
  }

  Future<void> _withdraw() async {
    if (withdrawing) return;
    setState(() => withdrawing = true);
    try {
      final accepted = await showDialog<bool>(context: context, builder: (ctx) => AlertDialog(
        title: const Text('Withdraw application?'),
        content: const Text('This stops the current review. A new application will require fresh document uploads.'),
        actions: [TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Keep application')),
          FilledButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Withdraw'))]));
      if (accepted != true || !mounted) return;
      final message = await social.withdrawVerification();
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(message)));
      await _load();
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(apiMessage(e))));
    } finally {
      if (mounted) setState(() => withdrawing = false);
    }
  }
}

class _ChecklistRow extends StatelessWidget {
  const _ChecklistRow({required this.icon, required this.title, required this.detail});
  final IconData icon;
  final String title, detail;
  @override
  Widget build(BuildContext context) => Padding(padding: const EdgeInsets.only(bottom: 18),
    child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Icon(icon, size: 22, color: Theme.of(context).colorScheme.primary), const SizedBox(width: 12),
      Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(title, style: const TextStyle(fontWeight: FontWeight.w700)), const SizedBox(height: 4),
        Text(detail, style: TextStyle(color: Theme.of(context).colorScheme.onSurfaceVariant,
          fontSize: 13, height: 1.5)),
      ])),
    ]));
}

class VerificationApplicationScreen extends StatefulWidget {
  const VerificationApplicationScreen({super.key, required this.social, this.current,
    this.initialName = ''});
  final SocialApi social;
  final VerificationApplication? current;
  final String initialName;
  @override
  State<VerificationApplicationScreen> createState() => _VerificationApplicationScreenState();
}

class _VerificationApplicationScreenState extends State<VerificationApplicationScreen> {
  late final name = TextEditingController(text: widget.current?.fullName ?? widget.initialName);
  late final identity = TextEditingController(text: widget.current?.idNumber ?? '');
  late final org = TextEditingController(text: widget.current?.orgName ?? '');
  late final title = TextEditingController(text: widget.current?.roleTitle ?? '');
  late final subjects = TextEditingController(text: widget.current?.subjects ?? '');
  late final experience = TextEditingController(text: widget.current?.experience.toString() ?? '');
  late final website = TextEditingController(text: widget.current?.website ?? '');
  late final phone = TextEditingController(text: widget.current?.contactPhone ?? '');
  late final notes = TextEditingController(text: widget.current?.notes ?? '');
  late String kind = const ['student', 'teacher', 'institute'].contains(widget.current?.kind)
    ? widget.current!.kind : 'student';
  final formKey = GlobalKey<FormState>();
  final scroll = ScrollController();
  final documents = <String, String>{};
  int step = 0;
  bool busy = false, picking = false, declaration = false;
  double progress = 0;
  String? error;
  bool get retained => FormRules.reuseDocuments(widget.current?.status);
  bool _has(String key) => documents.containsKey(key) || retained && switch (key) {
    'id' => widget.current!.hasDocId,
    'proof' => widget.current!.hasDocProof,
    _ => widget.current!.hasDocExtra,
  };

  @override
  void dispose() {
    for (final c in [name, identity, org, title, subjects, experience, website, phone, notes]) { c.dispose(); }
    scroll.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => PopScope(canPop: !busy,
    child: Scaffold(
      appBar: AppBar(title: const Text('Your application'),
        leading: IconButton(tooltip: 'Close application', onPressed: busy ? null : () => Navigator.pop(context),
          icon: const Icon(Icons.close_rounded))),
      body: SafeArea(top: false, child: SingleChildScrollView(controller: scroll,
        keyboardDismissBehavior: ScrollViewKeyboardDismissBehavior.onDrag,
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 28),
        child: Center(child: ConstrainedBox(constraints: const BoxConstraints(maxWidth: 680),
          child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
            FlowSteps(labels: const ['Details', 'Documents', 'Review'], current: step),
            const SizedBox(height: 24),
            if (error != null) ...[FormNotice(error!, isError: true), const SizedBox(height: 18)],
            if (step == 0) _details(),
            if (step == 1) _uploads(),
            if (step == 2) _review(),
            const SizedBox(height: 20),
            if (busy) ...[
              LinearProgressIndicator(value: progress < 1 ? progress : null),
              const SizedBox(height: 10),
              Text(progress < 1 ? 'Uploading documents… ${(progress * 100).round()}%'
                : 'Upload complete. Waiting for confirmation…', textAlign: TextAlign.center),
              const SizedBox(height: 16),
            ],
            PrimaryAction(label: busy ? 'Submitting application…' : step < 2 ? 'Continue' : 'Submit for review',
              busy: busy, icon: step == 2 ? Icons.check_circle_outline : Icons.arrow_forward_rounded,
              onPressed: picking ? null : _next),
            if (step > 0) TextButton.icon(onPressed: busy || picking ? null : () => _move(step - 1),
              icon: const Icon(Icons.arrow_back, size: 18), label: const Text('Previous step')),
          ]))),
      )),
    ));

  Widget _details() => Form(key: formKey, child: FormSection(title: 'Tell us about yourself',
    icon: Icons.person_outline, subtitle: 'Use the details on your supporting documents.', children: [
      RoleSelector(value: kind, onChanged: (v) => setState(() => kind = v)),
      const SizedBox(height: 14),
      _field(name, 'Full name', validator: FormRules.name, max: 120),
      _field(identity, 'CNIC / B-Form number', validator: FormRules.identity,
        keyboard: TextInputType.number, max: 20, helper: '13 digits, with or without hyphens'),
      _field(org, kind == 'institute' ? 'Institute name' : 'School / organisation${kind == 'student' ? ' (optional)' : ''}',
        validator: kind == 'student' ? null : (v) => (v ?? '').trim().isEmpty ? 'Enter your organisation name.' : null, max: 160),
      if (kind != 'student') ...[
        _field(title, 'Role / designation (optional)', max: 120),
        _field(website, 'Website (optional)', keyboard: TextInputType.url, validator: FormRules.website, max: 200),
      ],
      if (kind == 'teacher') ...[
        _field(subjects, 'Subjects (optional)', max: 255),
        _field(experience, 'Years of experience (optional)', keyboard: TextInputType.number,
          validator: (v) => (v ?? '').isEmpty ? null : int.tryParse(v!) == null ||
            int.parse(v) < 0 || int.parse(v) > 60 ? 'Enter a number from 0 to 60.' : null, max: 2),
      ],
      _field(phone, 'Contact phone (optional)', keyboard: TextInputType.phone, max: 30),
      _field(notes, 'Anything the reviewer should know? (optional)', max: 2000, lines: 3),
    ]));

  Widget _field(TextEditingController controller, String label, {
    String? Function(String?)? validator, TextInputType? keyboard, int max = 200,
    int lines = 1, String? helper,
  }) => Padding(padding: const EdgeInsets.only(bottom: 18), child: TextFormField(
    controller: controller, validator: validator, keyboardType: keyboard,
    maxLines: lines, inputFormatters: [LengthLimitingTextInputFormatter(max)],
    autovalidateMode: AutovalidateMode.onUserInteraction,
    decoration: InputDecoration(labelText: label, errorMaxLines: 3, helperText: helper,
      helperMaxLines: 2, alignLabelWithHint: lines > 1),
  ));

  Widget _uploads() => FormSection(title: 'Add your documents', icon: Icons.upload_file_outlined,
    subtitle: 'JPG, PNG, WEBP or PDF · up to 6 MB each', children: [
      if (retained) ...[const FormNotice('Your previously uploaded documents are kept for this update. Replace a file only if needed.'),
        const SizedBox(height: 18)],
      _document('id', 'Identity document', 'Required · Clear CNIC or B-Form copy'),
      _document('proof', 'Proof of role', kind == 'student' ? 'Optional · Student card or enrolment letter'
        : kind == 'teacher' ? 'Required · Staff ID or employment letter' : 'Required · Institute registration or authorisation'),
      _document('extra', 'Supporting document', 'Optional · Additional evidence for your application'),
      const FormNotice('Include all edges of the document. Avoid blurred photos, glare and unrelated personal documents.',
        icon: Icons.photo_camera_outlined),
    ]);

  Widget _document(String key, String label, String help) {
    final selected = documents[key];
    final exists = _has(key);
    final colors = Theme.of(context).colorScheme;
    return Container(margin: const EdgeInsets.only(bottom: 16), padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(color: colors.primary.withValues(alpha: exists ? .06 : .02),
        border: Border.all(color: exists ? colors.primary.withValues(alpha: .5) : colors.outlineVariant),
        borderRadius: BorderRadius.circular(18)),
      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        Row(children: [Icon(exists ? Icons.check_circle_outline : Icons.description_outlined,
          color: colors.primary), const SizedBox(width: 10),
          Expanded(child: Text(label, style: const TextStyle(fontWeight: FontWeight.w800)))]),
        const SizedBox(height: 8), Text(help, style: TextStyle(fontSize: 12, color: colors.onSurfaceVariant)),
        if (exists) ...[const SizedBox(height: 10), Text(selected?.split(Platform.pathSeparator).last
          ?? 'Previously uploaded · will be kept', style: TextStyle(color: colors.primary, fontSize: 13))],
        const SizedBox(height: 12),
        OutlinedButton.icon(onPressed: picking ? null : () => _pick(key),
          icon: const Icon(Icons.attach_file, size: 18), label: Text(exists ? 'Replace file' : 'Choose file')),
        if (selected != null) TextButton(onPressed: picking ? null : () => setState(() => documents.remove(key)),
          child: Text(retained ? 'Undo selection' : 'Remove file')),
      ]));
  }

  Widget _review() => FormSection(title: 'Ready for review?', icon: Icons.fact_check_outlined,
    subtitle: 'Check the details before you submit.', children: [
      _summary('Application type', kind[0].toUpperCase() + kind.substring(1)),
      _summary('Full name', name.text.trim()),
      _summary('CNIC / B-Form', identity.text.trim()),
      if (org.text.trim().isNotEmpty) _summary('Organisation', org.text.trim()),
      if (kind != 'student' && title.text.trim().isNotEmpty) _summary('Role', title.text.trim()),
      if (kind != 'student' && website.text.trim().isNotEmpty) _summary('Website', website.text.trim()),
      if (kind == 'teacher' && subjects.text.trim().isNotEmpty) _summary('Subjects', subjects.text.trim()),
      if (kind == 'teacher' && experience.text.isNotEmpty) _summary('Experience', '${experience.text} years'),
      if (phone.text.trim().isNotEmpty) _summary('Contact phone', phone.text.trim()),
      if (notes.text.trim().isNotEmpty) _summary('Notes', notes.text.trim()),
      const Divider(height: 28),
      for (final entry in {'id': 'Identity document', 'proof': 'Proof of role', 'extra': 'Supporting document'}.entries)
        if (_has(entry.key)) _ChecklistRow(icon: Icons.check_circle_outline, title: entry.value,
          detail: documents[entry.key]?.split(Platform.pathSeparator).last ?? 'Previously uploaded'),
      CheckboxListTile(value: declaration, onChanged: busy ? null : (v) => setState(() => declaration = v ?? false),
        contentPadding: EdgeInsets.zero, controlAffinity: ListTileControlAffinity.leading,
        title: const Text('I confirm these details are accurate and I am authorised to submit these documents.',
          style: TextStyle(fontSize: 13, height: 1.5))),
    ]);

  Widget _summary(String label, String value) => Padding(padding: const EdgeInsets.only(bottom: 14),
    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text(label, style: TextStyle(color: Theme.of(context).colorScheme.onSurfaceVariant, fontSize: 12)),
      const SizedBox(height: 3), Text(value, style: const TextStyle(fontWeight: FontWeight.w600)),
    ]));

  Future<void> _pick(String key) async {
    if (picking || busy) return;
    setState(() { picking = true; error = null; });
    try {
      final result = await FilePicker.pickFile(type: FileType.custom,
        allowedExtensions: const ['jpg', 'jpeg', 'png', 'webp', 'pdf']);
      if (!mounted || result == null) return; // Cancelling must preserve the selected file.
      final path = result.path;
      if (path == null || path.isEmpty) { setState(() => error = 'Couldn’t open this file. Choose a downloaded copy.'); return; }
      final bytes = await File(path).length();
      if (!mounted) return;
      final problem = FormRules.document(path, bytes);
      setState(() { error = problem; if (problem == null) documents[key] = path; });
    } catch (_) {
      if (mounted) setState(() => error = 'Couldn’t read this file. Download it to your phone and try again.');
    } finally {
      if (mounted) setState(() => picking = false);
    }
  }

  void _move(int value) {
    FocusManager.instance.primaryFocus?.unfocus();
    setState(() { step = value; error = null; });
    if (scroll.hasClients) scroll.jumpTo(0);
  }

  Future<void> _next() async {
    if (busy || picking) return;
    if (step == 0) {
      if (formKey.currentState?.validate() ?? false) _move(1);
      return;
    }
    if (!_has('id') || kind != 'student' && !_has('proof')) {
      setState(() => error = 'Add your identity document${kind == 'student' ? '' : ' and proof of role'} to continue.');
      if (scroll.hasClients) scroll.jumpTo(0);
      return;
    }
    if (step == 1) { _move(2); return; }
    if (!declaration) { setState(() => error = 'Please confirm the declaration before submitting.');
      if (scroll.hasClients) scroll.jumpTo(0); return; }
    setState(() { busy = true; error = null; progress = 0; });
    try {
      final message = await widget.social.submitVerification(fields: {
        'kind': kind, 'full_name': name.text.trim(), 'id_number': identity.text.trim(),
        'org_name': org.text.trim(), 'role_title': kind == 'student' ? '' : title.text.trim(),
        'subjects': kind == 'teacher' ? subjects.text.trim() : '',
        'experience': kind == 'teacher' ? experience.text.trim() : '0',
        'website': kind == 'student' ? '' : website.text.trim(),
        'contact_phone': phone.text.trim(), 'notes': notes.text.trim(),
      }, idDocument: documents['id'], proofDocument: documents['proof'], extraDocument: documents['extra'],
        onProgress: (value) { if (mounted) setState(() => progress = value.clamp(0.0, 1.0)); });
      if (mounted) Navigator.pop(context, message);
    } catch (e) {
      if (mounted) { setState(() => error = apiMessage(e)); if (scroll.hasClients) scroll.jumpTo(0); }
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }
}
