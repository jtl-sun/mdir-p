# Changelog

## 2.17.2

### Repository cleanup

- Removed old version-named launchers, build output, caches, and package
  metadata from the GitHub source tree.
- Replaced import-time widget monkey patching with explicit application class
  settings, so behavior no longer depends on import order.
- Consolidated the package version and moved current settings to
  `%USERPROFILE%\.mdir-p.json`; the old `.mdir18.json` file remains readable
  for a seamless upgrade.
- Pinned Textual to the tested 8.2.8 release and added Windows GitHub Actions
  validation.

## 2.17.1

### Selection improvements

- `Shift+Up` and `Shift+Down` now select correctly from the first key press.
- `Shift+Click` selects the complete range between the current anchor and the
  clicked row.
- `Shift+Home`, `Shift+End`, `Shift+Page Up`, and `Shift+Page Down` are
  supported.
- Fast right-button dragging interpolates all crossed rows so intermediate
  items are not skipped when mouse events arrive slowly.
- Holding a right-button drag at the top or bottom edge now scrolls the file
  list automatically and continues selecting rows on following pages.

### Filename display

- The Name column now displays the filename title without repeating the final
  extension.
- The Extension column remains immediately to the right and adds a three-cell
  visual gap for easier scanning.
- Directory names containing dots are preserved unchanged.

### Validation

- MDIR-P package self-check passed.
- All 12 automated tests passed with Textual 8.2.8.
- The `mdir_p-2.17.1-py3-none-any.whl` installation package built
  successfully.
