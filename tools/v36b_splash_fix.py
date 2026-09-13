from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / 'flutter/lib/main.dart'
text = path.read_text(encoding='utf-8')
start = text.find('class _SplashScreenState extends State<SplashScreen>')
if start < 0:
    raise RuntimeError('v3.6b splash state start not found')

replacement = r'''class _SplashScreenState extends State<SplashScreen>
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
              colors: [Color(0xFF07152F), Color(0xFF142B63), Color(0xFF3E2D92)],
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
            ),
          ),
          child: Stack(
            children: [
              Positioned(
                top: -120,
                right: -85,
                child: _orb(270, const Color(0x263AD7F0)),
              ),
              Positioned(
                bottom: -130,
                left: -100,
                child: _orb(300, const Color(0x267D63FF)),
              ),
              Positioned.fill(
                child: SafeArea(
                  child: Center(
                    child: FadeTransition(
                      opacity: CurvedAnimation(
                        parent: _controller,
                        curve: Curves.easeOut,
                      ),
                      child: ScaleTransition(
                        scale: Tween(begin: .92, end: 1.0).animate(
                          CurvedAnimation(
                            parent: _controller,
                            curve: Curves.easeOutCubic,
                          ),
                        ),
                        child: Container(
                          margin: const EdgeInsets.symmetric(horizontal: 34),
                          padding: const EdgeInsets.fromLTRB(26, 30, 26, 24),
                          decoration: BoxDecoration(
                            color: Colors.white.withValues(alpha: .07),
                            borderRadius: BorderRadius.circular(30),
                            border: Border.all(
                              color: Colors.white.withValues(alpha: .12),
                            ),
                          ),
                          child: const Column(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              BrandMark(size: 78, light: true),
                              SizedBox(height: 20),
                              Text(
                                'Learn today. Lead tomorrow.',
                                textAlign: TextAlign.center,
                                style: TextStyle(
                                  color: Color(0xE6FFFFFF),
                                  fontSize: 15,
                                  fontWeight: FontWeight.w600,
                                  letterSpacing: .1,
                                ),
                              ),
                              SizedBox(height: 8),
                              Text(
                                'Preparing your learning space',
                                style: TextStyle(
                                  color: Color(0x9FFFFFFF),
                                  fontSize: 12.5,
                                ),
                              ),
                              SizedBox(height: 26),
                              SizedBox(
                                width: 150,
                                child: LinearProgressIndicator(
                                  minHeight: 3,
                                  borderRadius: BorderRadius.all(
                                    Radius.circular(99),
                                  ),
                                  backgroundColor: Color(0x30FFFFFF),
                                  color: Colors.white,
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
        ),
      );

  Widget _orb(double size, Color color) => Container(
        width: size,
        height: size,
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          color: color,
        ),
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
                    style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                          fontWeight: FontWeight.w800,
                        ),
                  ),
                  const SizedBox(height: 10),
                  Text(
                    message,
                    textAlign: TextAlign.center,
                    style: const TextStyle(
                      color: AppColors.muted,
                      height: 1.5,
                    ),
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
'''

# v3.6's first splash transform can consume the old OfflineScreen class.
# Rebuild the complete tail from the Splash state onward so the file is valid
# regardless of whether OfflineScreen survived that intermediate transform.
text = text[:start] + replacement
if text.count('class OfflineScreen extends StatelessWidget') != 1:
    raise RuntimeError('v3.6b offline screen reconstruction failed')
if text.count('Widget _orb(double size, Color color)') != 1:
    raise RuntimeError('v3.6b orb helper reconstruction failed')
path.write_text(text, encoding='utf-8')
print('TaleemPK v3.6 splash class fix applied successfully')
