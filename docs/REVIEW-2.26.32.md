# mDIR-P 2.26.32 검토 및 재빌드 기록

## 수정 이유

2.26.31에서 우클릭 MouseDown 직후부터 native pointer poller가 활성화되어 있었다. Windows Terminal의 pixel→cell 변환값과 Textual MouseDown row가 1~2행 다르게 계산되면, 실제 마우스가 정지해 있어도 `_toggle_drag_range_to()`가 그 차이를 drag range로 해석해 주변 행까지 선택/해제할 수 있었다.

## 수정 구조

- MouseDown: 클릭한 정확한 row 하나만 즉시 toggle.
- Drag Controller: right button hold 상태는 유지하지만 `drag_started=False`로 시작.
- Textual MouseMove 또는 native GetCursorPos에서 실제 cell 이동이 관찰된 뒤에만 drag를 arm.
- Textual origin과 native origin을 별도 보관해 좌표계 rounding 차이 자체가 drag를 시작시키지 않게 함.
- drag가 arm되기 전에는 hovered-row 처리와 edge auto-scroll 모두 금지.
- 실제 빠른 drag가 30 ms timer tick 전에 끝나면 MouseUp endpoint를 한 번 처리.

## 보존한 구조

2.26.19의 단일 30 ms Drag Controller, MouseMove coalescing, one-toggle-per-row, skipped-row filling, distance-based edge acceleration을 유지한다. 2.26.31의 Windows long-path Copy/Move 수정도 변경하지 않았다.

## 회귀 확인

- stationary right click + native row mismatch: clicked row만 선택.
- 같은 조건에서 clicked row 해제: 다른 row가 새로 선택되지 않음.
- 기존 continuous drag test는 explicit `drag_started=True` 상태로 controller의 연속 선택 기능을 계속 검증.
- Python compile 및 가능한 targeted tests를 실행하고 Windows Terminal에서 실제 mouse test를 추가 확인한다.
