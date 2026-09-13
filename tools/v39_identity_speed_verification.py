from pathlib import Path
import re
import shutil

ROOT = Path(__file__).resolve().parents[1]


def r(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def w(path: str, text: str) -> None:
    p = ROOT / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding='utf-8')


def once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f'v3.9 missing target: {label}')
    return text.replace(old, new, 1)


# ---------------------------------------------------------------------------
# 1) Native sign-in identity: report the real Android model before bootstrap
# parses the request, and pass explicit app/device metadata on every request.
# ---------------------------------------------------------------------------
path = 'flutter/lib/core/api_client.dart'
text = r(path)
old_headers = "  Map<String, String> get authHeaders => {\n        'X-Requested-With': 'XMLHttpRequest',\n        'Accept': 'application/json',\n        if (_token != null) 'Authorization': 'Bearer $_token',\n      };"
new_headers = "  Map<String, String> get authHeaders => {\n        'X-Requested-With': 'XMLHttpRequest',\n        'Accept': 'application/json',\n        'User-Agent': 'TaleemPKAndroid/3.9',\n        'X-TaleemPK-App': 'TaleemPK Android',\n        if (_token != null) 'Authorization': 'Bearer $_token',\n      };"
text = once(text, old_headers, new_headers, 'native request headers')

# Include timezone metadata on authentication calls. The server still uses the
# connection IP for the security alert's network area; timezone is a useful
# diagnostic hint but is not treated as a physical location.
text = text.replace(
    "      'device': await NativeBridge.deviceName(),\n    }, authenticated: false);",
    "      'device': await NativeBridge.deviceName(),\n      'client': 'TaleemPK Android app',\n      'tz_offset': '${DateTime.now().timeZoneOffset.inMinutes}',\n      'tz_name': DateTime.now().timeZoneName,\n    }, authenticated: false);",
)
w(path, text)

# Apply a realistic Android browser-style UA before the shared website
# bootstrap loads. Some shared helpers cache parsed device/browser information
# during bootstrap, which is why changing HTTP_USER_AGENT only inside the login
# function could still produce Unknown device / Unknown browser emails.
early_identity = r'''/* Native identity must be available before bootstrap parses the request. */
$nativeEarlyAction = strtolower(trim((string) ($_POST['action'] ?? '')));
$nativeEarlyDevice = trim((string) ($_POST['device'] ?? $_SERVER['HTTP_X_TALEEMPK_DEVICE'] ?? ''));
if (in_array($nativeEarlyAction, ['login', 'verify_2fa'], true) && $nativeEarlyDevice !== '') {
    $nativeModel = preg_replace('/\s*·\s*Android.*$/u', '', $nativeEarlyDevice);
    $nativeModel = preg_replace('/[^A-Za-z0-9 ._()\-]/u', '', (string) $nativeModel);
    if ($nativeModel === '') { $nativeModel = 'Android device'; }
    $androidRelease = 'Android';
    if (preg_match('/Android\s+([0-9A-Za-z._-]+)/i', $nativeEarlyDevice, $nativeMatch)) {
        $androidRelease = 'Android ' . $nativeMatch[1];
    }
    $_SERVER['HTTP_X_TALEEMPK_NATIVE'] = '1';
    $_SERVER['HTTP_X_TALEEMPK_DEVICE'] = $nativeEarlyDevice;
    $_SERVER['HTTP_USER_AGENT'] = 'Mozilla/5.0 (Linux; ' . $androidRelease . '; ' . $nativeModel . ') AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Mobile Safari/537.36 TaleemPKAndroid/3.9';
}

'''
for path in ['backend/api/mobile.php', 'flutter/backend/api/mobile.php']:
    text = r(path)
    marker = "/* Set JSON before loading the application. If a shared include terminates\n   early, Android must never be handed an HTML content type. */\n"
    if early_identity not in text:
        text = once(text, marker, early_identity + marker, f'early native identity in {path}')

    # The shared sign-in mailer receives record_signin() output. Explicitly
    # provide all common device/browser keys so the email cannot fall back to
    # Unknown even if the website parser does not recognize a custom app UA.
    signin_line = "    $signin = record_signin((int) $u['id']);\n"
    signin_block = r'''    $signin = record_signin((int) $u['id']);
    if (!is_array($signin)) { $signin = []; }
    $signin['device'] = $safeDevice;
    $signin['device_name'] = $safeDevice;
    $signin['device_label'] = $safeDevice;
    $signin['browser'] = 'TaleemPK Android app';
    $signin['browser_name'] = 'TaleemPK Android app';
    $signin['client'] = 'TaleemPK Android app';
    $signin['os'] = 'Android';
    $signin['platform'] = 'Android';
'''
    text = once(text, signin_line, signin_block, f'sign-in alert identity in {path}')
    text = text.replace('TaleemPKApp/3.8', 'TaleemPKApp/3.9')
    text = text.replace("'api_version' => '3.8'", "'api_version' => '3.9'")
    w(path, text)


# ---------------------------------------------------------------------------
# 2) Faster Telegram-like navigation + polished global error surface.
# ---------------------------------------------------------------------------
path = 'flutter/lib/widgets/common.dart'
text = r(path)
error_start = text.find('class ErrorView extends StatelessWidget {')
error_end = text.find('class EmptyView extends StatelessWidget {', error_start)
if error_start < 0 or error_end < 0:
    raise RuntimeError('v3.9 common ErrorView boundary missing')
error_view = r'''class ErrorView extends StatelessWidget {
  const ErrorView({super.key, required this.message, required this.retry});
  final String message;
  final VoidCallback retry;
  @override
  Widget build(BuildContext context) => Center(
    child: Padding(
      padding: const EdgeInsets.all(20),
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 420),
        child: Container(
          padding: const EdgeInsets.all(20),
          decoration: BoxDecoration(
            color: Theme.of(context).colorScheme.surface,
            borderRadius: BorderRadius.circular(22),
            border: Border.all(
              color: Theme.of(context).colorScheme.outlineVariant.withValues(alpha: .45),
            ),
            boxShadow: const [
              BoxShadow(color: Color(0x0A071426), blurRadius: 20, offset: Offset(0, 8)),
            ],
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                width: 52,
                height: 52,
                decoration: BoxDecoration(
                  color: AppColors.blue.withValues(alpha: .09),
                  borderRadius: BorderRadius.circular(17),
                ),
                child: const Icon(Icons.sync_problem_rounded, color: AppColors.blue, size: 27),
              ),
              const SizedBox(height: 13),
              const Text(
                'Something needs attention',
                textAlign: TextAlign.center,
                style: TextStyle(fontSize: 16, fontWeight: FontWeight.w900),
              ),
              const SizedBox(height: 6),
              Text(
                message,
                textAlign: TextAlign.center,
                style: const TextStyle(color: AppColors.muted, height: 1.4),
              ),
              const SizedBox(height: 15),
              FilledButton.icon(
                onPressed: retry,
                icon: const Icon(Icons.refresh_rounded),
                label: const Text('Try again'),
              ),
            ],
          ),
        ),
      ),
    ),
  );
}

'''
text = text[:error_start] + error_view + text[error_end:]

if 'PageRoute<T> premiumRoute<T>' not in text:
    text += r'''

PageRoute<T> premiumRoute<T>({
  required WidgetBuilder builder,
  RouteSettings? settings,
  bool fullscreenDialog = false,
}) => PageRouteBuilder<T>(
  settings: settings,
  fullscreenDialog: fullscreenDialog,
  transitionDuration: const Duration(milliseconds: 170),
  reverseTransitionDuration: const Duration(milliseconds: 135),
  pageBuilder: (context, animation, secondaryAnimation) => builder(context),
  transitionsBuilder: (context, animation, secondaryAnimation, child) {
    final curved = CurvedAnimation(
      parent: animation,
      curve: Curves.easeOutCubic,
      reverseCurve: Curves.easeInCubic,
    );
    return FadeTransition(
      opacity: Tween<double>(begin: .94, end: 1).animate(curved),
      child: SlideTransition(
        position: Tween<Offset>(
          begin: const Offset(.035, 0),
          end: Offset.zero,
        ).animate(curved),
        child: child,
      ),
    );
  },
);
'''
w(path, text)

# Use the faster route for the high-frequency surfaces. These files already
# import common.dart, so no extra dependency is introduced.
for path in [
    'flutter/lib/screens/home_screen.dart',
    'flutter/lib/screens/profile_screen.dart',
    'flutter/lib/screens/conversations_screen.dart',
    'flutter/lib/screens/feed_screen.dart',
    'flutter/lib/screens/home_shell.dart',
    'flutter/lib/screens/security_screen.dart',
    'flutter/lib/screens/verification_screen.dart',
]:
    text = r(path)
    if "../widgets/common.dart" not in text:
        raise RuntimeError(f'v3.9 route target lacks common.dart import: {path}')
    text = re.sub(r'MaterialPageRoute<([^>]+)>\(', r'premiumRoute<\1>(', text)
    text = text.replace('MaterialPageRoute(', 'premiumRoute(')
    w(path, text)


# ---------------------------------------------------------------------------
# 3) Verification form: clearer 3-stage flow, passport-compatible input,
# stronger role validation, and more premium document cards.
# ---------------------------------------------------------------------------
path = 'flutter/lib/screens/verification_screen.dart'
text = r(path)
headline = "                Text('Verify your TaleemPK profile', style: Theme.of(sheet).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w900)),\n"
steps = r'''                Text('Verify your TaleemPK profile', style: Theme.of(sheet).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w900)),
                const SizedBox(height: 12),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 11),
                  decoration: BoxDecoration(
                    color: Theme.of(sheet).colorScheme.surfaceContainerHighest.withValues(alpha: .35),
                    borderRadius: BorderRadius.circular(17),
                  ),
                  child: const Row(
                    children: [
                      Expanded(child: _VerificationStep(icon: Icons.person_outline_rounded, label: 'Details', active: true)),
                      _VerificationStepDivider(),
                      Expanded(child: _VerificationStep(icon: Icons.description_outlined, label: 'Documents')),
                      _VerificationStepDivider(),
                      Expanded(child: _VerificationStep(icon: Icons.fact_check_outlined, label: 'Review')),
                    ],
                  ),
                ),
'''
text = once(text, headline, steps, 'verification step header')

old_id = "                TextField(controller: idNumber, keyboardType: TextInputType.number, decoration: const InputDecoration(labelText: 'CNIC / B-Form / Passport number *', hintText: '35202-1234567-1')),"
new_id = "                TextField(controller: idNumber, keyboardType: TextInputType.text, textCapitalization: TextCapitalization.characters, autocorrect: false, decoration: const InputDecoration(labelText: 'CNIC / B-Form / Passport number *', hintText: 'e.g. 35202-1234567-1 or AB1234567'))," 
text = once(text, old_id, new_id, 'passport-compatible identity input')

old_validation = """                          if (current?.hasDocId != true && idDoc == null) {
                            showMessage(sheet, 'Select an identity document.');
                            return;
                          }
                          if (kind != 'student' && current?.hasDocProof != true && proofDoc == null) {"""
new_validation = """                          if ((kind == 'teacher' || kind == 'institute') && orgName.text.trim().length < 2) {
                            showMessage(sheet, kind == 'teacher' ? 'Enter your school, college or institute.' : 'Enter the institute or organization name.');
                            return;
                          }
                          if (kind == 'teacher' && roleTitle.text.trim().length < 2) {
                            showMessage(sheet, 'Enter your teaching role or designation.');
                            return;
                          }
                          if (website.text.trim().isNotEmpty) {
                            final uri = Uri.tryParse(website.text.trim());
                            if (uri == null || !(uri.hasScheme && uri.host.isNotEmpty)) {
                              showMessage(sheet, 'Enter a complete website address, including https://');
                              return;
                            }
                          }
                          if (current?.hasDocId != true && idDoc == null) {
                            showMessage(sheet, 'Select an identity document.');
                            return;
                          }
                          if (kind != 'student' && current?.hasDocProof != true && proofDoc == null) {"""
text = once(text, old_validation, new_validation, 'verification role validation')

# Improve document picker card feedback without changing accepted file types.
text = text.replace(
    "          border: Border.all(color: Theme.of(context).dividerColor),\n          borderRadius: BorderRadius.circular(15),",
    "          color: path == null ? null : AppColors.success.withValues(alpha: .035),\n          border: Border.all(color: path == null ? Theme.of(context).dividerColor : AppColors.success.withValues(alpha: .30)),\n          borderRadius: BorderRadius.circular(17),",
    1,
)
text = text.replace(
    "            const Icon(Icons.description_outlined, color: AppColors.blue),",
    "            Icon(path == null ? Icons.upload_file_rounded : Icons.check_circle_rounded, color: path == null ? AppColors.blue : AppColors.success),",
    1,
)

# Add tiny reusable stage widgets after the screen State class, before the
# status value object.
status_marker = '\nclass _StatusInfo {'
verify_helpers = r'''
class _VerificationStep extends StatelessWidget {
  const _VerificationStep({required this.icon, required this.label, this.active = false});
  final IconData icon;
  final String label;
  final bool active;
  @override
  Widget build(BuildContext context) => Column(
    mainAxisSize: MainAxisSize.min,
    children: [
      Container(
        width: 30,
        height: 30,
        decoration: BoxDecoration(
          color: active ? AppColors.blue : Theme.of(context).colorScheme.surface,
          shape: BoxShape.circle,
          border: Border.all(color: active ? AppColors.blue : Theme.of(context).dividerColor),
        ),
        child: Icon(icon, size: 16, color: active ? Colors.white : AppColors.muted),
      ),
      const SizedBox(height: 4),
      Text(label, style: TextStyle(fontSize: 10.5, fontWeight: active ? FontWeight.w900 : FontWeight.w700, color: active ? AppColors.blue : AppColors.muted)),
    ],
  );
}

class _VerificationStepDivider extends StatelessWidget {
  const _VerificationStepDivider();
  @override
  Widget build(BuildContext context) => Expanded(
    child: Container(
      margin: const EdgeInsets.only(bottom: 20),
      height: 1.5,
      color: Theme.of(context).dividerColor,
    ),
  );
}
'''
if status_marker not in text:
    raise RuntimeError('v3.9 verification status marker missing')
text = text.replace(status_marker, '\n' + verify_helpers + status_marker, 1)
w(path, text)


# ---------------------------------------------------------------------------
# 4) Security copy: explain location accuracy instead of implying GPS.
# ---------------------------------------------------------------------------
path = 'flutter/lib/screens/security_screen.dart'
text = r(path)
needle = "'Your account security settings are synced with TaleemPK on the web.'"
if needle in text:
    text = text.replace(
        needle,
        "'Your account security settings are synced with TaleemPK on the web. Sign-in location is a network/IP area, so mobile carriers or VPNs can show a nearby city rather than your exact GPS position.'",
        1,
    )
w(path, text)


# ---------------------------------------------------------------------------
# 5) Release version and generated-source audit.
# ---------------------------------------------------------------------------
path = 'flutter/pubspec.yaml'
text = r(path)
text = re.sub(r'^version:\s*[^\n]+', 'version: 3.9.0+390', text, count=1, flags=re.M)
w(path, text)

# Keep mirrored API source identical for packaging.
shutil.copy2(ROOT / 'backend/api/mobile.php', ROOT / 'flutter/backend/api/mobile.php')

api = r('flutter/lib/core/api_client.dart')
common = r('flutter/lib/widgets/common.dart')
verification = r('flutter/lib/screens/verification_screen.dart')
security = r('flutter/lib/screens/security_screen.dart')
mobile = r('backend/api/mobile.php')
pubspec = r('flutter/pubspec.yaml')
assert "'User-Agent': 'TaleemPKAndroid/3.9'" in api
assert "'client': 'TaleemPK Android app'" in api
assert 'TaleemPKAndroid/3.9' in mobile
assert "$signin['device'] = $safeDevice;" in mobile
assert "$signin['browser'] = 'TaleemPK Android app';" in mobile
assert "'api_version' => '3.9'" in mobile
assert 'PageRoute<T> premiumRoute<T>' in common
assert 'Something needs attention' in common
assert '_VerificationStep' in verification
assert 'AB1234567' in verification
assert 'Enter your teaching role or designation.' in verification
assert 'network/IP area' in security
assert 'version: 3.9.0+390' in pubspec
print('TaleemPK v3.9 identity/speed/verification polish applied successfully')
