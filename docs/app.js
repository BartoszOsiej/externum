/* Externum Live Playground — run, extend and compile the language client-side.
 * Pyodide (WASM CPython) hosts the real Externum transpiler + runtime.
 * "Extend" hot-loads user modules into the running interpreter and persists
 * them locally; shared links restore the whole session from a URL hash.      */

const PYODIDE_INDEX = 'https://cdn.jsdelivr.net/pyodide/v0.26.4/full/';
const REPO_RAW = 'https://raw.githubusercontent.com/BartoszOsiej/externum/main/';

const CORE_FILES = [
  'externum/__init__.py',
  'externum/lexer.py',
  'externum/parser.py',
  'externum/compiler.py',
  'externum/runtime/__init__.py',
];

const STDLIB_MODULES = ['mathx', 'strings', 'structs', 'fs'];

const EXAMPLES = {
  hello: `# Hello world — Externum style: every binding is declared and typed
name: Str = "world"
print("Hello from Externum!")

x: Int = 0b1010
print(f"0b1010 = {x}")
print("1 + 1 =", 1 + 1)`,
  oop: `# Classes and inheritance
class Animal:
    def __init__(self, name: Str):
        self.name = name
    def speak(self) -> Str:
        return "..."

class Dog(Animal):
    def speak(self) -> Str:
        return "Woof!"

class Cat(Animal):
    def speak(self) -> Str:
        return "Meow!"

zoo: List[Animal] = [Dog("Rex"), Cat("Mruczek")]
for a in zoo:
    print(f"{a.name} says: {a.speak()}")`,
  comprehensions: `# Comprehensions, lambdas and generators
numbers: List[Int] = [1, 2, 3, 4, 5, 6]

squares: List[Int] = [n * n for n in numbers if n % 2 == 0]
print("even squares:", squares)

double: Any = lambda x: x * 2
print("doubled:", [double(n) for n in numbers])

def fib(n: Int):
    mut a: Int = 0
    mut b: Int = 1
    for _ in range(n):
        yield a
        t: Int = a
        a = b
        b = t + b

print("fib:", [x for x in fib(10)])`,
  fstrings: `# F-strings, dicts and formatting
user: Dict[Str, Any] = {"name": "Bartosz", "lang": "Externum", "score": 99}

print(f"{user['name']} writes {user['lang']}")
print(f"score: {user['score']}%")
print(f"pi ~= {3.1415926535:.2f}")

squares: Dict[Int, Int] = {n: n * n for n in range(1, 6)}
print(squares)`,
  modules: `# Stdlib imports — the stdlib itself is written in Externum
import mathx

print("factorial(5) =", mathx.factorial(5))
print("gcd(48, 36)  =", mathx.gcd(48, 36))
print("fib(10)      =", mathx.fib(10))

import strings
print("reversed:", strings.reverse("externum"))
print("palindrome:", strings.is_palindrome("kajak"))`,
  shell: `# Inline Bash — sandboxed by your browser tab
\`echo hello from bash\`

%%
echo "multi-line shell block"
echo "running inside a WASM sandbox"
%%`,
  usemod: `# Assumes you hot-loaded a module called "mymodule" in the EXTEND tab.
import mymodule

print(mymodule.hello("Externum"))
print("2^10 =", mymodule.pow2(10))`,
  pokedex: `# Mini Pokédex — classes, inheritance, comprehensions, lambdas
class Pokemon:
    def __init__(self, name: Str, ptype: Str, power: Int):
        self.name = name
        self.ptype = ptype
        self.power = power
    def describe(self) -> Str:
        return f"{self.name} ({self.ptype}) power {self.power}"

pokedex: List[Pokemon] = [
    Pokemon("Pikachu", "electric", 55),
    Pokemon("Charizard", "fire", 84),
    Pokemon("Blastoise", "water", 79),
]

for p in pokedex:
    print(" -", p.describe())

strongest: Any = max(pokedex, key=lambda p: p.power)
print("Strongest:", strongest.describe())

fire: List[Str] = [p.name for p in pokedex if p.ptype == "fire"]
print("Fire types:", fire)`,
};

const MODULE_TEMPLATE = `# mymodule.ext — your own contribution to the language
# Externum v3 is strictly typed: declare params and returns.

def hello(name: Str) -> Str:
    return f"hello {name}"

def pow2(n: Int) -> Int:
    return 2 ** n
`;

const DESCRIBE_TEMPLATE = (desc) => {
  const funcs = [];
  const re = /(?:function|func|fn)?\s*([a-zA-Z_][\w]*)\s*\(([^)]*)\)/g;
  let m;
  while ((m = re.exec(desc)) !== null) {
    const [, name, args] = m;
    if (['a', 'the', 'that', 'and', 'or'].includes(name)) continue;
    const argList = args.split(',').map(s => s.trim()).filter(Boolean)
      .map(a => /^[a-zA-Z_]\w*$/.test(a) ? `${a}: Any` : a);
    funcs.push({ name, args: argList });
  }
  if (funcs.length === 0) {
    const words = desc.toLowerCase().replace(/[^a-z0-9 ]/g, '').split(' ').filter(Boolean);
    const name = words.find(w => w.length > 3) || 'my_function';
    funcs.push({ name, args: ['x: Any'] });
  }
  const body = funcs.map(f =>
`def ${f.name}(${f.args.join(', ')}) -> Any:
    """
    ${desc.trim().slice(0, 140)}
    """
    # TODO: implement — then hit "Load into runtime",
    # or propose it to the official stdlib!
    raise NotImplementedError("${f.name} is not implemented yet")`
  ).join('\n\n');
  return `# Module generated from description:\n# "${desc.trim()}"\n\n${body}\n`;
};

const DESCRIBE_TEMPLATE = (desc) => {
  const funcs = [];
  const re = /(?:function|func|fn)?\s*([a-zA-Z_][\w]*)\s*\(([^)]*)\)/g;
  let m;
  while ((m = re.exec(desc)) !== null) {
    const [, name, args] = m;
    if (['a', 'the', 'that', 'and', 'or'].includes(name)) continue;
    const argList = args.split(',').map(s => s.trim()).filter(Boolean);
    funcs.push({ name, args: argList });
  }
  if (funcs.length === 0) {
    const words = desc.toLowerCase().replace(/[^a-z0-9 ]/g, '').split(' ').filter(Boolean);
    const name = words.find(w => w.length > 3) || 'my_function';
    funcs.push({ name, args: ['x'] });
  }
  const body = funcs.map(f =>
`def ${f.name}(${f.args.join(', ')}):
    """${desc.trim().slice(0, 120)}"""
    # TODO: implement — or propose it to the stdlib!
    raise NotImplementedError("${f.name} is not implemented yet")`
  ).join('\n\n');
  return `# Module generated from description:\n# "${desc.trim()}"\n\n${body}\n`;
};

/* ---------------- state ---------------- */
let pyodide = null;
let booting = null;
const LS_KEY = 'externum_playground_modules_v1';

const $ = (id) => document.getElementById(id);
const statusEl = () => $('status');

function setStatus(text, kind = 'idle') {
  statusEl().textContent = text;
  statusEl().className = `status ${kind}`;
}

const loadModules = () => {
  try { return JSON.parse(localStorage.getItem(LS_KEY)) || {}; }
  catch { return {}; }
};
const saveModules = (mods) => localStorage.setItem(LS_KEY, JSON.stringify(mods));

/* ---------------- pyodide boot ---------------- */
async function fetchText(url, fallbackUrl) {
  const r = await fetch(url);
  if (r.ok) return r.text();
  if (fallbackUrl) {
    const r2 = await fetch(fallbackUrl);
    if (r2.ok) return r2.text();
  }
  throw new Error(`Failed to fetch ${url}`);
}

async function boot() {
  if (pyodide) return pyodide;
  if (booting) return booting;
  setStatus('Booting Python (WebAssembly)… ~10 MB, cached after first load', 'busy');
  booting = (async () => {
    if (!window.loadPyodide) {
      await new Promise((res, rej) => {
        const s = document.createElement('script');
        s.src = PYODIDE_INDEX + 'pyodide.js';
        s.onload = res; s.onerror = () => rej(new Error('Pyodide CDN unreachable'));
        document.head.appendChild(s);
      });
    }
    const py = await window.loadPyodide({ indexURL: PYODIDE_INDEX });

    // core language sources: bundled copy ships with this site
    py.FS.mkdirTree('/lib/externum/runtime');
    py.FS.mkdirTree('/lib/lib');
    for (const f of CORE_FILES) {
      const text = await fetchText('externum-live/' + f);
      py.FS.writeFile('/lib/' + f, text);
    }

    // stdlib: try LIVE version from the repo main branch first (the language
    // evolves when /define proposals merge), fall back to the bundled copy.
    for (const mod of STDLIB_MODULES) {
      const live = await fetchText(REPO_RAW + 'lib/' + mod + '.ext',
                                   'externum-live/lib/' + mod + '.ext')
        .catch(() => null);
      const src = live ?? await fetchText('externum-live/lib/' + mod + '.ext');
      py.FS.writeFile(`/lib/lib/${mod}.ext`, src);
    }

    // overlay user modules on top of stdlib
    for (const [name, code] of Object.entries(loadModules())) {
      py.FS.writeFile(`/lib/lib/${name}.ext`, code);
    }

    py.runPython(`
import sys, io, os
sys.path.insert(0, '/lib')
os.chdir('/lib')

def ext_run(source):
    from externum import Runtime
    buf = io.StringIO()
    old = sys.stdout, sys.stderr
    sys.stdout = sys.stderr = buf
    try:
        Runtime(search_roots=['/lib']).run(source)
        return ('ok', buf.getvalue())
    except Exception as e:
        return ('err', f'{type(e).__name__}: {e}\\n' + buf.getvalue())
    finally:
        sys.stdout, sys.stderr = old

def ext_compile(source, target):
    from externum import Lexer, Parser, Compiler
    ast = list(Parser(Lexer(source).tokenize()).parse())
    out = Compiler(ast).compile(target)
    return out if isinstance(out, str) and out.strip() else f'# (target "{target}" produced no output)'

def ext_install_module(name, code):
    safe = ''.join(c for c in name if c.isalnum() or c == '_')
    if not safe or safe[0].isdigit():
        return ('err', 'invalid module name')
    with open(f'/lib/lib/{safe}.ext', 'w') as fh:
        fh.write(code)
    for m in [k for k in list(sys.modules) if k == safe]:
        del sys.modules[m]
    return ('ok', f'/lib/lib/{safe}.ext')

def ext_remove_module(name):
    p = f'/lib/lib/{name}.ext'
    if os.path.exists(p):
        os.remove(p)
        return ('ok', p)
    return ('err', 'not found')
`);
    pyodide = py;
    setStatus('Runtime ready — you are running a real language implementation', 'ok');
    return py;
  })();
  try {
    return await booting;
  } catch (e) {
    setStatus(`Runtime failed: ${e.message}`, 'err');
    booting = null;
    throw e;
  }
}

/* ---------------- run tab ---------------- */
async function runProgram() {
  const code = $('code').value;
  if (!code.trim()) return;
  $('run').disabled = true;
  setStatus('Compiling + executing…', 'busy');
  try {
    const py = await boot();
    const res = py.globals.get('ext_run')(code).toJs();
    const [kind, text] = res;
    const out = $('output');
    out.textContent = text || '(no output)';
    out.className = 'console' + (kind === 'err' ? ' error' : '');
    setStatus(kind === 'ok' ? 'Finished — exit 0' : 'Program raised an error', kind);
  } catch (e) {
    $('output').textContent = String(e);
    $('output').className = 'console error';
    setStatus('Runtime error', 'err');
  } finally {
    $('run').disabled = false;
  }
}

/* ---------------- compile tab ---------------- */
async function compileAll() {
  $('compile').disabled = true;
  setStatus('Compiling to all targets…', 'busy');
  try {
    const py = await boot();
    const code = $('code').value;
    for (const t of ['python', 'bash', 'binary']) {
      try {
        const out = py.globals.get('ext_compile')(code, t);
        $(`out-${t}`).textContent = out;
      } catch (e) {
        $(`out-${t}`).textContent = '# compile error:\n' + e;
      }
    }
    setStatus('Compiled: python · bash · binary', 'ok');
  } catch (e) {
    setStatus(`Compile failed: ${e.message}`, 'err');
  } finally {
    $('compile').disabled = false;
  }
}

/* ---------------- extend tab ---------------- */
function renderModList() {
  const mods = loadModules();
  const names = Object.keys(mods);
  const wrap = $('modlist');
  wrap.innerHTML = '';
  if (!names.length) {
    wrap.innerHTML = '<span class="chip empty">none yet — load one above</span>';
    return;
  }
  for (const n of names) {
    const chip = document.createElement('span');
    chip.className = 'chip';
    chip.textContent = '🧬 ' + n;
    chip.title = 'click to edit · double-click to remove';
    chip.onclick = () => { $('modname').value = n; $('modcode').value = mods[n]; };
    chip.ondblclick = () => removeModule(n);
    wrap.appendChild(chip);
  }
}

async function installModule(name, code) {
  const py = await boot();
  const res = py.globals.get('ext_install_module')(name, code).toJs();
  if (res[0] === 'err') throw new Error(res[1]);
  return res[1];
}

async function loadModule() {
  const name = $('modname').value.trim();
  const code = $('modcode').value;
  if (!/^[A-Za-z_][\w]*$/.test(name)) { setStatus('Module name must be a valid identifier', 'err'); return; }
  if (!code.trim()) { setStatus('Module source is empty', 'err'); return; }
  $('loadmod').disabled = true;
  setStatus(`Hot-loading ${name}.ext into the running runtime…`, 'busy');
  try {
    await installModule(name, code);
    const mods = loadModules();
    mods[name] = code;
    saveModules(mods);
    renderModList();
    setStatus(`✅ ${name} loaded — "import ${name}" works everywhere now (Run tab)`, 'ok');
  } catch (e) {
    setStatus(`Load failed: ${e.message}`, 'err');
  } finally {
    $('loadmod').disabled = false;
  }
}

async function removeModule(name) {
  delete loadModules()[name];
  const mods = loadModules(); delete mods[name]; saveModules(mods);
  renderModList();
  if (pyodide) pyodide.globals.get('ext_remove_module')(name);
  setStatus(`Removed ${name}`, 'idle');
}

function proposeToStdlib() {
  const name = $('modname').value.trim() || 'mymodule';
  const code = $('modcode').value;
  const body = [
    '### `/define` proposal — new stdlib module', '',
    `**Module name:** \`${name}\``, '',
    '```ext', code, '```', '',
    '_Submitted from the web playground. The command bot will validate it ' +
    'against the test suite and open a PR into `lib/`._',
  ].join('\n');
  const url = 'https://github.com/BartoszOsiej/externum/issues/new'
    + '?title=' + encodeURIComponent(`/define module ${name}`)
    + '&body=' + encodeURIComponent(body)
    + '&labels=' + encodeURIComponent('stdlib-proposal');
  window.open(url, '_blank', 'noopener');
}

/* ---------------- share ---------------- */
function shareSession() {
  const payload = { p: $('code').value, m: loadModules() };
  location.hash = 's=' + btoa(unescape(encodeURIComponent(JSON.stringify(payload))));
  navigator.clipboard.writeText(location.href)
    .then(() => setStatus('🔗 Session link copied to clipboard', 'ok'))
    .catch(() => setStatus('🔗 Link is in the address bar', 'ok'));
}

function restoreFromHash() {
  if (!location.hash.startsWith('#s=')) return false;
  try {
    const data = JSON.parse(decodeURIComponent(escape(atob(location.hash.slice(3)))));
    if (data.p) $('code').value = data.p;
    if (data.m && typeof data.m === 'object') saveModules(data.m);
    return true;
  } catch { return false; }
}

/* ---------------- wiring ---------------- */
document.querySelectorAll('.tab').forEach(t => t.addEventListener('click', () => {
  document.querySelectorAll('.tab').forEach(x => x.classList.remove('active'));
  document.querySelectorAll('.panel').forEach(x => x.classList.remove('active'));
  t.classList.add('active');
  $(`panel-${t.dataset.tab}`).classList.add('active');
}));

document.querySelectorAll('.segbtn').forEach(b => b.addEventListener('click', () => {
  document.querySelectorAll('.segbtn').forEach(x => x.classList.remove('active'));
  b.classList.add('active');
  const describe = b.dataset.mode === 'describe';
  $('describe').style.display = describe ? '' : 'none';
  $('descwrap').style.display = describe ? '' : 'none';
  $('genfromdesc').style.display = describe ? '' : 'none';
}));

$('example').addEventListener('change', () => { $('code').value = EXAMPLES[$('example').value] || ''; });
$('run').addEventListener('click', runProgram);
$('compile').addEventListener('click', compileAll);
$('loadmod').addEventListener('click', loadModule);
$('propose').addEventListener('click', proposeToStdlib);
$('share').addEventListener('click', shareSession);
$('clearmods').addEventListener('click', () => {
  for (const n of Object.keys(loadModules())) { if (pyodide) pyodide.globals.get('ext_remove_module')(n); }
  saveModules({}); renderModList();
  setStatus('All custom modules removed', 'idle');
});
$('genfromdesc').addEventListener('click', () => {
  const d = $('describe').value.trim();
  if (!d) { setStatus('Describe the functions first', 'err'); return; }
  $('modcode').value = DESCRIBE_TEMPLATE(d);
  if (!$('modname').value.trim()) $('modname').value = 'mymodule';
  $('modfile').textContent = $('modname').value.trim() + '.ext';
  setStatus('Skeleton generated — refine it, then Load into runtime', 'ok');
});
$('modname').addEventListener('input', () => {
  $('modfile').textContent = ($('modname').value.trim() || 'mymodule') + '.ext';
});
document.addEventListener('keydown', (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
    e.preventDefault();
    if ($('panel-run').classList.contains('active')) runProgram();
    else if ($('panel-compile').classList.contains('active')) compileAll();
    else loadModule();
  }
});

/* ---------------- init ---------------- */
(function init() {
  const restored = restoreFromHash();
  if (!restored) $('code').value = EXAMPLES.hello;
  $('modcode').value = MODULE_TEMPLATE;
  renderModList();
})();
