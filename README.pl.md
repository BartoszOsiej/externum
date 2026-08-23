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

## Hard Mode (`--hard`) — giga trudny

Uruchom dowolny program przez `externum run program.ext --hard` (albo
`compile … --hard`), by włączyć hardcore'owy ruleset. Istniejące programy,
które go łamią, zawodzą głośno:

- **Obowiązkowe deklaracje** — każda zmienna potrzebuje `x: Typ` przed
  użyciem; użycie niezadeklarowanej nazwy to błąd kompilacji.
- **Statyczne typowanie** — niezgodności przypisań/zwracanych wartości są
  odrzucane na etapie kompilacji (`Int` rozszerza się do `Float`; reszta
  musi się zgadzać).
- **Ręczna pamięć** — `alloc(Int)`, `free(p)`, dereferencja `@p`;
  double-free i use-after-free to **błędy kompilacji** (ownership jest
  egzekwowane).
- **`match`/`case`** — pattern matching z literałami, bindami, guardami
  i destrukcią list/krotek.
- **Traity** — `trait X:` + `impl X for Y:`; implementacje z brakującymi
  metodami lub złymi typami zwracanymi są odrzucane.
- **Bloki `unsafe:`** — furtka ratunkowa: w środku pomijane są sprawdzenia.
- **Makra** — `macro NAZWA(a, b) { … }` rozwijane w czasie kompilacji.
- **Współbieżność** — `spawn(f(...))`, `chan()`, `send(ch, v)`, `recv(ch)`.
- **Egzotyczne operatory** — `≠`, `≈`, `←` działają jak `!=`, `==`, `=`.

```bash
externum run examples/hardcore.ext --hard
```

## DRM (`--protect`) — obfuskacja, watermark, licencja

Każdy chroniony build niesie pełny stack defense-in-depth:

1. **Klucze licencyjne** — podpisywane HMAC-SHA256; `externum keygen
   --app-id X --secret S` wydaje klucze, artefakt je weryfikuje (env
   `EXTERNUM_LICENSE`), nigdy nie osadzając sekretu.
2. **Watermark** — nagłówek autora/aplikacji/buildu/hashu źródła w każdym
   pliku.
3. **Wykrywanie modyfikacji** — SHA-256 źródła + self-hash artefaktu
   osadzone; zmodyfikowane kopie są wykrywane.
4. **Obfuskacja** — literały stringów kodowane przez helper runtime'u.

```bash
externum compile app.ext --protect --app-id game --author buffy --secret s3cret
EXTERNUM_LICENSE=<klucz> externum run app.ext --protect --app-id game --author buffy --secret s3cret
```

Standardowa biblioteka `drm.ext` udostępnia `sign`/`verify`/`watermark`
w samym języku.

## Testy

```bash
python3 -m unittest discover -s tests -v   # 167 testów
```

## Struktura projektu

```
externum/
├── lexer.py          # Tokenizacja (bracket-aware, bash, f-stringi)
├── parser.py         # Pełna gramatyka → AST
├── compiler.py       # Codegen → Python / Bash / binary
├── typesys.py        # type checker (hard mode: typy statyczne, ownership)
├── hardmode.py       # makra + pipeline hard mode
├── drm.py            # DRM: klucze licencyjne, watermark, tamper-detection, obfuskacja
├── runtime/          # Runtime: exec, import .ext, REPL (+ rtlib.py: pamięć/współbieżność)
└── __main__.py       # CLI (run / repl / compile / keygen)
lib/                  # Standardowa biblioteka (.ext) — w tym drm.ext
lib/drm.ext           # DRM stdlib: sign / verify / watermark w Externum
examples/             # hello, calc, pokedex, hardcore.ext
tests/                # 167 testów jednostkowych
WIKI.md               # Specyfikacja języka
```

## Roadmap

Moduły zarezerwowane w API (`externum.llm`, `neural`, `distributed`,
`types`, `spec`, `debug`) pozostają w planie — pakiet działa bez nich.
