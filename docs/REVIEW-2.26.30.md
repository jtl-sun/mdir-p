# mDIR-P 2.26.30 검토 및 재빌드 기록

## 기준과 범위

- 검토 기준: 사용자가 제공한 mDIR-P-2.26.29.zip 및 Development Handoff and Rebuild Guide.
- 원본 ZIP SHA256: `2c534fa2ace5ca52fb964226e1a26545117d5f64575cd40e3a8550d3b389d5d6`.
- Windows 저장소: https://github.com/jtl-sun/mdir-p
- 원본 보존을 위해 검토 수정본은 2.26.30으로 구분한다. Ubuntu 저장소는 이번 변경 대상에 포함하지 않는다.
- 첨부 문서는 개발 이력과 요구사항의 참고 자료이며, 구현 및 검사 결과와 구분한다.

## 유지한 업데이트

| 영역 | 동작 및 주요 소스 |
|---|---|
| 양쪽 패널 | Sh/Th 및 전체 선택·해제·반전이 각 패널에 독립 적용. `app.py`, `file_pane.py`, `thumbnail_app.py` |
| 선택 표시 | 디렉터리 글자색과 구별되는 청록색 배경 및 체크 표시 |
| 대량 선택 | 변경된 행 중심 갱신, 마우스 이동 이벤트 병합, 30ms 드래그 제어 및 가장자리 자동 스크롤 |
| 썸네일 | 가상화, 제한된 작업 수, 오른쪽 드래그 선택, 목록 전환과 선택 공유 |
| 키보드 | 활성 패널/대화상자에 따른 입력 전달. Ctrl+H, Ctrl+F3, 매크로, 작업공간 및 속성 회귀 검사 |
| 미리보기 | 이미지/PDF/텍스트 및 Office PDF 캐시. 별도 Office 작업 세션, 취소, 제한 시간, 대체 렌더러 |
| 삭제 | 일반 삭제 후 명시적 관리자 재시도, Windows Shell COM, 휴지통/10GiB 이상 개별 파일 정책 분리 |
| 최근 폴더 | 양쪽 경로 표시줄의 ▼, 공유 MRU 최대 40개, Alt+Down, 바깥 클릭 시 닫고 해당 조작 전달 |
| 설치 | Windows Terminal 전용 프로필, 스크롤바 및 여백 설정, 바로가기 설치 |

## 이번에 수정한 문제

1. 관리자 휴지통 삭제를 취소해도 다음 영구 삭제 묶음이 실행될 수 있었다. 취소 시 다음 묶음을 시작하지 않도록 수정했다.
2. 두 번째 관리자 삭제 묶음에서 오류가 나면 첫 묶음의 완료 결과를 잃었다. 완료 항목과 오류를 함께 반환한다.
3. Windows Shell에 전달하는 경로에서 링크를 해석하던 처리를 제거했다. 선택한 링크의 절대 경로를 그대로 전달한다.
4. Office 변환 잠금을 기다리는 요청도 취소 대상으로 등록한다. 취소된 대기 요청은 Office 작업을 시작하지 않는다.
5. 늦게 실행되는 시작 화면 정리 함수가 열린 대화상자의 포커스를 빼앗지 않도록 제한했다.
6. 최근 폴더 테스트는 시작 화면 제거와 메뉴 포커스 완료를 기다린다. Office 단위 테스트는 진단 로그를 격리하여 Windows 임시 폴더 파일 잠금 오류를 막는다.

## 검사와 재현

원본 전체 검사: 198개 중 실패 2개, 오류 1개. 최근 폴더 시작/포커스 시점과 테스트 로그 파일 잠금에서 발생했다. 수정 후에는 아래 전체 검사를 다시 실행하고 GitHub Actions에서 동일 검사를 통과한 커밋만 릴리즈한다. 실제 실행 결과는 해당 릴리즈 커밋의 Actions 기록을 기준으로 확인한다.

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -e ".[preview,dev]"
.venv\Scripts\python -m mdir --check
.venv\Scripts\python -m unittest discover -s tests -v
.venv\Scripts\python -m build
.venv\Scripts\python tools/package_release.py
```

`package_release.py`는 Git 저장소의 HEAD를 압축하므로 먼저 변경을 커밋해야 한다. ZIP만 풀어 실행한 폴더에는 Git 이력이 없으므로 GitHub 저장소를 복제하고 릴리즈 태그를 체크아웃하여 빌드한다. Python 3.12와 Textual 8.2.8을 사용한다. Office 충실도 미리보기에는 Microsoft Office 또는 LibreOffice가 필요하다. 의존성 전체는 `pyproject.toml`을 기준으로 설치한다.

`tests/test_review_regressions.py`는 관리자 삭제 취소·부분 완료·링크 경로 및 대기 중 Office 요청 취소를 검사한다. 실제 권한 상승이나 사용자 파일 삭제는 수행하지 않는다. 최근 폴더 테스트는 실제 Textual 이벤트 및 포커스를 검사한다. 나머지 테스트는 파일 작업, 키보드, 양쪽 패널, 대량 선택, 썸네일, 미리보기, 캐시, 설치 프로필 등을 포함한다.

## 수동 확인이 필요한 환경 의존 동작

자동 검사 통과가 다음 환경별 확인을 대신하지 않는다.

- 설치된 Excel/Word/PowerPoint의 실제 문서 페이지 배치와 Office 종료 처리.
- UAC 창의 전면 표시, 다른 Windows 계정/권한 및 실제 휴지통 동작. 테스트용 파일로만 확인한다.
- 실제 Windows Terminal의 화면 배율/다중 모니터에서 미리보기 위치와 빠른 마우스 드래그.
- 최근 폴더 메뉴를 빠르게 열고 닫은 뒤 다른 패널/버튼을 클릭하는 실사용 흐름.

## 배포 절차

변경 브랜치 → PR의 Windows 검사 통과 → main 병합 → main 검사 및 패키징 → `v2.26.30` 릴리즈. `.github/workflows/ci.yml`이 ZIP, wheel, 소스 배포본 및 SHA256SUMS를 생성한다. 이미 공개된 같은 버전의 자산은 덮어쓰지 않는다. 설치 시 실행 중인 mDIR을 닫고 ZIP을 풀어 `INSTALL_MDIR.bat`을 실행한다.

이 기록은 소스 코드의 대체물이 아니다. 동일 앱을 재현하려면 릴리즈 태그의 전체 소스, pyproject.toml, 설치 스크립트, 테스트 및 이 문서를 함께 보관한다. 다음 개발자는 이 문서의 수정 이유와 회귀 테스트를 유지하고 새로운 변경은 새 버전으로 배포한다.
