import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';

import '../core/app_state.dart';
import '../core/social_api.dart';
import '../core/social_models.dart';
import '../core/theme.dart';
import '../widgets/common.dart';
import 'home_shell.dart';

class VerificationScreen extends StatefulWidget {
  const VerificationScreen({super.key});

  @override
  State<VerificationScreen> createState() => _VerificationScreenState();
}

class _VerificationScreenState extends State<VerificationScreen> {
  VerificationState? state;
  bool loading = true;
  String? error;

  SocialApi get social => SocialApi(AppScope.of(context).api);

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    if (mounted) setState(() { loading = true; error = null; });
    try {
      final value = await social.verificationStatus();
      if (mounted) setState(() => state = value);
    } catch (e) {
      if (mounted) setState(() => error = apiMessage(e));
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: const PremiumAppBar(
          title: 'Get verified',
          subtitle: 'Native identity & role verification',
        ),
        body: loading
            ? const Center(child: CircularProgressIndicator())
            : error != null
                ? ErrorView(message: error!, retry: _load)
                : RefreshIndicator(
                    onRefresh: _load,
                    child: ListView(
                      physics: const AlwaysScrollableScrollPhysics(),
                      padding: const EdgeInsets.fromLTRB(16, 8, 16, 30),
                      children: [
                        _hero(),
                        const SizedBox(height: 14),
                        if (!(state?.emailVerified ?? false)) _emailWarning(),
                        if (state?.application != null) ...[
                          _statusCard(state!.application!),
                          const SizedBox(height: 14),
                        ],
                        _processCard(),
                        const SizedBox(height: 14),
                        if (_canSubmit) _applyCard(),
                      ],
                    ),
                  ),
      );

  bool get _canSubmit {
    final s = state;
    if (s == null || !s.emailVerified || s.verified) return false;
    final status = s.application?.status;
    return s.application == null ||
        status == 'info' ||
        status == 'rejected' ||
        status == 'withdrawn' ||
        status == 'expired';
  }

  Widget _hero() => Container(
        padding: const EdgeInsets.all(20),
        decoration: BoxDecoration(
          gradient: const LinearGradient(
            colors: [AppColors.navy, Color(0xFF3157E8), Color(0xFF7657EF)],
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
          ),
          borderRadius: BorderRadius.circular(26),
        ),
        child: const Row(
          children: [
            Icon(Icons.verified_user_rounded, color: Colors.white, size: 42),
            SizedBox(width: 15),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Trusted profiles stand out',
                    style: TextStyle(
                      color: Colors.white,
                      fontWeight: FontWeight.w900,
                      fontSize: 19,
                    ),
                  ),
                  SizedBox(height: 5),
                  Text(
                    'Submit your identity and role evidence securely inside TaleemPK. Most reviews are completed within two working days.',
                    style: TextStyle(color: Colors.white70, height: 1.35),
                  ),
                ],
              ),
            ),
          ],
        ),
      );

  Widget _emailWarning() => Card(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Icon(Icons.mark_email_unread_outlined, color: AppColors.warning),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text('Confirm your email first', style: TextStyle(fontWeight: FontWeight.w900)),
                    const SizedBox(height: 4),
                    const Text(
                      'Email confirmation is the first verification checkpoint. Confirm it on your account, then pull down to refresh this screen.',
                      style: TextStyle(color: AppColors.muted, height: 1.35),
                    ),
                    const SizedBox(height: 10),
                    OutlinedButton.icon(
                      onPressed: _load,
                      icon: const Icon(Icons.refresh_rounded),
                      label: const Text('Refresh status'),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      );

  Widget _statusCard(VerificationApplication a) {
    final status = _statusInfo(a.status);
    final open = a.status == 'pending' || a.status == 'info';
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(17),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Container(
                  width: 42,
                  height: 42,
                  decoration: BoxDecoration(
                    color: status.color.withValues(alpha: .10),
                    borderRadius: BorderRadius.circular(13),
                  ),
                  child: Icon(status.icon, color: status.color),
                ),
                const SizedBox(width: 11),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(status.label, style: const TextStyle(fontWeight: FontWeight.w900, fontSize: 16)),
                      Text(
                        a.caseId > 0 ? 'Reference SH-V${a.caseId.toString().padLeft(6, '0')} · Submission ${a.attemptNo}' : 'Submission ${a.attemptNo}',
                        style: const TextStyle(color: AppColors.muted, fontSize: 12),
                      ),
                    ],
                  ),
                ),
              ],
            ),
            if (a.adminNote.isNotEmpty) ...[
              const SizedBox(height: 14),
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(13),
                decoration: BoxDecoration(
                  color: AppColors.warning.withValues(alpha: .08),
                  borderRadius: BorderRadius.circular(14),
                ),
                child: Text(a.adminNote, style: const TextStyle(height: 1.35)),
              ),
            ],
            const SizedBox(height: 16),
            _timeline(a),
            if (open) ...[
              const SizedBox(height: 12),
              OutlinedButton.icon(
                onPressed: _withdraw,
                icon: const Icon(Icons.cancel_outlined, color: AppColors.danger),
                label: const Text('Withdraw application', style: TextStyle(color: AppColors.danger)),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _timeline(VerificationApplication a) {
    final outcome = a.status == 'approved' || a.status == 'rejected' || a.status == 'expired';
    final assessment = a.viewed || a.reviewed || outcome || a.status == 'info';
    final stages = <(String, bool)>[
      ('Email confirmed', state?.emailVerified ?? false),
      ('Application received', true),
      ('Assessment', assessment),
      ('Outcome issued', outcome),
    ];
    return Column(
      children: [
        for (var i = 0; i < stages.length; i++)
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Column(
                children: [
                  Icon(
                    stages[i].$2 ? Icons.check_circle_rounded : Icons.radio_button_unchecked_rounded,
                    size: 19,
                    color: stages[i].$2 ? AppColors.success : AppColors.muted,
                  ),
                  if (i < stages.length - 1)
                    Container(width: 2, height: 22, color: Theme.of(context).dividerColor),
                ],
              ),
              const SizedBox(width: 10),
              Padding(
                padding: const EdgeInsets.only(top: 1),
                child: Text(
                  stages[i].$1,
                  style: TextStyle(
                    fontWeight: stages[i].$2 ? FontWeight.w800 : FontWeight.w500,
                    color: stages[i].$2 ? null : AppColors.muted,
                  ),
                ),
              ),
            ],
          ),
      ],
    );
  }

  Widget _processCard() => Card(
        child: Padding(
          padding: const EdgeInsets.all(17),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text('What we check', style: TextStyle(fontWeight: FontWeight.w900, fontSize: 16)),
              const SizedBox(height: 12),
              _bullet(Icons.badge_outlined, 'Identity', 'CNIC/B-Form, student card or passport photo page.'),
              _bullet(Icons.school_outlined, 'Role evidence', 'Teachers and institutes also provide proof of role or registration.'),
              _bullet(Icons.shield_outlined, 'Account match', 'The same identity cannot be active on two TaleemPK accounts.'),
              _bullet(Icons.history_rounded, 'Audit trail', 'Resubmissions stay attached to the same review case when more information is requested.'),
            ],
          ),
        ),
      );

  Widget _bullet(IconData icon, String title, String text) => Padding(
        padding: const EdgeInsets.only(bottom: 11),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(icon, color: AppColors.blue, size: 20),
            const SizedBox(width: 10),
            Expanded(
              child: RichText(
                text: TextSpan(
                  style: TextStyle(color: Theme.of(context).colorScheme.onSurface, height: 1.35),
                  children: [
                    TextSpan(text: '$title — ', style: const TextStyle(fontWeight: FontWeight.w800)),
                    TextSpan(text: text),
                  ],
                ),
              ),
            ),
          ],
        ),
      );

  Widget _applyCard() {
    final info = state?.application?.status == 'info';
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(17),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(info ? 'Provide requested information' : 'Start verification', style: const TextStyle(fontWeight: FontWeight.w900, fontSize: 16)),
            const SizedBox(height: 5),
            Text(
              info ? 'Your reference and queue position are preserved when you resubmit.' : 'Your documents are sent to the same verification queue used by TaleemPK on the web.',
              style: const TextStyle(color: AppColors.muted, height: 1.35),
            ),
            const SizedBox(height: 14),
            FilledButton.icon(
              onPressed: _openApplication,
              icon: const Icon(Icons.verified_rounded),
              label: Text(info ? 'Update application' : 'Apply for verification'),
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _withdraw() async {
    final yes = await showDialog<bool>(
          context: context,
          builder: (d) => AlertDialog(
            title: const Text('Withdraw application?'),
            content: const Text('You can submit a new application later.'),
            actions: [
              TextButton(onPressed: () => Navigator.pop(d, false), child: const Text('Keep it')),
              FilledButton(onPressed: () => Navigator.pop(d, true), child: const Text('Withdraw')),
            ],
          ),
        ) ??
        false;
    if (!yes || !mounted) return;
    try {
      final message = await social.withdrawVerification();
      if (mounted) showMessage(context, message);
      await _load();
    } catch (e) {
      if (mounted) showMessage(context, apiMessage(e));
    }
  }

  Future<void> _openApplication() async {
    final current = state?.application;
    var kind = current?.kind ?? (AppScope.of(context).user?.role == 'institute' ? 'institute' : AppScope.of(context).user?.role == 'teacher' ? 'teacher' : 'student');
    final fullName = TextEditingController(text: current?.fullName ?? AppScope.of(context).user?.name ?? '');
    final idNumber = TextEditingController(text: current?.idNumber ?? '');
    final orgName = TextEditingController(text: current?.orgName ?? '');
    final roleTitle = TextEditingController(text: current?.roleTitle ?? '');
    final subjects = TextEditingController(text: current?.subjects ?? '');
    final experience = TextEditingController(text: (current?.experience ?? 0) > 0 ? '${current!.experience}' : '');
    final website = TextEditingController(text: current?.website ?? '');
    final phone = TextEditingController(text: current?.contactPhone ?? '');
    final notes = TextEditingController(text: current?.notes ?? '');
    String? idDoc, proofDoc, extraDoc;
    bool declaration = false, submitting = false;
    double upload = 0;

    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      builder: (sheet) => StatefulBuilder(
        builder: (sheet, setModal) => Padding(
          padding: EdgeInsets.fromLTRB(18, 8, 18, MediaQuery.viewInsetsOf(sheet).bottom + 18),
          child: SingleChildScrollView(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text('Verification application', style: Theme.of(sheet).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w900)),
                const SizedBox(height: 16),
                DropdownButtonFormField<String>(
                  initialValue: kind,
                  decoration: const InputDecoration(labelText: 'Verification type'),
                  items: const [
                    DropdownMenuItem(value: 'student', child: Text('Student')),
                    DropdownMenuItem(value: 'teacher', child: Text('Teacher')),
                    DropdownMenuItem(value: 'institute', child: Text('Institute')),
                  ],
                  onChanged: submitting ? null : (v) => setModal(() => kind = v ?? kind),
                ),
                const SizedBox(height: 10),
                TextField(controller: fullName, decoration: const InputDecoration(labelText: 'Full legal name *')),
                const SizedBox(height: 10),
                TextField(controller: idNumber, keyboardType: TextInputType.number, decoration: const InputDecoration(labelText: 'CNIC / B-Form number *', hintText: '35202-1234567-1')),
                const SizedBox(height: 10),
                TextField(controller: orgName, decoration: const InputDecoration(labelText: 'School / institute')),
                const SizedBox(height: 10),
                TextField(controller: roleTitle, decoration: const InputDecoration(labelText: 'Role / designation')),
                const SizedBox(height: 10),
                TextField(controller: subjects, decoration: const InputDecoration(labelText: 'Subjects / field')),
                const SizedBox(height: 10),
                TextField(controller: experience, keyboardType: TextInputType.number, decoration: const InputDecoration(labelText: 'Experience in years')),
                const SizedBox(height: 10),
                TextField(controller: website, keyboardType: TextInputType.url, decoration: const InputDecoration(labelText: 'Website')),
                const SizedBox(height: 10),
                TextField(controller: phone, keyboardType: TextInputType.phone, decoration: const InputDecoration(labelText: 'Contact phone')),
                const SizedBox(height: 10),
                TextField(controller: notes, minLines: 3, maxLines: 6, maxLength: 2000, decoration: const InputDecoration(labelText: 'Additional information')),
                const SizedBox(height: 4),
                _docPicker(
                  sheet,
                  title: 'Identity document *',
                  subtitle: current?.hasDocId == true && idDoc == null ? 'Existing document is already on this case' : 'CNIC, student card or passport photo page',
                  path: idDoc,
                  enabled: !submitting,
                  onPick: (v) => setModal(() => idDoc = v),
                ),
                const SizedBox(height: 9),
                _docPicker(
                  sheet,
                  title: kind == 'student' ? 'Proof of role (optional)' : 'Proof of role *',
                  subtitle: current?.hasDocProof == true && proofDoc == null ? 'Existing role evidence is already on this case' : 'Staff card, appointment letter, degree or institute registration',
                  path: proofDoc,
                  enabled: !submitting,
                  onPick: (v) => setModal(() => proofDoc = v),
                ),
                const SizedBox(height: 9),
                _docPicker(
                  sheet,
                  title: 'Extra document (optional)',
                  subtitle: current?.hasDocExtra == true && extraDoc == null ? 'Existing extra document will be kept' : 'Any additional supporting evidence',
                  path: extraDoc,
                  enabled: !submitting,
                  onPick: (v) => setModal(() => extraDoc = v),
                ),
                CheckboxListTile(
                  contentPadding: EdgeInsets.zero,
                  value: declaration,
                  onChanged: submitting ? null : (v) => setModal(() => declaration = v ?? false),
                  controlAffinity: ListTileControlAffinity.leading,
                  title: const Text('I confirm these details and documents are mine and accurate.', style: TextStyle(fontSize: 13, fontWeight: FontWeight.w700)),
                ),
                if (submitting) ...[
                  const SizedBox(height: 4),
                  LinearProgressIndicator(value: upload > 0 ? upload : null),
                  const SizedBox(height: 8),
                  Text(upload > 0 ? 'Uploading ${(upload * 100).round()}%' : 'Submitting securely…', textAlign: TextAlign.center, style: const TextStyle(color: AppColors.muted)),
                ],
                const SizedBox(height: 8),
                FilledButton.icon(
                  onPressed: submitting
                      ? null
                      : () async {
                          if (fullName.text.trim().length < 3 || idNumber.text.trim().isEmpty) {
                            showMessage(sheet, 'Enter your full name and CNIC/B-Form number.');
                            return;
                          }
                          if (current?.hasDocId != true && idDoc == null) {
                            showMessage(sheet, 'Select an identity document.');
                            return;
                          }
                          if (kind != 'student' && current?.hasDocProof != true && proofDoc == null) {
                            showMessage(sheet, 'Select proof of your teacher or institute role.');
                            return;
                          }
                          if (!declaration) {
                            showMessage(sheet, 'Confirm the declaration before submitting.');
                            return;
                          }
                          setModal(() { submitting = true; upload = 0; });
                          try {
                            final message = await social.submitVerification(
                              fields: {
                                'kind': kind,
                                'full_name': fullName.text.trim(),
                                'id_number': idNumber.text.trim(),
                                'org_name': orgName.text.trim(),
                                'role_title': roleTitle.text.trim(),
                                'subjects': subjects.text.trim(),
                                'experience': experience.text.trim(),
                                'website': website.text.trim(),
                                'contact_phone': phone.text.trim(),
                                'notes': notes.text.trim(),
                              },
                              idDocument: idDoc,
                              proofDocument: proofDoc,
                              extraDocument: extraDoc,
                              onProgress: (v) {
                                if (sheet.mounted) setModal(() => upload = v);
                              },
                            );
                            if (sheet.mounted) {
                              Navigator.pop(sheet);
                              showMessage(context, message);
                            }
                            await _load();
                          } catch (e) {
                            if (sheet.mounted) {
                              setModal(() => submitting = false);
                              showMessage(sheet, apiMessage(e));
                            }
                          }
                        },
                  icon: const Icon(Icons.send_rounded),
                  label: Text(current?.status == 'info' ? 'Resubmit application' : 'Submit application'),
                ),
              ],
            ),
          ),
        ),
      ),
    );

    for (final c in [fullName, idNumber, orgName, roleTitle, subjects, experience, website, phone, notes]) {
      c.dispose();
    }
  }

  Widget _docPicker(
    BuildContext context, {
    required String title,
    required String subtitle,
    required String? path,
    required bool enabled,
    required ValueChanged<String?> onPick,
  }) => Container(
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          border: Border.all(color: Theme.of(context).dividerColor),
          borderRadius: BorderRadius.circular(15),
        ),
        child: Row(
          children: [
            const Icon(Icons.description_outlined, color: AppColors.blue),
            const SizedBox(width: 10),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(title, style: const TextStyle(fontWeight: FontWeight.w800)),
                  const SizedBox(height: 2),
                  Text(
                    path == null ? subtitle : path.split('/').last,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(color: AppColors.muted, fontSize: 11.5),
                  ),
                ],
              ),
            ),
            TextButton(
              onPressed: !enabled
                  ? null
                  : () async {
                      final result = await FilePicker.platform.pickFiles(
                        allowMultiple: false,
                        type: FileType.custom,
                        allowedExtensions: const ['jpg', 'jpeg', 'png', 'webp', 'pdf'],
                      );
                      onPick(result?.files.single.path);
                    },
              child: Text(path == null ? 'Choose' : 'Replace'),
            ),
          ],
        ),
      );

  _StatusInfo _statusInfo(String status) {
    switch (status) {
      case 'pending':
        return const _StatusInfo('In review queue', Icons.hourglass_top_rounded, AppColors.blue);
      case 'info':
        return const _StatusInfo('Further information required', Icons.info_outline_rounded, AppColors.warning);
      case 'approved':
        return const _StatusInfo('Approved', Icons.verified_rounded, AppColors.success);
      case 'rejected':
        return const _StatusInfo('Not approved', Icons.cancel_outlined, AppColors.danger);
      case 'withdrawn':
        return const _StatusInfo('Withdrawn', Icons.remove_circle_outline_rounded, AppColors.muted);
      case 'expired':
        return const _StatusInfo('Expired — you can apply again', Icons.event_busy_outlined, AppColors.warning);
      default:
        return const _StatusInfo('Application status', Icons.fact_check_outlined, AppColors.blue);
    }
  }
}

class _StatusInfo {
  const _StatusInfo(this.label, this.icon, this.color);
  final String label;
  final IconData icon;
  final Color color;
}
