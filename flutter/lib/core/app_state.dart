import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'api_client.dart';
import 'models.dart';

enum AppStatus { starting, signedOut, loading, signedIn, offline }

class AppState extends ChangeNotifier {
  AppState(this.api) {
    api.onSessionExpired = _sessionExpired;
  }
  final ApiClient api;
  AppStatus status = AppStatus.starting;
  BootstrapData? bootstrap;
  String? error;
  bool darkMode = false;

  User? get user => bootstrap?.user;

  void _sessionExpired(String message) {
    bootstrap = null;
    error = message;
    status = AppStatus.signedOut;
    notifyListeners();
  }

  Future<void> start() async {
    final prefs = await SharedPreferences.getInstance();
    darkMode = prefs.getBool('dark_mode') ?? false;
    final hasToken = await api.restoreSession();
    if (!hasToken) {
      status = AppStatus.signedOut;
      notifyListeners();
      return;
    }
    await refreshSession();
  }

  Future<void> refreshSession() async {
    status = AppStatus.loading;
    error = null;
    notifyListeners();
    try {
      bootstrap = await api.bootstrap();
      status = AppStatus.signedIn;
    } on ApiException catch (e) {
      error = e.message;
      status = e.status == 401 ? AppStatus.signedOut : AppStatus.offline;
    }
    notifyListeners();
  }

  Future<AuthResult> login(String identifier, String password) async {
    final result = await api.login(identifier, password);
    if (result.token != null) {
      await api.saveToken(result.token!);
      bootstrap = await api.bootstrap();
      status = AppStatus.signedIn;
      notifyListeners();
    }
    return result;
  }

  Future<void> finishTwoFactor(String challenge, String code) async {
    final result = await api.verifyTwoFactor(challenge, code);
    if (result.token == null)
      throw const ApiException('Verification did not complete.');
    await api.saveToken(result.token!);
    bootstrap = await api.bootstrap();
    status = AppStatus.signedIn;
    notifyListeners();
  }

  Future<void> logout() async {
    await api.logout();
    bootstrap = null;
    status = AppStatus.signedOut;
    notifyListeners();
  }

  Future<void> toggleTheme() async {
    darkMode = !darkMode;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool('dark_mode', darkMode);
    notifyListeners();
  }
}

class AppScope extends InheritedNotifier<AppState> {
  const AppScope({super.key, required AppState state, required super.child})
    : super(notifier: state);
  static AppState of(BuildContext context) =>
      context.getInheritedWidgetOfExactType<AppScope>()!.notifier!;
}
