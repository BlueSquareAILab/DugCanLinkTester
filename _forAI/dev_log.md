## 2026-03-26 (3차)

- `_forAI` 문서를 현재 저장소 상태 기준으로 다시 정리했다.
  - `readme.md`에 현재 작업 기준(텍스트 프로토콜, GUI 배포 우선, 배포 2종, 테스트/산출물 현황)을 반영
  - 문서 역할을 `현재 상태 / 계획 / 로그 / 메모`로 다시 구분
- 저장소 상태를 다시 검증했다.
  - `uv run python -m unittest discover tests -v` 실행 결과 18개 테스트 통과
  - `release/` 폴더에 `DugCanLinkTester-MonitorOnly-win64.zip`, `DugCanLinkTester-MonitorHID-win64.zip` 산출물 존재 확인
- 현재 기준 정리:
  - 실제 운영 기준은 텍스트 시리얼 프로토콜
  - GUI 모니터가 주 배포 대상이고 CLI는 개발/진단용
  - 바이너리 `PacketParser`는 향후 전환 가능성을 위해 유지

## 2026-03-26 (2차)

- 시리얼 프로토콜을 바이너리 → 텍스트로 전환:
  - `protocol.py`에 `parse_text_line()` 추가 (정규식 기반 텍스트 파싱)
  - `serial_receiver.py`에 `TextLineParser` 클래스 추가
  - `SerialReceiver`, `SerialReaderThread`가 `TextLineParser` 사용하도록 변경
  - 기존 `PacketParser`(바이너리)는 향후 전환용으로 보존
- 텍스트 파싱 테스트 8개 추가 (`tests/test_text_parser.py`)
- 전체 18개 테스트 통과 확인
- README 전면 수정: 텍스트 프로토콜 기준, HID 보류 반영
- CAN_Joystick_Sample 펌웨어와 호환성 검증 완료

## 2026-03-26

- 저장소 기준 검증 결과:
  - 자동 테스트 파일은 없었고 `unittest discover` 결과는 `0 tests`
  - 패킷 파서, 모듈 import, GUI offscreen 생성은 수동 스모크 기준 정상
- `pyside6-deploy --dry-run main.py`는 현재 프로젝트 루트 내부 `.venv`의 QML 파일 탐색 문제로 실패했다.
- 배포 전략을 `Windows + PyInstaller onedir + zip 2종(MonitorOnly / MonitorHID)`으로 고정했다.
- 이번 단계에서 적용한 작업:
  - `PacketParser`, `protocol`, GUI 스모크 테스트 추가
  - CLI `--port` 명시 요구로 변경
  - PyInstaller spec 2종과 PowerShell 배포 스크립트 추가
  - README에 빌드 절차와 산출물 이름 반영
