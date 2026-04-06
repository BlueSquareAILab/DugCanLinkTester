# DugCanLinkTester 현재 계획

## 현재 기준

- Windows 배포 흐름은 `PyInstaller onedir + zip` 기준으로 정리한다.
- 최종 사용자 대상은 GUI 모니터이며, CLI는 개발/진단용으로 유지한다.
- 현재 통신 기준은 `DigCanLink JSON 스트림`이며, 레거시 텍스트 프로토콜도 병행 지원한다.
- 바이너리 파서는 보존만 한다.

## 이번 단계에서 완료된 항목

- [x] `PacketParser` / `protocol` 회귀 테스트 추가
- [x] 텍스트 파서 테스트 추가
- [x] GUI offscreen 스모크 테스트 추가
- [x] CLI `--port` 명시 요구로 변경
- [x] PyInstaller spec 2종 추가
- [x] Windows 빌드 스크립트 추가
- [x] 루트 `README.md`를 텍스트 프로토콜 + 배포 절차 기준으로 정리
- [x] `_forAI` 문서 구조 재정리
- [x] `DigCanLink` JSON 파서 추가
- [x] GUI를 `LH/RH + AIN/DIN + start/stop + 응답 로그` 구조로 확장
- [x] CLI가 JSON report / response도 표시하도록 확장
- [x] 납품처 재사용 기준으로 `SerialReceiver` / `parse_serial_line()` 중심 구조를 README에 명시
- [x] 시뮬레이터 연동용 최소 예제 추가
- [x] 굴착기 시뮬레이터 기준 `Travel Pedal Unit` 패널과 `Axis 2 / Axis 1` 시각화 추가

## 현재 남은 확인 항목

- 실제 `DigCanLink` 장치 연결 시 GUI에서 `about/start` 자동 전송과 응답 로그가 정상 동작하는지 확인
- 실제 `DigCanLink` 장치 연결 시 `LH/RH`, `Travel Pedal Unit`, `AIN`, `DIN`이 UI에 의도대로 갱신되는지 확인
- 실제 COM 장치 연결 상태에서 GUI/CLI 수신 카운트가 정상 증가하는지 확인
- `PGN 0xFDDA` 실기기 캡처 기준으로 페달 byte 의미를 해석할 수 있는지 확인
- 납품처 시뮬레이터 쪽에서 `examples/simulator_receiver_minimal.py` 구조로 실제 연동 가능한지 확인
- `MonitorHID` 배포본 실행 시 `joy.cpl`에 장치가 생성되는지 확인
- Vortex Studio에서 HID 입력 소스로 정상 인식되는지 확인

## 보류 / 다음 단계

- `input dump` / `input map` 응답을 GUI 전용 구조화 패널로 더 세분화할지 검토
- JSON/텍스트 자동 감지 운영을 안정화한 뒤 바이너리 패킷 전환 여부 재평가
- HID 기능은 실제 장치 인식 검증 전까지 기본 배포 기준에서 보수적으로 유지
