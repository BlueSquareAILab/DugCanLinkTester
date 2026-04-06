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

## 2026-04-05

- `DigCanLink` JSON 스트림을 새 기본 수신 포맷으로 추가
  - `protocol.py`에 `DigInputReport`, `DeviceResponse`, JSON 파싱 추가
  - 레거시 텍스트 파서는 `FDD6/FDD7`뿐 아니라 `FDD8/FDD9`도 지원하도록 확장
- `serial_receiver.py`를 확장해 JSON report / response 콜백도 전달하도록 변경
- CLI 수신기(`joystick_receiver.py`)가 JSON report / response를 함께 출력하도록 변경
- GUI를 `DigCanLink` 기준으로 확장
  - `dig_monitor_window.py` 추가
  - `LH/RH 조이스틱`, `AIN1~AIN4`, `DIN1~DIN7`, 장치 상태, 응답 로그 표시
  - `start`, `stop`, `about`, `input dump`, `input map` 명령 버튼 추가
  - 연결 직후 `about`, `start` 자동 전송
- 테스트 갱신:
  - JSON 파서 테스트 추가
  - GUI 스모크 테스트 갱신
  - `python -m unittest` 기준 23개 테스트 통과 확인
- GUI 방향성 표시를 보강
  - 축 그래프 우측에 `+ / Neutral / -` 방향 라벨을 추가
  - `X`, `AUX X`는 `Left/Right`, `Y`는 `Down/Back` / `Up/Forward` 기준으로 표시
  - 표기 기준은 문서의 `negative / positive / neutral` 의미를 그대로 따른다.
- 납품처 인수 기준으로 구조/문서를 재정리
  - README에 GUI와 별도로 `SerialReceiver`, `TextLineParser`, `parse_serial_line()`를 재사용 진입점으로 명시
  - `valid`, `age_ms`, `signed`, `AINx/DINx` 같은 실사용 핵심 필드 의미를 별도 표로 정리
  - `examples/simulator_receiver_minimal.py`를 추가해 외부 시뮬레이터 연동 기준 코드를 제공
  - 패키지 버전을 `0.2.2`로 갱신
- 축값 해석 보정
  - 실기기 로그 기준으로 `raw=0 + neutral=1`이 중립으로 반복되는 패턴을 반영해 `signed` 계산식을 보수적으로 수정
  - `neutral=0`, `positive only`, `negative only`인 경우 방향 비트를 우선 반영
  - 비트가 모호할 때만 기존 `raw-128` 방식으로 fallback
  - HID 매핑도 같은 규칙을 쓰도록 정렬
 - CAN 갱신 상태/디버깅 보강
   - `DigInputReport`가 `can_updated`, `joystick_updated`, `can_rx_idle_ms`, `joystick_rx_idle_ms`, frame count, `last_joystick_can_id`를 함께 파싱
   - GUI 상단 Device State에 CAN/Joystick 갱신 여부와 idle/counter를 직접 표시
   - 그래프 우측 `raw` 표시는 signed 역산이 아니라 실제 `raw` 값을 표시하도록 수정
   - 연결 세션마다 `logs/digcanlink_monitor_*.jsonl` 파일에 command / response / input_report 로그를 저장
   - Mega 자동 리셋 때문에 초기 `about/start`가 유실되는 문제를 막기 위해 연결 직후 약 `1.8초/2.1초` 지연 후 자동 전송하도록 수정
   - 패키지 버전을 `0.2.6`로 갱신
 - Device State 정상 상태 판독 기준을 문서화
   - `README.md`에 정상 상태 예시(`CAN=OK`, `CAN Update=RX`, `Joy Update=RX`, 낮은 idle, 증가하는 frame count`)를 추가
   - `0xCFDD7D1` 예시를 RH AUX (`PGN 0xFDD7`, `SA 0xD1`)로 해석하는 기준을 명시
   - `_forAI/readme.md`, `_forAI/memo.md`에도 동일한 판단 기준을 요약 기록
 - 주행페달 preview UI/프로토콜 추가
   - 굴착기 시뮬레이터 입력 기준으로 CAN 유닛을 `Joystick LH/RH + Travel Pedal LH/RH` 4슬롯으로 문서화
   - `DigInputReport`가 `pedal_updated`, `pedal_frame_count`, `pedal_rx_idle_ms`, `last_pedal_can_id`, `pedal.lh/rh` raw payload를 파싱
   - GUI에 `Travel Pedal LH/RH` 패널을 추가하고 `B0~B7` raw byte 막대를 표시
   - 페달 기대 SA는 `0xED`, `0xEE`로 두고, 실제 SA가 달라도 첫 2개 pedal source를 좌/우 슬롯에 반응시키는 정책을 문서화
   - 루트 `README.md`와 `_forAI` 문서에 굴착기 시뮬레이터 프로젝트 맥락을 기록
   - 패키지 버전을 `0.3.0`으로 갱신
 - 주행페달 문서 재확인 반영
   - `주행페달` 시트 기준 Source Address는 `0xED` 하나로 정리
   - Pin-Out 표의 `CAN1 & CAN2 channel internally connected for daisy chain` 문구를 근거로 단일 CAN 노드로 판단
   - Mapping 표 기준 `Axis 2 = Byte1/2`, `Axis 1 = Byte3/4`
   - GUI를 `Travel Pedal Unit` 단일 패널 + `Axis 2 (2-/2+)`, `Axis 1 (1-/1+)` 그래프로 변경
   - CLI/프로토콜 포맷도 `PEDU` 단일 유닛 기준으로 정리
   - 패키지 버전을 `0.3.1`으로 갱신
 - LH BTN2/Horn 진단 보강
   - 최근 로그 집계상 `LH b1/b3/b4`는 들어오고 `LH b2`만 0인 패턴을 확인
   - 문서상 LH `Button 2`는 `Horn`으로 표기됨을 README/_forAI에 반영
   - GUI에 `btn_raw=0x..` 표시를 추가하고 JSON `buttons.raw`를 함께 파싱하도록 변경
   - 패키지 버전을 `0.3.2`로 갱신
 - 2026-04-06 현장 판단 메모
   - 구현/문서 매핑은 정상으로 보고 있음
   - `LH BTN2/Horn`만 실기 신호가 안 들어오는 상태로 기록
   - 다음 점검 우선순위는 LH Horn 스위치, 하네스, 커넥터, 장치 설정
- 버튼 진단 UI/프로토콜 간소화
  - `btn_raw` 표시와 JSON `buttons.raw` 파싱 제거
  - 패키지 버전을 `0.3.3`로 갱신
- 테스터 런타임 정리
  - GUI의 시리얼 오픈 실패 `print()` 제거, 창 내부 상태/로그로 전환
  - `SerialReceiver`도 직접 콘솔 출력 대신 `on_open_failed` 콜백으로 정리
  - 패키지 버전을 `0.3.4`로 갱신
