import 'package:flutter/material.dart';

import 'core/api_client.dart';
import 'core/app_state.dart';
import 'core/theme.dart';
import 'screens/auth_screen.dart';
import 'screens/home_shell.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final state = AppState(ApiClient());
  runApp(
    AppScope(
      state: state,
      child: StudyHubApp(state: state),
    ),
  );
  await state.start();
}

class StudyHubApp extends StatelessWidget {
  const StudyHubApp({super.key, required this.state});
  final AppState state;

  @override
  Widget build(BuildContext context) => AnimatedBuilder(
    animation: state,
    builder: (context, _) => MaterialApp(
      title: 'TaleemPK',
      debugShowCheckedModeBanner: false,
      theme: studyHubTheme(),
      darkTheme: studyHubDarkTheme(),
      themeMode: state.darkMode ? ThemeMode.dark : ThemeMode.light,
      home: switch (state.status) {
        AppStatus.starting || AppStatus.loading => const SplashScreen(),
        AppStatus.signedOut => const AuthScreen(),
        AppStatus.signedIn => const HomeShell(),
        AppStatus.offline => OfflineScreen(
          message: state.error ?? 'Could not connect to TaleemPK.',
        ),
      },
    ),
  );
}

class SplashScreen extends StatefulWidget {
  const SplashScreen({super.key});
  @override
  State<SplashScreen> createState() => _SplashScreenState();
}

class _SplashScreenState extends State<SplashScreen>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 1100),
  )..forward();
  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    body: Container(
      decoration: const BoxDecoration(
        gradient: LinearGradient(
          colors: [Color(0xFF06122C), Color(0xFF152B63), Color(0xFF5131AD)],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
      ),
      child: Stack(
        children: [
          Positioned(
            top: -90,
            right: -80,
            child: _orb(250, const Color(0x332BCEE8)),
          ),
          Positioned(
            bottom: -100,
            left: -90,
            child: _orb(280, const Color(0x337B61FF)),
          ),
          Center(
            child: FadeTransition(
              opacity: CurvedAnimation(
                parent: _controller,
                curve: Curves.easeOut,
              ),
              child: ScaleTransition(
                scale: Tween(begin: .84, end: 1.0).animate(
                  CurvedAnimation(
                    parent: _controller,
                    curve: Curves.easeOutBack,
                  ),
                ),
                child: const Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    BrandMark(size: 82, light: true),
                    SizedBox(height: 22),
                    Text(
                      'Learn today. Lead tomorrow.',
                      style: TextStyle(
                        color: Color(0xCCFFFFFF),
                        fontSize: 15,
                        letterSpacing: .2,
                      ),
                    ),
                    SizedBox(height: 38),
                    SizedBox(
                      width: 30,
                      height: 30,
                      child: CircularProgressIndicator(
                        color: Colors.white,
                        strokeWidth: 2.5,
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
    ),
  );

  Widget _orb(double size, Color color) => Container(
    width: size,
    height: size,
    decoration: BoxDecoration(shape: BoxShape.circle, color: color),
  );
}

class OfflineScreen extends StatelessWidget {
  const OfflineScreen({super.key, required this.message});
  final String message;
  @override
  Widget build(BuildContext context) => Scaffold(
    body: SafeArea(
      child: Center(
        child: Padding(
          padding: const EdgeInsets.all(32),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const BrandMark(),
              const SizedBox(height: 42),
              const Icon(
                Icons.cloud_off_rounded,
                size: 58,
                color: AppColors.muted,
              ),
              const SizedBox(height: 18),
              Text(
                'Connection interrupted',
                style: Theme.of(context).textTheme.headlineSmall
                    ?.copyWith(fontWeight: FontWeight.w800),
              ),
              const SizedBox(height: 10),
              Text(
                message,
                textAlign: TextAlign.center,
                style: const TextStyle(color: AppColors.muted, height: 1.5),
              ),
              const SizedBox(height: 28),
              FilledButton.icon(
                onPressed: AppScope.of(context).refreshSession,
                icon: const Icon(Icons.refresh_rounded),
                label: const Text('Try again'),
              ),
              TextButton(
                onPressed: AppScope.of(context).logout,
                child: const Text('Sign in with another account'),
              ),
            ],
          ),
        ),
      ),
    ),
  );
}
