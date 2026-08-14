"""Tests for Externum NV2.0 DRM.

Covers the full stack: HMAC license keys (sign/verify/expiry/tamper),
watermarking (author + app + source hash in every artifact), tamper
detection (source hash + artifact self-hash embedded) and obfuscation
(string literals encoded through a runtime helper).
"""

import base64
import hashlib
import os
import subprocess
import sys
import tempfile
import unittest

from externum import drm
from externum.runtime import Runtime

RT = Runtime()

SECRET = 's3cret-dev-key'
APP = 'nv2-test-app'
AUTHOR = 'Buffy'


class TestLicenseKeys(unittest.TestCase):
    def test_make_and_verify(self):
        key = drm.make_license(SECRET, APP, AUTHOR)
        self.assertTrue(drm.verify_license(key, SECRET))

    def test_wrong_secret_rejected(self):
        key = drm.make_license(SECRET, APP, AUTHOR)
        self.assertFalse(drm.verify_license(key, 'other-secret'))

    def test_tampered_key_rejected(self):
        key = drm.make_license(SECRET, APP, AUTHOR)
        decoded = base64.urlsafe_b64decode(key.encode()).decode()
        forged = decoded.replace(AUTHOR, 'attacker')
        forged_b64 = base64.urlsafe_b64encode(forged.encode()).decode()
        self.assertFalse(drm.verify_license(forged_b64, SECRET))

    def test_expired_key_rejected(self):
        key = drm.make_license(SECRET, APP, AUTHOR, expires=1)  # 1970
        self.assertFalse(drm.verify_license(key, SECRET))

    def test_never_expiring_key_ok(self):
        key = drm.make_license(SECRET, APP, AUTHOR, expires=0)
        self.assertTrue(drm.verify_license(key, SECRET))

    def test_garbage_key_rejected(self):
        self.assertFalse(drm.verify_license('not-a-key', SECRET))
        self.assertFalse(drm.verify_license('', SECRET))


class TestProtect(unittest.TestCase):
    SRC = """
def main():
    print('top-secret-payload')
    print(1 + 1)
main()
"""

    def test_watermark_present(self):
        code = drm.protect_python(self.SRC, APP, AUTHOR, self.SRC, secret=SECRET)
        self.assertIn(APP, code)
        self.assertIn(AUTHOR, code)
        self.assertIn('sha256:', code)
        self.assertIn('protected build', code)
        self.assertIn('Externum::DRM::', code)

    def test_source_hash_embedded(self):
        code = drm.protect_python(self.SRC, APP, AUTHOR, self.SRC, secret=SECRET)
        src_sha = hashlib.sha256(self.SRC.encode()).hexdigest()
        self.assertIn(src_sha, code)

    def test_artifact_self_hash_embedded(self):
        code = drm.protect_python(self.SRC, APP, AUTHOR, self.SRC, secret=SECRET)
        self.assertIn('_EXT_DRM_ARTIFACT_SHA', code)

    def test_strings_obfuscated(self):
        code = drm.protect_python(self.SRC, APP, AUTHOR, self.SRC, secret=SECRET)
        # the plain payload must not appear as a readable literal
        self.assertNotIn("'top-secret-payload'", code)
        self.assertNotIn('"top-secret-payload"', code)
        self.assertIn('_ext_s(', code)

    def test_obfuscated_program_still_runs(self):
        code = drm.protect_python(self.SRC, APP, AUTHOR, self.SRC, secret=SECRET)
        ns = {'__name__': '__main__', '__file__': '<protected>'}
        import io, contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            exec(compile(code, '<protected>', 'exec'), ns)
        self.assertIn('top-secret-payload', buf.getvalue())
        self.assertIn('2', buf.getvalue())


class TestRuntimeGuard(unittest.TestCase):
    SRC = """
def main():
    print('guarded')
main()
"""

    def _protect_run(self, license_key=None):
        import contextlib, io
        old = os.environ.get('EXTERNUM_LICENSE')
        if license_key is None:
            os.environ.pop('EXTERNUM_LICENSE', None)
        else:
            os.environ['EXTERNUM_LICENSE'] = license_key
        try:
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                RT.run(self.SRC, protect={
                    'app_id': APP, 'author': AUTHOR, 'secret': SECRET,
                })
            return buf.getvalue()
        finally:
            if old is None:
                os.environ.pop('EXTERNUM_LICENSE', None)
            else:
                os.environ['EXTERNUM_LICENSE'] = old

    def test_runs_with_valid_license(self):
        key = drm.make_license(SECRET, APP, AUTHOR)
        out = self._protect_run(key)
        self.assertIn('guarded', out)

    def test_runs_without_license_key(self):
        # license check is enforced when a key is provided; absent key = run
        out = self._protect_run(None)
        self.assertIn('guarded', out)

    def test_raises_with_wrong_license(self):
        key = drm.make_license('wrong-secret', APP, AUTHOR)
        with self.assertRaises(RuntimeError) as ctx:
            self._protect_run(key)
        self.assertIn('invalid license key', str(ctx.exception))


class TestDrmStdlib(unittest.TestCase):
    def test_sign_verify_watermark_via_ext_module(self):
        src = """
import drm

def main():
    key: Str = drm.sign('s', 'app1', 'buffy')
    print(drm.verify(key, 's'))
    print(drm.verify(key, 'wrong'))
    print(drm.watermark('app1', 'buffy').startswith('Externum::DRM::'))
main()
"""
        ns = RT.run(src)
        self.assertIn('True', str(ns))


class TestCliSmoke(unittest.TestCase):
    def test_keygen_and_compile_cli(self):
        import subprocess, sys
        # keygen
        out = subprocess.run(
            [sys.executable, '-m', 'externum', 'keygen',
             '--app-id', 'cli-app', '--author', 'cli', '--secret', 'cli-secret'],
            capture_output=True, text=True, cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        )
        self.assertEqual(out.returncode, 0, out.stderr)
        key = out.stdout.strip().splitlines()[-1]
        self.assertTrue(drm.verify_license(key, 'cli-secret'))
        # compile with hard + protect
        src_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'examples', 'hello.ext')
        out2 = subprocess.run(
            [sys.executable, '-m', 'externum', 'compile', src_path,
             '--target', 'python', '--protect',
             '--app-id', 'cli-app', '--author', 'cli', '--secret', 'cli-secret'],
            capture_output=True, text=True, cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        )
        self.assertEqual(out2.returncode, 0, out2.stderr)
        self.assertIn('cli-app', out2.stdout)
        self.assertIn('Externum::DRM', out2.stdout)
        # the strict language rejects undeclared variables loudly — write a
        # deliberately broken file and watch the compiler fail
        bad_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'tests', '_bad_tmp.ext')
        with open(bad_path, 'w', encoding='utf-8') as fh:
            fh.write('x = 5\n')
        try:
            out3 = subprocess.run(
                [sys.executable, '-m', 'externum', 'compile', bad_path,
                 '--target', 'python'],
                capture_output=True, text=True, cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            )
        finally:
            os.remove(bad_path)
        self.assertNotEqual(out3.returncode, 0)
        self.assertIn('not declared', out3.stderr)


class TestNv2Launcher(unittest.TestCase):
    """The NV-2.0 launcher (all protections in Externum .ext) must gate on
    the license, verify the game binary and launch it — compiled as a
    DRM-protected, self-contained artifact."""

    def _build(self, tmp: str):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        fake = os.path.join(tmp, 'nv2_engine')
        with open(fake, 'w', encoding='utf-8') as fh:
            fh.write('#!/bin/sh\necho FAKE_GAME_OK $@\n')
        os.chmod(fake, 0o755)
        bin_sha = hashlib.sha256(open(fake, 'rb').read()).hexdigest()
        key = drm.make_license(SECRET, 'nv2-engine', 'NV-2.0')
        key_sha = hashlib.sha256(key.encode()).hexdigest()

        template = open(os.path.join(root, 'tools', 'nv2_launcher.ext')).read()
        src = (template.replace('PATCH_ME_BUILD_SHA', bin_sha)
               .replace('PATCH_ME_LICENSE_SHA', key_sha)
               .replace('PATCH_ME_BINARY', './nv2_engine'))
        launcher_ext = os.path.join(tmp, 'nv2_launcher.ext')
        with open(launcher_ext, 'w', encoding='utf-8') as fh:
            fh.write(src)
        ebin = os.path.join(tmp, 'nv2_launcher.ebin')
        r = subprocess.run(
            [sys.executable, '-m', 'externum', 'compile', launcher_ext,
             '--protect', '--target', 'python',
             '--app-id', 'nv2-engine', '--author', 'NV-2.0',
             '--secret', SECRET, '-o', ebin],
            capture_output=True, text=True,
            cwd=root,
        )
        self.assertEqual(r.returncode, 0, r.stderr)
        return ebin, key

    def _run(self, ebin: str, cwd: str, args):
        return subprocess.run([sys.executable, ebin] + args,
                              capture_output=True, text=True, cwd=cwd)

    def test_launcher_gates_license_binary_and_launches(self):
        tmp = tempfile.mkdtemp()
        ebin, key = self._build(tmp)

        out = self._run(ebin, tmp, ['--key', 'wrong-key'])
        self.assertEqual(out.returncode, 3, out.stdout)
        self.assertIn('invalid license', out.stdout)

        out = self._run(ebin, tmp, [])
        self.assertEqual(out.returncode, 2, out.stdout)
        self.assertIn('license key required', out.stdout)

        out = self._run(ebin, tmp, ['--key', key, '--world', 'seed42'])
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertIn('FAKE_GAME_OK', out.stdout)
        self.assertIn('--world seed42', out.stdout)
        self.assertIn('Externum::DRM', out.stdout)

        with open(os.path.join(tmp, 'nv2_engine'), 'a', encoding='utf-8') as fh:
            fh.write('\necho TAMPERED\n')
        out = self._run(ebin, tmp, ['--key', key])
        self.assertEqual(out.returncode, 4, out.stdout)
        self.assertIn('modified', out.stdout)


class TestArtifactSelfCheck(unittest.TestCase):
    """The embedded runtime guard must verify the artifact's own bytes:
    an unmodified file runs, a modified one refuses to start."""

    def _protect_and_write(self, tmp_path: str) -> str:
        src = 'x: Int = 1\nprint(x)\n'
        code = RT.compile_to_python(src, protect={
            'app_id': APP, 'author': AUTHOR, 'secret': SECRET, 'build_id': '1',
        })
        with open(tmp_path, 'w', encoding='utf-8') as fh:
            fh.write(code)
        return code

    def test_clean_artifact_runs(self):
        path = os.path.join(tempfile.mkdtemp(), 'artifact.py')
        self._protect_and_write(path)
        out = subprocess.run([sys.executable, path], capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn('1', out.stdout)

    def test_tampered_artifact_refuses_to_run(self):
        path = os.path.join(tempfile.mkdtemp(), 'artifact.py')
        self._protect_and_write(path)
        with open(path, 'a', encoding='utf-8') as fh:
            fh.write('print(999)\n')
        out = subprocess.run([sys.executable, path], capture_output=True, text=True)
        self.assertNotEqual(out.returncode, 0)
        self.assertIn('tampered', out.stderr)

    def test_wrong_license_refuses_to_run(self):
        path = os.path.join(tempfile.mkdtemp(), 'artifact.py')
        self._protect_and_write(path)
        env = dict(os.environ)
        env['EXTERNUM_LICENSE'] = 'wrong-key'
        out = subprocess.run([sys.executable, path], capture_output=True, text=True,
                             env=env)
        self.assertNotEqual(out.returncode, 0)
        self.assertIn('license', out.stderr)


if __name__ == '__main__':
    unittest.main()
