"""Externum playground bootstrap — runs inside Pyodide (loaded from /lib).

This file lives outside any JS template literal on purpose: backslashes and
quotes here are plain Python, so a JS string-escaping bug can never break it.
The Pages workflow copies it into docs/externum-live/, and app.js loads it
from disk with pyodide.runPythonAsync(text) after writing the FS files.

Exposed helpers (called from app.js):
  ext_run(source)              -> ('ok', output) | ('err', message + output)
  ext_compile(source, target)  -> compiled source text for 'python'/'bash'/'binary'
  ext_install_module(name, code) -> write a user .ext module into /lib/lib
  ext_remove_module(name)      -> delete that module
"""

import io
import os
import sys

sys.path.insert(0, "/lib")
os.chdir("/lib")


def ext_run(source):
    from externum import Runtime

    buf = io.StringIO()
    old = sys.stdout, sys.stderr
    sys.stdout = sys.stderr = buf
    try:
        Runtime(search_roots=["/lib"]).run(source)
        return ("ok", buf.getvalue())
    except Exception as e:
        return ("err", "{}: {}\n{}".format(type(e).__name__, e, buf.getvalue()))
    finally:
        sys.stdout, sys.stderr = old


def ext_compile(source, target):
    from externum import Compiler, Lexer, Parser

    ast = list(Parser(Lexer(source).tokenize()).parse())
    out = Compiler(ast).compile(target)
    # single-target compile returns a list of lines; "all" returns a dict of strings
    if isinstance(out, list):
        out = "\n".join(out)
    elif not isinstance(out, str):
        out = ""
    return out if out.strip() else '# (target "{}" produced no output)'.format(target)


def ext_install_module(name, code):
    safe = "".join(c for c in name if c.isalnum() or c == "_")
    if not safe or safe[0].isdigit():
        return ("err", "invalid module name")
    with open("/lib/lib/{}.ext".format(safe), "w") as fh:
        fh.write(code)
    for m in [k for k in list(sys.modules) if k == safe]:
        del sys.modules[m]
    return ("ok", "/lib/lib/{}.ext".format(safe))


def ext_remove_module(name):
    p = "/lib/lib/{}.ext".format(name)
    if os.path.exists(p):
        os.remove(p)
        return ("ok", p)
    return ("err", "not found")
