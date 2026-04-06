# DugCanLinkTester

`DigCanLink`와 `CAN_Joystick_Sample`의 시리얼 출력을 PC에서 모니터링하고, 외부 시뮬레이터 연동 기준 코드로 재사용하기 위한 Python 도구입니다.

현재는 `DigCanLink`의 JSON 스트림(`input_report`, 명령 응답)을 기본 대상으로 하며, 기존 `CAN_Joystick_Sample`의 텍스트 출력도 계속 지원합니다. 이 저장소는 `DugSimulator` 내 굴착기(포크레인) 시뮬레이터 연동 프로젝트의 모니터/디버그 도구 역할을 합니다.

## 1. 전체 구성

```text
DigCanLink / CAN_Joystick_Sample
  → Serial Output (115200 bps)
     - DigCanLink: JSON input_report + JSON command response
     - Legacy Sample: text joystick lines
  → DugCanLinkTester
     → CLI Receiver  (joystick-receiver)
     → PySide6 GUI Monitor  (joystick-monitor)
```

## 2. 프로젝트 구성

```text
DugCanLinkTester/
├─ DugCanLinker/
│  ├─ protocol.py              # 데이터 모델, DigCanLink JSON/legacy 파싱, 포맷팅
│  ├─ serial_receiver.py       # TextLineParser + SerialReceiver (시리얼 수신)
│  ├─ joystick_receiver.py     # CLI 수신기
│  ├─ dig_monitor_window.py    # 메인 GUI 윈도우/위젯
│  ├─ joystick_monitor.py      # GUI 실행 엔트리
│  └─ vortex_hid.py            # Xbox 가상 패드 출력 (HID, 보류)
├─ examples/
│  └─ simulator_receiver_minimal.py  # 납품처/시뮬레이터 연동 참고 예제
├─ tests/                      # 회귀 테스트 (unittest)
├─ packaging/                  # PyInstaller spec 파일
├─ tools/                      # Windows 배포 빌드 스크립트
├─ main.py                     # GUI 모니터 실행 엔트리
├─ pyproject.toml              # 패키지/의존성 정의
└─ README.md
```

## 3. 실행 환경

요구 사항:

- Python 3.11 이상
- [uv](https://docs.astral.sh/uv/) 패키지 매니저
- Arduino 장치 연결 (`DigCanLink` 또는 `CAN_Joystick_Sample`)
- 기본 보레이트 `115200`

의존성:

- `PySide6 >= 6.6`
- `pyserial >= 3.5`

설치:

```bash
uv sync
```

## 4. 빠른 시작

### GUI 모니터

```bash
uv run joystick-monitor --port COM3
```

포트를 지정하지 않으면 GUI에서 포트를 선택할 수 있습니다:

```bash
uv run joystick-monitor
```

### CLI 수신기

```bash
uv run joystick-receiver --port COM3
```

CLI는 `--port`를 반드시 지정해야 합니다.

출력 예:

```text
Listening on COM3 @ 115200bps...
[     1] RESP  {"result":"ok","version":"1.7.4","system_version":5,"board":"Mega2560",...}
[     2] REPORT stream=ON can=OK upd=Y joy_upd=Y ped_upd=Y last=0xCFDD7D1 joy_last=0xCFDD7D1 ped_last=0xCFDDAED idle=3ms joy_idle=3ms ped_idle=5ms cnt=21423 joy_cnt=21423 ped_cnt=120 LH[sa=0xD0 main=Y X=+180 Y=  +1 aux=Y X=  +0] RH[sa=0xD1 main=Y X=  +0 Y=  +0 aux=Y X=  +0] PEDU[sa=0xED age=5ms A2=  +2 A1=  +4 data=01 02 03 04 05 06 07 08] AIN[AIN1=321 AIN2=322 AIN3=323 AIN4=324] DIN[-]
```

## 5. 납품처 / 시뮬레이터 적용 기준

### 어떤 구조를 기준으로 응용하면 되는가

GUI는 사람용 모니터 도구이고, 외부 시뮬레이터 연동은 아래 레이어를 기준으로 잡는 것을 권장합니다.

| 용도 | 권장 진입점 | 비고 |
|------|------|------|
| 자체 시리얼 루프가 이미 있을 때 | `parse_serial_line()` | 한 줄씩 직접 파싱 |
| 바이트 단위 시리얼 입력 처리까지 같이 쓸 때 | `TextLineParser` | JSON/legacy 자동 판별 |
| 가장 쉽게 붙일 때 | `SerialReceiver` | 콜백 기반, 실사용 권장 |
| 수신 데이터 모델 | `DigInputReport`, `DeviceResponse` | GUI/CLI와 동일한 구조 |
| 운영자 확인용 | `joystick-monitor` | UI는 참고/검증용 |

즉, 납품처가 별도 시뮬레이터를 만들거나 붙일 때는 GUI를 긁어 쓰는 구조가 아니라 `SerialReceiver` 또는 `parse_serial_line()`을 직접 재사용하는 구조가 가장 안전합니다.

### 권장 적용 순서

1. 장치 연결 후 `about`으로 장치 상태와 버전을 확인합니다.
2. 필요하면 `start`를 보내 주기 출력이 활성화된 상태를 보장합니다.
3. 이후 `input_report`만 소비해서 시뮬레이터 입력 상태를 갱신합니다.
4. 조이스틱은 `valid`가 `true`일 때만 반영하고, `age_ms`로 stale 여부를 판단합니다.
5. `AINx`, `DINx`는 현재 물리 채널명 기준이므로, 시스템 의미 이름은 상위 시뮬레이터에서 매핑합니다.

### 응용 시 반드시 봐야 하는 필드

| 필드 | 의미 | 권장 사용 |
|------|------|------|
| `main.valid`, `aux.valid` | 해당 축 데이터가 최근 프레임 기준 유효한지 | `false`면 입력 미반영 |
| `age_ms` | 마지막 유효 프레임 이후 경과 시간 | timeout / stale 판단 |
| `raw` | 장치 원값 `0..255` | 원문 기록이 필요할 때 |
| `signed` | 방향 비트를 우선 반영한 파생값 | `neutral=0`, `positive=+raw`, `negative=-raw`, 모호할 때만 `raw-128` fallback |
| `neg`, `pos`, `neu` | 문서 정의 2-bit 방향 상태 | 방향/중립 판정 보조 |
| `can_ready` | CAN 컨트롤러 초기화 상태 | 장치 health 체크 |
| `can_updated` | 직전 리포트 이후 아무 CAN 프레임이 들어왔는지 | 버스 전체 수신 여부 확인 |
| `joystick_updated` | 직전 리포트 이후 LH/RH 조이스틱 프레임이 들어왔는지 | 실제 조이스틱 입력 갱신 여부 확인 |
| `can_rx_idle_ms` | 마지막 CAN 수신 이후 경과 시간 | 버스 정지 여부 판단 |
| `joystick_rx_idle_ms` | 마지막 조이스틱 CAN 수신 이후 경과 시간 | 조이스틱 stale 판단 |
| `can_frame_count`, `joystick_frame_count` | 누적 수신 카운트 | 장시간 디버그/로그 분석 |
| `last_can_id` | 최근 수신 CAN ID | 디버그용 |
| `last_joystick_can_id` | 최근 수신 조이스틱 CAN ID | 조이스틱 수신 경로 확인 |
| `pedal_updated` | 직전 리포트 이후 페달 CAN 프레임이 들어왔는지 | 페달 수신 여부 확인 |
| `pedal_rx_idle_ms` | 마지막 페달 CAN 수신 이후 경과 시간 | 페달 stale 판단 |
| `pedal_frame_count` | 누적 페달 CAN 프레임 수 | 장시간 디버그/로그 분석 |
| `last_pedal_can_id` | 최근 수신 페달 CAN ID | 페달 수신 경로 확인 |
| `pedal.lh`, `pedal.rh` | wire-format 호환용 raw pedal slot | 현재는 값이 들어온 slot을 단일 Travel Pedal unit으로 해석 |
| `primary_pedal.axis_2`, `primary_pedal.axis_1` | 주행페달 축 2 / 축 1 해석값 | `2-/2+`, `1-/1+` 반응을 직관적으로 확인 |
| `AINx`, `DINx` | 인터페이스 보드 물리 채널 | 상위 의미 매핑 전 기본 키 |

### Device State 정상 상태 예시

다음은 GUI 상단 `Device State`가 정상 수신 중일 때의 대표 예시입니다.

| 항목 | 예시 값 | 정상 상태 해석 |
|------|------|------|
| `Device` | `DigLink-001` | 장치 ID가 정상 응답으로 들어옴 |
| `Version` | `1.6.0 / sys 5` | 펌웨어/시스템 버전 응답 정상 |
| `Protocol` | `digcanlink_json` | 현재 수신 포맷이 DigCanLink JSON임 |
| `Streaming` | `ON` | 자동 `input_report` 출력 중 |
| `Interval` | `100 ms` | 현재 자동 출력 주기 |
| `CAN` | `OK` | MCP2515 초기화 성공 |
| `CAN Update` | `RX` | 직전 리포트 구간에 CAN 프레임이 실제로 들어옴 |
| `Joy Update` | `RX` | 직전 리포트 구간에 조이스틱 프레임도 들어옴 |
| `Pedal Update` | `RX` | 직전 리포트 구간에 페달 preview 프레임도 들어옴 |
| `CAN Idle` | `3 ms` | 마지막 CAN 수신이 매우 최근이라 버스가 살아 있음 |
| `Joy Idle` | `3 ms` | 마지막 조이스틱 수신도 매우 최근임 |
| `Pedal Idle` | `5 ms` | 마지막 페달 수신도 매우 최근임 |
| `CAN Frames` | `21423` | 누적 CAN 프레임 수. 정상 상태에서는 계속 증가해야 함 |
| `Joy Frames` | `21423` | 누적 조이스틱 프레임 수. 정상 상태에서는 계속 증가해야 함 |
| `Pedal Frames` | `120` | 누적 페달 CAN 프레임 수. 페달 연결 후에는 계속 증가해야 함 |
| `Last CAN ID` | `0xCFDD7D1` | 최근 버스에서 받은 마지막 CAN ID |
| `Last Joy CAN` | `0xCFDD7D1` | 최근 받은 조이스틱 프레임 ID |
| `Last Pedal CAN` | `0xCFDDAED` | 최근 받은 페달 preview 프레임 ID |

추가 해석:

- `CAN Frames`와 `Joy Frames`가 둘 다 계속 증가하면 버스와 조이스틱 수신이 모두 살아 있는 상태입니다.
- `Pedal Frames`도 같이 증가하면 페달 CAN preview 수신도 살아 있는 상태입니다.
- `CAN Idle`, `Joy Idle`이 `100 ms`보다 충분히 작게 유지되면 현재 주기 안에서 계속 갱신 중으로 보면 됩니다.
- `Pedal Idle`도 `100 ms`보다 충분히 작게 유지되면 페달 preview가 계속 갱신 중입니다.
- `Last CAN ID`와 `Last Joy CAN`이 같으면, 최근 버스 프레임 자체가 조이스틱 프레임이었다는 뜻입니다.
- `0xCFDD7D1`은 RH AUX 조이스틱 프레임(`PGN 0xFDD7`, `SA 0xD1`)입니다.
- `CAN Frames`는 증가하는데 `Joy Frames`가 멈추면, 다른 CAN 트래픽만 있고 조이스틱 갱신은 끊긴 상태입니다.

## CAN 유닛 구성

문서의 `주행페달` 시트를 다시 확인한 결과, 물리 CAN 노드와 시뮬레이터 논리 입력을 구분해서 보는 편이 맞습니다.

- 물리 CAN 노드 3개
- `Joystick LH`
- `Joystick RH`
- `Travel Pedal` (`SA=0xED`)

- 논리 입력 그룹 4개
- `Joystick LH`
- `Joystick RH`
- `Travel Pedal Axis 2`
- `Travel Pedal Axis 1`

조이스틱 2대는 현재 문서 기준 PGN 해석이 완료되어 있고, 주행페달은 `PGN 0xFDDA`, `SA=0xED` 단일 노드 안에 `Axis 2`와 `Axis 1`이 함께 들어오는 구조로 보는 쪽이 문서와 로그에 맞습니다. GUI와 로그는 이 raw payload를 그대로 보존하면서 `Axis 2 (2-/2+)`, `Axis 1 (1-/1+)`로 같이 보여줍니다.

### 최소 연동 예제

아래 예제는 납품처가 가장 빨리 응용할 수 있는 기준 코드입니다.

```bash
uv run python .\examples\simulator_receiver_minimal.py --port COM3
```

이 스크립트는 `about`, `start`를 자동 전송하고, 표준 출력으로 정규화된 JSON 라인을 뿌립니다. 실제 시뮬레이터에서는 `print()` 대신 자체 API 호출로 바꾸면 됩니다.

예제 파일:

- `examples/simulator_receiver_minimal.py`

## 6. 지원 프로토콜

### DigCanLink JSON 스트림

`DigCanLink`는 기본적으로 100ms 주기의 `input_report`를 출력하며, `about`, `start`, `stop`, `input dump`, `input map` 같은 명령 응답도 JSON으로 반환합니다.

예시:

```json
{"type":"input_report","interval_ms":100,"streaming":true,"data":{"can_ready":true,"can_updated":true,"joystick_updated":true,"pedal_updated":true,"can_frame_count":42,"joystick_frame_count":12,"pedal_frame_count":7,"can_rx_idle_ms":8,"joystick_rx_idle_ms":6,"pedal_rx_idle_ms":9,"last_can_id":217962449,"last_joystick_can_id":217962704,"last_pedal_can_id":217963245,"joystick":{"lh":{"sa":208,"main":{"valid":true}},"rh":{"sa":209,"main":{"valid":true},"aux":{"valid":true}}},"pedal":{"lh":{"name":"Pedal LH","expected_sa":237,"sa":237,"valid":true,"pgn":64986,"len":8,"data":[1,2,3,4,5,6,7,8]},"rh":{"name":"Pedal RH","expected_sa":238,"valid":false,"len":0,"data":[0,0,0,0,0,0,0,0]}},"ain":{"AIN1":321,"AIN2":322,"AIN3":323,"AIN4":324},"din":{"DIN1":false,"DIN2":true}}}
```

참고:

- 현재 wire-format은 호환성 때문에 `pedal.lh`, `pedal.rh` 두 raw slot을 유지합니다.
- 하지만 문서 재확인 기준 실제 장치는 `SA=0xED` 단일 Travel Pedal unit으로 해석하는 쪽이 맞습니다.
- 테스터는 값이 들어온 slot을 자동으로 골라 `primary_pedal`로 보고, `Axis 2 / Axis 1` 그래프로 표시합니다.

GUI는 연결 직후 Mega 자동 리셋 시간을 약 `1.8초` 기다린 뒤 `about`, `start`를 자동 전송합니다. 상단 버튼으로 `start`, `stop`, `about`, `input dump`, `input map`을 수동 제어할 수도 있습니다.

### 레거시 텍스트 스트림

기존 `CAN_Joystick_Sample`의 텍스트 출력도 계속 지원합니다.

### 메인 조이스틱 (예: PGN 0xFDD6, 0xFDD8)

```text
ID:0xCFDD6D1 PGN:0xFDD6 X(st=0 -=1 +=0 N=0 pos=250) Y(st=0 -=0 +=0 N=0 pos=128) B1:0 B2:0 B3:0 B4:0
```

### AUX 조이스틱 (예: PGN 0xFDD7, 0xFDD9)

```text
ID:0xCFDD7D1 PGN:0xFDD7 AUX_X(st=0 -=0 +=0 N=1 pos=0)
```

### 주행페달 preview (DigCanLink JSON)

- 페달은 현재 `PGN 0xFDDA` 기준 raw preview 슬롯으로 표시합니다.
- 문서 `주행페달` 시트 기준 기본 Source Address는 `0xED` 하나입니다.
- 같은 프레임 안에서 `Axis 2 = Byte1/2`, `Axis 1 = Byte3/4`로 해석합니다.
- 현재 GUI는 raw `B0~B7` 바이트를 보존하면서, 상단에는 `Axis 2 (2-/2+)`, `Axis 1 (1-/1+)` 그래프를 같이 보여줍니다.
- 문서 근거:
  - General 표: `Source Address = 0xED`
  - Pin-Out 표: `CAN1 & CAN2 channel internally connected for daisy chain`
  - Mapping 표: `X Axis (2)` / `Y-Axis (1)`

### 축 필드 의미

`X(st=S -=N +=P N=U pos=V)` 형식:

| 필드 | 의미 |
|------|------|
| `st` | 축 상태 코드 (2-bit, 0..3) |
| `-`  | 음수 방향 negative (2-bit) |
| `+`  | 양수 방향 positive (2-bit) |
| `N`  | 중립 neutral (2-bit) |
| `pos` | 위치값 (0..255, 중립 ≈ 128) |

### 버튼 필드

`B1:v B2:v B3:v B4:v` — 각 2-bit 값 (0=OFF, 1~3=ON)

### 파싱 흐름

- JSON 라인: `parse_json_line()` → `DigInputReport` 또는 `DeviceResponse`
- 레거시 텍스트 라인: `parse_text_line()` → `MainPacket` 또는 `AuxPacket`
- `TextLineParser`는 두 포맷을 자동 판별합니다.

## 7. GUI 모니터 기능

- `Joystick LH`, `Joystick RH` 각각의 메인/AUX 축 그래프
- `Travel Pedal Unit` 패널
- `Axis 2 (2-/2+)`, `Axis 1 (1-/1+)` 그래프와 상태줄
- raw `B0~B7` byte 패널
- 각 축 그래프 우측에 `+/-/Neutral` 방향 라벨 표시
- 버튼 4개 상태 LED
- `AIN1~AIN4` 아날로그 입력 막대 표시
- `DIN1~DIN7` 디지털 입력 ON/OFF 표시
- 장치 정보, 스트리밍 상태, CAN/Joystick/Pedal 갱신 여부, idle 시간, 마지막 CAN ID 표시
- 명령/응답 로그 표시
- 연결 세션마다 `logs/digcanlink_monitor_YYYYMMDD_HHMMSS.jsonl` 디버그 로그 저장
- GUI의 시리얼 오픈 실패는 콘솔 `print()` 대신 창 내부 상태/로그로 처리
- 포트 연결 직후에는 Mega 재부팅 시간을 고려해 약 `1.8초` 후 `about`, `2.1초` 후 `start`를 자동 전송
- `start`, `stop`, `about`, `input dump`, `input map` 전송 버튼
- 기존 HID 링크(vgamepad) 유지

## 8. 장치별 참고

### DigCanLink

| 항목 | 값 |
|------|------|
| MCU | Arduino Mega 2560 |
| CAN Controller | MCP2515 (8MHz 크리스탈) |
| CAN 속도 | 500 kbps |
| 시리얼 보레이트 | 115200 |
| 기본 출력 | `input_report` JSON 100ms 주기 |
| 제어 명령 | `start`, `stop`, `about`, `input dump`, `input map` |
| 표시 대상 | LH/RH 조이스틱, Travel Pedal unit, AIN1~AIN4, DIN1~DIN7 |
| 프로젝트 맥락 | 굴착기(포크레인) 시뮬레이터 입력 인터페이스 |

주의:

- 현재 `AIN1~AIN4`, `DIN1~DIN7`은 물리 채널명 그대로 노출합니다.
- 실제 장비 의미 이름은 현장 배선/상위 시스템 매핑 기준으로 정하는 것을 권장합니다.
- 주행페달은 현재 raw preview를 유지하지만, 문서 기준 `Axis 2 / Axis 1` 방향 그래프를 함께 표시합니다.
- `주행페달` 시트 기준 물리 CAN 노드는 `SA=0xED` 하나이고, `0xFDDA` 프레임에 두 축이 함께 실립니다.

### CAN_Joystick_Sample

| 항목 | 값 |
|------|------|
| 조이스틱 SA | `0xD1` |
| 선택 핀(D10) HIGH (기본) | 메인(`0xFDD6`) + AUX(`0xFDD7`) 둘 다 출력 |
| 선택 핀(D10) LOW (GND) | AUX(`0xFDD7`)만 출력 |
| LED(D13) | 부팅 시 3회 깜박, CAN 접속 시 ON, 데이터 수신 시 500ms 깜박임 |

## 9. J1939 CAN 원본 프로토콜

29-bit Extended CAN ID 구조:

```text
[28:26] Priority    [25] Reserved    [24] Data Page
[23:16] PF          [15:8] PS        [7:0] SA
```

| 항목 | 값 |
|------|------|
| Main PGN | `0xFDD6` (CAN ID: `0x0CFDD6D1`) |
| AUX PGN | `0xFDD7` (CAN ID: `0x0CFDD7D1`) |

### PGN 0xFDD6 메인 조이스틱 (CAN 8바이트)

| Byte | 의미 |
|------|------|
| `d[0]` | X축 상태 비트필드 `[7:6]status [5:4]negative [3:2]positive [1:0]neutral` |
| `d[1]` | X축 위치값 `0..255` |
| `d[2]` | Y축 상태 비트필드 (동일 구조) |
| `d[3]` | Y축 위치값 `0..255` |
| `d[4]` | 미사용 |
| `d[5]` | 버튼 `[7:6]btn2 [5:4]btn1 [3:2]btn4 [1:0]btn3` |
| `d[6..7]` | 미사용 |

### PGN 0xFDD7 AUX 조이스틱 (CAN 8바이트)

| Byte | 의미 |
|------|------|
| `d[0]` | AUX X축 상태 `[7:6]status [5:4]positive [3:2]negative [1:0]neutral` |
| `d[1]` | AUX X축 위치값 `0..255` |
| `d[2..7]` | 미사용 |

> FDD7의 `d[0]`은 FDD6과 positive/negative 비트 순서가 반대입니다.

## 10. 테스트

```bash
cd DugCanLinkTester
python -m unittest discover tests/ -v
```

## 11. 문제 해결

### 포트가 열리지 않을 때

- 장치 관리자에서 COM 포트 번호 확인
- 다른 시리얼 모니터가 포트를 점유 중인지 확인

### DigCanLink에서 데이터가 안 들어올 때

- `start` 상태인지 확인
- GUI 상단 `About` / `Start` 버튼을 눌러 응답 로그 확인
- `about` 응답에서 `can_ready:true`인지 확인
- 정상 상태 기준은 `CAN=OK`, `CAN Update=RX`, `Joy Update=RX`, `CAN Idle/Joy Idle`이 낮고, `CAN Frames/Joy Frames`가 계속 증가하는 경우다
- 페달이 연결되면 `Pedal Update=RX`, `Pedal Idle`이 낮고 `Pedal Frames`가 계속 증가해야 정상이다
- 연결 직후 `Device`, `Version`이 바로 안 뜨면 약 2초 정도 기다린 뒤 자동 `about` 응답이 들어오는지 확인
- `can_updated`가 계속 `RX`인데 `joystick_updated`만 멈추면 버스는 살아 있고 조이스틱 프레임만 stale 상태

### DIN 입력이 일부만 이상할 때

- 펌웨어는 `DIN1~DIN7`을 모두 같은 방식으로 읽습니다: `INPUT_PULLUP` + `LOW`일 때 active
- 즉 특정 채널만 이상하면, 소프트웨어보다 배선/스위치 타입/공통 GND/노이즈 차이를 먼저 의심하는 편이 맞습니다.
- 2026-04-06 로그 기준으로도 채널별 거동이 갈렸습니다.
  - 최근 세션에서 `DIN1`은 자주 active, `DIN2`는 일부 active, `DIN3~DIN7`은 계속 0
  - 이 패턴은 “모든 DIN을 똑같이 잘못 읽는 버그”보다는 각 입력선의 전기적 상태 차이에 더 가깝습니다.
- 긴 배선, 떠 있는 입력, open-collector 출력, active-high 소스, 공통 GND 누락 등이 있으면 내부 pull-up만으로는 불안정할 수 있습니다.

### LH BTN2/Horn이 안 들어올 때

- 2026-04-06 실기 로그 기준으로 `LH BTN1/BTN3/BTN4`는 감지됐고 `RH BTN2`도 감지됐지만, `LH BTN2/Horn`만 끝까지 `0`이었다.
- 문서상 LH `Byte 6` 배치는 코드와 일치한다. 즉 현재 구현 로직이 BTN2 비트를 잘못 읽는 정황은 약하다.
- 현재 GUI는 기본 버튼 상태(`BTN1~BTN4`)만 표시하며, 추가 버튼 디버깅 표시는 제거했다.
- `joystick_rx_idle_ms`가 계속 증가하면 조이스틱 CAN 갱신이 끊긴 것
- `pedal_updated`가 멈추거나 `pedal_rx_idle_ms`가 계속 증가하면 페달 CAN 갱신이 끊긴 것
- `logs/` 아래 세션 로그 JSONL을 보면 시점별 report/response/command를 다시 추적할 수 있음

### 레거시 샘플에서 데이터가 안 들어올 때

- Arduino에 `CAN_Joystick_Sample` 펌웨어가 올라가 있는지 확인
- 시리얼 모니터에서 `MCP2515 Init OK` 메시지가 뜨는지 확인
- D13 LED가 깜박이는지 확인 (깜박이면 데이터 수신 중)
- MCP2515 크리스탈이 8MHz인지, CAN 속도가 500kbps인지 확인
- 조이스틱 SA가 `0xD1`인지 확인

### 값이 반대로 보일 때

- AUX(`PGN 0xFDD7`)는 CAN 원본 비트 순서가 메인과 다름
- GUI 방향 라벨 기준:
  - `X`, `AUX X`: `- Left`, `+ Right`
- `Y`: `- Down/Back`, `+ Up/Forward`
- 위 방향 라벨은 문서의 `negative / positive / neutral` 의미를 그대로 풀어쓴 것이다.
- 펌웨어가 내부적으로 처리하므로 시리얼 출력에서는 동일한 형식으로 나옴

## 12. 배포판 빌드 (실행 파일)

PyInstaller로 `.exe` 배포판을 만듭니다. Python이 없는 PC에서도 실행 가능합니다.

### 사전 준비

```bash
uv sync --group build
```

### 모니터 전용 빌드

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\build_release.ps1 -Target MonitorOnly
```

산출물:

- `release/DugCanLinkTester-MonitorOnly-win64.zip`

압축을 풀면 `DugCanLinkTesterMonitor.exe`로 바로 실행할 수 있습니다.

### 배포판 사용법

1. zip 파일을 대상 PC에 복사 후 압축 해제
2. `DugCanLinkTesterMonitor.exe` 실행
3. GUI에서 COM 포트 선택 후 Connect

### 빌드 구조

```text
DugCanLinkTester/
├─ packaging/
│  ├─ monitor_only.spec        # 모니터 전용 PyInstaller spec
│  └─ monitor_hid.spec         # HID 포함 spec (보류)
├─ tools/
│  └─ build_release.ps1        # 빌드 + zip 생성 스크립트
├─ dist/                       # PyInstaller 빌드 임시 출력 (gitignore)
└─ release/                    # 최종 zip 산출물
```

## 13. 향후 계획

- **DigCanLink 중심 통합 고도화**: `input dump/map` 응답을 구조화된 패널로 더 세분화
- **바이너리 프로토콜 전환**: 개발 안정화 후 텍스트 → 바이너리 패킷으로 변경 예정 (기존 `PacketParser` 코드 보존됨)
- **HID 링크**: Xbox 가상 패드 출력 기능 (현재 보류)

## 14. 관련 프로젝트

- `../DigCanLink`: Mega 2560 인터페이스 보드 입력 통합 펌웨어
- `../CAN_Joystick_Sample`: J1939 CAN 수신 → 시리얼 텍스트 출력 Arduino 펌웨어
