# Externum

**Externum v3.0** — pełny język programowania będący mieszanką czytelności
Pythona, wydajności kodu binarnego i kontroli systemu Basha. Jedno źródło
kompiluje się do **Python**, **Bash** i reprezentacji **binarnej** — albo
wykonuje się wprost.

```
Externum = Python_readability ⊕ Binary_performance ⊕ Bash_control
```

## Co potrafi (v3)

| Obszar | Wsparcie |
|---|---|
| **Typy danych** | listy, słowniki, krotki, zbiory (także wielolinijkowe), f-stringi, literały binarne `0b` i hex `0x` |
| **Przepływ sterowania** | `if/elif/else`, `while`, `for ... in` (wielozmienne), `break`, `continue`, `try/except/else/finally`, `with`, `assert` |
| **Funkcje** | parametry z wartościami domyślnymi, `*args`/`**kwargs`, adnotacje typów (opcjonalne), rekurencja, lambdy, domknięcia, generatory (`yield`) |
| **OOP** | klasy, dziedziczenie, metody, `self`, atrybuty |
| **Moduły** | `import`/`from ... import`, własne moduły `.ext` (loader), standardowa biblioteka |
| **Wyrażenia** | pełny priorytet operatorów, porównania łańcuchowe, bitowe `& \| ^ ~ << >>`, ternary, comprehensions (list/dict), rozpakowywanie krotek |
| **Shell** | bash inline `` `cmd` `` i bloki `%% ... %%` |
| **Narzędzia** | REPL, kompilacja do 3 targetów, `argv` |

## Instalacja

```bash
pip install -e .        # Python 3.10+
externum --version      # Externum 3.0.0
```

## Użycie

```bash
# Wykonaj program
externum run examples/pokedex.ext

# REPL
externum repl

# Kompilacja do wszystkich targetów
externum examples/hello.ext

# Kompilacja do Pythona / Basha
externum examples/hello.ext --target python -o hello.py
externum examples/hello.ext --target bash
```

## Przykład (pokedex)

`examples/pokedex.ext` używa klas z dziedziczeniem, comprehensions,
lambd, wyjątków, generatorów, f-stringów i biblioteki standardowej:

```python
import mathx
import strings

class Fire(Pokemon):
    def __init__(self, name, hp=50):
        Pokemon.__init__(self, name, ["fire"], hp)

fire_team = [p.name for p in squad if p.is_type("fire")]
weakest = min(squad, key=lambda p: p.hp)
nums = [f for f in fibonacci(10) if f % 2 == 0]
```

## Standardowa biblioteka (napisana w Externum)

| Moduł | Zawartość |
|---|---|
| `structs` | `Stack`, `Queue`, `Counter` |
| `strings` | `reverse`, `is_palindrome`, `slugify`, `word_count`, `capitalize`, `truncate` |
| `mathx` | `clamp`, `is_even`, `gcd`, `fib`, `factorial`, `sum_of_digits` |
| `fs` | `read_file`, `write_file`, `append_file`, `file_exists`, `list_dir` |

```bash
externum run examples/pokedex.ext
```

## Testy

```bash
python3 -m unittest discover -s tests -v   # 118 testów
```

## Struktura projektu

```
externum/
├── lexer.py          # Tokenizacja (bracket-aware, bash, f-stringi)
├── parser.py         # Pełna gramatyka → AST
├── compiler.py       # Codegen → Python / Bash / binary
├── runtime/          # Runtime: exec, import .ext, REPL
└── __main__.py       # CLI (run / repl / compile)
lib/                  # Standardowa biblioteka (.ext)
examples/             # hello, calc, pokedex
tests/                # 118 testów jednostkowych
WIKI.md               # Specyfikacja języka
```

## Roadmap

Moduły zarezerwowane w API (`externum.llm`, `neural`, `distributed`,
`types`, `spec`, `debug`) pozostają w planie — pakiet działa bez nich.
