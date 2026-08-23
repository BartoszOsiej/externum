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


def _ext_alloc(type_name="Any", count=1):
    """Allocate `count` slots of `type_name`. Returns an opaque pointer id."""
    if count < 1:
        raise RuntimeError(f"alloc: count must be >= 1, got {count}")
    pid = next(_ext_next_id)
    _ext_heap[pid] = {"type": type_name, "count": count, "values": [None] * count}
    return pid


def _ext_free(pid):
    """Free a pointer. Double-free and free of unknown ids raise."""
    slot = _ext_heap.pop(pid, None)
    if slot is None:
        raise RuntimeError(f"free: invalid or already-freed pointer {pid}")


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


def _ext_spawn(fn):
    """Run `fn` on a daemon thread."""
    thread = threading.Thread(target=fn, daemon=True)
    thread.start()
    return thread


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
