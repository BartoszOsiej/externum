"""Main entry point for the Externum compiler, runtime and REPL."""

import sys
import argparse

from .lexer import Lexer
from .parser import Parser
from .compiler import Compiler
from . import __version__


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog='externum',
        description='Externum - Python + Binary + Bash Language',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  externum run program.ext [args...]   # execute a program
  externum repl                        # interactive shell
  externum program.ext --target python # compile to Python
  externum program.ext -o out.py       # compile to a file
        """,
    )
    p.add_argument('--version', action='version', version=f'Externum {__version__}')
    sub = p.add_subparsers(dest='command')

    run_p = sub.add_parser('run', help='Execute an .ext program')
    run_p.add_argument('file', help='Source file to run')
    run_p.add_argument('args', nargs='*', help='Arguments passed to the program')

    sub.add_parser('repl', help='Start the interactive Externum shell')

    comp = sub.add_parser('compile', help='Compile an .ext program (default)')
    comp.add_argument('file', help='Source file to compile')
    comp.add_argument('--target', choices=['python', 'binary', 'bash', 'all'],
                      default='all', help='Output target')
    comp.add_argument('--output', '-o', help='Output file')
    return p


def _read_source(path: str) -> str:
    try:
        with open(path, 'r', encoding='utf-8') as fh:
            return fh.read()
    except FileNotFoundError:
        print(f"Error: File '{path}' not found", file=sys.stderr)
        sys.exit(1)
    except IOError as exc:
        print(f'Error reading file: {exc}', file=sys.stderr)
        sys.exit(1)


def cmd_run(args) -> None:
    try:
        from .runtime import Runtime

        Runtime().run_file(args.file, argv=args.args)
    except SyntaxError as exc:
        print(f'Syntax Error: {exc}', file=sys.stderr)
        sys.exit(1)
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001 - CLI boundary
        print(f'Runtime Error: {exc}', file=sys.stderr)
        sys.exit(1)


def cmd_repl(args) -> None:
    try:
        from .runtime import Runtime

        Runtime().repl()
    except KeyboardInterrupt:
        print()
    except Exception as exc:  # noqa: BLE001
        print(f'Error: {exc}', file=sys.stderr)
        sys.exit(1)


def cmd_compile(args) -> None:
    source = _read_source(args.file)
    try:
        tokens = Lexer(source).tokenize()
        ast = list(Parser(tokens).parse())
        result = Compiler(ast).compile(args.target)
    except SyntaxError as exc:
        print(f'Syntax Error: {exc}', file=sys.stderr)
        sys.exit(1)
    except Exception as exc:  # noqa: BLE001 - CLI boundary
        print(f'Error: {exc}', file=sys.stderr)
        sys.exit(1)

    if args.target == 'all':
        output = (
            '# Externum Generated Code\n'
            '# Python target:\n'
            f"{result['python']}\n\n"
            '# Bash target:\n'
            f"{result['bash']}\n\n"
            '# Binary target:\n'
            f"{result['binary']}\n"
        )
    else:
        output = result if isinstance(result, str) else '\n'.join(result)

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as fh:
            fh.write(output)
        print(f'Output written to {args.output}')
    else:
        print(output)


def main(argv=None) -> None:
    argv = list(sys.argv[1:] if argv is None else argv)

    # Backwards compatible form: `externum file.ext [--target ...]`
    if argv and argv[0] not in ('run', 'repl', 'compile') and not argv[0].startswith('-'):
        argv = ['compile'] + argv

    args = _build_parser().parse_args(argv)
    if args.command == 'run':
        cmd_run(args)
    elif args.command == 'repl':
        cmd_repl(args)
    else:
        cmd_compile(args)


if __name__ == '__main__':
    main()
