<?php
// Controller contract tests: no database or email is contacted.
if ($argc === 1) {
    $cases = [
        'wrong_password' => 401, 'unknown' => 401, 'blocked' => 403,
        'malformed' => 400, 'incorrect' => 400, 'correct' => 200,
        'already_verified' => 200, 'resend' => 200, 'cooldown' => 429,
        'rate_limited' => 429, 'pending_teacher' => 200,
    ];
    foreach ($cases as $case => $status) {
        $output = shell_exec(PHP_BINARY . ' ' . escapeshellarg(__FILE__) . ' ' . escapeshellarg($case));
        $result = json_decode($output, true);
        if (!$result || $result['status'] !== $status || isset($result['data']['token'])) {
            throw new RuntimeException("Failed $case: $output");
        }
        if ($case === 'incorrect' && $result['commits'] !== 1) throw new RuntimeException('Failed attempts must persist');
        if ($case === 'pending_teacher' && $result['account_status'] !== 'pending') throw new RuntimeException('Review bypass');
    }
    echo "Email controller: 11 authentication, code and resend scenarios passed\n";
    exit;
}
$case = $argv[1];
$action = in_array($case, ['resend', 'cooldown'], true) ? 'resend_email_code' : 'verify_email';
$_POST = ['identifier' => 'student', 'password' => $case === 'wrong_password' ? 'wrong' : 'test-password',
    'code' => $case === 'malformed' ? 'abc123' : ($case === 'incorrect' ? '222222' : '123456')];
$account = ['id' => 7, 'status' => $case === 'blocked' ? 'suspended' : ($case === 'pending_teacher' ? 'pending' : 'active'),
    'password_hash' => password_hash('test-password', PASSWORD_DEFAULT), 'email_verified' => $case === 'already_verified' ? 1 : 0];
class TestConnection {
    public bool $transaction = false;
    public int $commits = 0;
    function beginTransaction() { $this->transaction = true; }
    function commit() { $this->transaction = false; $this->commits++; }
    function rollBack() { $this->transaction = false; }
    function inTransaction() { return $this->transaction; }
}
$connection = new TestConnection();
function db() { global $connection; return $connection; }
function api_burst_limit($key, $limit) { global $case; return $case !== 'rate_limited'; }
function login_rate_blocked($id) { return 0; }
function login_spray_blocked() { return 0; }
function login_rate_fail($id) {}
function login_spray_fail() {}
function fetch_one($sql, $params) { global $account, $case; return $case === 'unknown' ? null : $account; }
function send_verify_code($account, $force) {
    global $case;
    if ($force) throw new RuntimeException('Resend must respect cooldown');
    return [$case !== 'cooldown', 'Check your email.'];
}
function check_verify_code($id, $code) { return [$code === '123456', 'Code checked.']; }
function respond($data, $status) {
    global $connection, $account;
    echo json_encode(['status' => $status, 'data' => $data, 'commits' => $connection->commits, 'account_status' => $account['status']]);
    exit;
}
function mobile_error($message, $status=400) { respond(['error' => $message], $status); }
function mobile_out($data=[]) { respond($data, 200); }
require __DIR__ . '/mobile_email_v51.php';
