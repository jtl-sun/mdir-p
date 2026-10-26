"""Independent, non-modal transfer window; the file worker stays in mDIR."""
from __future__ import annotations
import json
import os
import queue
import subprocess
import sys
import threading
from dataclasses import asdict
from pathlib import Path


class BackgroundProgressWindow:
    def __init__(self, operation, source, destination):
        self.commands = queue.SimpleQueue()
        self.pending = queue.Queue(maxsize=1)
        self.closed = False
        flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        self.process = subprocess.Popen(
            [sys.executable, '-u', '-m', 'mdir.background_progress', '--window'],
            cwd=str(Path(__file__).resolve().parent.parent),
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, encoding='utf-8', creationflags=flags,
        )
        threading.Thread(target=self._write, daemon=True).start()
        threading.Thread(target=self._read, daemon=True).start()
        self._send(dict(operation=operation, source=source, destination=destination))

    def _send(self, value):
        if self.closed: return
        try: self.pending.get_nowait()
        except queue.Empty: pass
        try: self.pending.put_nowait(value)
        except queue.Full: pass

    def update(self, snapshot):
        self._send(asdict(snapshot))

    def _write(self):
        try:
            while True:
                value = self.pending.get()
                if value is None: break
                self.process.stdin.write(json.dumps(value) + '\n')
                self.process.stdin.flush()
        except (OSError, ValueError):
            pass
        finally:
            self.process.stdin.close()

    def _read(self):
        try:
            for line in self.process.stdout:
                command = line.strip()
                if command in {'pause', 'resume', 'foreground', 'cancel'}:
                    self.commands.put(command)
        except (OSError, ValueError):
            pass
        finally:
            self.process.stdout.close()

    def close(self):
        if self.closed: return
        self.closed = True
        try: self.pending.get_nowait()
        except queue.Empty: pass
        try: self.pending.put_nowait(None)
        except queue.Full: pass
        if self.process.poll() is None:
            self.process.terminate()
        def reap():
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
        threading.Thread(target=reap, daemon=True).start()


def run_window():
    import tkinter as tk
    from tkinter import ttk
    incoming = queue.SimpleQueue()
    def read():
        try:
            for line in sys.stdin:
                incoming.put(json.loads(line))
        finally:
            incoming.put(None)
    threading.Thread(target=read, daemon=True).start()
    root = tk.Tk()
    root.title('mDIR — Background')
    root.attributes('-topmost', True)
    try:
        root.iconbitmap(str(Path(__file__).resolve().parent / 'assets' / 'mdir.ico'))
    except tk.TclError:
        pass
    root.geometry('520x160+25+25')
    root.resizable(True, False)
    root.configure(bg='#252525')
    root.minsize(420, 160)
    name = tk.StringVar(value='Preparing…')
    metrics = tk.StringVar(value='0 B / ?')
    status = tk.StringVar(value='Running')
    tk.Label(root, textvariable=name, bg='#252525', fg='white', anchor='w').pack(fill='x', padx=10, pady=(8, 2))
    bar = ttk.Progressbar(root, maximum=100)
    bar.pack(fill='x', padx=10, pady=4)
    tk.Label(root, textvariable=metrics, bg='#252525', fg='white', anchor='w').pack(fill='x', padx=10)
    row = tk.Frame(root, bg='#252525'); row.pack(fill='x', padx=10, pady=8)
    tk.Label(row, textvariable=status, bg='#252525', fg='#b8d9ff').pack(side='left')
    paused = False
    def send(command):
        print(command, flush=True)
    def toggle():
        nonlocal paused
        paused = not paused
        send('pause' if paused else 'resume')
        pause.configure(text='Resume' if paused else 'Pause')
        status.set('Paused' if paused else 'Running')
    ttk.Button(row, text='Foreground', command=lambda: send('foreground')).pack(side='right', padx=3)
    ttk.Button(row, text='Cancel', command=lambda: send('cancel')).pack(side='right', padx=3)
    pause = ttk.Button(row, text='Pause', command=toggle); pause.pack(side='right', padx=3)
    root.protocol('WM_DELETE_WINDOW', lambda: send('foreground'))
    def size(value):
        for unit in ('B', 'KB', 'MB', 'GB', 'TB'):
            if value < 1024 or unit == 'TB': return f'{value:,.1f} {unit}'
            value /= 1024
    def tick():
        latest = {}
        while not incoming.empty():
            value = incoming.get()
            if value is None:
                root.destroy(); return
            latest.update(value)
        if latest:
            if 'operation' in latest: root.title('mDIR — ' + latest['operation'].title())
            if 'current_name' in latest:
                name.set(latest['current_name'])
                total = latest.get('total_bytes')
                done = latest.get('bytes_done', 0)
                items = latest.get('items_done', 0)
                count = latest.get('total_items')
                percent = done / total * 100 if total else (items / count * 100 if count else 0)
                bar['value'] = min(100, percent)
                eta = latest.get('eta_seconds')
                metrics.set(f'{percent:.0f}%   {size(done)} / {size(total) if total is not None else "?"}   {size(latest.get("bytes_per_second", 0))}/s   ETA: {int(eta)}s' if eta is not None else f'{percent:.0f}%   {size(done)} / {size(total) if total is not None else "?"}')
                status.set(f'{"Paused" if paused else "Running"}  {items}/{count if count is not None else "?"}')
        root.after(100, tick)
    tick()
    root.mainloop()


if __name__ == '__main__':
    run_window()
