## mDIR-P 2.26.15

- Independent left/right thumbnail views and hidden-file controls.
- Right-aligned Select All, Deselect All and Invert Selection buttons on both panes.
- Teal selected-item backgrounds, white text and check marks, distinct from folder colors.
- Right-button drag selection: toggle each crossed item once per gesture, including fast movement and edge scrolling.
- Preserve selection when switching back to the file list and reuse existing copy/move actions.

Also includes preview loading/lifecycle fixes, modal visibility fixes and Windows Terminal shortcut/focus fixes since 2.26.5.

### Windows
Close mDIR, extract `mDIR-P-2.26.15.zip`, run `INSTALL_MDIR.bat`, and reopen mDIR. Python 3.11 or newer is required.

Release assets are built from the merged commit only after CI tests and package checks pass. Checksums are in `SHA256SUMS.txt`.
