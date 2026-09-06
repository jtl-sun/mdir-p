"""Hide Azure Cloud Shell in an existing Windows Terminal JSON settings file."""
import argparse
import copy
import json
import os
from pathlib import Path
import tempfile


def updated_settings(settings):
    result = copy.deepcopy(settings)
    for profile in result.get("profiles", {}).get("list", []):
        if profile.get("source") == "Windows.Terminal.Azure" or profile.get("name") == "Azure Cloud Shell":
            profile["hidden"] = True
    sources = result.setdefault("disabledProfileSources", [])
    if "Windows.Terminal.Azure" not in sources:
        sources.append("Windows.Terminal.Azure")
    return result


def apply(path):
    original = path.read_bytes()
    # Reject unsupported JSONC safely, before writing a backup or settings.
    settings = json.loads(original.decode("utf-8-sig"))
    updated = updated_settings(settings)
    if settings == updated:
        return None
    payload = (json.dumps(updated, ensure_ascii=False, indent=4) + "\n").encode("utf-8")
    # Exclusive backup creation never overwrites an earlier backup.
    with tempfile.NamedTemporaryFile(prefix="settings.backup-", suffix=".json", dir=path.parent, delete=False) as backup:
        backup.write(original)
        backup_path = Path(backup.name)
    with tempfile.NamedTemporaryFile(prefix="settings.pending-", suffix=".json", dir=path.parent, delete=False) as pending:
        pending.write(payload)
        pending_path = Path(pending.name)
    try:
        if path.read_bytes() != original:
            raise RuntimeError("Settings changed during editing. Close the settings editor and retry.")
        os.replace(pending_path, path)
    finally:
        pending_path.unlink(missing_ok=True)
    return backup_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("settings", type=Path, help="Exact path to the active settings.json")
    args = parser.parse_args()
    try:
        backup = apply(args.settings)
    except (OSError, ValueError, TypeError, AttributeError, RuntimeError) as exc:
        parser.exit(1, f"Not applied: {exc}\nJSON comments/trailing commas are unsupported. Send the file for a targeted edit.\n")
    print(f"Applied. Original backup: {backup}" if backup else "Already configured; no changes.")
    print("Restart Windows Terminal. Ubuntu and other settings are preserved.")


if __name__ == "__main__":
    main()
