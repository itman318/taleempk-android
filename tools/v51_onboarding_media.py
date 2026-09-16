"""Apply v5.1 onboarding, dashboard and media fixes after the existing generators."""
from pathlib import Path
root=Path(__file__).resolve().parents[1]
source=root/'tools/v51'
def replace(path, old, new):
    text=path.read_text()
    assert old in text, f'Missing anchor in {path}: {old[:90]}'
    path.write_text(text.replace(old,new))
for name in ['home_screen','email_verification_sheet','attachment_sheet','media_preview_screen','photo_editor_screen']:
    (root/f'flutter/lib/screens/{name}.dart').write_text((source/f'{name}.dart').read_text())
auth=root/'flutter/lib/screens/auth_screen.dart'
backdrop=auth.read_text().split('class _StudyBackdrop',1)[1]
auth.write_text((source/'auth_screen.dart').read_text()+'\nclass _StudyBackdrop'+backdrop)
(root/'flutter/lib/core/single_flight.dart').write_text((source/'single_flight.dart').read_text())
api=root/'flutter/lib/core/api_client.dart'
replace(api,'    this.needsTwoFactor = false,','    this.needsTwoFactor = false,\n    this.needsEmailVerification = false,\n    this.email,')
replace(api,'  final bool needsTwoFactor;', '  final bool needsTwoFactor, needsEmailVerification;\n  final String? email;')
replace(api,'class ApiClient {', '''class RegistrationResult {
  const RegistrationResult(this.message, this.needsEmailVerification, this.needsReview);
  final String message;
  final bool needsEmailVerification, needsReview;
}

class ApiClient {''')
replace(api,'  Future<String> register({','  Future<RegistrationResult> register({')
replace(api,"    return '${data['message'] ?? 'Account created successfully.'}';", "    return RegistrationResult('${data['message'] ?? 'Account created successfully.'}',\n      data['needs_email_verification'] == true, data['needs_review'] == true);")
replace(api, "    int voiceSeconds = 0,", "    int voiceSeconds = 0,\n    bool viewOnce = false,")
replace(api, "  }) async {\n    final fields = <String, String>{", '''  }) async {
    if (viewOnce && encrypted) {
      final capabilities = await _request({'action': 'media_capabilities'});
      if (capabilities['encrypted_view_once'] != true) {
        throw const ApiException('Update the website API before sending view once photos.');
      }
    }
    final fields = <String, String>{''')
replace(api, "      if (encrypted) 'enc_att': '1',", "      if (encrypted) 'enc_att': '1',\n      if (viewOnce) 'view_once': '1',")
replace(api,'  Future<BootstrapData> bootstrap()', '''  Future<String> confirmEmail({required String identifier, required String password, String? code}) async {
    final data = await _request({
      'action': code == null ? 'resend_email_code' : 'verify_email',
      'identifier': identifier.trim(), 'password': password,
      if (code != null) 'code': code.trim(),
    }, authenticated: false);
    return '${data['message'] ?? 'Email confirmed.'}';
  }

  Future<BootstrapData> bootstrap()''')
replace(api,"    needsTwoFactor: data['needs_2fa'] == true,", "    needsTwoFactor: data['needs_2fa'] == true,\n    needsEmailVerification: data['needs_email_verification'] == true,\n    email: _nullable(data['email']),")
chat=root/'flutter/lib/screens/chat_screen.dart'
s=chat.read_text()
a=s.index('  Future<void> _pickAttachment() async {'); b=s.index('  Future<String> _prepareViewOnceFile(',a)
s=s[:a]+(source/'chat_methods.dart').read_text()+s[b:]
s=s[:s.index('class _PhotoStroke')]
s=s.replace("import 'dart:ui' as ui;\n",'').replace("import 'package:flutter/rendering.dart';\n",'')
s=s.replace("import '../core/outbox.dart';", "import '../core/outbox.dart';\nimport '../core/single_flight.dart';\nimport 'attachment_sheet.dart';\nimport 'media_preview_screen.dart';")
a=s.index('  Future<void> _openAttachment(ChatMessage m) async {'); b=s.index('  Widget _encryptedBubble',a)
part=s[a:b].replace('  Future<void> _openAttachment(ChatMessage m) async {',
  '  final _attachmentViewer = SingleFlight();\n  Future<void> _openAttachment(ChatMessage m) => _attachmentViewer.run(() async {')
part=part.replace('    if (viewOnce) await NativeBridge.setSecureScreen(true);\n    try {',
  '    try {\n      if (viewOnce) await NativeBridge.setSecureScreen(true);')
# Consume protected media before presenting its bytes. A failed consume must not allow replay.
old_consume = '''      if (viewOnce && !m.mine && !m.playedByMe) {
        try {
          await _appState.api.markViewOnceConsumed(m.id);
          m.playedByMe = true;
          if (mounted) setState(() {});
        } catch (_) {}
      }
'''
assert old_consume in part
part = part.replace(old_consume, '')
part = part.replace('      if (_isImage(m.attachmentType)) {', '''      if (_isImage(m.attachmentType)) {
        if (viewOnce && !m.mine) {
          await _appState.api.markViewOnceConsumed(m.id);
          m.playedByMe = true;
          if (!mounted) return;
          setState(() {});
        }''')
part=part.rstrip()
assert part.endswith('  }')
part=part[:-3]+'  });\n\n'
s=s[:a]+part+s[b:]
a=s.index('  Future<void> _uploadManyImages('); b=s.index('  Future<void> _upload(String path)', a)
part=s[a:b]
part=part.replace('      var uploadPath = originalPath;', '      var uploadPath = originalPath;\n      String? encryptedPath;')
part=part.replace('        await _appState.api.sendFile(', '''        var content = '';
        if (e2eeState.enabled) {
          final sealed = await e2ee.encryptFile(widget.conversation, uploadPath,
            originalName: uploadPath.split(Platform.pathSeparator).last, mime: _mimeForPath(originalPath), content: 'Photo');
          encryptedPath = sealed.path;
          content = sealed.ciphertext;
        }
        await _appState.api.sendFile(''')
part=part.replace('          uploadPath,', '''          encryptedPath ?? uploadPath,
          encrypted: encryptedPath != null,
          content: content,
          viewOnce: viewOnce,''')
part=part.replace('      } finally {', '''      } finally {
        if (encryptedPath != null) { try { await File(encryptedPath).delete(); } catch (_) {} }''')
part=part.replace('    setState(() {\n      sending = true;', '    if (!mounted) return;\n    setState(() {\n      sending = true;')
s=s[:a]+part+s[b:]
# Prevent concurrent decryptions from replacing the same message attachment repeatedly.
a=s.index('  Future<void> _unlockEncryptedMessage(');b=s.index('  Future<void> _encryptionInfo()',a)
part=s[a:b].replace('  Future<void> _unlockEncryptedMessage(ChatMessage message) async {',
    '  final _decryptingAttachment = SingleFlight();\n  Future<void> _unlockEncryptedMessage(ChatMessage message) => _decryptingAttachment.run(() async {')
part=part.rstrip();assert part.endswith('  }');part=part[:-3]+'  });\n\n'
s=s[:a]+part+s[b:]
chat.write_text(s)
# Carry the same group epoch as the file key, even if the group rekeys mid-send.
e2ee=root/'flutter/lib/core/e2ee_service.dart'
replace(e2ee,'required this.mime});', "required this.mime, this.ciphertext = ''});")
replace(e2ee,'  final String path, name, mime;', '  final String path, name, mime;\n  final String ciphertext;')
text=e2ee.read_text();a=text.index('  Future<E2eeFileResult> encryptFile(');b=text.index('  Future<E2eeFileResult> decryptFile(',a)
part=text[a:b]
part=part.replace('    required String mime,', "    required String mime,\n    String content = '',")
part=part.replace('    String key;', '    String key;\n    var epoch = 0;')
part=part.replace("      final epoch = _int(state['epoch']);", "      epoch = _int(state['epoch']);")
part=part.replace('    return E2eeFileResult(', """    var packet = '';
    if (content.isNotEmpty) {
      packet = await _sealText(key, content);
      if (epoch > 0) {
        final pieces = packet.split('.');
        if (pieces.length != 3) throw const ApiException('Encryption failed.');
        packet = 'g1.$epoch.${pieces[1]}.${pieces[2]}';
      }
    }
    return E2eeFileResult(
      ciphertext: packet,""")
e2ee.write_text(text[:a]+part+text[b:])
for folder in ['backend/api','flutter/backend/api']:
    target=root/folder/'mobile.php'
    replace(target,"if ($action === 'login') {", "require_once __DIR__ . '/mobile_email_v51.php';\n\nif ($action === 'login') {")
    old="""    if ($u['status'] !== 'active') { mobile_error((string) ($u['status_reason'] ?: 'This account is not active.'), 403); }
    if ((int) $u['email_verified'] !== 1) { mobile_error('Verify your email before signing in to the app.', 403); }"""
    new="""    if ((int) $u['email_verified'] !== 1 && in_array($u['status'], ['active', 'pending'], true)) {
        mobile_out(['needs_email_verification' => true, 'email' => $u['email'],
            'message' => 'Enter the email verification code to continue.']);
    }
    if ($u['status'] !== 'active') { mobile_error((string) ($u['status_reason'] ?: 'This account is not active.'), 403); }"""
    replace(target,old,new)
    replace(target, "$u = mobile_user();\n$uid = (int) $u['id'];", "$u = mobile_user();\nif ($action === 'media_capabilities') { mobile_out(['encrypted_view_once' => true]); }\n$uid = (int) $u['id'];")
    (root/folder/'chat_send.php').write_text((source/'chat_send.php').read_text())
    (root/folder/'mobile_email_v51.php').write_text((source/'mobile_email_v51.php').read_text())
replace(root/'flutter/pubspec.yaml','version: 5.0.0+500','version: 5.1.0+510')
print('v5.1 email verification, home, attachments and image editor applied')
