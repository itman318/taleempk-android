import 'dart:async';
import 'dart:convert';

import 'package:web_socket_channel/web_socket_channel.dart';

class RealtimeEvent {
  const RealtimeEvent({
    required this.conversationId,
    required this.type,
    this.messageId = 0,
    this.fromPush = false,
  });

  final int conversationId;
  final String type;
  final int messageId;
  final bool fromPush;
}

class RealtimeService {
  RealtimeService._();
  static final RealtimeService instance = RealtimeService._();

  final StreamController<RealtimeEvent> _events =
      StreamController<RealtimeEvent>.broadcast(sync: true);
  final Set<int> _rooms = <int>{};

  WebSocketChannel? _channel;
  StreamSubscription<dynamic>? _socketSub;
  Timer? _reconnectTimer;
  Timer? _heartbeat;
  String _url = '';
  String _ticket = '';
  int _attempt = 0;
  int _generation = 0;
  bool _connecting = false;
  bool _connected = false;

  Stream<RealtimeEvent> get events => _events.stream;
  bool get connected => _connected;

  Future<void> configure({
    required String url,
    required String ticket,
  }) async {
    final nextUrl = url.trim();
    final nextTicket = ticket.trim();
    if (nextUrl.isEmpty || nextTicket.isEmpty) {
      stop(clearRooms: false);
      return;
    }
    final same = nextUrl == _url && nextTicket == _ticket;
    _url = nextUrl;
    _ticket = nextTicket;
    if (same && (_connected || _connecting)) return;
    _generation++;
    await _disconnectSocket();
    await _connect(_generation);
  }

  void subscribe(int conversationId) {
    if (conversationId <= 0) return;
    _rooms.add(conversationId);
    _send(<String, dynamic>{
      'type': 'subscribe',
      'conversation_id': conversationId,
    });
  }

  void unsubscribe(int conversationId) {
    if (conversationId <= 0) return;
    _rooms.remove(conversationId);
    _send(<String, dynamic>{
      'type': 'unsubscribe',
      'conversation_id': conversationId,
    });
  }

  void publish(
    int conversationId, {
    String type = 'message',
    int messageId = 0,
  }) {
    if (conversationId <= 0) return;
    _send(<String, dynamic>{
      'type': 'event',
      'event': type,
      'conversation_id': conversationId,
      if (messageId > 0) 'message_id': messageId,
    });
  }

  void inject(
    int conversationId, {
    String type = 'message',
    int messageId = 0,
    bool fromPush = false,
  }) {
    if (conversationId <= 0 || _events.isClosed) return;
    _events.add(
      RealtimeEvent(
        conversationId: conversationId,
        type: type,
        messageId: messageId,
        fromPush: fromPush,
      ),
    );
  }

  Future<void> _connect(int generation) async {
    if (_connecting || _url.isEmpty || _ticket.isEmpty) return;
    _connecting = true;
    try {
      final base = Uri.parse(_url);
      final uri = base.replace(queryParameters: <String, String>{
        ...base.queryParameters,
        'ticket': _ticket,
      });
      final channel = WebSocketChannel.connect(uri);
      await channel.ready.timeout(const Duration(seconds: 7));
      if (generation != _generation) {
        await channel.sink.close();
        return;
      }
      _channel = channel;
      _connected = true;
      _attempt = 0;
      _socketSub = channel.stream.listen(
        _onData,
        onDone: _onDisconnected,
        onError: (_) => _onDisconnected(),
        cancelOnError: true,
      );
      for (final room in _rooms) {
        _send(<String, dynamic>{
          'type': 'subscribe',
          'conversation_id': room,
        });
      }
      _heartbeat?.cancel();
      _heartbeat = Timer.periodic(const Duration(seconds: 22), (_) {
        _send(<String, dynamic>{'type': 'ping'});
      });
    } catch (_) {
      _connected = false;
      _scheduleReconnect();
    } finally {
      _connecting = false;
    }
  }

  void _onData(dynamic raw) {
    try {
      final decoded = jsonDecode('$raw');
      if (decoded is! Map) return;
      final data = Map<String, dynamic>.from(decoded);
      if ('${data['type'] ?? ''}' != 'event') return;
      final conversationId = _asInt(data['conversation_id']);
      if (conversationId <= 0 || !_rooms.contains(conversationId)) return;
      inject(
        conversationId,
        type: '${data['event'] ?? 'message'}',
        messageId: _asInt(data['message_id']),
      );
    } catch (_) {
      // Ignore malformed gateway frames; API polling remains authoritative.
    }
  }

  void _send(Map<String, dynamic> frame) {
    if (!_connected || _channel == null) return;
    try {
      _channel!.sink.add(jsonEncode(frame));
    } catch (_) {
      _onDisconnected();
    }
  }

  void _onDisconnected() {
    if (!_connected && _channel == null) return;
    _connected = false;
    _heartbeat?.cancel();
    _heartbeat = null;
    _socketSub?.cancel();
    _socketSub = null;
    _channel = null;
    _scheduleReconnect();
  }

  void _scheduleReconnect() {
    _reconnectTimer?.cancel();
    if (_url.isEmpty || _ticket.isEmpty) return;
    _attempt = (_attempt + 1).clamp(1, 6);
    final delayMs = 700 * (1 << (_attempt - 1));
    final capped = delayMs.clamp(700, 15000);
    final generation = _generation;
    _reconnectTimer = Timer(Duration(milliseconds: capped), () {
      if (generation == _generation) _connect(generation);
    });
  }

  Future<void> _disconnectSocket() async {
    _reconnectTimer?.cancel();
    _reconnectTimer = null;
    _heartbeat?.cancel();
    _heartbeat = null;
    final sub = _socketSub;
    _socketSub = null;
    if (sub != null) {
      try {
        await sub.cancel();
      } catch (_) {}
    }
    final channel = _channel;
    _channel = null;
    _connected = false;
    if (channel != null) {
      try {
        await channel.sink.close();
      } catch (_) {}
    }
  }

  void stop({bool clearRooms = true}) {
    _generation++;
    _url = '';
    _ticket = '';
    _reconnectTimer?.cancel();
    _reconnectTimer = null;
    _heartbeat?.cancel();
    _heartbeat = null;
    _socketSub?.cancel();
    _socketSub = null;
    try {
      _channel?.sink.close();
    } catch (_) {}
    _channel = null;
    _connecting = false;
    _connected = false;
    _attempt = 0;
    if (clearRooms) _rooms.clear();
  }

  static int _asInt(dynamic value) =>
      value is int ? value : int.tryParse('$value') ?? 0;
}
