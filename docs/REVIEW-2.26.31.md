# mDIR-P 2.26.31 long-path Copy/Move review

## Problem

Deep Windows trees (notably Unity `Library/PackageCache`) could copy successfully from the source yet fail inside mDIR's safe staging directory because the staging name repeated the full target name plus a UUID, pushing nested paths past the classic Windows path limit.

## Changes

- Windows file-operation roots are converted to extended-length paths before recursive copy/move.
- UNC roots use the `\\?\UNC\...` form.
- Transactional staging/backup siblings use short random names while remaining on the same destination volume.
- `copy2` gets two short retries only for WinError 2/3 and only if the source still exists.
- No file is silently skipped if it disappears during a live-project copy.
- Existing progress throttling remains unchanged.

## Safety preserved

Copy still completes into a hidden sibling before publish; overwrite still backs up the old target and rolls it back if publish fails. Directory-into-self protection and explicit overwrite confirmation are unchanged.

## Manual Windows check

Copy a deep Unity project tree between two drives, including `Library/PackageCache`, then compare source/destination counts and open the project. Repeat with overwrite enabled on a disposable copy.
