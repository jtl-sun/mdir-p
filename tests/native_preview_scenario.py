"""Real Tcl/decoder integration, isolated so interpreter teardown is also tested."""
import os
from pathlib import Path
import queue
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PIL import Image
from mdir.preview.native import _NativePreviewWindow, NativePreviewController, PaneLayout
from mdir.thumbnail import ThumbnailItem
from mdir.thumbnail_native import ThumbnailManager, PaneState


def main(order):
    with tempfile.TemporaryDirectory() as directory:
        folder = Path(directory)
        paths = []
        for name, color in [('한글 (JQ).png', 'red'), ('second.jpg', 'blue')]:
            path = folder / name
            with Image.new('RGB', (180, 120), color) as image:
                image.save(path)
            paths.append(path)
        broken = folder / 'broken.png'
        broken.write_bytes(b'not an image')
        events = []
        manager = ThumbnailManager(SimpleNamespace(post_message=events.append), 1)
        def start_thumbnails():
            assert manager.start()
            state = PaneState('left', folder, ('folder', 1, 1, 1, True),
                (ThumbnailItem(paths[0], paths[0].name, False),), 0, frozenset(), 144,
                True, PaneLayout(0, 0, 50, 30, 100, 30),
                ('#202020', '#dddddd', '#7894a8', '#f1cd69'), suspended=True)
            manager.publish({'left': state})
            deadline = time.monotonic() + 4
            while not events and time.monotonic() < deadline:
                time.sleep(.02)
            assert events and not manager.error, manager.error

        failures = []
        commands = queue.Queue()
        # Only physical positioning/hooks are disabled: Tk, PhotoImage, decoder,
        # result queues, zoom, canvas, and teardown are the production code.
        with patch.object(_NativePreviewWindow, '_position_over_terminal'), \
             patch.object(_NativePreviewWindow, '_follow_terminal'), \
             patch.object(_NativePreviewWindow, '_install_mouse_wheel_hook'):
            if order != 'preview-first':
                start_thumbnails()
            if order == 'controller-lifecycle':
                import gc
                import weakref
                roots = []
                rendered = queue.Queue()
                original_init = _NativePreviewWindow.__init__
                original_render = _NativePreviewWindow._render
                def initialize(instance, *args, **kwargs):
                    original_init(instance, *args, **kwargs)
                    roots.append(weakref.ref(instance.root))
                def render(instance):
                    original_render(instance)
                    if instance.photo is not None:
                        rendered.put(instance.photo.tk is instance.root.tk)
                controller = NativePreviewController(SimpleNamespace())
                try:
                    with patch.object(_NativePreviewWindow, '__init__', initialize), \
                         patch.object(_NativePreviewWindow, '_render', render):
                        for _ in range(3):
                            assert controller.show(paths[0])
                            assert rendered.get(timeout=8)
                            assert controller.shutdown(), controller.last_error
                            gc.collect()
                            assert all(ref() is None for ref in roots), 'Destroyed Preview root retained'
                            while not rendered.empty():
                                rendered.get_nowait()
                finally:
                    assert controller.shutdown()
                    assert manager.shutdown()
                print('PASS', order)
                return
            window = _NativePreviewWindow(commands, terminal_hwnd=0,
                open_callback=lambda path: None, full_view_callback=lambda: None,
                files_callback=lambda: None)
            if order == 'preview-first':
                start_thumbnails()
            window.root.report_callback_exception = lambda kind, error, tb: failures.append(str(error))
            if order == 'modal-suspend':
                phase = [0]
                deadline = time.monotonic() + 8
                acknowledged = threading.Event()
                retained = []
                commands.put(('show', {'path': str(paths[0])}))
                commands.put(('suspend', acknowledged))
                def dialog_tick():
                    try:
                        assert not failures, failures
                        assert time.monotonic() < deadline, 'Dialog suspension timed out'
                        if phase[0] == 0 and acknowledged.is_set() and window.photo is not None:
                            assert not window.visible
                            assert window.path == paths[0]
                            window.native_size()
                            retained.extend([window.photo, window.scale, window._load_generation])
                            commands.put(('resume', None)); phase[0] = 1
                        elif phase[0] == 1 and window.visible:
                            assert window.photo is retained[0]
                            assert (window.scale, window._load_generation) == tuple(retained[1:])
                            acknowledged.clear()
                            commands.put(('suspend', acknowledged)); phase[0] = 2
                        elif phase[0] == 2 and acknowledged.is_set():
                            assert not window.visible
                            window._request_path(paths[1]); phase[0] = 3
                        elif phase[0] == 3 and window.photo is not None:
                            assert not window.visible, 'Decode reopened Preview over the dialog'
                            assert window.path == paths[1]
                            commands.put(('resume', None)); phase[0] = 4
                        elif phase[0] == 4 and window.visible:
                            retained.clear()
                            commands.put(('suspend', None))
                            commands.put(('hide', None))
                            commands.put(('show', {'path': str(paths[0])}))
                            phase[0] = 5
                        elif phase[0] == 5 and window.path == paths[0] and window.photo is not None:
                            assert window.visible, 'A closed suspended preview blocked the next show'
                            commands.put(('shutdown', None))
                            return
                        window.root.after(20, dialog_tick)
                    except BaseException as error:
                        retained.clear()
                        failures.append(str(error))
                        commands.put(('shutdown', None))
                window.root.after(0, dialog_tick)
                try:
                    window.run()
                finally:
                    assert manager.shutdown()
                assert not failures, failures
                assert phase[0] == 5
                print('PASS', order)
                return
            original_render = window._render
            injected = [order == 'render-failure']
            def render():
                if injected[0]:
                    injected[0] = False
                    raise RuntimeError('injected render failure')
                original_render()
            window._render = render
            steps = [(paths[0], order == 'render-failure'), (paths[1], False),
                     (broken, True), (paths[0], False)]
            if order == 'formats':
                import fitz
                from openpyxl import Workbook
                pdf = folder / 'sample.pdf'
                with fitz.open() as document:
                    document.new_page().insert_text((20, 30), 'mDIR preview')
                    document.save(pdf)
                sheet = folder / 'sample.xlsx'
                book = Workbook(); book.active.append(['mDIR', 123]); book.save(sheet); book.close()
                steps.extend([(pdf, False), (sheet, False)])
            remaining = list(steps)
            current = [None]
            deadline = [time.monotonic() + 8]
            rendered = []
            def tick():
                try:
                    assert not failures, failures
                    assert time.monotonic() < deadline[0], 'Preview stuck: ' + str(window.status_label.cget('text'))
                    if current[0] is None:
                        if not remaining:
                            # Closing thumbnails while Preview is alive must not
                            # invalidate Preview images or the next decode.
                            assert manager.shutdown()
                            window.native_size(); window.fit()
                            assert window.photo is not None
                            commands.put(('shutdown', None))
                            return
                        current[0] = remaining.pop(0)
                        if len(rendered) == 1:
                            # Superseded selections must release the decoder handshake.
                            window._request_path(broken)
                            window._request_path(paths[0])
                        window._request_path(current[0][0])
                        deadline[0] = time.monotonic() + 8
                    status = str(window.status_label.cget('text'))
                    if current[0][1]:
                        if 'Use Open' in status:
                            assert window.document_source is None
                            assert window.photo is None
                            current[0] = None
                    elif window.photo is not None and 'Zoom' in status:
                        assert window.path == current[0][0]
                        assert window.photo.tk is window.root.tk, 'Image belongs to a different Tcl interpreter'
                        assert window.canvas.type(window.canvas_image) == 'image'
                        assert str(window.photo) in window.root.tk.call('image', 'names')
                        window.native_size()
                        assert window.scale == 1.0
                        window._zoom_at(20, 20, 120)
                        window.fit()
                        rendered.append(window.path.name)
                        current[0] = None
                    window.root.after(20, tick)
                except BaseException as error:
                    failures.append(str(error))
                    commands.put(('shutdown', None))
            window.root.after(0, tick)
            try:
                window.run()
            finally:
                assert manager.shutdown()
            assert not failures, failures
            assert len(rendered) == sum(not fail for _, fail in steps), rendered
            assert not any(t.name in ('MDIR-Native-Image-Loader', 'mdir-thumbnail-ui') and t.is_alive()
                           for t in threading.enumerate())
            print('PASS', order, ascii(rendered))


if __name__ == '__main__':
    main(sys.argv[1])

