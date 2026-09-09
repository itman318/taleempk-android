import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_webrtc/flutter_webrtc.dart';

import '../core/api_client.dart';
import '../core/app_state.dart';
import '../core/models.dart';
import '../core/theme.dart';

class CallScreen extends StatefulWidget {
  const CallScreen({
    super.key,
    required this.conversation,
    required this.video,
  });

  final Conversation conversation;
  final bool video;

  @override
  State<CallScreen> createState() => _CallScreenState();
}

class _CallScreenState extends State<CallScreen> {
  final localRenderer = RTCVideoRenderer();
  final remoteRenderer = RTCVideoRenderer();

  RTCPeerConnection? peer;
  MediaStream? localStream;
  Timer? pollTimer;
  int callId = 0, lastSignalId = 0, seconds = 0;
  String status = 'Calling…';
  bool muted = false, cameraOff = false, speaker = true, ending = false;

  @override
  void initState() {
    super.initState();
    _start();
  }

  Future<void> _start() async {
    await localRenderer.initialize();
    await remoteRenderer.initialize();
    try {
      final api = AppScope.of(context).api;
      final started = await api.startCall(
        widget.conversation.id,
        video: widget.video,
      );
      callId = _int(started['call_id']);
      if (callId <= 0) {
        throw const ApiException('The call could not be started.');
      }

      final ice = (started['ice'] is List)
          ? (started['ice'] as List)
                .whereType<Map>()
                .map((e) => e.cast<String, dynamic>())
                .toList()
          : <Map<String, dynamic>>[
              {'urls': 'stun:stun.l.google.com:19302'},
            ];

      peer = await createPeerConnection({'iceServers': ice});
      peer!.onIceCandidate = (candidate) {
        final value = candidate.candidate;
        if (value == null || value.isEmpty || callId <= 0) return;
        api.sendCallSignal(callId, 'ice', {
          'candidate': value,
          'sdpMid': candidate.sdpMid,
          'sdpMLineIndex': candidate.sdpMLineIndex,
        }).catchError((_) {});
      };
      peer!.onTrack = (event) {
        if (event.streams.isNotEmpty) {
          remoteRenderer.srcObject = event.streams.first;
          if (mounted) setState(() {});
        }
      };
      peer!.onConnectionState = (state) {
        if (!mounted) return;
        setState(() {
          if (state == RTCPeerConnectionState.RTCPeerConnectionStateConnected) {
            status = 'Connected';
          } else if (state ==
              RTCPeerConnectionState.RTCPeerConnectionStateFailed) {
            status = 'Connection failed';
          }
        });
      };

      localStream = await navigator.mediaDevices.getUserMedia({
        'audio': true,
        'video': widget.video
            ? {
                'facingMode': 'user',
                'width': {'ideal': 720},
                'height': {'ideal': 1280},
              }
            : false,
      });
      localRenderer.srcObject = localStream;
      for (final track in localStream!.getTracks()) {
        await peer!.addTrack(track, localStream!);
      }

      final offer = await peer!.createOffer();
      await peer!.setLocalDescription(offer);
      await api.sendCallSignal(callId, 'offer', {
        'type': offer.type,
        'sdp': offer.sdp,
      });

      pollTimer = Timer.periodic(
        const Duration(milliseconds: 900),
        (_) => _poll(),
      );
      await _poll();
    } catch (e) {
      if (mounted) {
        setState(() => status = apiMessage(e));
      }
    }
  }

  Future<void> _poll() async {
    if (callId <= 0 || ending || !mounted) return;
    try {
      final state = await AppScope.of(context).api.callState(
        callId,
        afterSignalId: lastSignalId,
      );
      final serverStatus = '${state['status'] ?? ''}';
      seconds = _int(state['seconds']);

      if (serverStatus == 'ringing') {
        status = state['delivered'] == true ? 'Ringing…' : 'Calling…';
      } else if (serverStatus == 'accepted') {
        status = 'Connected';
      } else if (serverStatus.isNotEmpty &&
          serverStatus != 'ringing' &&
          serverStatus != 'accepted') {
        status = serverStatus == 'missed'
            ? 'No answer'
            : serverStatus == 'declined'
            ? 'Call declined'
            : 'Call ended';
        await _finishLocal();
        if (mounted) setState(() {});
        return;
      }

      final signals = state['signals'];
      if (signals is List) {
        for (final raw in signals) {
          if (raw is! Map) continue;
          final signal = raw.cast<String, dynamic>();
          final id = _int(signal['id']);
          if (id > lastSignalId) lastSignalId = id;
          final kind = '${signal['kind'] ?? ''}';
          final payload = signal['payload'];
          if (payload is! Map) continue;
          final data = payload.cast<String, dynamic>();
          if (kind == 'answer') {
            await peer?.setRemoteDescription(
              RTCSessionDescription(
                '${data['sdp'] ?? ''}',
                '${data['type'] ?? 'answer'}',
              ),
            );
          } else if (kind == 'ice') {
            await peer?.addCandidate(
              RTCIceCandidate(
                '${data['candidate'] ?? ''}',
                data['sdpMid']?.toString(),
                _int(data['sdpMLineIndex']),
              ),
            );
          }
        }
      }
      if (mounted) setState(() {});
    } catch (_) {
      // A single missed signalling poll should not tear down a live call.
    }
  }

  Future<void> _hangUp() async {
    if (ending) return;
    ending = true;
    try {
      if (callId > 0) {
        await AppScope.of(context).api.endCall(callId);
      }
    } catch (_) {}
    await _finishLocal();
    if (mounted) Navigator.pop(context);
  }

  Future<void> _finishLocal() async {
    pollTimer?.cancel();
    pollTimer = null;
    for (final track in localStream?.getTracks() ?? <MediaStreamTrack>[]) {
      track.stop();
    }
    await localStream?.dispose();
    localStream = null;
    await peer?.close();
    peer = null;
  }

  void _toggleMute() {
    muted = !muted;
    for (final track in localStream?.getAudioTracks() ?? <MediaStreamTrack>[]) {
      track.enabled = !muted;
    }
    setState(() {});
  }

  void _toggleCamera() {
    if (!widget.video) return;
    cameraOff = !cameraOff;
    for (final track in localStream?.getVideoTracks() ?? <MediaStreamTrack>[]) {
      track.enabled = !cameraOff;
    }
    setState(() {});
  }

  Future<void> _switchCamera() async {
    final tracks = localStream?.getVideoTracks() ?? <MediaStreamTrack>[];
    if (tracks.isNotEmpty) {
      await Helper.switchCamera(tracks.first);
    }
  }

  @override
  void dispose() {
    pollTimer?.cancel();
    for (final track in localStream?.getTracks() ?? <MediaStreamTrack>[]) {
      track.stop();
    }
    localStream?.dispose();
    peer?.close();
    localRenderer.dispose();
    remoteRenderer.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final connected = status == 'Connected';
    return PopScope(
      canPop: false,
      onPopInvokedWithResult: (_, __) => _hangUp(),
      child: Scaffold(
        backgroundColor: const Color(0xFF050B17),
        body: Stack(
          fit: StackFit.expand,
          children: [
            if (widget.video && remoteRenderer.srcObject != null)
              RTCVideoView(
                remoteRenderer,
                objectFit: RTCVideoViewObjectFit.RTCVideoViewObjectFitCover,
              )
            else
              _audioBackground(),
            if (widget.video && localRenderer.srcObject != null)
              Positioned(
                right: 18,
                top: MediaQuery.paddingOf(context).top + 18,
                width: 112,
                height: 158,
                child: ClipRRect(
                  borderRadius: BorderRadius.circular(18),
                  child: RTCVideoView(
                    localRenderer,
                    mirror: true,
                    objectFit:
                        RTCVideoViewObjectFit.RTCVideoViewObjectFitCover,
                  ),
                ),
              ),
            SafeArea(
              child: Column(
                children: [
                  const SizedBox(height: 22),
                  Text(
                    widget.conversation.title,
                    style: const TextStyle(
                      color: Colors.white,
                      fontSize: 24,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    connected ? _clock(seconds) : status,
                    style: const TextStyle(
                      color: Color(0xFFC7D0E0),
                      fontSize: 15,
                    ),
                  ),
                  const Spacer(),
                  Padding(
                    padding: const EdgeInsets.fromLTRB(20, 0, 20, 34),
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                      children: [
                        _round(
                          muted ? Icons.mic_off_rounded : Icons.mic_rounded,
                          _toggleMute,
                          muted ? 'Unmute' : 'Mute',
                        ),
                        if (widget.video)
                          _round(
                            cameraOff
                                ? Icons.videocam_off_rounded
                                : Icons.videocam_rounded,
                            _toggleCamera,
                            cameraOff ? 'Camera on' : 'Camera off',
                          ),
                        if (widget.video)
                          _round(
                            Icons.cameraswitch_rounded,
                            _switchCamera,
                            'Switch',
                          ),
                        _round(
                          Icons.call_end_rounded,
                          _hangUp,
                          'End',
                          danger: true,
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _audioBackground() => Container(
    decoration: const BoxDecoration(
      gradient: LinearGradient(
        colors: [Color(0xFF071020), Color(0xFF132B56), Color(0xFF3A246A)],
        begin: Alignment.topLeft,
        end: Alignment.bottomRight,
      ),
    ),
    child: Center(
      child: Container(
        width: 128,
        height: 128,
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          color: const Color(0xFF17284C),
          boxShadow: const [
            BoxShadow(color: Color(0x663157E8), blurRadius: 45),
          ],
        ),
        alignment: Alignment.center,
        child: Text(
          widget.conversation.title.isEmpty
              ? '?'
              : widget.conversation.title[0].toUpperCase(),
          style: const TextStyle(
            color: Colors.white,
            fontSize: 48,
            fontWeight: FontWeight.w800,
          ),
        ),
      ),
    ),
  );

  Widget _round(
    IconData icon,
    FutureOr<void> Function() onTap,
    String label, {
    bool danger = false,
  }) => Column(
    mainAxisSize: MainAxisSize.min,
    children: [
      IconButton.filled(
        style: IconButton.styleFrom(
          backgroundColor:
              danger ? AppColors.danger : const Color(0xCC23304A),
          foregroundColor: Colors.white,
          minimumSize: const Size(58, 58),
        ),
        onPressed: () => onTap(),
        icon: Icon(icon),
      ),
      const SizedBox(height: 7),
      Text(
        label,
        style: const TextStyle(color: Color(0xFFCBD4E4), fontSize: 11),
      ),
    ],
  );

  String _clock(int value) =>
      '${(value ~/ 60).toString().padLeft(2, '0')}:${(value % 60).toString().padLeft(2, '0')}';

  int _int(dynamic value) =>
      value is int ? value : int.tryParse('$value') ?? 0;
}
