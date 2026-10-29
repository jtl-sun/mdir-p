from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from .advanced import advanced_data_dir


MAX_SHORTCUTS = 16
SHORTCUT_KINDS = {"folder", "file", "program", "web", "action", "command"}
CONFIG_ENVIRONMENT_VARIABLE = "MDIR_P_SHORTCUTS"
LEGACY_CONFIG_PATH = Path.home() / ".mdir-p-shortcuts.json"
CONFIG_DIRECTORY_NAME = "Config"
CONFIG_FILENAME = "shortcuts.json"


@dataclass(frozen=True)
class ShortcutDefinition:
    """One user-configurable item displayed in the top shortcut bar."""

    label: str
    kind: str
    target: str
    args: tuple[str, ...] = ()
    pane: str = "active"


DEFAULT_SHORTCUTS = (
    ShortcutDefinition("Home", "folder", "{home}"),
    ShortcutDefinition("MDIR-P", "folder", "{project}"),
    ShortcutDefinition("PowerShell", "action", "powershell_here"),
    ShortcutDefinition("Preview", "action", "toggle_preview"),
    ShortcutDefinition("AI", "action", "toggle_ai_terminal"),
    ShortcutDefinition("GitHub", "web", "https://github.com/jtl-sun/mdir-p"),
)


def shortcut_config_path() -> Path:
    """Return the per-user shortcut file, always outside the source tree."""
    configured = os.environ.get(CONFIG_ENVIRONMENT_VARIABLE, "").strip()
    if configured:
        return Path(os.path.expandvars(configured)).expanduser()
    return advanced_data_dir("mDIR-P") / CONFIG_DIRECTORY_NAME / CONFIG_FILENAME


def migrate_legacy_shortcut_config(
    destination: Path | None = None,
    legacy_path: Path | None = None,
) -> Path | None:
    """Copy a valid legacy shortcut JSON into the new private config location.

    The legacy file is intentionally kept as a backup. Migration never reads
    from the project/release directory and never writes personal links there.
    """
    target = destination or shortcut_config_path()
    source = legacy_path or LEGACY_CONFIG_PATH
    if target.exists() or not source.exists():
        return target if target.exists() else None
    try:
        values = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return None
    if not isinstance(values, list):
        return None
    parsed = parse_shortcuts(values)
    save_shortcuts(parsed, target)
    return target


def _definition_from_value(value: object) -> ShortcutDefinition | None:
    if not isinstance(value, dict):
        return None

    label = str(value.get("label", "")).strip()
    kind = str(value.get("type", value.get("kind", ""))).strip().lower()
    target = str(value.get("target", "")).strip()
    pane = str(value.get("pane", "active")).strip().lower()
    raw_args = value.get("args", [])

    if not label or kind not in SHORTCUT_KINDS or not target:
        return None
    if pane not in {"active", "left", "right"}:
        pane = "active"
    if not isinstance(raw_args, list):
        raw_args = []

    return ShortcutDefinition(
        label=label[:24],
        kind=kind,
        target=target,
        args=tuple(str(argument) for argument in raw_args),
        pane=pane,
    )


def parse_shortcuts(values: object) -> list[ShortcutDefinition]:
    """Validate untrusted JSON values and return a bounded shortcut list."""
    if not isinstance(values, list):
        return []
    parsed: list[ShortcutDefinition] = []
    for value in values:
        definition = _definition_from_value(value)
        if definition is not None:
            parsed.append(definition)
        if len(parsed) >= MAX_SHORTCUTS:
            break
    return parsed


def load_shortcuts(path: Path | None = None) -> list[ShortcutDefinition]:
    """Load private user shortcuts, or use safe built-in defaults."""
    config_path = path or shortcut_config_path()
    if path is None and not os.environ.get(CONFIG_ENVIRONMENT_VARIABLE, "").strip():
        migrate_legacy_shortcut_config(config_path, LEGACY_CONFIG_PATH)
    try:
        values = json.loads(config_path.read_text(encoding="utf-8"))
        if isinstance(values, list):
            return parse_shortcuts(values)
        return list(DEFAULT_SHORTCUTS)
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return list(DEFAULT_SHORTCUTS)


def _serializable(shortcuts: Iterable[ShortcutDefinition]) -> list[dict[str, object]]:
    values: list[dict[str, object]] = []
    for shortcut in shortcuts:
        value = asdict(shortcut)
        value["type"] = value.pop("kind")
        value["args"] = list(shortcut.args)
        values.append(value)
    return values


def ensure_shortcut_config(path: Path | None = None) -> Path:
    """Create an editable private shortcut file when one does not exist."""
    config_path = path or shortcut_config_path()
    if path is None and not os.environ.get(CONFIG_ENVIRONMENT_VARIABLE, "").strip():
        migrated = migrate_legacy_shortcut_config(config_path, LEGACY_CONFIG_PATH)
        if migrated is not None:
            return migrated
    if config_path.exists():
        return config_path
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        json.dumps(
            _serializable(DEFAULT_SHORTCUTS),
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return config_path


def save_shortcuts(
    shortcuts: Iterable[ShortcutDefinition],
    path: Path | None = None,
) -> Path:
    """Persist a validated shortcut list using an atomic file replacement."""
    config_path = path or shortcut_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = config_path.with_suffix(config_path.suffix + ".tmp")
    temporary_path.write_text(
        json.dumps(
            _serializable(tuple(shortcuts)[:MAX_SHORTCUTS]),
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    temporary_path.replace(config_path)
    return config_path


def expand_shortcut_text(
    value: str,
    *,
    current: Path,
    left: Path,
    right: Path,
    project: Path,
    selected: Path | None = None,
    left_selected: Path | None = None,
    right_selected: Path | None = None,
) -> str:
    """Expand MDIR placeholders and normal Windows environment variables."""
    replacements = {
        "{current}": str(current),
        "{left}": str(left),
        "{right}": str(right),
        "{selected}": str(selected or current),
        "{left_selected}": str(left_selected or left),
        "{right_selected}": str(right_selected or right),
        "{home}": str(Path.home()),
        "{project}": str(project),
    }
    expanded = value
    for token, replacement in replacements.items():
        expanded = expanded.replace(token, replacement)
    return os.path.expandvars(os.path.expanduser(expanded))
