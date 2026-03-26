# DugCanLinkTester 현재 계획

## 현재 기준

- Windows 배포 흐름은 `PyInstaller onedir + zip` 기준으로 정리한다.
- 최종 사용자 대상은 GUI 모니터이며, CLI는 개발/진단용으로 유지한다.
- 현재 통신 기준은 텍스트 시리얼 프로토콜이고, 바이너리 파서는 보존만 한다.

## 이번 단계에서 완료된 항목

- [x] `PacketParser` / `protocol` 회귀 테스트 추가
- [x] 텍스트 파서 테스트 추가
- [x] GUI offscreen 스모크 테스트 추가
- [x] CLI `--port` 명시 요구로 변경
- [x] PyInstaller spec 2종 추가
- [x] Windows 빌드 스크립트 추가
- [x] 루트 `README.md`를 텍스트 프로토콜 + 배포 절차 기준으로 정리
- [x] `_forAI` 문서 구조 재정리

## 현재 남은 확인 항목

- 실제 COM 장치 연결 상태에서 GUI/CLI 수신 카운트가 정상 증가하는지 확인
- `MonitorHID` 배포본 실행 시 `joy.cpl`에 장치가 생성되는지 확인
- Vortex Studio에서 HID 입력 소스로 정상 인식되는지 확인

## 보류 / 다음 단계

- 텍스트 프로토콜 운영을 안정화한 뒤 바이너리 패킷 전환 여부 재평가
- HID 기능은 실제 장치 인식 검증 전까지 기본 배포 기준에서 보수적으로 유지
