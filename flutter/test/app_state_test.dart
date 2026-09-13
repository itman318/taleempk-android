import 'package:flutter_test/flutter_test.dart';
import 'package:studyhub_flutter/core/api_client.dart';
import 'package:studyhub_flutter/core/app_state.dart';

void main() {
  test('expired native session returns the whole app to signed-out state', () {
    final api = ApiClient();
    final state = AppState(api)
      ..status = AppStatus.signedIn
      ..error = null;

    api.onSessionExpired?.call('Session expired');

    expect(state.status, AppStatus.signedOut);
    expect(state.bootstrap, isNull);
    expect(state.error, 'Session expired');
  });
}
