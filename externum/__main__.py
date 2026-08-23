"""Main entry point for the Externum v4 compiler, runtime and REPL."""

import argparse
import sys

from . import __version__
from .bytecode import BytecodeCompiler
from .compiler import Compiler
from .lexer import Lexer
from .parser import Parser
from .vm import VM


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="externum",
        description="Externum - Python + Binary + Bash Language",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  externum run program.ext [args...]   # execute a program
  externum repl                        # interactive shell
  externum program.ext --target python # compile to Python
  externum program.ext -o out.py       # compile to a file
        """,
    )
    p.add_argument("--version", action="version", version=f"Externum {__version__}")
    sub = p.add_subparsers(dest="command")

    run_p = sub.add_parser("run", help="Execute an .ext program")
    run_p.add_argument("file", help="Source file to run")
    run_p.add_argument("args", nargs="*", help="Arguments passed to the program")
    run_p.add_argument(
        "--backend",
        choices=["vm", "python"],
        default="python",
        help="Execution backend: python (default, transpile) or vm (native EXBC)",
    )
    run_p.add_argument("--protect", action="store_true", help="Apply the DRM stack to the program before running")
    run_p.add_argument("--app-id", default=None, help="Application id for DRM")
    run_p.add_argument("--author", default=None, help="Author name for DRM")
    run_p.add_argument("--secret", default=None, help="DRM signing secret (compile-time only)")
    run_p.add_argument("--build-id", default=None, help="Build id baked into the DRM watermark")

    sub.add_parser("repl", help="Start the interactive Externum shell")

    comp = sub.add_parser("compile", help="Compile an .ext program (default)")
    comp.add_argument("file", help="Source file to compile")
    comp.add_argument(
        "--target", choices=["python", "binary", "bash", "all", "bytecode"], default="all", help="Output target"
    )
    comp.add_argument("--output", "-o", help="Output file")
    comp.add_argument(
        "--protect",
        action="store_true",
        help="Embed the full DRM stack (license, watermark, tamper check, obfuscation)",
    )
    comp.add_argument("--app-id", default=None, help="Application id for DRM")
    comp.add_argument("--author", default=None, help="Author name for DRM")
    comp.add_argument("--secret", default=None, help="DRM signing secret (compile-time only)")
    comp.add_argument("--build-id", default=None, help="Build id baked into the DRM watermark")
    comp.add_argument(
        "--hard", action="store_true", help="Enable strict type checking (declarations, annotations, ownership)"
    )

    key = sub.add_parser("keygen", help="Generate DRM license keys")
    key.add_argument("--app-id", required=True, help="Application id")
    key.add_argument("--author", default="", help="Author name")
    key.add_argument("--secret", required=True, help="Signing secret")
    key.add_argument("--expires", type=int, default=None, help="Unix timestamp expiry (0/absent = never)")
    key.add_argument("--count", type=int, default=1, help="How many keys")

    # v4 commands
    check_p = sub.add_parser("check", help="Run static analysis on an .ext program")
    check_p.add_argument("file", help="Source file to check")

    vm_p = sub.add_parser("vm", help="Run an .ext program via the EXBC VM (alias for run --backend vm)")
    vm_p.add_argument("file", help="Source file to run")
    vm_p.add_argument("args", nargs="*", help="Arguments passed to the program")

    ide_p = sub.add_parser("ide", help="Launch the Externum TUI IDE")
    ide_p.add_argument("file", nargs="?", default=None, help="File to open (optional)")

    return p


def _read_source(path: str) -> str:
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except FileNotFoundError:
        print(f"Error: File '{path}' not found", file=sys.stderr)
        sys.exit(1)
    except OSError as exc:
        print(f"Error reading file: {exc}", file=sys.stderr)
        sys.exit(1)


def cmd_run(args) -> None:
    backend = getattr(args, "backend", "vm")
    if backend == "vm":
        cmd_vm(args)
        return
    try:
        from .runtime import Runtime

        protect = None
        if args.protect:
            protect = {
                "app_id": args.app_id or "externum-app",
                "author": args.author or "unknown",
                "secret": args.secret or "externum-drm",
                "build_id": args.build_id,
            }
        Runtime().run_file(args.file, argv=args.args, protect=protect)
    except SyntaxError as exc:
        print(f"Syntax Error: {exc}", file=sys.stderr)
        sys.exit(1)
    except SystemExit:
        raise
    except Exception as exc:
        print(f"Runtime Error: {exc}", file=sys.stderr)
        sys.exit(1)


def cmd_keygen(args) -> None:
    from . import __version__
    from .drm import make_license

    print(f"Externum {__version__} — DRM keygen (secret is never stored)")
    for _ in range(args.count):
        print(make_license(args.secret, args.app_id, args.author, args.expires))


def cmd_repl(args) -> None:
    try:
        from .runtime import Runtime

        Runtime().repl()
    except KeyboardInterrupt:
        print()
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


def cmd_compile(args) -> None:
    source = _read_source(args.file)
    try:
        from .runtime import Runtime

        protect = None
        if args.protect:
            protect = {
                "app_id": args.app_id or "externum-app",
                "author": args.author or "unknown",
                "secret": args.secret or "externum-drm",
                "build_id": args.build_id,
            }
        rt = Runtime()
        check = getattr(args, "hard", False)
        py = rt.compile_to_python(source, protect=protect, check=check)
        if args.target == "all":
            # DRM-protected Python plus the raw bash/binary targets
            tokens = Lexer(source).tokenize()
            ast = list(Parser(tokens).parse())
            compiled = Compiler(ast).compile("all")
            result = {
                "python": py,
                "bash": compiled["bash"],
                "binary": compiled["binary"],
            }
        elif args.target == "python":
            result = py
        else:
            tokens = Lexer(source).tokenize()
            ast = list(Parser(tokens).parse())
            result = Compiler(ast).compile(args.target)
            if args.target == "bash":
                result = result["bash"]
            elif args.target == "binary":
                result = result["binary"]
    except SyntaxError as exc:
        print(f"Syntax Error: {exc}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    if args.target == "all":
        # bash/binary sections are embedded as comments so the combined
        # artifact stays a valid, runnable Python file
        def _comment(lines: str) -> str:
            return "\n".join("# " + ln for ln in lines.splitlines())

        output = (
            "# Externum Generated Code\n"
            "# Python target:\n"
            f"{result['python']}\n\n"
            "# Bash target (commentary — not Python):\n"
            f"{_comment(result['bash'])}\n\n"
            "# Binary target (commentary — not Python):\n"
            f"{_comment(result['binary'])}\n"
        )
    else:
        output = result if isinstance(result, str) else "\n".join(result)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(output)
        print(f"Output written to {args.output}")
    else:
        print(output)


def cmd_vm(args) -> None:
    """Run via the native EXBC virtual machine."""
    source = _read_source(args.file)
    try:
        from .analysis import preprocess

        processed, _ = preprocess(source)
        tokens = Lexer(processed).tokenize()
        ast = list(Parser(tokens).parse())
        compiler = BytecodeCompiler(ast, module_name=args.file)
        module = compiler.compile()
        vm = VM(argv=getattr(args, "args", []))
        result = vm.run_module(module)
    except SyntaxError as exc:
        print(f"Syntax Error: {exc}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"Runtime Error: {exc}", file=sys.stderr)
        sys.exit(1)


def cmd_ide(args) -> None:
    """Launch the Externum TUI IDE — written in Externum itself."""
    import os

    # Find ide.ext in lib/
    lib_path = os.path.join(os.path.dirname(__file__), "..", "lib", "ide.ext")
    if not os.path.isfile(lib_path):
        lib_path = os.path.join(os.getcwd(), "lib", "ide.ext")
    if not os.path.isfile(lib_path):
        # Try from project root
        lib_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lib", "ide.ext")
    if not os.path.isfile(lib_path):
        print("Error: lib/ide.ext not found", file=sys.stderr)
        sys.exit(1)

    source = _read_source(lib_path)
    try:
        from .analysis import preprocess

        processed, _ = preprocess(source)
        tokens = Lexer(processed).tokenize()
        ast = list(Parser(tokens).parse())
        compiler = BytecodeCompiler(ast, module_name="ide.ext")
        module = compiler.compile()
        argv_list = [args.file] if getattr(args, "file", None) else []
        vm = VM(argv=argv_list)
        vm.run_module(module)
    except KeyboardInterrupt:
        pass
    except SystemExit:
        pass
    except Exception as exc:
        # If the IDE exited cleanly, don't show error
        print(f"IDE error: {exc}", file=sys.stderr)
        sys.exit(1)


def cmd_check(args) -> None:
    """Run static analysis on a source file."""
    source = _read_source(args.file)
    try:
        from .analysis import check_or_raise, preprocess

        processed, _ = preprocess(source)
        tokens = Lexer(processed).tokenize()
        parser = Parser(tokens)
        ast = parser.parse()
        ast_list = list(ast)
        check_or_raise(ast_list, parser.annotations, parser.signatures, parser.traits, parser.impls, parser.mutable)
        print(f"{args.file}: all checks passed ✓")
    except Exception as exc:
        print(f"Check failed: {exc}", file=sys.stderr)
        sys.exit(1)


def main(argv=None) -> None:
    argv = list(sys.argv[1:] if argv is None else argv)

    # Backwards compatible form: `externum file.ext [--target ...]`
    if (
        argv
        and argv[0] not in ("run", "repl", "compile", "keygen", "check", "vm", "ide")
        and not argv[0].startswith("-")
    ):
        argv = ["compile"] + argv

    args = _build_parser().parse_args(argv)
    if args.command == "run":
        cmd_run(args)
    elif args.command == "repl":
        cmd_repl(args)
    elif args.command == "keygen":
        cmd_keygen(args)
    elif args.command == "vm":
        cmd_vm(args)
    elif args.command == "ide":
        cmd_ide(args)
    elif args.command == "check":
        cmd_check(args)
    else:
        cmd_compile(args)


if __name__ == "__main__":
    main()
