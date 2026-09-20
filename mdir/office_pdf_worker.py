"""Private persistent Microsoft Office COM host used for PDF preview conversion.

The worker is intentionally isolated from mDIR's UI process.  It uses DispatchEx
so it never attaches to the user's interactive Excel, Word, or PowerPoint session.
"""
from __future__ import annotations

import json
import sys
import time


def emit(**event) -> None:
    print(json.dumps(event, ensure_ascii=True), flush=True)


def _excel_configure_sheet(app, sheet) -> None:
    # Match xViewer's fast preview layout: keep page orientation/margins but fit
    # each visible sheet into one preview page when Excel can do so quickly.
    if sheet.Visible != -1:
        return
    try:
        app.PrintCommunication = False
        setup = sheet.PageSetup
        setup.PrintArea = ""
        setup.Zoom = False
        setup.FitToPagesWide = 1
        setup.FitToPagesTall = 1
    finally:
        app.PrintCommunication = True


def main() -> int:
    excel = None
    word = None
    powerpoint = None
    com = None
    try:
        import pythoncom
        import win32com.client
        import win32process

        com = pythoncom
        com.CoInitialize()

        for line in sys.stdin:
            job = json.loads(line)
            kind = str(job.get("kind", "")).lower()
            source = job["source"]
            target = job["target"]
            started = time.monotonic()
            stage = "startup"
            document = None

            def progress(name: str) -> None:
                nonlocal stage
                stage = name
                emit(stage=name, kind=kind, elapsed=time.monotonic() - started)

            try:
                if kind == "excel":
                    if excel is None:
                        progress("startup")
                        excel = win32com.client.DispatchEx("Excel.Application")
                        try:
                            pid = win32process.GetWindowThreadProcessId(excel.Hwnd)[1]
                            emit(office_pid=pid, app="excel")
                        except Exception:
                            pass
                        excel.Visible = False
                        excel.DisplayAlerts = False
                        excel.EnableEvents = False
                        excel.ScreenUpdating = False
                        excel.AskToUpdateLinks = False
                        excel.AutomationSecurity = 3

                    progress("open")
                    document = excel.Workbooks.Open(
                        source,
                        UpdateLinks=0,
                        ReadOnly=True,
                        Password="",
                        WriteResPassword="",
                        IgnoreReadOnlyRecommended=True,
                        Notify=False,
                        AddToMru=False,
                    )
                    try:
                        excel.Calculation = -4135  # xlCalculationManual
                        excel.CalculateBeforeSave = False
                    except Exception:
                        pass

                    if job.get("layout", True):
                        progress("page_setup")
                        for sheet in document.Worksheets:
                            try:
                                _excel_configure_sheet(excel, sheet)
                            except Exception as exc:
                                emit(warning="Page setup: " + str(exc))

                    progress("export")
                    # xlTypePDF=0, xlQualityStandard=0, IgnorePrintAreas=True.
                    document.ExportAsFixedFormat(
                        0,
                        target,
                        0,
                        False,
                        True,
                        com.Missing,
                        com.Missing,
                        False,
                    )

                elif kind == "word":
                    if word is None:
                        progress("startup")
                        word = win32com.client.DispatchEx("Word.Application")
                        try:
                            pid = win32process.GetWindowThreadProcessId(word.Hwnd)[1]
                            emit(office_pid=pid, app="word")
                        except Exception:
                            pass
                        word.Visible = False
                        word.DisplayAlerts = 0
                        try:
                            word.ScreenUpdating = False
                        except Exception:
                            pass
                        try:
                            word.AutomationSecurity = 3
                        except Exception:
                            pass

                    progress("open")
                    document = word.Documents.Open(
                        source,
                        ConfirmConversions=False,
                        ReadOnly=True,
                        AddToRecentFiles=False,
                        Visible=False,
                        OpenAndRepair=False,
                        NoEncodingDialog=True,
                    )
                    progress("export")
                    # wdExportFormatPDF = 17.  The short signature is the most
                    # compatible across supported Word releases.
                    document.ExportAsFixedFormat(target, 17)
                elif kind == "powerpoint":
                    if powerpoint is None:
                        progress("startup")
                        powerpoint = win32com.client.DispatchEx(
                            "PowerPoint.Application"
                        )
                        try:
                            hwnd = int(
                                getattr(
                                    powerpoint,
                                    "HWND",
                                    getattr(powerpoint, "Hwnd", 0),
                                )
                            )
                            if hwnd:
                                pid = win32process.GetWindowThreadProcessId(hwnd)[1]
                                emit(office_pid=pid, app="powerpoint")
                        except Exception:
                            pass
                        try:
                            powerpoint.DisplayAlerts = 1  # ppAlertsNone
                        except Exception:
                            pass
                        try:
                            powerpoint.AutomationSecurity = 3
                        except Exception:
                            pass

                    progress("open")
                    # ReadOnly=-1 (msoTrue), Untitled=0 and WithWindow=0 keep
                    # the user's presentation untouched and avoid a visible
                    # document window while the private COM host stays warm.
                    document = powerpoint.Presentations.Open(
                        source,
                        ReadOnly=-1,
                        Untitled=0,
                        WithWindow=0,
                    )
                    progress("export")
                    # ppFixedFormatTypePDF = 2.  PowerPoint's own exporter
                    # preserves slide size, fonts, images and master layout.
                    document.ExportAsFixedFormat(target, 2)
                else:
                    raise RuntimeError(f"Unsupported Office preview kind: {kind}")

                progress("close")
                if kind == "powerpoint":
                    document.Close()
                else:
                    document.Close(False)
                document = None
                emit(done=True, kind=kind, elapsed=time.monotonic() - started)

            except Exception as exc:
                # Report before cleanup; Office Close/Quit can itself hang.  A
                # failed job ends this worker so the supervisor can kill only
                # the private Office process and start from a clean state.
                emit(
                    done=False,
                    kind=kind,
                    stage=stage,
                    error=str(exc),
                    elapsed=time.monotonic() - started,
                )
                return 1
            finally:
                if document is not None:
                    try:
                        if kind == "powerpoint":
                            document.Close()
                        else:
                            document.Close(False)
                    except Exception:
                        pass

    except Exception as exc:
        emit(done=False, stage="startup", error=str(exc))
        return 1
    finally:
        if excel is not None:
            try:
                excel.Quit()
            except Exception:
                pass
        if word is not None:
            try:
                word.Quit()
            except Exception:
                pass
        if powerpoint is not None:
            try:
                powerpoint.Quit()
            except Exception:
                pass
        if com is not None:
            com.CoUninitialize()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
