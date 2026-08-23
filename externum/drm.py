"""Externum — DRM (defense in depth).

Every compiled artifact can carry the full protection stack:

1. **License keys** — `make_license()` produces an HMAC-SHA256 signed key
   (`app_id:author:expires:signature`); `verify_license()` checks it without
   ever embedding the signing secret in the artifact.
2. **Watermark** — every output carries a signed header identifying the
   author, application id and build; a runtime-readable marker is embedded
   in the payload.
3. **Tamper detection** — the SHA-256 of the original source and of the
   artifact itself are embedded; the artifact re-verifies its own file hash
   at startup and refuses to run silently-modified copies.
4. **Obfuscation** — plain string literals are encoded (base64) and decoded
   through a generated helper, so payloads are not readable in plain text.

`protect_python()` applies all four to compiled Python output. The CLI
exposes it as `externum compile --protect`.
"""

import base64
import hashlib
import hmac
import re
import time
from typing import Optional


class DrmError(Exception):
    """Raised when license/tamper verification fails."""


# ------------------------------------------------------------------- licenses
def make_license(secret: str, app_id: str, author: str,
                 expires: Optional[int] = None) -> str:
    """Sign a license: `app_id:author:expires` + HMAC-SHA256 signature."""
    payload = f'{app_id}:{author}:{expires or 0}'
    sig = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return base64.urlsafe_b64encode(f'{payload}:{sig}'.encode()).decode()


def verify_license(key: str, secret: str) -> bool:
    """Verify a license key against the signing secret (constant-time)."""
    try:
        decoded = base64.urlsafe_b64decode(key.encode()).decode()
    except Exception:
        return False
    parts = decoded.split(':')
    if len(parts) < 4:
        return False
    payload = ':'.join(parts[:-1])
    sig = parts[-1]
    expected = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected):
        return False
    try:
        _, _, expires = payload.rsplit(':', 2)
        exp = int(expires)
    except ValueError:
        return False
    if exp and time.time() > exp:
        return False
    return True


# ------------------------------------------------------------------- obfuscate
_PLAIN_STR = re.compile(r"(?<![\\\w])(?:'[^'\\\n]*'|\"[^\"\\\n]*\")")


def _obfuscate_strings(code: str) -> str:
    """Encode plain double-quoted string literals through a base64 helper."""
    helper = (
        'def _ext_s(_b64):\n'
        '    import base64\n'
        '    return base64.b64decode(_b64).decode("utf-8")\n'
    )
    def _replace(m):
        literal = m.group(0)
        inner = literal[1:-1]
        encoded = base64.b64encode(inner.encode()).decode()
        return f'_ext_s("{encoded}")'
    return helper + _PLAIN_STR.sub(_replace, code)


# ------------------------------------------------------------------- protect
def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def protect_python(code: str, app_id: str, author: str, source: str,
                   secret: str = 'externum-drm', build_id: str = None) -> str:
    """Apply the full DRM stack to compiled Python output.

    `secret` is compile-time only — it signs the embedded license expected
    value but is never written into the artifact. The artifact stores the
    *expected* HMAC digest, so a wrong key fails even though the secret is
    not present.
    """
    build_id = build_id or f'{int(time.time())}'
    source_sha = _sha256(source.encode())
    obfuscated = _obfuscate_strings(code)

    # expected license value for this artifact (digest, not the secret)
    expected_key = make_license(secret, app_id, author)
    expected_sha = _sha256(expected_key.encode())

    header = (
        '# ============================================================\n'
        '# Externum :: protected build\n'
        f'#   app_id : {app_id}\n'
        f'#   author : {author}\n'
        f'#   build  : {build_id}\n'
        f'#   source : sha256:{source_sha}\n'
        '#   This file is watermarked and integrity-checked. Do not edit.\n'
        '# ============================================================\n'
    )

    guard = f'''
# ---- Externum DRM runtime guard (embedded in every protected file) ----
_EXT_DRM_APP = {app_id!r}
_EXT_DRM_AUTHOR = {author!r}
_EXT_DRM_SOURCE_SHA = {source_sha!r}
_EXT_DRM_EXPECTED = {expected_sha!r}
_EXT_DRM_WATERMARK = 'Externum::DRM::' + _EXT_DRM_APP + '::' + _EXT_DRM_AUTHOR

def _ext_drm_self_check():
    import hashlib, os, sys
    def _h(b):
        return hashlib.sha256(b).hexdigest()
    # 1) license — env key must match the expected digest
    key = os.environ.get('EXTERNUM_LICENSE', '')
    if key:
        if _h(key.encode()) != _EXT_DRM_EXPECTED:
            raise RuntimeError('Externum DRM: invalid license key')
    # 2) tamper detection — verify this file's own bytes against the
    #    artifact hash embedded at build time
    blob = None
    try:
        mod = sys.modules.get('__main__')
        fname = getattr(mod, '__file__', None)
        if fname and os.path.isfile(fname):
            with open(fname, 'rb') as fh:
                blob = fh.read()
    except Exception:
        blob = None
    if blob is not None:
        import re as _re
        # anchor on the DRM header block (`# ====` + marker line). The CLI
        # may wrap the artifact, and `externum run --protect` points
        # __file__ at the .ext source (no header -> check skipped). The
        # two-line sequence never occurs inside the guard itself, so it
        # cannot self-match.
        m = list(_re.finditer(rb'# ={{10,}}\\n# Externum :: protected build', blob))
        if m:
            blob = blob[m[-1].start():]
            call = blob.rfind(b'_ext_drm_self_check()')
            if call < 0:
                raise RuntimeError('Externum DRM: malformed artifact')
            # only comments may follow the guard. `--target all` artifacts
            # append commented bash/binary sections (all `#` lines); any
            # real code after the guard is tampering
            for ln in blob[call + len(b'_ext_drm_self_check()'):].splitlines():
                if ln.strip() and not ln.strip().startswith(b'#'):
                    raise RuntimeError('Externum DRM: file was tampered with')
            blob = blob[:call + len(b'_ext_drm_self_check()') + 1]
            # the embedded sha line is itself part of the file; splice it
            # out (with its leading newline) before hashing — the build
            # hashed the artifact without that line
            needle = (b"_EXT_DRM_ARTIFACT_SHA = '" + _EXT_DRM_ARTIFACT_SHA.encode()
                      + b"'")
            pos = blob.find(needle)
            if pos >= 0:
                start = pos - 1 if pos > 0 else 0
                blob = blob[:start] + blob[pos + len(needle):]
            if _h(blob) != _EXT_DRM_ARTIFACT_SHA:
                raise RuntimeError('Externum DRM: file was tampered with')
    return _EXT_DRM_WATERMARK

_ext_drm_self_check()
'''

    protected = header + obfuscated + guard

    # final artifact hash — the guard's own bytes are part of the artifact,
    # so a modified copy produces a different fingerprint.
    artifact_sha = _sha256(protected.encode())
    protected = protected.replace(
        '_EXT_DRM_WATERMARK = \'Externum::DRM::\' + _EXT_DRM_APP + \'::\' + _EXT_DRM_AUTHOR',
        '_EXT_DRM_WATERMARK = \'Externum::DRM::\' + _EXT_DRM_APP + \'::\' + _EXT_DRM_AUTHOR\n'
        f'_EXT_DRM_ARTIFACT_SHA = {artifact_sha!r}',
    )
    return protected
