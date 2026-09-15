"""File-pane shortcut routing shared by native Windows input and Textual."""
from dataclasses import dataclass
from .keymap import KEY_DEFINITIONS, normalize_shortcut
from .preview.hotkey import PreviewHotkey
from textual.message import Message


MODIFIERS = {0xA2: 'ctrl', 0xA3: 'ctrl', 0xA0: 'shift', 0xA1: 'shift',
             0xA4: 'alt', 0xA5: 'alt', 0x5B: 'super', 0x5C: 'super'}
NAMED_KEYS = {'backspace': 8, 'tab': 9, 'enter': 13, 'escape': 27, 'space': 32,
              'pageup': 33, 'pagedown': 34, 'end': 35, 'home': 36, 'left': 37,
              'up': 38, 'right': 39, 'down': 40, 'insert': 45, 'delete': 46}


def shortcut_routes(overrides):
    routes = {}
    for definition in KEY_DEFINITIONS:
        key = normalize_shortcut(overrides.get(definition.binding_id, definition.default_key))
        params = (definition.default_key,) if definition.action == 'thumbnail_navigate' else ()
        routes[key] = (definition.action, params)
    return routes


def key_signature(key):
    *modifiers, base = key.split('+')
    if base in NAMED_KEYS:
        vk = NAMED_KEYS[base]
    elif base.startswith('f') and base[1:].isdigit():
        vk = 0x70 + int(base[1:]) - 1
    elif len(base) == 1 and base.isascii() and base.isalnum():
        vk = ord(base.upper())
    else:
        raise ValueError(f'Unsupported native shortcut: {key}')
    return vk, frozenset(modifiers)


@dataclass(frozen=True)
class KeyCapture:
    consume: bool = False
    key: str | None = None
    epoch: int = 0


class ShortcutKeyState:
    """Only transient pressed-key state; never store input text or history."""
    def __init__(self):
        self.modifiers = set()
        self.down = set()
        self.captured = set()
        self.config = (0, {})

    def configure(self, epoch, routes):
        mapping = {}
        for key, (action, _) in routes.items():
            repeat = action in {'thumbnail_navigate', 'mark', 'parent'} or action.startswith('shift_select_')
            mapping[key_signature(key)] = (key, repeat)
        self.config = epoch, mapping  # Atomic snapshot for the keyboard thread.

    def feed(self, key, down, foreground):
        if key in MODIFIERS:
            self.modifiers.add(key) if down else self.modifiers.discard(key)
            return KeyCapture()
        was_down = key in self.down
        if not down:
            self.down.discard(key)
            consumed = key in self.captured
            self.captured.discard(key)
            return KeyCapture(consumed)
        self.down.add(key)
        epoch, mapping = self.config
        binding = mapping.get((key, frozenset(MODIFIERS[k] for k in self.modifiers)))
        if foreground and binding and (not was_down or key in self.captured):
            self.captured.add(key)
            return KeyCapture(True, binding[0] if not was_down or binding[1] else None, epoch)
        return KeyCapture(key in self.captured)


class NativeShortcut(Message):
    def __init__(self, key, epoch):
        super().__init__()
        self.key, self.epoch = key, epoch


class NativeShortcuts(PreviewHotkey):
    """Consume registered chords only in the active mDIR file-pane context."""
    def __init__(self, terminal_hwnd, notify):
        super().__init__(terminal_hwnd, notify)
        self.matcher = ShortcutKeyState()

    def configure(self, epoch, routes):
        self.matcher.configure(epoch, routes)
