<?php
/** Public mobile email confirmation; password + existing hashed email code required. */
if (in_array($action, ['verify_email', 'resend_email_code'], true)) {
    if (!api_burst_limit('mobile_email_verification', 10)) {
        mobile_error('Too many requests. Wait a minute and try again.', 429);
    }
    $identifier = strtolower(trim((string) ($_POST['identifier'] ?? '')));
    $password = (string) ($_POST['password'] ?? '');
    if ($identifier === '' || $password === '') { mobile_error('Sign in again to verify your email.', 400); }
    if (max(login_rate_blocked($identifier), login_spray_blocked()) > time()) {
        mobile_error('Too many attempts. Try again later.', 429);
    }
    $account = fetch_one('SELECT * FROM users WHERE email=? OR username=? LIMIT 1', [$identifier, $identifier]);
    if (!$account || !password_verify($password, (string) $account['password_hash'])) {
        login_rate_fail($identifier); login_spray_fail();
        mobile_error('That email or password is not right.', 401);
    }
    // Serialise code attempts and resends: concurrent requests cannot bypass attempt/cooldown limits.
    $connection = db();
    try {
        $connection->beginTransaction();
        $account = fetch_one('SELECT * FROM users WHERE id=? FOR UPDATE', [(int) $account['id']]);
        if (!$account || !password_verify($password, (string) $account['password_hash'])) {
            $connection->rollBack();
            mobile_error('Your account changed. Please sign in again.', 401);
        }
        if (!in_array($account['status'], ['active', 'pending'], true)) {
            $connection->rollBack();
            mobile_error('This account is not available.', 403);
        }
        if ((int) $account['email_verified'] === 1) {
            $connection->commit();
            mobile_out(['message' => 'Email already confirmed. You can sign in.', 'email_verified' => true]);
        }
        if ($action === 'resend_email_code') {
            [$ok, $message] = send_verify_code($account, false);
        } else {
            $code = trim((string) ($_POST['code'] ?? ''));
            if (!preg_match('/^[0-9]{6}$/', $code)) {
                $connection->rollBack();
                mobile_error('Enter the six-digit email code.', 400);
            }
            [$ok, $message] = check_verify_code((int) $account['id'], $code);
        }
        // Persist failed-code counters too. Never create a login session here.
        $connection->commit();
        if (!$ok) { mobile_error($message, $action === 'resend_email_code' ? 429 : 400); }
        mobile_out(['message' => $message, 'email_verified' => $action === 'verify_email']);
    } catch (Throwable $error) {
        if ($connection->inTransaction()) { $connection->rollBack(); }
        error_log('TaleemPK mobile email verification database/mail failure');
        mobile_error('Email verification is temporarily unavailable. Please try again.', 503);
    }
}
