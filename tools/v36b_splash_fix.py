from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / 'flutter/lib/main.dart'
text = path.read_text(encoding='utf-8')
start = text.find('class _SplashScreenState extends State<SplashScreen>')
end = text.find('class OfflineScreen extends StatelessWidget', start)
if start < 0 or end < 0:
    raise RuntimeError('v3.6b splash class boundary not found')

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

'''
text = text[:start] + replacement + text[end:]
if text.count('class OfflineScreen extends StatelessWidget') != 1:
    raise RuntimeError('v3.6b offline screen boundary is invalid')
if text.count('Widget _orb(double size, Color color)') != 1:
    raise RuntimeError('v3.6b orb helper is invalid')
path.write_text(text, encoding='utf-8')
print('TaleemPK v3.6 splash class fix applied successfully')
