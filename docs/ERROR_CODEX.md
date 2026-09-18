# Error Codex — Externum Compiler

> Complete reference for every compiler error code (EXT_ERR_01 through EXT_ERR_40). Each entry includes the error message, structural explanation, example stack trace, and mitigation path.

---

## Legend

| Field | Description |
|---|---|
| **Code** | Unique error identifier |
| **Phase** | Compiler phase where the error originates |
| **Severity** | Fatal (compilation stops) / Warning (compilation continues) |
| **Target** | Which emission targets are affected (Python, Bash, Native, All) |

---

## EXT_ERR_01 — LEXER: Unexpected Character

```
Phase: Lexer
Severity: Fatal
Target: All
```

**Error Message:**
```
EXT_ERR_01: Unexpected character at line {line}, column {col}: '{char}'
```

**Explanation:** The lexer encountered a character that is not part of the Externum language grammar. This typically happens when copy-pasting code from a word processor that introduces smart quotes, em-dashes, or non-ASCII whitespace.

**Stack Trace:**
```
Error: EXT_ERR_01: Unexpected character at line 3, column 12: '\u201c'
  at externum/lexer/tokenizer.rs:142
  at externum/lexer/tokenizer.rs:87 (next_token)
  at externum/parser/mod.rs:23 (parse_file)
  at externum/compiler/mod.rs:45 (compile)
```

**Mitigation:**
1. Check the source file for non-ASCII characters: `externum check-encoding input.ext`
2. Replace smart quotes (`""`) with straight quotes (`""`)
3. Replace em-dashes (`—`) with double-hyphens (`--`)
4. Run `externum fmt input.ext` to auto-fix common encoding issues

---

## EXT_ERR_02 — LEXER: Unterminated String Literal

```
Phase: Lexer
Severity: Fatal
Target: All
```

**Error Message:**
```
EXT_ERR_02: Unterminated string literal at line {line}, column {col}
```

**Explanation:** A string literal was opened with `"` but never closed before the end of the line or file.

**Stack Trace:**
```
Error: EXT_ERR_02: Unterminated string literal at line 7, column 5
  at externum/lexer/tokenizer.rs:203
  at externum/lexer/tokenizer.rs:87 (next_token)
  at externum/parser/mod.rs:23 (parse_file)
```

**Mitigation:**
1. Check for missing closing `"` on the line
2. Check for escaped quotes that broke the string: `\"` inside a string is fine, but `"` without escape is not
3. Multi-line strings must use `"""..."""` (triple-quote syntax)

---

## EXT_ERR_03 — LEXER: Invalid Number Literal

```
Phase: Lexer
Severity: Fatal
Target: All
```

**Error Message:**
```
EXT_ERR_03: Invalid number literal at line {line}, column {col}: '{literal}'
```

**Explanation:** The lexer found a token that looks like a number but contains invalid digits for its base (e.g., `0x1G` for hex, `0b2` for binary).

**Mitigation:**
1. Check hex literals use only `0-9a-fA-F`
2. Check binary literals use only `0-1`
3. Check octal literals use only `0-7`

---

## EXT_ERR_04 — LEXER: Invalid Identifier

```
Phase: Lexer
Severity: Fatal
Target: All
```

**Error Message:**
```
EXT_ERR_04: Invalid identifier at line {line}, column {col}: '{token}'
```

**Explanation:** An identifier contains characters that are not allowed (starts with digit, contains special characters).

**Mitigation:**
1. Identifiers must start with a letter or underscore
2. Identifiers may contain letters, digits, and underscores
3. No Unicode characters in identifiers (ASCII only)

---

## EXT_ERR_05 — PARSER: Expected Token

```
Phase: Parser
Severity: Fatal
Target: All
```

**Error Message:**
```
EXT_ERR_05: Expected {expected} at line {line}, column {col}, found '{found}'
```

**Explanation:** The parser expected a specific token (e.g., `(`, `)`, `:`, `=`) but found a different one. This indicates a syntax error.

**Stack Trace:**
```
Error: EXT_ERR_05: Expected ')' at line 5, column 15, found 'newline'
  at externum/parser/expressions.rs:67
  at externum/parser/expressions.rs:34 (parse_expression)
  at externum/parser/statements.rs:12 (parse_let)
  at externum/parser/mod.rs:45 (parse_file)
```

**Mitigation:**
1. Check for missing closing parenthesis, bracket, or brace
2. Check for missing colon after function parameters
3. Check for missing `=` in variable declarations
4. Look at the line above — the error is often on the previous line

---

## EXT_ERR_06 — PARSER: Unexpected Token

```
Phase: Parser
Severity: Fatal
Target: All
```

**Error Message:**
```
EXT_ERR_06: Unexpected token '{token}' at line {line}, column {col}
```

**Explanation:** The parser encountered a token that cannot appear at this position in the grammar.

**Mitigation:**
1. Review the grammar: https://github.com/BartoszOsiej/externum/blob/main/docs/grammar.md
2. Common mistake: using `=` instead of `==` in conditions
3. Common mistake: missing `fn` keyword before function definition

---

## EXT_ERR_07 — PARSER: Invalid Expression

```
Phase: Parser
Severity: Fatal
Target: All
```

**Error Message:**
```
EXT_ERR_07: Invalid expression at line {line}, column {col}
```

**Explanation:** The parser found a sequence of tokens that does not form a valid expression.

**Mitigation:**
1. Break complex expressions into simpler parts
2. Check operator precedence — add explicit parentheses
3. Verify all sub-expressions are syntactically correct

---

## EXT_ERR_08 — TYPE CHECKER: Type Mismatch

```
Phase: Type Checker
Severity: Fatal
Target: All
```

**Error Message:**
```
EXT_ERR_08: Type mismatch at line {line}, column {col}: expected '{expected}', found '{found}'
```

**Explanation:** The type checker found that an expression has a different type than expected.

**Stack Trace:**
```
Error: EXT_ERR_08: Type mismatch at line 12, column 5: expected 'int', found 'string'
  at externum/types/checker.rs:89
  at externum/types/checker.rs:56 (check_binary_op)
  at externum/types/checker.rs:34 (check_expression)
  at externum/compiler/mod.rs:78 (type_check)
```

**Mitigation:**
1. Check variable types match their usage
2. Check function return types match declared types
3. Use explicit type casts if needed: `int(x)` or `string(n)`

---

## EXT_ERR_09 — TYPE CHECKER: Undefined Variable

```
Phase: Type Checker
Severity: Fatal
Target: All
```

**Error Message:**
```
EXT_ERR_09: Undefined variable '{name}' at line {line}, column {col}
```

**Explanation:** The variable is used but was never declared in scope.

**Mitigation:**
1. Check for typos in variable names
2. Check the variable is declared before use
3. Check the variable is in the correct scope (not nested inside another function)

---

## EXT_ERR_10 — TYPE CHECKER: Undefined Function

```
Phase: Type Checker
Severity: Fatal
Target: All
```

**Error Message:**
```
EXT_ERR_10: Undefined function '{name}' at line {line}, column {col}
```

**Explanation:** A function is called but was never defined.

**Mitigation:**
1. Check for typos in function name
2. Check the function is defined before the call site
3. Check the function is imported (if in another module)

---

## EXT_ERR_11 — TYPE CHECKER: Argument Count Mismatch

```
Phase: Type Checker
Severity: Fatal
Target: All
```

**Error Message:**
```
EXT_ERR_11: Function '{name}' expects {expected} arguments, found {found} at line {line}
```

**Explanation:** A function is called with the wrong number of arguments.

**Mitigation:**
1. Check the function signature for the expected argument count
2. Check for missing or extra arguments in the call

---

## EXT_ERR_12 — TYPE CHECKER: Cannot Apply Operator

```
Phase: Type Checker
Severity: Fatal
Target: All
```

**Error Message:**
```
EXT_ERR_12: Cannot apply operator '{op}' to types '{left}' and '{right}' at line {line}
```

**Explanation:** An operator is used with incompatible types (e.g., `string + int`).

**Mitigation:**
1. Use explicit type conversion: `int(s)` or `string(n)`
2. Check that both operands have compatible types
3. For string concatenation, use the `++` operator, not `+`

---

## EXT_ERR_13 — TYPE CHECKER: Return Type Mismatch

```
Phase: Type Checker
Severity: Fatal
Target: All
```

**Error Message:**
```
EXT_ERR_13: Function '{name}' declares return type '{expected}', but returns '{found}' at line {line}
```

**Explanation:** A function's return statement has a different type than declared.

**Mitigation:**
1. Check all return statements in the function
2. Ensure all return paths return the declared type
3. Use explicit conversion if needed

---

## EXT_ERR_14 — EMITTER: Unsupported Construct

```
Phase: Emitter (Bash)
Severity: Fatal
Target: Bash only
```

**Error Message:**
```
EXT_ERR_14: Unsupported construct for Bash target at line {line}: '{construct}'
```

**Explanation:** The source code uses a construct that cannot be emitted as Bash. The Bash emitter has the most restrictions of the three targets.

**Stack Trace:**
```
Error: EXT_ERR_14: Unsupported construct for Bash target at line 15: 'closure'
  at externum/emitter/bash/mod.rs:134
  at externum/emitter/bash/expressions.rs:67
  at externum/emitter/mod.rs:23 (emit)
```

**Mitigation:**
1. Closures are not supported in Bash target — use named functions instead
2. Hash maps are not supported — use parallel arrays (key array + value array)
3. See https://github.com/BartoszOsiej/externum/blob/main/docs/bash-compat.md
4. If you must use closures, target Python or Native instead

---

## EXT_ERR_15 — EMITTER: Bash Word Splitting Hazard

```
Phase: Emitter (Bash)
Severity: Warning
Target: Bash only
```

**Error Message:**
```
EXT_ERR_15: Potential word splitting at line {line}: variable '{var}' is unquoted
```

**Explanation:** A variable in the Bash output is not quoted, which could cause word splitting or globbing.

**Mitigation:**
1. The emitter will automatically quote variables where possible
2. If this warning persists, wrap the variable in quotes manually in the source
3. This is a warning, not a fatal error — the Bash output will still compile

---

## EXT_ERR_16 — EMITTER: Native Target Requires Linker

```
Phase: Emitter (Native)
Severity: Fatal
Target: Native only
```

**Error Message:**
```
EXT_ERR_16: Native target requires a C linker, but none was found
```

**Explanation:** The native emitter needs a C compiler/linker (gcc or cc) to produce the final binary.

**Mitigation:**
1. Install gcc: `apt install gcc` or `pacman -S gcc`
2. Set the linker path: `externum compile --linker /path/to/gcc input.ext`
3. Or target Python/Bash instead: `externum compile --target python input.ext`

---

## EXT_ERR_17 — EMITTER: Native Compilation Failed

```
Phase: Emitter (Native)
Severity: Fatal
Target: Native only
```

**Error Message:**
```
EXT_ERR_17: Native compilation failed at line {line}: {cc_error}
```

**Explanation:** The generated C code was rejected by the C compiler.

**Mitigation:**
1. Check the generated C code: `externum compile --target native --emit-c input.ext -o output.c`
2. The C code is in `output.c` — compile it manually to see the full error
3. Common cause: complex expressions that generate invalid C

---

## EXT_ERR_18 — LINKER: Multiple Definition

```
Phase: Linker (Native)
Severity: Fatal
Target: Native only
```

**Error Message:**
```
EXT_ERR_18: Multiple definition of symbol '{name}'
```

**Explanation:** Two functions or variables have the same name in the generated C code.

**Mitigation:**
1. Check for duplicate function names across modules
2. Use qualified names: `module::function` instead of bare `function`
3. This is a compiler bug if the source has no duplicates — report it

---

## EXT_ERR_19 — RUNTIME: Division by Zero

```
Phase: Runtime (Python target)
Severity: Runtime error
Target: Python
```

**Error Message:**
```
EXT_ERR_19: Division by zero at line {line}
```

**Explanation:** The Python runtime encountered a division by zero.

**Mitigation:**
1. Add a check before the division: `if divisor != 0: ...`
2. Use try/except in the source to handle the error
3. This is a runtime error, not a compiler error — check your logic

---

## EXT_ERR_20 — RUNTIME: Index Out of Bounds

```
Phase: Runtime (Python target)
Severity: Runtime error
Target: Python
```

**Error Message:**
```
EXT_ERR_20: Index out of bounds at line {line}: index {idx}, length {len}
```

**Explanation:** An array/list index is out of range.

**Mitigation:**
1. Check array bounds before indexing
2. Use `if idx < len(arr):` guard
3. Use `arr[idx] if idx < len(arr) else default` for safe access

---

## EXT_ERR_21 — RUNTIME: Stack Overflow (Native)

```
Phase: Runtime (Native target)
Severity: Fatal
Target: Native
```

**Error Message:**
```
EXT_ERR_21: Stack overflow at line {line}
```

**Explanation:** The native binary hit the stack size limit, usually from infinite recursion.

**Mitigation:**
1. Check for infinite recursion in function calls
2. Convert recursive functions to iterative where possible
3. Increase stack size: `externum compile --stack-size 16777216 input.ext`

---

## EXT_ERR_22 — RUNTIME: Segfault (Native)

```
Phase: Runtime (Native target)
Severity: Fatal
Target: Native
```

**Error Message:**
```
EXT_ERR_22: Segmentation fault at line {line}
```

**Explanation:** The native binary accessed invalid memory. This is a compiler bug — the generated C code has a memory safety issue.

**Mitigation:**
1. Report this as a bug: https://github.com/BartoszOsiej/externum/issues
2. Include the source code and generated C code
3. Use Python target as a workaround: `externum compile --target python input.ext`

---

## EXT_ERR_23 — COMPILER: Internal Error

```
Phase: Compiler
Severity: Fatal
Target: All
```

**Error Message:**
```
EXT_ERR_23: Internal compiler error at {file}:{line}: {message}
```

**Explanation:** The compiler hit an unreachable code path. This is a compiler bug.

**Mitigation:**
1. Report this as a bug: https://github.com/BartoszOsiej/externum/issues
2. Include the source code and full error output
3. Try simplifying the source code to find the trigger

---

## EXT_ERR_24 — COMPILER: Out of Memory

```
Phase: Compiler
Severity: Fatal
Target: All
```

**Error Message:**
```
EXT_ERR_24: Out of memory during {phase}
```

**Explanation:** The compiler ran out of memory. Usually caused by very large files or deep recursion.

**Mitigation:**
1. Split the source file into smaller modules
2. Reduce recursion depth
3. Increase system memory or use swap

---

## EXT_ERR_25 — COMPILER: File Not Found

```
Phase: Compiler
Severity: Fatal
Target: All
```

**Error Message:**
```
EXT_ERR_25: File not found: '{path}'
```

**Mitigation:**
1. Check the file path for typos
2. Use absolute paths or verify relative path from CWD
3. Check file permissions

---

## EXT_ERR_26 — COMPILER: I/O Error

```
Phase: Compiler
Severity: Fatal
Target: All
```

**Error Message:**
```
EXT_ERR_26: I/O error: {os_error} at '{path}'
```

**Mitigation:**
1. Check file permissions
2. Check disk space
3. Check if the output directory exists

---

## EXT_ERR_27 — COMPILER: Import Not Found

```
Phase: Type Checker
Severity: Fatal
Target: All
```

**Error Message:**
```
EXT_ERR_27: Import not found: '{module}' at line {line}
```

**Explanation:** An `import` statement references a module that cannot be found.

**Mitigation:**
1. Check the module path for typos
2. Ensure the module file exists in the same directory or in `externum_modules/`
3. Use relative imports: `import .mymodule` for same-directory modules

---

## EXT_ERR_28 — COMPILER: Circular Import

```
Phase: Type Checker
Severity: Fatal
Target: All
```

**Error Message:**
```
EXT_ERR_28: Circular import detected: {module_a} → {module_b} → {module_a}
```

**Explanation:** Two or more modules import each other, creating a circular dependency.

**Mitigation:**
1. Break the cycle by extracting shared code into a third module
2. Use late imports (import inside a function) to defer the dependency
3. Restructure the code to remove the circular dependency

---

## EXT_ERR_29 — COMPILER: Feature Not Supported

```
Phase: Compiler
Severity: Fatal
Target: All
```

**Error Message:**
```
EXT_ERR_29: Feature '{feature}' is not yet implemented
```

**Explanation:** The source code uses a feature that is not yet implemented in the compiler.

**Mitigation:**
1. Check the language specification for status of the feature
2. Rewrite the code to use supported constructs
3. Track implementation status: https://github.com/BartoszOsiej/externum/issues

---

## EXT_ERR_30 — COMPILER: Version Mismatch

```
Phase: Compiler
Severity: Fatal
Target: All
```

**Error Message:**
```
EXT_ERR_30: Source file requires Externum {required}, but compiler is version {current}
```

**Explanation:** The source file uses syntax or features from a newer version of Externum.

**Mitigation:**
1. Update Externum: `pip install --upgrade externum`
2. Or rewrite the source to use the older syntax

---

## EXT_ERR_31 — PARSER: Indentation Error

```
Phase: Parser
Severity: Fatal
Target: All
```

**Error Message:**
```
EXT_ERR_31: Indentation error at line {line}: expected {expected} spaces, found {found}
```

**Explanation:** Externum uses significant whitespace (like Python). Inconsistent indentation causes parse errors.

**Mitigation:**
1. Use spaces, not tabs (4 spaces per indent level)
2. Run `externum fmt input.ext` to auto-fix indentation
3. Check your editor settings for tab/space conversion

---

## EXT_ERR_32 — PARSER: Unexpected End of File

```
Phase: Parser
Severity: Fatal
Target: All
```

**Error Message:**
```
EXT_ERR_32: Unexpected end of file at line {line}: expected '{token}'
```

**Explanation:** The file ended before a expected token was found (unclosed block, missing closing brace).

**Mitigation:**
1. Check for missing closing braces, brackets, or parentheses
2. Check for missing `end` keyword in block statements
3. The error line number points to the last line of the file

---

## EXT_ERR_33 — TYPE CHECKER: Already Defined

```
Phase: Type Checker
Severity: Fatal
Target: All
```

**Error Message:**
```
EXT_ERR_33: Variable '{name}' already defined at line {line} (previous definition at line {prev_line})
```

**Explanation:** A variable is declared twice in the same scope.

**Mitigation:**
1. Rename the second variable
2. Or use the existing variable instead of re-declaring it
3. Check for copy-paste errors

---

## EXT_ERR_34 — TYPE CHECKER: Cannot Infer Type

```
Phase: Type Checker
Severity: Fatal
Target: All
```

**Error Message:**
```
EXT_ERR_34: Cannot infer type of variable '{name}' at line {line}
```

**Explanation:** The type checker cannot determine the type of a variable (usually from an empty initial value).

**Mitigation:**
1. Add an explicit type annotation: `let x: int = ...`
2. Provide an initial value: `let x = 0`
3. Don't use `let x = nil` without a type annotation

---

## EXT_ERR_35 — EMITTER: Bash Recursive Function Limit

```
Phase: Emitter (Bash)
Severity: Warning
Target: Bash only
```

**Error Message:**
```
EXT_ERR_35: Function '{name}' may exceed Bash call stack limit at line {line}
```

**Explanation:** Bash has a limited call stack (~10,000 frames). Deeply recursive functions may exhaust it.

**Mitigation:**
1. Convert to iterative if possible
2. Add a recursion depth limit in the source
3. Use Python or Native target for deep recursion

---

## EXT_ERR_36 — RUNTIME: Bash Read-Only Variable

```
Phase: Runtime (Bash target)
Severity: Runtime error
Target: Bash
```

**Error Message:**
```
EXT_ERR_36: Cannot assign to read-only variable '{name}' at line {line}
```

**Explanation:** The generated Bash script tries to modify a variable that was declared as read-only.

**Mitigation:**
1. Check for `readonly` or `declare -r` in the generated Bash
2. The compiler may have marked a constant as read-only
3. Use a different variable name

---

## EXT_ERR_37 — RUNTIME: Bash Argument List Too Long

```
Phase: Runtime (Bash target)
Severity: Runtime error
Target: Bash
```

**Error Message:**
```
EXT_ERR_37: Argument list too long at line {line}
```

**Explanation:** The Bash target passes too many arguments to a command, exceeding the OS limit.

**Mitigation:**
1. Use arrays instead of passing many arguments
2. Use xargs for large argument lists
3. Use Python or Native target for large data processing

---

## EXT_ERR_38 — COMPILER: Timeout

```
Phase: Compiler
Severity: Fatal
Target: All
```

**Error Message:**
```
EXT_ERR_38: Compilation timed out after {seconds} seconds
```

**Explanation:** The compiler took too long. Usually caused by extremely complex type inference or circular logic.

**Mitigation:**
1. Simplify the source code
2. Add explicit type annotations to reduce inference complexity
3. Increase timeout: `externum compile --timeout 300 input.ext`

---

## EXT_ERR_39 — PARSER: Duplicate Key

```
Phase: Parser
Severity: Warning
Target: All
```

**Error Message:**
```
EXT_ERR_39: Duplicate key '{key}' in map literal at line {line} (previous at line {prev_line})
```

**Explanation:** A map/dictionary literal has the same key twice. The second value overwrites the first.

**Mitigation:**
1. Remove the duplicate key
2. If intentional (overwrite), use explicit assignment: `map[key] = value`

---

## EXT_ERR_40 — COMPILER: Platform Not Supported

```
Phase: Compiler
Severity: Fatal
Target: Native
```

**Error Message:**
```
EXT_ERR_40: Native target not supported on platform '{platform}'
```

**Explanation:** The native emitter only supports Linux x86_64 and Linux aarch64.

**Mitigation:**
1. Use Python or Bash target on unsupported platforms
2. Cross-compile from a supported platform
3. Supported platforms: Linux x86_64, Linux aarch64, macOS x86_64, macOS aarch64

---

## Quick Reference Table

| Code | Phase | Severity | Target | Short Description |
|---|---|---|---|---|
| EXT_ERR_01 | Lexer | Fatal | All | Unexpected character |
| EXT_ERR_02 | Lexer | Fatal | All | Unterminated string |
| EXT_ERR_03 | Lexer | Fatal | All | Invalid number literal |
| EXT_ERR_04 | Lexer | Fatal | All | Invalid identifier |
| EXT_ERR_05 | Parser | Fatal | All | Expected token |
| EXT_ERR_06 | Parser | Fatal | All | Unexpected token |
| EXT_ERR_07 | Parser | Fatal | All | Invalid expression |
| EXT_ERR_08 | Type Checker | Fatal | All | Type mismatch |
| EXT_ERR_09 | Type Checker | Fatal | All | Undefined variable |
| EXT_ERR_10 | Type Checker | Fatal | All | Undefined function |
| EXT_ERR_11 | Type Checker | Fatal | All | Argument count mismatch |
| EXT_ERR_12 | Type Checker | Fatal | All | Cannot apply operator |
| EXT_ERR_13 | Type Checker | Fatal | All | Return type mismatch |
| EXT_ERR_14 | Emitter | Fatal | Bash | Unsupported construct |
| EXT_ERR_15 | Emitter | Warning | Bash | Word splitting hazard |
| EXT_ERR_16 | Emitter | Fatal | Native | No linker found |
| EXT_ERR_17 | Emitter | Fatal | Native | C compilation failed |
| EXT_ERR_18 | Linker | Fatal | Native | Multiple definition |
| EXT_ERR_19 | Runtime | Error | Python | Division by zero |
| EXT_ERR_20 | Runtime | Error | Python | Index out of bounds |
| EXT_ERR_21 | Runtime | Fatal | Native | Stack overflow |
| EXT_ERR_22 | Runtime | Fatal | Native | Segfault |
| EXT_ERR_23 | Compiler | Fatal | All | Internal error |
| EXT_ERR_24 | Compiler | Fatal | All | Out of memory |
| EXT_ERR_25 | Compiler | Fatal | All | File not found |
| EXT_ERR_26 | Compiler | Fatal | All | I/O error |
| EXT_ERR_27 | Type Checker | Fatal | All | Import not found |
| EXT_ERR_28 | Type Checker | Fatal | All | Circular import |
| EXT_ERR_29 | Compiler | Fatal | All | Feature not supported |
| EXT_ERR_30 | Compiler | Fatal | All | Version mismatch |
| EXT_ERR_31 | Parser | Fatal | All | Indentation error |
| EXT_ERR_32 | Parser | Fatal | All | Unexpected EOF |
| EXT_ERR_33 | Type Checker | Fatal | All | Already defined |
| EXT_ERR_34 | Type Checker | Fatal | All | Cannot infer type |
| EXT_ERR_35 | Emitter | Warning | Bash | Recursive function limit |
| EXT_ERR_36 | Runtime | Error | Bash | Read-only variable |
| EXT_ERR_37 | Runtime | Error | Bash | Argument list too long |
| EXT_ERR_38 | Compiler | Fatal | All | Timeout |
| EXT_ERR_39 | Parser | Warning | All | Duplicate key |
| EXT_ERR_40 | Compiler | Fatal | Native | Platform not supported |

---

*Last updated: 2026-09-11. 40 error codes documented.*
