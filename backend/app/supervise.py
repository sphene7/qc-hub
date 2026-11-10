"""Startup supervision logs: GC, memory, runtime, context switches, slow requests.

Enabled automatically when the app starts. Set SUPERVISE=0 to turn it off.
SUPERVISE_INTERVAL seconds between snapshots (default 30).
SUPERVISE_SLOW_MS marks a request as blocking (default 500).
"""

from __future__ import annotations

import ctypes
import gc
import os
import sys
import threading
import time
from ctypes import wintypes
from datetime import datetime
from pathlib import Path

from .logutil import log

LOG_DIR = Path(__file__).resolve().parents[1] / "logs" / "supervise"
_MAX_BYTES = 2_000_000
_lock = threading.Lock()
_started = False
_stop = threading.Event()

_gc_events = 0
_gc_pause_ms = 0.0
_gc_phase_started: float | None = None
_gc_hooked = False

_last_cpu_s: float | None = None
_last_switches: int | None = None
_last_mono: float | None = None


def _enabled() -> bool:
    return os.getenv("SUPERVISE", "1").strip().lower() not in {"0", "false", "no", "off"}


def _interval() -> float:
    try:
        return max(5.0, float(os.getenv("SUPERVISE_INTERVAL", "30")))
    except ValueError:
        return 30.0


def _slow_ms() -> float:
    try:
        return max(1.0, float(os.getenv("SUPERVISE_SLOW_MS", "500")))
    except ValueError:
        return 500.0


def _stamp() -> str:
    return datetime.now().strftime("%m-%d %H:%M:%S")


def _append(name: str, message: str) -> None:
    line = f"[{_stamp()}] {message}"
    path = LOG_DIR / name
    with _lock:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.exists() and path.stat().st_size > _MAX_BYTES:
                bak = path.with_suffix(path.suffix + ".1")
                if bak.exists():
                    bak.unlink()
                path.replace(bak)
            with path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
        except OSError:
            return


def _on_gc(phase: str, _info: dict) -> None:
    global _gc_events, _gc_pause_ms, _gc_phase_started
    if phase == "start":
        _gc_phase_started = time.perf_counter()
        return
    if phase != "stop" or _gc_phase_started is None:
        return
    _gc_pause_ms += (time.perf_counter() - _gc_phase_started) * 1000
    _gc_events += 1
    _gc_phase_started = None


def _hook_gc() -> None:
    global _gc_hooked
    if _gc_hooked:
        return
    gc.callbacks.append(_on_gc)
    _gc_hooked = True


def _gc_line() -> str:
    global _gc_events, _gc_pause_ms
    stats = gc.get_stats()
    parts = []
    for gen, row in enumerate(stats):
        parts.append(
            f"gen{gen}={row.get('collections', 0)}/{row.get('collected', 0)}"
        )
    events = _gc_events
    pause = _gc_pause_ms
    _gc_events = 0
    _gc_pause_ms = 0.0
    counts = gc.get_count()
    return (
        f"pause_events={events} pause_ms={pause:.1f} "
        f"pending={counts[0]}/{counts[1]}/{counts[2]} " + " ".join(parts)
    )


def _memory_line() -> str:
    if sys.platform != "win32":
        return "platform=non-windows"
    mem = _win_memory()
    if mem is None:
        return "unavailable"
    rss, private, avail, total, load = mem
    return (
        f"rss={rss:.0f}MB private={private:.0f}MB "
        f"sys_avail={avail:.0f}MB sys_total={total:.0f}MB load={load:.0f}%"
    )


def _runtime_line() -> str:
    cpu = _process_cpu_seconds()
    handles = _process_handle_count()
    threads = threading.active_count()
    cpu_txt = f"{cpu:.1f}" if cpu is not None else "-"
    handle_txt = str(handles) if handles is not None else "-"
    return f"pid={os.getpid()} py_threads={threads} handles={handle_txt} cpu_s={cpu_txt}"


def _switches_line() -> str:
    global _last_switches, _last_mono, _last_cpu_s
    now = time.perf_counter()
    switches, os_threads = _process_context_switches()
    cpu = _process_cpu_seconds()
    rate = "-"
    cpu_pct = "-"
    if switches is not None and _last_switches is not None and _last_mono is not None:
        elapsed = now - _last_mono
        if elapsed > 0:
            rate = f"{(switches - _last_switches) / elapsed:.0f}"
    if cpu is not None and _last_cpu_s is not None and _last_mono is not None:
        elapsed = now - _last_mono
        if elapsed > 0:
            # One full core is 100%.
            cpu_pct = f"{(cpu - _last_cpu_s) / elapsed * 100:.0f}"
    if switches is not None:
        _last_switches = switches
    if cpu is not None:
        _last_cpu_s = cpu
    _last_mono = now
    total = str(switches) if switches is not None else "-"
    nthreads = str(os_threads) if os_threads is not None else "-"
    return f"switches_per_s={rate} total={total} os_threads={nthreads} cpu_pct={cpu_pct}"


def _snapshot() -> None:
    _append("gc.log", _gc_line())
    _append("memory.log", _memory_line())
    _append("runtime.log", _runtime_line())
    _append("switches.log", _switches_line())


def _loop() -> None:
    interval = _interval()
    while not _stop.wait(interval):
        try:
            _snapshot()
        except Exception as exc:
            _append("runtime.log", f"snapshot_error={exc}")


def start_supervisor() -> None:
    """Start background snapshots once per process. Safe to call from startup."""
    global _started
    if _started or not _enabled():
        if not _enabled():
            log("监督未开启 (SUPERVISE=0)")
        return
    _started = True
    _hook_gc()
    try:
        _snapshot()
    except Exception as exc:
        _append("runtime.log", f"snapshot_error={exc}")
    threading.Thread(target=_loop, name="supervise", daemon=True).start()
    log(
        f"监督已开启 interval={_interval():.0f}s slow={_slow_ms():.0f}ms "
        f"dir={LOG_DIR}"
    )


def note_blocking(method: str, path: str, elapsed_ms: float, status: str) -> None:
    """Record a request that ran longer than SUPERVISE_SLOW_MS."""
    if not _enabled() or elapsed_ms < _slow_ms():
        return
    text = path if len(path) <= 180 else path[:180] + "..."
    _append("blocking.log", f"{method} {text} {elapsed_ms:.0f}ms status={status}")


def _kernel32() -> ctypes.WinDLL:
    dll = ctypes.WinDLL("kernel32", use_last_error=True)
    dll.GetCurrentProcess.restype = ctypes.c_void_p
    dll.GetProcessHandleCount.argtypes = [ctypes.c_void_p, ctypes.POINTER(wintypes.DWORD)]
    dll.GetProcessHandleCount.restype = wintypes.BOOL
    return dll


def _psapi() -> ctypes.WinDLL:
    dll = ctypes.WinDLL("psapi", use_last_error=True)
    dll.GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD]
    dll.GetProcessMemoryInfo.restype = wintypes.BOOL
    return dll


def _win_memory() -> tuple[float, float, float, float, float] | None:
    class MEMORYSTATUSEX(ctypes.Structure):
        _fields_ = [
            ("dwLength", wintypes.DWORD),
            ("dwMemoryLoad", wintypes.DWORD),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    class PROCESS_MEMORY_COUNTERS_EX(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD),
            ("PageFaultCount", wintypes.DWORD),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
            ("PrivateUsage", ctypes.c_size_t),
        ]

    try:
        status = MEMORYSTATUSEX()
        status.dwLength = ctypes.sizeof(status)
        kernel = _kernel32()
        kernel.GlobalMemoryStatusEx.argtypes = [ctypes.POINTER(MEMORYSTATUSEX)]
        kernel.GlobalMemoryStatusEx.restype = wintypes.BOOL
        if not kernel.GlobalMemoryStatusEx(ctypes.byref(status)):
            return None
        counters = PROCESS_MEMORY_COUNTERS_EX()
        counters.cb = ctypes.sizeof(counters)
        ok = _psapi().GetProcessMemoryInfo(
            kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb
        )
        if not ok:
            return None
        mb = 1024 * 1024
        return (
            counters.WorkingSetSize / mb,
            counters.PrivateUsage / mb,
            status.ullAvailPhys / mb,
            status.ullTotalPhys / mb,
            float(status.dwMemoryLoad),
        )
    except (OSError, AttributeError):
        return None


def _process_cpu_seconds() -> float | None:
    if sys.platform != "win32":
        return None

    class FILETIME(ctypes.Structure):
        _fields_ = [("dwLowDateTime", wintypes.DWORD), ("dwHighDateTime", wintypes.DWORD)]

    def as_int(value: FILETIME) -> int:
        return (value.dwHighDateTime << 32) | value.dwLowDateTime

    created, exited, kernel_time, user = FILETIME(), FILETIME(), FILETIME(), FILETIME()
    kernel = _kernel32()
    kernel.GetProcessTimes.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(FILETIME),
        ctypes.POINTER(FILETIME),
        ctypes.POINTER(FILETIME),
        ctypes.POINTER(FILETIME),
    ]
    kernel.GetProcessTimes.restype = wintypes.BOOL
    ok = kernel.GetProcessTimes(
        kernel.GetCurrentProcess(),
        ctypes.byref(created),
        ctypes.byref(exited),
        ctypes.byref(kernel_time),
        ctypes.byref(user),
    )
    if not ok:
        return None
    return (as_int(kernel_time) + as_int(user)) / 10_000_000


def _process_handle_count() -> int | None:
    if sys.platform != "win32":
        return None
    count = wintypes.DWORD()
    kernel = _kernel32()
    ok = kernel.GetProcessHandleCount(kernel.GetCurrentProcess(), ctypes.byref(count))
    if not ok:
        return None
    return int(count.value)


def _process_context_switches() -> tuple[int | None, int | None]:
    """Return (total context switches, OS thread count) for this process."""
    if sys.platform != "win32" or ctypes.sizeof(ctypes.c_void_p) != 8:
        return None, None
    try:
        return _walk_process_info(os.getpid())
    except (OSError, ValueError):
        return None, None


def _walk_process_info(pid: int) -> tuple[int | None, int | None]:
    # Windows 10 x64 SYSTEM_PROCESS_INFORMATION is 256 bytes, then threads of 80.
    # ContextSwitches sits at byte 64 of each SYSTEM_THREAD_INFORMATION.
    ntdll = ctypes.WinDLL("ntdll")
    status_mismatch = 0xC0000004
    system_process_information = 5
    size = 1024 * 1024
    for _ in range(6):
        buf = ctypes.create_string_buffer(size)
        retlen = wintypes.ULONG()
        status = ntdll.NtQuerySystemInformation(
            system_process_information, buf, size, ctypes.byref(retlen)
        )
        status &= 0xFFFFFFFF
        if status == status_mismatch:
            size *= 2
            continue
        if status != 0:
            return None, None
        data = buf.raw
        offset = 0
        for _step in range(10000):
            if offset + 256 > len(data):
                return None, None
            next_off = int.from_bytes(data[offset:offset + 4], "little")
            nthreads = int.from_bytes(data[offset + 4:offset + 8], "little")
            proc_id = int.from_bytes(data[offset + 80:offset + 88], "little")
            if proc_id == pid:
                total = 0
                cursor = offset + 256
                for _thread in range(nthreads):
                    if cursor + 80 > len(data):
                        return None, None
                    total += int.from_bytes(data[cursor + 64:cursor + 68], "little")
                    cursor += 80
                return total, nthreads
            if next_off == 0:
                return None, None
            offset += next_off
        return None, None
    return None, None
