import 'dart:async';
import 'dart:io';
import 'dart:ui' as ui;
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:studyhub_flutter/core/api_client.dart';
import 'package:studyhub_flutter/core/app_state.dart';
import 'package:studyhub_flutter/core/models.dart';
import 'package:studyhub_flutter/core/theme.dart';
import 'package:studyhub_flutter/core/single_flight.dart';
import 'package:studyhub_flutter/screens/auth_screen.dart';
import 'package:studyhub_flutter/screens/attachment_sheet.dart';
import 'package:studyhub_flutter/screens/email_verification_sheet.dart';
import 'package:studyhub_flutter/screens/home_screen.dart';
import 'package:studyhub_flutter/screens/media_preview_screen.dart';
import 'package:studyhub_flutter/screens/photo_editor_screen.dart';
import 'v50_forms_test.dart' as helpers;

class EmailClient extends ApiClient {
  int calls = 0, registrations = 0;
  String? codeSent;
  Completer<String>? pending;
  @override
  Future<RegistrationResult> register({required String role, required String name, required String username,
    required String email, required String phone, required String dob, required String password}) async {
    registrations++;
    return const RegistrationResult('Account created.', true, false);
  }
  @override
  Future<AuthResult> login(String identifier, String password) async =>
    const AuthResult(needsEmailVerification: true, email: 'student@example.com');
  @override
  Future<String> confirmEmail({required String identifier, required String password, String? code}) {
    calls++; codeSent = code;
    expect(identifier, 'student'); expect(password, 'password');
    return pending?.future ?? Future.value('Code sent.');
  }
}
void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  setUpAll(() async {
    final root = Platform.environment['FLUTTER_ROOT']!;
    for (final family in ['sans','Roboto']) {
      final loader = FontLoader(family);
      for (final name in ['Roboto-Regular.ttf','Roboto-Bold.ttf']) {
        loader.addFont(File('$root/bin/cache/artifacts/material_fonts/$name').readAsBytes().then(ByteData.sublistView));
      }
      await loader.load();
    }
    final loader = FontLoader('MaterialIcons')..addFont(File('$root/bin/cache/artifacts/material_fonts/MaterialIcons-Regular.otf')
      .readAsBytes().then(ByteData.sublistView));
    await loader.load();
  });
  test('rapid photo taps create exactly one viewer and reset on close/error', () async {
    final gate = SingleFlight(); final visible = Completer<void>(); var opens = 0;
    final first = gate.run(() async { opens++; await visible.future; });
    await Future.wait(List.generate(5, (_) => gate.run(() async { opens++; })));
    expect(opens, 1); visible.complete(); await first;
    await expectLater(gate.run(() async { throw StateError('download failed'); }), throwsStateError);
    await gate.run(() async { opens++; }); expect(opens, 2);
  });
  testWidgets('unverified login opens native email-code form without signing in', (tester) async {
    final api = EmailClient();
    final app = AppState(api);
    await tester.pumpWidget(AppScope(state: app, child: MaterialApp(theme: studyHubTheme(), home: const AuthScreen())));
    await tester.enterText(helpers.field('Email or username'), 'student');
    await tester.enterText(helpers.field('Password'), 'password');
    await helpers.tapVisible(tester, find.text('Sign in'));
    expect(find.byType(EmailVerificationSheet), findsOneWidget);
    expect(helpers.field('Email verification code'), findsOneWidget);
    expect(api.token, isNull);
    await helpers.tapVisible(tester, find.text('Verify email'));
    expect(api.calls, 0);
    api.pending = Completer<String>();
    await tester.enterText(helpers.field('Email verification code'), '123456');
    await tester.tap(find.text('Verify email')); await tester.pump();
    await tester.tap(find.text('Verify email')); await tester.pump();
    expect(api.calls, 1); expect(api.codeSent, '123456');
    api.pending!.complete('Email confirmed.'); await tester.pumpAndSettle();
    expect(find.text('Email verified. Sign in to continue.'), findsOneWidget);
    expect(api.token, isNull);
    await tester.pumpWidget(const SizedBox()); app.dispose();
  });
  testWidgets('signup requires Create account and immediately offers email confirmation', (tester) async {
    final api = EmailClient();
    final app = AppState(api);
    await tester.pumpWidget(AppScope(state: app, child: MaterialApp(theme: studyHubTheme(), home: const AuthScreen())));
    await helpers.tapVisible(tester, find.text('New here? Create an account'));
    await tester.enterText(helpers.field('Full name'), 'Ayesha Khan');
    await tester.enterText(helpers.field('Username'), 'student');
    await helpers.tapVisible(tester, find.text('Continue'));
    await tester.enterText(helpers.field('Email address'), 'student@example.com');
    await helpers.tapVisible(tester, helpers.field('Date of birth'));
    await helpers.tapVisible(tester, find.text('OK'));
    await helpers.tapVisible(tester, find.text('Continue'));
    await tester.enterText(helpers.field('Password'), 'GoodPassword123!');
    await tester.testTextInput.receiveAction(TextInputAction.next);
    await tester.pumpAndSettle(); expect(api.registrations, 0);
    await tester.enterText(helpers.field('Confirm password'), 'GoodPassword123!');
    expect(api.registrations, 0);
    await helpers.tapVisible(tester, find.text('Create account'));
    expect(api.registrations, 1); expect(find.byType(EmailVerificationSheet), findsOneWidget);
    await tester.pumpWidget(const SizedBox()); app.dispose();
  });
  testWidgets('resend cooldown and server error keep the code form usable', (tester) async {
    final api = EmailClient();
    await tester.pumpWidget(MaterialApp(theme: studyHubTheme(), home: Scaffold(body: EmailVerificationSheet(
      api: api, identifier: 'student', password: 'password'))));
    await helpers.tapVisible(tester, find.text('Resend code'));
    expect(api.calls, 1); expect(api.codeSent, isNull); expect(find.text('Resend in 60s'), findsOneWidget);
    api.pending = Completer<String>();
    await tester.enterText(helpers.field('Email verification code'), '111111');
    await tester.tap(find.text('Verify email')); await tester.pump();
    api.pending!.completeError(const ApiException('That code has expired.'));
    await tester.pumpAndSettle();
    expect(find.text('That code has expired.'), findsOneWidget);
    expect(helpers.field('Email verification code'), findsOneWidget);
    await tester.pumpWidget(const SizedBox());
  });
  for (final dark in [false,true]) {
    testWidgets('dashboard and attachment sheet fit small screens dark=$dark', (tester) async {
      tester.view.physicalSize = const Size(360,800); tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize); addTearDown(tester.view.resetDevicePixelRatio);
      final state = AppState(ApiClient())..bootstrap = BootstrapData.fromJson({
        'user': {'id':1,'name':'Ayesha Khan','username':'ayesha','role':'student','verified':true},
        'shortcuts': [
          {'title':'Study dashboard','subtitle':'Your plan and next steps','route':'study.php','icon':'study'},
          {'title':'Study library','subtitle':'Notes and learning resources','route':'library.php','icon':'library'},
          {'title':'Study groups','subtitle':'Learn together by subject','route':'groups.php','icon':'groups'},
        ]});
      final key = GlobalKey();
      await tester.pumpWidget(AppScope(state: state, child: MaterialApp(theme: dark ? studyHubDarkTheme() : studyHubTheme(),
        builder: (context, child) => MediaQuery(data: MediaQuery.of(context).copyWith(textScaler: const TextScaler.linear(1.3)),
          child: RepaintBoundary(key: key, child: child!)), home: const HomeScreen())));
      await tester.pumpAndSettle(); expect(tester.takeException(), isNull);
      await helpers.preview(tester, key, 'v51-home-${dark ? 'dark' : 'light'}');
      await tester.pumpWidget(MaterialApp(theme: dark ? studyHubDarkTheme() : studyHubTheme(), home: Scaffold(
        body: RepaintBoundary(key: key, child: const AttachmentSheet(isGroup: false)))));
      await tester.pumpAndSettle(); expect(find.text('Edit before sending'), findsNothing);
      await helpers.preview(tester, key, 'v51-attachments-${dark ? 'dark' : 'light'}');
      await tester.pumpWidget(const SizedBox()); state.dispose();
    });
  }
  testWidgets('image crop exports selected pixels, preview requires explicit send', (tester) async {
    late Directory temp; late String path;
    await tester.runAsync(() async {
      final recorder = ui.PictureRecorder();
      final drawing = Canvas(recorder)..drawColor(Colors.red, BlendMode.src);
      drawing.drawRect(const Rect.fromLTWH(40, 0, 40, 60), Paint()..color=Colors.blue);
      final picture = recorder.endRecording(); final source = await picture.toImage(80,60); picture.dispose();
      final cropped = await cropPixels(source, cropSelection(const Offset(1,1), const Offset(.5,0)));
      expect(cropped.width,40); expect(cropped.height,60);
      final rgba = await cropped.toByteData(); expect(rgba!.getUint8(2),255); expect(rgba.getUint8(0),0);
      await expectLater(cropPixels(source, Rect.zero), throwsArgumentError);
      temp = await Directory.systemTemp.createTemp('v51-test-'); path = '${temp.path}/photo.png';
      final png = await source.toByteData(format: ui.ImageByteFormat.png);
      await File(path).writeAsBytes(png!.buffer.asUint8List());
      source.dispose(); cropped.dispose();
    });
    var sends = 0;
    await tester.pumpWidget(MaterialApp(theme: studyHubTheme(), home: Builder(builder: (context) => Scaffold(body: TextButton(
      child: const Text('Pick'), onPressed: () async {
        final paths = await Navigator.push<List<String>>(context, MaterialPageRoute(builder: (_) => MediaPreviewScreen(paths:[path])));
        if (paths != null) sends++;
      })))));
    await helpers.tapVisible(tester,find.text('Pick'));
    expect(sends,0); expect(find.text('Edit / Crop'),findsOneWidget);
    await helpers.tapVisible(tester,find.text('Send 1')); expect(sends,1);
    await helpers.tapVisible(tester,find.text('Pick'));
    await tester.tap(find.byTooltip('Cancel sending')); await tester.pumpAndSettle(); expect(sends,1);
    await tester.pumpWidget(const SizedBox()); await temp.delete(recursive:true);
  });
}
