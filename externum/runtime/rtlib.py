"""Externum runtime support library.

Provides the `_ext_*` helpers that the compiler emits
constructs (manual memory management, pointer dereference, concurrency,
traits/impls, match). These are injected into the execution namespace of
every compiled program, so `.ext` code can use `alloc`, `free`, `@p`,
`spawn`, `chan`, `send`, `recv` without importing anything.
"""

import itertools
import queue
import threading

# ---------------------------------------------------------------- memory heap
# A tiny, explicit heap. A "pointer" is an integer id into this dict.
_ext_heap = {}
_ext_next_id = itertools.count(1)

_SIZEOF = {"Int": 8, "Float": 8, "Str": 16, "Bool": 1, "Ptr": 8}


# ---------------------------------------------------------------------------
# Resource-bounded executor for the dynamic language.
#
# Externum v4 is self-hosted: user-supplied programs execute here.  A
# resource-bounded executor shrinks the blast radius of untrusted input, which
# is exactly the class of bug this repository is built to catch.  The values
# below are deliberately conservative and are NOT lowered silently in future
# releases without a deliberate decision.
# ---------------------------------------------------------------------------
_MAX_HEAP_SLOTS = 65536     # total heap cells the VM may hold at once
_MAX_THREADS = 16            # concurrently executing _ext_spawn workers
_MAX_FREED = 1024            # retained so double-free / re-free can be caught
_heap_lock = threading.RLock()       # serialises heap + counter edits
_heap_count = 0                      # live heap slots
_freed_ids = set()                   # ids eligible for re-free
_thread_pool = queue.Queue()         # running _ext_spawn workers


def _bounded(f):
    """Thin guard: fail-closed on over-run.  Internal-only; callers are trusted."""
    def wrapper(*a, **kw):
        with _heap_lock:
            if _heap_count >= _MAX_HEAP_SLOTS:
                raise RuntimeError("alloc: heap exhausted")
            if _thread_pool.qsize() >= _MAX_THREADS:
                raise RuntimeError("spawn: thread cap reached")
            n = f(*a, **kw)
        return n
    return wrapper


def _ext_alloc(type_name="Any", count=1):
    """Allocate `count` slots of `type_name`. Returns an opaque pointer id."""
    global _heap_count, _freed_ids
    if count < 1:
        raise RuntimeError(f"alloc: count must be >= 1, got {count}")
    with _heap_lock:
        if _heap_count + count > _MAX_HEAP_SLOTS:
            raise RuntimeError("alloc: heap exhausted")
        pid = next(_ext_next_id)
        if pid in _freed_ids:
            _freed_ids.remove(pid)
        _ext_heap[pid] = {"type": type_name, "count": count, "values": [None] * count}
        _heap_count += count
    return pid


def _ext_free(pid):
    """Free a pointer. Double-free and free of unknown ids raise."""
    global _heap_count, _freed_ids
    with _heap_lock:
        slot = _ext_heap.pop(pid, None)
        if slot is None:
            raise RuntimeError(f"free: invalid or already-freed pointer {pid}")
        _heap_count -= slot["count"]
        if len(_freed_ids) < _MAX_FREED:
            _freed_ids.add(pid)
    return pid


def _ext_load(pid, index=0):
    """Dereference a pointer (read)."""
    slot = _ext_heap.get(pid)
    if slot is None:
        raise RuntimeError(f"deref: invalid or freed pointer {pid}")
    if not 0 <= index < slot["count"]:
        raise RuntimeError(f"deref: index {index} out of bounds ({slot['count']} slots)")
    return slot["values"][index]


def _ext_store(pid, value, index=0):
    """Write through a pointer (`@p = v`)."""
    slot = _ext_heap.get(pid)
    if slot is None:
        raise RuntimeError(f"store: invalid or freed pointer {pid}")
    if not 0 <= index < slot["count"]:
        raise RuntimeError(f"store: index {index} out of bounds ({slot['count']} slots)")
    slot["values"][index] = value


def _ext_addr(value):
    """Take the address of a value: wraps it in a fresh 1-slot heap cell."""
    pid = next(_ext_next_id)
    _ext_heap[pid] = {"type": "Any", "count": 1, "values": [value]}
    return pid


def _ext_sizeof(type_name):
    """Abstract per-type size table (compile-time concept made concrete)."""
    return _SIZEOF.get(str(type_name).strip("[]"), 8)


# ---------------------------------------------------------------- concurrency
def _ext_chan():
    """Create a bounded-safe channel (thread-safe queue)."""
    return queue.Queue()


def _ext_send(ch, value):
    ch.put(value)


def _ext_recv(ch):
    return ch.get()


@_bounded
def _ext_spawn(fn):
    """Run `fn` on a daemon thread, capped by _MAX_THREADS."""
    global _thread_pool
    def _runner():
        try:
            fn()
        finally:
            _thread_pool.task_done()
    _thread_pool.put(_runner)
    threading.Thread(target=_runner, daemon=True).start()
    return _thread_pool.qsize()


def _ext_match_error(value):
    raise RuntimeError(f"match: no case matched {value!r}")


# ---------------------------------------------------------------- traits/impls
_ext_traits = {}  # trait name -> class
_ext_impls = {}  # (trait, class) -> True


def _ext_impls_of(trait):
    return [cls for (t, cls) in _ext_impls if t == trait]


# ---------------------------------------------------------------- namespace
def externum_globals() -> dict:
    """The full runtime support namespace injected into executed programs."""
    return {
        "_ext_heap": _ext_heap,
        "_ext_alloc": _ext_alloc,
        "_ext_free": _ext_free,
        "_ext_load": _ext_load,
        "_ext_store": _ext_store,
        "_ext_addr": _ext_addr,
        "_ext_sizeof": _ext_sizeof,
        "_ext_chan": _ext_chan,
        "_ext_send": _ext_send,
        "_ext_recv": _ext_recv,
        "_ext_spawn": _ext_spawn,
        "_ext_match_error": _ext_match_error,
        "_ext_traits": _ext_traits,
        "_ext_impls": _ext_impls,
        "_ext_impls_of": _ext_impls_of,
    }
