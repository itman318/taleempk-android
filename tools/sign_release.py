"""Sign a compiled release APK with an existing, privately stored release key.

Never generate or rotate a key here. Keep the keystore and password outside git.
Usage: python3 tools/sign_release.py --sdk-tools PATH --key-dir PATH --input APK --output APK
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import zipfile


def run(command, environment=None):
    result = subprocess.run([str(x) for x in command], capture_output=True, text=True, env=environment)
    if result.returncode:
        raise RuntimeError(f'{Path(str(command[0])).name} failed: {result.stderr[-2000:]}')
    return result.stdout


def payload_hashes(path):
    with zipfile.ZipFile(path) as archive:
        assert archive.testzip() is None, 'Corrupt APK payload'
        return {name: hashlib.sha256(archive.read(name)).hexdigest()
                for name in archive.namelist() if not name.startswith('META-INF/')}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['sdk-tools', 'key-dir', 'input', 'output']:
        parser.add_argument('--' + name, required=True, type=Path)
    args = parser.parse_args()
    assert args.input.resolve() != args.output.resolve(), 'Keep the original APK'
    assert not args.output.exists(), 'Do not overwrite a previous release'
    key = args.key_dir / 'taleempk-release.keystore'
    password = args.key_dir / 'keystore-password.txt'
    metadata = json.loads((args.key_dir / 'public-signing-info.json').read_text())
    assert key.is_file() and password.is_file(), 'Original release key is required'
    assert metadata['subject'] != 'C=US,O=Android,CN=Android Debug'
    badging = run([args.sdk_tools / 'aapt2', 'dump', 'badging', args.input])
    assert "name='online.taleempk.studyhub'" in badging, 'Wrong application'
    assert 'application-debuggable' not in badging, 'Debuggable builds cannot be released'
    assert "minSdkVersion:'24'" in badging, 'Review changed minimum Android version'
    before = payload_hashes(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    aligned = args.output.with_suffix('.aligned.apk')
    assert not aligned.exists(), 'Inspect and remove an unfinished aligned file first'
    try:
        run([args.sdk_tools / 'zipalign', '-P', '16', '-f', '4', args.input, aligned])
        run(['java', '-jar', args.sdk_tools / 'apksigner.jar', 'sign',
             '--ks', key, '--ks-type', metadata['store_type'],
             '--ks-key-alias', metadata['alias'],
             '--ks-pass', 'env:TALEEMPK_SIGNING_PASSWORD', '--key-pass', 'env:TALEEMPK_SIGNING_PASSWORD',
             '--min-sdk-version', '24', '--v1-signing-enabled', 'false',
             '--v2-signing-enabled', 'true', '--v3-signing-enabled', 'true',
             '--v4-signing-enabled', 'false', '--out', args.output, aligned],
            environment=dict(os.environ, TALEEMPK_SIGNING_PASSWORD=password.read_text().strip()))
        result = run(['java', '-jar', args.sdk_tools / 'apksigner.jar', 'verify',
                      '--verbose', '--print-certs', '--min-sdk-version', '24', args.output])
        assert metadata['certificate_sha256'] in result, 'Unexpected signing certificate'
        assert 'Verified using v2 scheme (APK Signature Scheme v2): true' in result
        assert 'Verified using v3 scheme (APK Signature Scheme v3): true' in result
        run([args.sdk_tools / 'zipalign', '-c', '-P', '16', '4', args.output])
        assert payload_hashes(args.output) == before, 'App payload changed during signing'
        with zipfile.ZipFile(args.output) as archive:
            abis = sorted({n.split('/')[1] for n in archive.namelist() if n.startswith('lib/')})
            assert abis == ['arm64-v8a', 'armeabi-v7a', 'x86_64']
        report = {'file': args.output.name, 'bytes': args.output.stat().st_size,
                  'sha256': hashlib.sha256(args.output.read_bytes()).hexdigest(),
                  'signer_sha256': metadata['certificate_sha256'],
                  'debuggable': False, 'v2_verified': True, 'v3_verified': True,
                  'alignment_16kb_verified': True, 'app_payload_unchanged': True,
                  'native_abis': abis}
        args.output.with_suffix('.verification.json').write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps(report, indent=2))
    finally:
        if aligned.exists():
            aligned.unlink()


if __name__ == '__main__':
    main()
