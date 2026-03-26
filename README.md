# DugCanLinkTester

J1939 CAN 조이스틱 데이터를 PC에서 모니터링하기 위한 Python 도구입니다.

Arduino Mega 2560 + MCP2515 브리지 펌웨어(`CAN_Joystick_Sample`)가 J1939 CAN 프레임을 받아 **텍스트 시리얼 출력**으로 변환하고, `DugCanLinkTester`는 그 텍스트를 파싱해서 CLI 또는 GUI로 표시합니다.

## 1. 전체 구성

```text
J1939 CAN Joystick
  → CAN frame (PGN 0xFDD6 / 0xFDD7)
  → Arduino Mega + MCP2515  (CAN_Joystick_Sample 펌웨어)
  → Text Serial Output (115200 bps, Serial.print)
  → DugCanLinkTester
     → CLI Receiver  (joystick-receiver)
     → PySide6 GUI Monitor  (joystick-monitor)
```

## 2. 프로젝트 구성

```text
DugCanLinkTester/
├─ DugCanLinker/
│  ├─ protocol.py              # 데이터 모델, 텍스트/바이너리 파싱, 포맷팅
│  ├─ serial_receiver.py       # TextLineParser + SerialReceiver (시리얼 수신 스레드)
│  ├─ joystick_receiver.py     # CLI 수신기
│  ├─ joystick_monitor.py      # PySide6 GUI 모니터
│  └─ vortex_hid.py            # Xbox 가상 패드 출력 (HID, 보류)
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
- Arduino 브리지 장치 연결 (CAN_Joystick_Sample 펌웨어)
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
[     1] MAIN  X=250(+122) Y=128(  +0)  B1=0 B2=0 B3=0 B4=0  seq=0
[     2] AUX   X=  0(-128)  seq=0
```

## 5. 시리얼 텍스트 프로토콜

현재 브리지 펌웨어는 `Serial.print()`로 텍스트를 한 줄씩 출력합니다.

### 메인 조이스틱 (PGN 0xFDD6)

```text
ID:0xCFDD6D1 PGN:0xFDD6 X(st=0 -=1 +=0 N=0 pos=250) Y(st=0 -=0 +=0 N=0 pos=128) B1:0 B2:0 B3:0 B4:0
```

### AUX 조이스틱 (PGN 0xFDD7)

```text
ID:0xCFDD7D1 PGN:0xFDD7 AUX_X(st=0 -=0 +=0 N=1 pos=0)
```

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

`TextLineParser`가 바이트를 줄 단위로 모아 `parse_text_line()`으로 파싱합니다:

1. 시리얼에서 바이트를 수신
2. `\n`이 올 때까지 버퍼에 축적
3. 한 줄 완성 시 정규식으로 PGN/축/버튼 추출
4. `MainPacket` 또는 `AuxPacket` 객체로 변환
5. 콜백 또는 Qt Signal로 GUI/CLI에 전달

## 6. 브리지 펌웨어 설정

이 프로젝트는 `CAN_Joystick_Sample` 펌웨어와 세트로 동작합니다.

| 항목 | 값 |
|------|------|
| MCU | Arduino Mega 2560 |
| CAN Controller | MCP2515 (8MHz 크리스탈) |
| CAN 속도 | 500 kbps |
| 조이스틱 SA | `0xD1` |
| 시리얼 보레이트 | 115200 |
| 선택 핀(D10) HIGH (기본) | 메인(`0xFDD6`) + AUX(`0xFDD7`) 둘 다 출력 |
| 선택 핀(D10) LOW (GND) | AUX(`0xFDD7`)만 출력 |
| LED(D13) | 부팅 시 3회 깜박, CAN 접속 시 ON, 데이터 수신 시 500ms 깜박임 |

## 7. J1939 CAN 원본 프로토콜

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

## 8. 테스트

```bash
cd DugCanLinkTester
python -m unittest discover tests/ -v
```

## 9. 문제 해결

### 포트가 열리지 않을 때

- 장치 관리자에서 COM 포트 번호 확인
- 다른 시리얼 모니터가 포트를 점유 중인지 확인

### 데이터가 안 들어올 때

- Arduino에 `CAN_Joystick_Sample` 펌웨어가 올라가 있는지 확인
- 시리얼 모니터에서 `MCP2515 Init OK` 메시지가 뜨는지 확인
- D13 LED가 깜박이는지 확인 (깜박이면 데이터 수신 중)
- MCP2515 크리스탈이 8MHz인지, CAN 속도가 500kbps인지 확인
- 조이스틱 SA가 `0xD1`인지 확인

### 값이 반대로 보일 때

- AUX(`PGN 0xFDD7`)는 CAN 원본 비트 순서가 메인과 다름
- 펌웨어가 내부적으로 처리하므로 시리얼 출력에서는 동일한 형식으로 나옴

## 10. 배포판 빌드 (실행 파일)

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

## 11. 향후 계획

- **바이너리 프로토콜 전환**: 개발 안정화 후 텍스트 → 바이너리 패킷으로 변경 예정 (기존 `PacketParser` 코드 보존됨)
- **HID 링크**: Xbox 가상 패드 출력 기능 (현재 보류)

## 12. 관련 프로젝트

- `../CAN_Joystick_Sample`: J1939 CAN 수신 → 시리얼 텍스트 출력 Arduino 펌웨어
