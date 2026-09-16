/// Locks immediately, before downloads or navigation can yield to another tap.
class SingleFlight {
  bool _running = false;
  Future<void> run(Future<void> Function() action) async {
    if (_running) return;
    _running = true;
    try { await action(); } finally { _running = false; }
  }
}
