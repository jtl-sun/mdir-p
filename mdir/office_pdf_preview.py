"""Fast cached PDF conversion for Excel, Word, and PowerPoint preview on Windows.

Design goals are borrowed from xViewer 2.7.4:
- use the real Microsoft Office PDF exporters for faithful layout;
- keep a private COM worker alive between previews to avoid repeated startup;
- never attach to the user's interactive Office process;
- cache by resolved path + size + mtime, so unchanged files reopen instantly;
- cancel a superseded conversion instead of making Preview wait behind it;
- fall back to a private headless LibreOffice conversion when Office is absent.
"""
from __future__ import annotations

import atexit
import hashlib
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass
from typing import Optional

EXCEL_PDF_EXTENSIONS = {".xlsx", ".xlsm", ".xltx", ".xltm", ".xls"}
WORD_PDF_EXTENSIONS = {".doc", ".docx"}
POWERPOINT_PDF_EXTENSIONS = {".ppt", ".pptx"}
OFFICE_PDF_EXTENSIONS = (
    EXCEL_PDF_EXTENSIONS | WORD_PDF_EXTENSIONS | POWERPOINT_PDF_EXTENSIONS
)
_CACHE_VERSION = "mdir-2.26.24-office-pdf-v2"
FOREGROUND_TIMEOUT = 15.0
FALLBACK_TIMEOUT = 15.0
_CACHE_MAX_FILES = 900
_CACHE_MAX_BYTES = 3 * 1024**3


@dataclass(frozen=True)
class OfficePdfResult:
    source: Path
    pdf_path: Optional[Path]
    from_cache: bool
    backend: str
    elapsed: float
    error: Optional[str] = None

    @property
    def ok(self) -> bool:
        return bool(
            self.pdf_path is not None
            and self.pdf_path.is_file()
            and not self.error
        )


def office_kind(path: Path) -> Optional[str]:
    suffix = Path(path).suffix.lower()
    if suffix in EXCEL_PDF_EXTENSIONS:
        return "excel"
    if suffix in WORD_PDF_EXTENSIONS:
        return "word"
    if suffix in POWERPOINT_PDF_EXTENSIONS:
        return "powerpoint"
    return None


def _cache_dir() -> Path:
    root = Path(os.environ.get("LOCALAPPDATA") or tempfile.gettempdir())
    return root / "mDIR" / "cache" / "office-pdf"


_LOG_LOCK = threading.Lock()


def _diagnostic(event: str, **details) -> None:
    # Local rotating diagnostics contain paths/timings but never document data.
    try:
        with _LOG_LOCK:
            log = logging.getLogger("mdir.office_pdf_preview")
            if not log.handlers:
                folder = _cache_dir().parent.parent / "logs"
                folder.mkdir(parents=True, exist_ok=True)
                handler = RotatingFileHandler(
                    folder / "office-pdf-preview.log",
                    maxBytes=2_000_000,
                    backupCount=2,
                    encoding="utf-8",
                )
                handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
                log.addHandler(handler)
                log.setLevel(logging.INFO)
                log.propagate = False
            log.info(
                json.dumps(
                    dict(event=event, **details),
                    ensure_ascii=False,
                    default=str,
                )
            )
    except Exception:
        pass


def office_pdf_cache_path(source: Path) -> Path:
    source = Path(source).resolve()
    stat = source.stat()
    kind = office_kind(source) or "office"
    value = (
        f"{_CACHE_VERSION}|{kind}|{source}|"
        f"{stat.st_size}|{stat.st_mtime_ns}"
    )
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:28]
    return _cache_dir() / f"{digest}.pdf"


def valid_pdf(path: Path) -> bool:
    try:
        with Path(path).open("rb") as stream:
            if stream.read(5) != b"%PDF-":
                return False
            stream.seek(0, 2)
            size = stream.tell()
            if size < 16:
                return False
            stream.seek(max(0, size - 4096))
            return b"%%EOF" in stream.read()
    except OSError:
        return False


def office_pdf_cache_hit(source: Path) -> Optional[Path]:
    try:
        target = office_pdf_cache_path(source)
        return target if valid_pdf(target) else None
    except OSError:
        return None


def prune_office_pdf_cache(
    max_files: int = _CACHE_MAX_FILES,
    max_bytes: int = _CACHE_MAX_BYTES,
) -> None:
    try:
        entries = []
        for path in _cache_dir().glob("*.pdf"):
            stat = path.stat()
            entries.append((stat.st_mtime, stat.st_size, path))
        total = sum(row[1] for row in entries)
        count = len(entries)
        for _, size, path in sorted(entries):
            if count <= max_files and total <= max_bytes:
                break
            try:
                path.unlink()
                total -= size
                count -= 1
            except OSError:
                pass
    except OSError:
        pass


class _PrivateOfficeHandle:
    """Retain a real process handle so PID reuse cannot kill an unrelated app."""

    def __init__(self, pid: int, started: float):
        self.handle = None
        handle = None
        try:
            import win32api
            import win32process

            # PROCESS_QUERY_LIMITED_INFORMATION | SYNCHRONIZE | TERMINATE
            handle = win32api.OpenProcess(0x1000 | 0x100000 | 1, False, pid)
            created = win32process.GetProcessTimes(handle)["CreationTime"].timestamp()
            if created >= started - 0.2:
                self.handle = handle
                handle = None
        except Exception as exc:
            _diagnostic("process_handle_unavailable", pid=pid, error=str(exc))
        finally:
            if handle is not None:
                try:
                    handle.Close()
                except Exception:
                    pass

    def close(self) -> None:
        if self.handle is not None:
            try:
                import win32api

                win32api.TerminateProcess(self.handle, 1)
            except Exception:
                pass
            finally:
                try:
                    self.handle.Close()
                except Exception:
                    pass
                self.handle = None


class _PersistentOfficeCom:
    """Supervise the private Office worker and enforce real deadlines."""

    def __init__(self, command=None):
        executable = Path(sys.executable)
        if executable.name.lower() == "pythonw.exe":
            executable = executable.with_name("python.exe")
        self.command = command or [
            str(executable),
            "-u",
            "-m",
            "mdir.office_pdf_worker",
        ]
        self.process = None
        self.events = None
        self.handles: dict[int, _PrivateOfficeHandle] = {}
        self.error = ""
        self.stage = "startup"
        self.started = 0.0

    def start(self) -> None:
        if self.process is not None and self.process.poll() is None:
            return
        self.stop()
        self.started = time.time()
        self.events = queue.Queue()
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONPATH"] = (
            str(Path(__file__).resolve().parent.parent)
            + os.pathsep
            + env.get("PYTHONPATH", "")
        )
        self.process = subprocess.Popen(
            self.command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            env=env,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        stream = self.process.stdout
        events = self.events

        def read_events() -> None:
            try:
                for line in stream:
                    try:
                        events.put(json.loads(line))
                    except ValueError:
                        pass
            finally:
                try:
                    stream.close()
                except Exception:
                    pass
                events.put(
                    dict(done=False, error="Office preview worker exited.")
                )

        threading.Thread(
            target=read_events,
            name="MDIR-Office-PDF-Events",
            daemon=True,
        ).start()

    def render(
        self,
        source: Path,
        target: Path,
        *,
        cancel: Optional[threading.Event] = None,
        timeout: float = FOREGROUND_TIMEOUT,
        layout: bool = True,
    ) -> bool:
        cancel = cancel or threading.Event()
        deadline = time.monotonic() + timeout
        self.error = ""
        self.stage = "startup"
        kind = office_kind(source)
        if kind is None:
            self.error = "Unsupported Office preview extension."
            return False
        try:
            self.start()
            self.process.stdin.write(
                json.dumps(
                    dict(
                        source=str(Path(source).resolve()),
                        target=str(Path(target).resolve()),
                        kind=kind,
                        layout=bool(layout),
                    )
                )
                + "\n"
            )
            self.process.stdin.flush()
            while True:
                if cancel.is_set():
                    self.error = "cancelled"
                    break
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    self.error = (
                        f"Office preview timed out at {self.stage} "
                        f"({timeout:g}s)."
                    )
                    break
                try:
                    event = self.events.get(timeout=min(0.05, remaining))
                except queue.Empty:
                    continue
                if "office_pid" in event:
                    pid = int(event["office_pid"])
                    if pid not in self.handles:
                        self.handles[pid] = _PrivateOfficeHandle(pid, self.started)
                if "stage" in event:
                    self.stage = str(event["stage"])
                _diagnostic("worker", source=source, **event)
                if "done" in event:
                    if event["done"] and valid_pdf(target):
                        return True
                    self.error = event.get(
                        "error", "Office did not create a complete PDF."
                    )
                    break
        except Exception as exc:
            self.error = str(exc)
        _diagnostic(
            "render_failed",
            source=source,
            stage=self.stage,
            error=self.error,
        )
        # On cancellation/timeout/error discard the private worker and its
        # Office processes.  The next request starts a clean session.
        self.stop()
        return False

    def stop(self) -> None:
        process, self.process = self.process, None
        if process is not None:
            try:
                if process.poll() is None:
                    process.terminate()
                    process.wait(timeout=0.6)
            except Exception:
                try:
                    process.kill()
                    process.wait(timeout=0.6)
                except Exception:
                    pass
            try:
                if process.stdin:
                    process.stdin.close()
            except Exception:
                pass
        for handle in list(self.handles.values()):
            handle.close()
        self.handles.clear()
        self.events = None


def _find_libreoffice() -> Optional[str]:
    candidates = [
        shutil.which("soffice"),
        r"C:\Program Files\LibreOffice\program\soffice.exe",
        r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
    ]
    return next(
        (str(path) for path in candidates if path and Path(path).is_file()),
        None,
    )


def _libreoffice_render(
    source: Path,
    target: Path,
    *,
    cancel: Optional[threading.Event] = None,
    timeout: float = FALLBACK_TIMEOUT,
) -> bool:
    executable = _find_libreoffice()
    if not executable:
        return False
    cancel = cancel or threading.Event()
    with tempfile.TemporaryDirectory(prefix="mdir-office-pdf-lo-") as folder:
        root = Path(folder)
        process = subprocess.Popen(
            [
                executable,
                "-env:UserInstallation=" + (root / "profile").as_uri(),
                "--headless",
                "--convert-to",
                "pdf",
                "--outdir",
                str(root),
                str(Path(source).resolve()),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        try:
            deadline = time.monotonic() + timeout
            while process.poll() is None:
                if cancel.wait(0.05) or time.monotonic() >= deadline:
                    return False
            output = root / (Path(source).stem + ".pdf")
            if process.returncode == 0 and valid_pdf(output):
                shutil.copyfile(output, target)
                return True
            return False
        finally:
            if process.poll() is None:
                try:
                    if os.name == "nt":
                        subprocess.run(
                            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            timeout=3,
                            creationflags=getattr(
                                subprocess, "CREATE_NO_WINDOW", 0
                            ),
                        )
                    else:
                        process.kill()
                    process.wait(timeout=3)
                except Exception:
                    pass


_SESSION_LOCK = threading.Lock()
_SESSION: Optional[_PersistentOfficeCom] = None
_ACTIVE_LOCK = threading.Lock()
_ACTIVE_CANCELS: set[threading.Event] = set()


def _get_session() -> _PersistentOfficeCom:
    global _SESSION
    if _SESSION is None:
        _SESSION = _PersistentOfficeCom()
    return _SESSION


def cancel_office_pdf_preview() -> None:
    """Cancel active Office conversion(s) when Preview moves to another file."""
    with _ACTIVE_LOCK:
        active = tuple(_ACTIVE_CANCELS)
    for item in active:
        item.set()


def render_office_pdf_cached(
    source: Path,
    *,
    cancel: Optional[threading.Event] = None,
) -> OfficePdfResult:
    source = Path(source)
    started = time.monotonic()
    cancel = cancel or threading.Event()
    temporary: Optional[Path] = None
    kind = office_kind(source)
    if kind is None:
        return OfficePdfResult(
            source, None, False, "failed", 0.0,
            "Unsupported Office preview extension.",
        )

    try:
        if cancel.is_set():
            raise RuntimeError("cancelled")

        cached = office_pdf_cache_hit(source)
        if cached is not None:
            try:
                os.utime(cached, None)
            except OSError:
                pass
            return OfficePdfResult(
                source, cached, True, "cache", time.monotonic() - started
            )

        target = office_pdf_cache_path(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(
            target.stem + "." + uuid.uuid4().hex + ".tmp.pdf"
        )

        # Serialize COM use but keep the worker alive between files.  Recheck
        # the cache after waiting: another preview thread may have just made it.
        # Register queued work too, so a newer selection cancels requests
        # waiting behind the current Office conversion.
        with _ACTIVE_LOCK:
            _ACTIVE_CANCELS.add(cancel)
        with _SESSION_LOCK:
            if cancel.is_set():
                raise RuntimeError("cancelled")
            cached = office_pdf_cache_hit(source)
            if cached is not None:
                return OfficePdfResult(
                    source, cached, True, "cache", time.monotonic() - started
                )
            if cancel.is_set():
                raise RuntimeError("cancelled")

            session = _get_session()
            backend = {
                "excel": "Microsoft Excel",
                "word": "Microsoft Word",
                "powerpoint": "Microsoft PowerPoint",
            }[kind]
            ok = session.render(source, temporary, cancel=cancel)

            # Excel page setup can be the slowest COM stage on unusual sheets.
            # Match xViewer: one bounded retry using the workbook's own layout.
            if (
                not ok
                and not cancel.is_set()
                and kind == "excel"
                and session.stage == "page_setup"
            ):
                ok = session.render(
                    source,
                    temporary,
                    cancel=cancel,
                    timeout=FALLBACK_TIMEOUT,
                    layout=False,
                )

            if not ok and not cancel.is_set():
                backend = "LibreOffice"
                ok = _libreoffice_render(
                    source,
                    temporary,
                    cancel=cancel,
                )

        if cancel.is_set():
            raise RuntimeError("cancelled")
        if not ok or not valid_pdf(temporary):
            raise RuntimeError(
                session.error
                or "Microsoft Office or LibreOffice is required for PDF preview."
            )

        # Do not publish a PDF for an older version of a file that changed while
        # Office was rendering it.
        if target != office_pdf_cache_path(source):
            raise RuntimeError(
                "The document changed during preview; select it again."
            )
        os.replace(temporary, target)
        temporary = None
        prune_office_pdf_cache()
        elapsed = time.monotonic() - started
        _diagnostic(
            "complete",
            source=source,
            backend=backend,
            elapsed=elapsed,
        )
        return OfficePdfResult(source, target, False, backend, elapsed)

    except Exception as exc:
        elapsed = time.monotonic() - started
        _diagnostic("failed", source=source, error=str(exc), elapsed=elapsed)
        return OfficePdfResult(
            source, None, False, "failed", elapsed, str(exc)
        )
    finally:
        with _ACTIVE_LOCK:
            _ACTIVE_CANCELS.discard(cancel)
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass


def shutdown_office_pdf_preview() -> None:
    global _SESSION
    cancel_office_pdf_preview()
    with _SESSION_LOCK:
        session, _SESSION = _SESSION, None
        if session is not None:
            session.stop()


atexit.register(shutdown_office_pdf_preview)
