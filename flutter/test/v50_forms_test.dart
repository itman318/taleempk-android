import 'dart:async';
import 'dart:io';
import 'dart:ui' as ui;
import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:studyhub_flutter/core/api_client.dart';
import 'package:studyhub_flutter/core/app_state.dart';
import 'package:studyhub_flutter/core/form_rules.dart';
import 'package:studyhub_flutter/core/social_api.dart';
import 'package:studyhub_flutter/core/social_models.dart';
import 'package:studyhub_flutter/core/theme.dart';
import 'package:studyhub_flutter/screens/auth_screen.dart';
import 'package:studyhub_flutter/screens/verification_screen.dart';

class FormClient extends ApiClient {
  int logins = 0;
  final response = Completer<AuthResult>();
  @override
  Future<AuthResult> login(String identifier, String password) { logins++; return response.future; }
}

class ReviewClient extends SocialApi {
  ReviewClient() : super(ApiClient());
  int submissions = 0;
  Map<String, String>? submitted;
  final response = Completer<String>();
  @override
  Future<VerificationState> verificationStatus() async => VerificationState(
    emailVerified: true, verified: false, canApply: true, application: application('info'));
  @override
  Future<String> submitVerification({required Map<String, String> fields,
    String? idDocument, String? proofDocument, String? extraDocument,
    void Function(double progress)? onProgress}) {
    submissions++; submitted = fields; return response.future;
  }
}

Future<void> tapVisible(WidgetTester tester, Finder finder) async {
  await tester.ensureVisible(finder);
  await tester.pumpAndSettle();
  await tester.tap(finder);
  await tester.pumpAndSettle();
}

Finder field(String label) => find.byWidgetPredicate((w) =>
  w is TextField && w.decoration?.labelText == label);

Future<void> preview(WidgetTester tester, GlobalKey key, String name) async {
  await tester.runAsync(() async {
    final boundary = key.currentContext!.findRenderObject()! as RenderRepaintBoundary;
    final image = await boundary.toImage(pixelRatio: 2);
    final bytes = await image.toByteData(format: ui.ImageByteFormat.png);
    final dir = Directory('build/previews')..createSync(recursive: true);
    File('${dir.path}/$name.png').writeAsBytesSync(bytes!.buffer.asUint8List());
    image.dispose();
  });
}

VerificationApplication application(String status) => VerificationApplication.fromJson({
  'kind': 'teacher', 'status': status, 'full_name': 'Ayesha Khan',
  'id_number': '3520212345678', 'org_name': 'Community School',
  'has_doc_id': true, 'has_doc_proof': true, 'has_doc_extra': false,
});

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  setUpAll(() async {
    // Widget tests otherwise use Ahem boxes, which cannot validate typography.
    final root = Platform.environment['FLUTTER_ROOT'] ??
      File(Platform.resolvedExecutable).parent.parent.parent.parent.parent.path;
    final directory = '$root/bin/cache/artifacts/material_fonts';
    for (final family in ['sans', 'Roboto']) {
      final text = FontLoader(family);
      for (final font in ['Roboto-Regular.ttf', 'Roboto-Bold.ttf']) {
        text.addFont(File('$directory/$font').readAsBytes().then((v) => ByteData.sublistView(v)));
      }
      await text.load();
    }
    final icons = FontLoader('MaterialIcons')..addFont(File('$directory/MaterialIcons-Regular.otf')
      .readAsBytes().then((v) => ByteData.sublistView(v)));
    await icons.load();
  });
  test('registration validation follows server rules without blocking old login passwords', () {
    expect(FormRules.username('bad name'), isNotNull);
    expect(FormRules.username('ayesha_123'), isNull);
    expect(FormRules.email('ayesha@'), isNotNull);
    expect(FormRules.email('ayesha@example.com'), isNull);
    expect(FormRules.password('12345678', creating: true), isNotNull);
    expect(FormRules.password('12345678', creating: false), isNull);
    expect(FormRules.password('Distinct!Password4', creating: true), isNull);
    expect(FormRules.identity('35202-1234567-8'), isNull);
    expect(FormRules.identity('1111111111111'), isNotNull);
    expect(FormRules.website('javascript:alert(1)'), isNotNull);
    expect(FormRules.website('https://example.com'), isNull);
    expect(FormRules.dateLabel(DateTime(2001, 2, 3)), '03-02-2001');
  });

  test('document limits reject empty, oversized and unsupported files', () {
    expect(FormRules.document('CNIC.JPG', 50000), isNull);
    expect(FormRules.document('proof.pdf', 6 * 1024 * 1024), isNull);
    expect(FormRules.document('proof.pdf', 6 * 1024 * 1024 + 1), isNotNull);
    expect(FormRules.document('proof.pdf', 0), isNotNull);
    expect(FormRules.document('proof.exe', 500), isNotNull);
    expect(FormRules.reuseDocuments('info'), isTrue);
    for (final status in ['rejected', 'withdrawn', 'expired', 'pending', null]) {
      expect(FormRules.reuseDocuments(status), isFalse);
    }
  });

  for (final dark in [false, true]) {
    for (final scale in [1.0, 1.6]) {
      testWidgets('signup is readable at 320px, dark=$dark scale=$scale', (tester) async {
        tester.view.physicalSize = const Size(320, 880);
        tester.view.devicePixelRatio = 1;
        addTearDown(tester.view.resetPhysicalSize);
        addTearDown(tester.view.resetDevicePixelRatio);
        final state = AppState(ApiClient());
        final boundary = GlobalKey();
        await tester.pumpWidget(AppScope(state: state, child: MaterialApp(
          theme: dark ? studyHubDarkTheme() : studyHubTheme(),
          builder: (context, child) => MediaQuery(data: MediaQuery.of(context).copyWith(
            textScaler: TextScaler.linear(scale)), child: RepaintBoundary(key: boundary, child: child!)),
          home: const AuthScreen())));
        await tapVisible(tester, find.text('New here? Create an account'));
        expect(find.text('A place to grow.'), findsOneWidget);
        expect(find.text('Student'), findsOneWidget);
        expect(tester.takeException(), isNull);
        if (scale == 1) {
          await tester.drag(find.byType(SingleChildScrollView), const Offset(0, 1200));
          await tester.pumpAndSettle();
          await preview(tester, boundary, dark ? 'signup-dark' : 'signup-light');
        }
        await tapVisible(tester, find.text('Continue'));
        expect(find.text('Enter your full name (at least 3 characters).'), findsOneWidget);
        await tester.enterText(field('Full name'), 'Ayesha Khan');
        await tester.enterText(field('Username'), 'ayesha_khan');
        await tapVisible(tester, find.text('Continue'));
        expect(field('Email address'), findsOneWidget);
        await tester.enterText(field('Email address'), 'invalid');
        await tapVisible(tester, find.text('Continue'));
        expect(find.text('Enter a valid email address.'), findsOneWidget);
        await tester.enterText(field('Email address'), 'ayesha@example.com');
        await tapVisible(tester, field('Date of birth'));
        await tapVisible(tester, find.text('OK'));
        await tapVisible(tester, find.text('Continue'));
        expect(field('Confirm password'), findsOneWidget);
        await tester.enterText(field('Password'), 'LongPassword123!');
        await tester.enterText(field('Confirm password'), 'OtherPassword123!');
        await tapVisible(tester, find.text('Create account'));
        expect(find.text('The passwords do not match.'), findsOneWidget);
        expect(tester.takeException(), isNull);
        await tester.pumpWidget(const SizedBox()); state.dispose();
      });
    }
  }

  testWidgets('login allows legacy passwords and prevents duplicate requests', (tester) async {
    final api = FormClient(); final state = AppState(api);
    await tester.pumpWidget(AppScope(state: state, child: MaterialApp(theme: studyHubTheme(), home: const AuthScreen())));
    await tester.enterText(field('Email or username'), 'admin');
    await tester.enterText(field('Password'), 'short');
    await tester.ensureVisible(find.text('Sign in'));
    await tester.tap(find.text('Sign in')); await tester.pump();
    expect(api.logins, 1);
    await tester.tap(find.text('Signing in…')); await tester.pump();
    expect(api.logins, 1);
    api.response.completeError(const ApiException('Check your account details.'));
    await tester.pumpAndSettle();
    expect(find.text('Check your account details.'), findsOneWidget);
    await tester.pumpWidget(const SizedBox()); state.dispose();
  });

  for (final status in ['info', 'rejected']) {
    testWidgets('verification $status respects document retention and declaration', (tester) async {
      tester.view.physicalSize = const Size(320, 880);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize); addTearDown(tester.view.resetDevicePixelRatio);
      final api = ReviewClient(); final boundary = GlobalKey();
      await tester.pumpWidget(MaterialApp(theme: studyHubTheme(),
        home: RepaintBoundary(key: boundary, child: VerificationApplicationScreen(
          social: api, current: application(status)))));
      await tester.pumpAndSettle();
      await preview(tester, boundary, 'verification-$status');
      await tapVisible(tester, find.text('Continue'));
      expect(find.text('Add your documents'), findsOneWidget);
      await tapVisible(tester, find.text('Continue'));
      if (status == 'info') {
        expect(find.text('Ready for review?'), findsOneWidget);
        await tapVisible(tester, find.text('Submit for review'));
        expect(api.submissions, 0);
        expect(find.text('Please confirm the declaration before submitting.'), findsOneWidget);
        await tapVisible(tester, find.byType(CheckboxListTile));
        await tester.ensureVisible(find.text('Submit for review'));
        await tester.tap(find.text('Submit for review')); await tester.pump();
        expect(api.submissions, 1);
        expect(api.submitted!['kind'], 'teacher');
        expect(api.submitted!['id_number'], '3520212345678');
        api.response.completeError(const ApiException('Please provide a clearer document.'));
        await tester.pumpAndSettle();
        expect(find.text('Please provide a clearer document.'), findsOneWidget);
      } else {
        expect(find.text('Add your documents'), findsOneWidget);
        expect(find.text('Add your identity document and proof of role to continue.'), findsOneWidget);
        expect(api.submissions, 0);
      }
      expect(tester.takeException(), isNull);
    });
  }

  for (final dark in [false, true]) {
    testWidgets('verification dashboard adapts to dark=$dark and enlarged text', (tester) async {
      tester.view.physicalSize = const Size(390, 940);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize); addTearDown(tester.view.resetDevicePixelRatio);
      final boundary = GlobalKey();
      await tester.pumpWidget(MaterialApp(theme: dark ? studyHubDarkTheme() : studyHubTheme(),
        builder: (context, child) => MediaQuery(data: MediaQuery.of(context).copyWith(
          textScaler: const TextScaler.linear(1.3)), child: RepaintBoundary(key: boundary, child: child!)),
        home: VerificationScreen(social: ReviewClient())));
      await tester.pumpAndSettle();
      expect(find.text('More information needed'), findsOneWidget);
      await preview(tester, boundary, dark ? 'verification-dashboard-dark' : 'verification-dashboard-light');
      await tester.ensureVisible(find.text('Update application'));
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
    });
  }
}
