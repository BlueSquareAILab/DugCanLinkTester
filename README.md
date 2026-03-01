# DugCanLinkTester

J1939 CAN 조이스틱 데이터를 PC에서 모니터링하기 위한 Python 도구입니다.

이 프로젝트는 CAN 프레임을 직접 읽지 않습니다. Arduino Mega 2560 + MCP2515 기반 브리지 펌웨어가 J1939 CAN 프레임을 받아 바이너리 시리얼 패킷으로 변환해 주고, `DugCanLinkTester`는 그 시리얼 패킷을 파싱해서 CLI 또는 GUI로 표시합니다.

운영 모드는 두 가지입니다.

- `Monitor Only`: 시리얼 패킷을 받아 GUI/CLI로 표시
- `Monitor + HID`: GUI에 표시하면서 동시에 Windows 가상 Xbox 패드로 출력

검토 기준 파일:

- `DugCanLinker/protocol.py`
- `DugCanLinker/serial_receiver.py`
- `DugCanLinker/joystick_receiver.py`
- `DugCanLinker/joystick_monitor.py`
- `../CAN_Joystick_Sample/src/main.cpp`
- `../CAN_Joystick_Sample/lib/J1939Con/joystick_can.*`
- `../CAN_Joystick_Sample/lib/J1939Con/joystick_serial.*`

## 1. 전체 구성

데이터 흐름은 아래와 같습니다.

```text
J1939 CAN Joystick
  -> CAN frame (PGN 0xFDD6 / 0xFDD7)
  -> Arduino Mega + MCP2515
  -> Binary Serial Protocol (115200 bps)
  -> DugCanLinkTester
     -> CLI Receiver
     -> PySide6 GUI Monitor
```

즉, 이 프로젝트의 핵심은 두 가지입니다.

- 시리얼 바이트 스트림에서 패킷을 안정적으로 복원하는 것
- 복원된 축/버튼 상태를 사람이 보기 쉬운 형태로 표시하는 것

## 2. 프로젝트 구성

```text
DugCanLinkTester/
├─ main.py                          # GUI 모니터 실행 엔트리
├─ pyproject.toml                   # 패키지/의존성 정의
├─ DugCanLinker/
│  ├─ protocol.py                   # 패킷 상수, 데이터 모델, 파싱/포맷팅
│  ├─ serial_receiver.py            # 바이트 스트림 상태머신 + 시리얼 수신 스레드
│  ├─ joystick_receiver.py          # CLI 수신기
│  ├─ joystick_monitor.py           # PySide6 GUI 모니터 + HID 통합 UI
│  └─ vortex_hid.py                 # Xbox 가상 패드 출력 로직
└─ README.md
```

역할 분리는 명확합니다.

- `protocol.py`: 순수 데이터 해석 로직
- `serial_receiver.py`: 바이트 단위 패킷 조립
- `joystick_receiver.py`: 콘솔 출력
- `joystick_monitor.py`: 실시간 GUI 표시

## 3. 실행 환경

요구 사항:

- Python 3.11 이상
- 시리얼 브리지 장치 연결
- 기본 보레이트 `115200`

의존성:

- `PySide6 >= 6.6`
- `pyserial >= 3.5`

선택 의존성:

- `vgamepad`: Windows 가상 Xbox 360 패드 출력용

중요:

- `vgamepad`는 필수가 아닙니다.
- 일반 모니터링만 쓸 때는 없어도 됩니다.
- Vortex Studio 연동 또는 Windows 게임패드 출력이 필요할 때만 설치합니다.

설치:

```bash
uv sync
```

HID 링크까지 같이 쓸 경우:

```bash
uv sync --extra hid
```

## 4. 빠른 시작

### 4.1 모니터만 실행

```bash
uv run joystick-monitor --port COM3
```

### 4.2 모니터 + HID 같이 실행

```bash
uv run joystick-monitor --port COM3 --hid
```

### 4.3 CLI로 패킷 확인

```bash
uv run joystick-receiver --port COM3
```

기본 연결 조건:

- 시리얼 포트: 예) `COM3`
- 보레이트: `115200`
- 브리지 펌웨어: `CAN_Joystick_Sample`

## 5. 실행 방법

### GUI 모니터

```bash
uv run joystick-monitor --port COM3
```

HID 링크를 시작부터 같이 켜려면:

```bash
uv run joystick-monitor --port COM3 --hid
```

기능:

- 메인 X/Y 축 실시간 그래프
- AUX X 축 실시간 그래프
- 축 상태 비트 표시
- 버튼 4개 LED 표시
- 패킷 수/에러 수 표시
- 같은 화면에서 Xbox 가상 패드(HID) 출력 제어
- Deadzone / Expo / Y축 반전 설정

### CLI 수신기

```bash
uv run joystick-receiver --port COM3
```

또는:

```bash
python -m DugCanLinker.joystick_receiver --port COM3
```

출력 예:

```text
[     1] MAIN  X=128(  +0) Y=130(  +2)  B1=0 B2=0 B3=0 B4=0  seq=0
[     2] AUX   X=140( +12)  seq=1
```

### GUI 안에서 HID를 쓰는 방법

GUI 실행 후 상단의 `Vortex HID Link` 영역에서 바로 켤 수 있습니다.

HID 매핑:

- Main X -> Left Stick X
- Main Y -> Left Stick Y
- AUX X -> Right Stick Y
- Button 1..4 -> `A`, `B`, `X`, `Y`

설정 항목:

- `Deadzone`: 중앙 데드존
- `Main Expo`: 메인 축 지수 곡선
- `AUX Expo`: AUX 축 지수 곡선
- `Invert Y`: Y축 반전 여부

검증 방법:

- `Win + R -> joy.cpl` 실행
- `Xbox 360 Controller for Windows` 계열 장치가 보이는지 확인
- 속성 창에서 Left Stick / Right Stick / 버튼이 실제 수신값대로 움직이는지 확인
- 이후 Vortex Studio의 Input Configuration에서 같은 장치를 Control Source로 매핑

HID를 켰는데 초기화에 실패하면:

- `uv sync --extra hid`가 되었는지 확인
- `vgamepad`가 설치되었는지 확인
- Windows 가상 게임패드 드라이버가 정상 설치되었는지 확인

명령행에서 초기값을 주고 싶다면:

```bash
uv run joystick-monitor --port COM3 --hid --deadzone 0.03 --expo 1.2 --aux-expo 1.5
```

## 6. 배포 메모

배포 시에는 사용자 유형을 나눠서 안내하는 것이 맞습니다.

### 6.1 모니터 전용 배포

- `vgamepad` 없이 사용 가능
- GUI/CLI 수신 기능만 제공

### 6.2 Vortex HID 포함 배포

- `vgamepad` 및 관련 드라이버 설치 필요
- 사용자 PC에서 Windows 가상 Xbox 패드가 생성되어야 함
- 설치 후 `joy.cpl`에서 먼저 동작 확인하는 것이 안전

권장 안내 문구:

- "모니터 기능만 사용할 경우 기본 설치만 진행"
- "Vortex Studio 연동이 필요할 경우 HID 구성 요소를 추가 설치"

즉, 현재 구조에서는 배포본에 HID 기능을 넣더라도 사용 설명서에는 `vgamepad`가 선택 설치 항목임을 분명히 적어야 합니다.

## 7. 브리지 펌웨어와의 관계

이 Python 프로젝트는 `CAN_Joystick_Sample` 펌웨어와 세트로 동작합니다.

브리지 펌웨어의 동작:

1. MCP2515에서 J1939 CAN 프레임 수신
2. Source Address가 `0xD1`인 조이스틱 프레임만 수용
3. 지원 PGN:
   - `0xFDD6`: 메인 조이스틱
   - `0xFDD7`: AUX 조이스틱
4. 수신 CAN 데이터를 자체 바이너리 시리얼 프로토콜로 재포장
5. USB Serial `115200bps`로 PC에 전달

하드웨어/펌웨어 기준값:

- MCU: Arduino Mega 2560
- CAN Controller: MCP2515
- MCP2515 Crystal: 8MHz
- CAN Bitrate: 500kbps
- Joystick SA: `0xD1`

## 8. J1939 CAN 원본 프로토콜

브리지 펌웨어는 29-bit Extended CAN ID를 사용합니다.

J1939 ID 구조:

```text
[28:26] Priority
[25]    Reserved
[24]    Data Page
[23:16] PF
[15:8]  PS
[7:0]   SA
```

현재 프로젝트에서 사용하는 조이스틱 관련 PGN:

| 항목 | 값 |
|---|---|
| Source Address | `0xD1` |
| Main PGN | `0xFDD6` |
| AUX PGN | `0xFDD7` |
| Main CAN ID 패턴 | `0x0CFDD6D1` |
| AUX CAN ID 패턴 | `0x0CFDD7D1` |

우선순위는 구현상 `0x0Cxxxxxx` 패턴으로 취급되므로 일반적으로 Priority 3 프레임으로 보면 됩니다.

### 8.1 PGN `0xFDD6` 메인 조이스틱

CAN 데이터 8바이트 해석:

| Byte | 의미 |
|---|---|
| `d[0]` | X축 상태 비트필드 |
| `d[1]` | X축 위치값 `0..255` |
| `d[2]` | Y축 상태 비트필드 |
| `d[3]` | Y축 위치값 `0..255` |
| `d[4]` | 사용 안 함 |
| `d[5]` | 버튼 상태 비트필드 |
| `d[6]` | 사용 안 함 |
| `d[7]` | 사용 안 함 |

`d[0]`, `d[2]` 축 상태 비트필드 구조:

| Bits | 의미 |
|---|---|
| `[7:6]` | 축 상태 코드 `status` |
| `[5:4]` | 음수 방향 `negative` |
| `[3:2]` | 양수 방향 `positive` |
| `[1:0]` | 중립 `neutral` |

X축의 방향 의미:

- `negative`: Left
- `positive`: Right

Y축의 방향 의미:

- `negative`: Back
- `positive`: Forward

버튼 비트필드 `d[5]`:

| Bits | 의미 |
|---|---|
| `[7:6]` | Button 2 |
| `[5:4]` | Button 1 |
| `[3:2]` | Button 4 |
| `[1:0]` | Button 3 |

### 8.2 PGN `0xFDD7` AUX 조이스틱

CAN 데이터 8바이트 해석:

| Byte | 의미 |
|---|---|
| `d[0]` | AUX X축 상태 비트필드 |
| `d[1]` | AUX X축 위치값 `0..255` |
| `d[2]`~`d[7]` | 사용 안 함 |

중요한 차이점:

- `0xFDD7`의 원본 CAN 비트 순서는 `0xFDD6`와 다릅니다.
- 펌웨어는 이를 내부적으로 정규화한 뒤 시리얼로 재전송합니다.

원본 CAN 비트필드 `d[0]`:

| Bits | 의미 |
|---|---|
| `[7:6]` | 축 상태 코드 `status` |
| `[5:4]` | Right Positive |
| `[3:2]` | Left Negative |
| `[1:0]` | Neutral |

즉, `FDD7`는 원본 CAN에서 `positive`와 `negative`의 위치가 메인 프레임과 반대입니다.

## 9. PC가 받는 시리얼 바이너리 프로토콜

Python이 실제로 처리하는 것은 CAN 프레임이 아니라 아래 시리얼 패킷입니다.

패킷 공통 구조:

```text
[SYNC1][SYNC2][TYPE][LEN][PAYLOAD ...][CHECKSUM]
```

| 필드 | 값 |
|---|---|
| `SYNC1` | `0xAA` |
| `SYNC2` | `0x55` |
| `TYPE` | `0x01` = MAIN, `0x02` = AUX |
| `LEN` | 페이로드 길이 |
| `CHECKSUM` | `TYPE ^ LEN ^ PAYLOAD...` XOR |

Python `PacketParser` 상태머신은 아래 순서로 파싱합니다.

1. `0xAA`
2. `0x55`
3. `TYPE`
4. `LEN`
5. `LEN` 바이트만큼 `PAYLOAD`
6. 마지막 1바이트를 XOR 체크섬으로 검증

제약:

- 최대 허용 길이: `16` 바이트
- 체크섬 오류 시 패킷 폐기
- sync가 어긋나면 다음 `0xAA`부터 재동기화

### 9.1 `PKT_MAIN (0x01)`

페이로드 길이: `7`

| Offset | 이름 | 설명 |
|---|---|---|
| `0` | `x_pos` | X 위치값 `0..255` |
| `1` | `x_status` | X 상태 비트필드 |
| `2` | `y_pos` | Y 위치값 `0..255` |
| `3` | `y_status` | Y 상태 비트필드 |
| `4` | `buttons` | 버튼 비트필드 |
| `5` | `flags` | 예약, 현재 `0x00` |
| `6` | `seq` | 송신 시퀀스 카운터 |

전체 패킷 길이:

- `2 + 1 + 1 + 7 + 1 = 12` bytes

축 상태 비트필드:

| Bits | 의미 |
|---|---|
| `[7:6]` | `status` |
| `[5:4]` | `negative` |
| `[3:2]` | `positive` |
| `[1:0]` | `neutral` |

버튼 비트필드:

| Bits | 의미 |
|---|---|
| `[7:6]` | `btn2` |
| `[5:4]` | `btn1` |
| `[3:2]` | `btn4` |
| `[1:0]` | `btn3` |

### 9.2 `PKT_AUX (0x02)`

페이로드 길이: `4`

| Offset | 이름 | 설명 |
|---|---|---|
| `0` | `x_pos` | AUX X 위치값 `0..255` |
| `1` | `x_status` | AUX X 상태 비트필드 |
| `2` | `flags` | 예약, 현재 `0x00` |
| `3` | `seq` | 송신 시퀀스 카운터 |

전체 패킷 길이:

- `2 + 1 + 1 + 4 + 1 = 9` bytes

중요:

- AUX의 시리얼 상태 바이트는 Python이 메인 축과 동일한 방식으로 해석할 수 있도록 정규화되어 있습니다.
- 즉, 시리얼 상에서는 AUX도 `[7:6]=status, [5:4]=negative, [3:2]=positive, [1:0]=neutral` 규칙을 사용합니다.

## 10. Python 내부 데이터 모델

### `AxisState`

| 필드 | 의미 |
|---|---|
| `position` | 원본 위치값 `0..255` |
| `status` | 2-bit 상태 코드 |
| `negative` | 음수 방향 상태 |
| `positive` | 양수 방향 상태 |
| `neutral` | 중립 상태 |

추가 계산값:

- `signed = position - 128`

즉, GUI와 CLI에서는 `0..255` 값을 `-128..+127` 기준으로도 함께 보여 줍니다.

예:

- `128 -> 0`
- `140 -> +12`
- `100 -> -28`

### `ButtonState`

4개 버튼을 각각 2-bit 값으로 보관합니다.

| 필드 | 의미 |
|---|---|
| `btn1` | Button 1 |
| `btn2` | Button 2 |
| `btn3` | Button 3 |
| `btn4` | Button 4 |

현재 GUI는 `0`이면 OFF, `1~3`이면 ON처럼 표시합니다.

## 11. 패킷 파서 동작 요약

`serial_receiver.py`의 `PacketParser`는 I/O와 독립적인 순수 상태머신입니다.

장점:

- 시리얼 외의 입력 소스에도 재사용 가능
- GUI/CLI가 동일한 파서를 공유
- 테스트 코드 작성이 쉬움

동작 규칙:

- 정상 패킷 수는 `stats.good`
- 에러 패킷 수는 `stats.errors`
- 길이 초과 또는 체크섬 오류 시 에러 카운트 증가
- 타입/길이가 맞지 않는 경우 체크섬이 맞아도 decode 결과는 `None`

주의할 점:

- 현재 `errors > 0`이 된 뒤에는 이후 정상 패킷마다 에러 콜백이 반복 호출될 수 있습니다.
- GUI에서는 크게 문제 없지만, 향후 로그 시스템을 붙일 때는 "에러 발생 시점 1회 통지"로 다듬는 것이 좋습니다.

## 12. 구현 검수 메모

코드 검토 기준으로 확인된 핵심 사항입니다.

- `protocol.py`와 `joystick_serial.cpp`의 메인 패킷 순서는 일치합니다.
- `FDD7` 원본 CAN 비트 순서는 메인과 다르지만, 브리지 펌웨어가 시리얼 전송 전에 정규화합니다.
- Python `parse_aux_payload()`는 이 정규화된 시리얼 포맷을 기준으로 맞게 구현돼 있습니다.
- GUI와 CLI 모두 동일한 `PacketParser`를 사용하므로 해석 결과가 일관됩니다.

실무적으로 반드시 알아둘 점:

- 이 문서의 "CAN 원본 프로토콜"과 "시리얼 프로토콜"은 서로 다릅니다.
- 특히 `AUX(FDD7)`는 CAN 비트 순서와 시리얼 비트 순서를 혼동하면 디버깅이 꼬이기 쉽습니다.

## 13. 문제 해결

### 포트가 열리지 않을 때

- 장치 관리자의 COM 포트 번호 확인
- 다른 시리얼 모니터가 포트를 점유 중인지 확인
- 보레이트가 `115200`인지 확인

### 데이터가 안 들어올 때

- Arduino 브리지 펌웨어가 올라가 있는지 확인
- MCP2515 설정이 `8MHz`, `500kbps`인지 확인
- 조이스틱 Source Address가 `0xD1`인지 확인
- CAN ID가 실제로 `0x0CFDD6D1`, `0x0CFDD7D1` 계열인지 확인

### 값이 반대로 보일 때

- CAN 원본을 보고 있는지, 시리얼 변환 후 값을 보고 있는지 먼저 구분
- 특히 AUX(`PGN 0xFDD7`)는 원본 CAN 비트 순서가 메인과 다름

### HID 장치가 안 보일 때

- GUI 상단에서 `Xbox Virtual Pad`가 활성화되었는지 확인
- `uv sync --extra hid`를 다시 실행
- `joy.cpl`에서 장치가 생성되는지 확인
- 회사 보안 정책이나 드라이버 설치 제한 때문에 가상 게임패드 드라이버가 막히지 않았는지 확인

## 14. 관련 프로젝트

- `../CAN_Joystick_Sample`: J1939 CAN 수신 후 시리얼 브리지 송신하는 Arduino 샘플
- `../DigCanLink`: 별도 Mega 2560 기반 CLI/설정 프로젝트

이 README는 현재 저장소의 구현을 기준으로 작성했습니다. 설명이 아니라 코드가 기준이며, 특히 프로토콜 표는 `joystick_can.*`, `joystick_serial.*`, `protocol.py` 구현을 대조해 정리했습니다.
