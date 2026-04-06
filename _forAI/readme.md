# _forAI README

실제 실행 방법과 배포 명령은 저장소 루트 `README.md`를 우선 기준으로 본다.  
`_forAI` 폴더는 현재 상태를 빠르게 파악하기 위한 보조 문서 묶음이다.

## 현재 작업 상태 요약

- 현재 기본 수신 대상은 `DigCanLink`의 **JSON 스트림**이다.
- 기존 `CAN_Joystick_Sample`의 **텍스트 시리얼 프로토콜도 호환 유지**한다.
- GUI는 `LH/RH 조이스틱`, `Travel Pedal unit`, `AIN1~AIN4`, `DIN1~DIN7`, 장치 상태, 명령/응답 로그까지 표시한다.
- GUI 상단에서 `start`, `stop`, `about`, `input dump`, `input map` 명령을 직접 전송할 수 있다.
- Device State의 정상 상태 기준은 `CAN=OK`, `CAN Update=RX`, `Joy Update=RX`, idle 값이 낮고 frame count가 계속 증가하는 경우다.
- 이 저장소는 `DugSimulator` 굴착기(포크레인) 시뮬레이터 프로젝트의 모니터/연동 도구다.
- 문서 재확인 기준 물리 CAN 노드는 `Joystick LH`, `Joystick RH`, `Travel Pedal` 총 3개다.
- 시뮬레이터 논리 입력 그룹은 `Joystick LH`, `Joystick RH`, `Pedal Axis 2`, `Pedal Axis 1` 총 4개로 본다.
- 최종 사용자 배포 기준은 **Windows GUI 모니터**이고, CLI는 개발/진단용으로 유지한다.
- 납품처/시뮬레이터 재사용 기준 엔트리로 `SerialReceiver`, `TextLineParser`, `parse_serial_line()`을 문서에 명시했다.
- `examples/simulator_receiver_minimal.py`를 외부 연동 기준 예제로 추가했다.
- `signed` 축값은 이제 `raw-128` 고정 가정이 아니라 방향 비트를 우선 반영하는 파생값으로 정리했다.
- 배포 방식은 **PyInstaller onedir + zip**으로 정리되어 있다.
- 배포 타깃은 `MonitorOnly`, `MonitorHID` 두 종류다.
- 기존 `PacketParser`와 바이너리 관련 코드는 향후 프로토콜 전환 가능성을 위해 보존 중이다.

## 현재 기준 확인된 상태

- 테스트: `python -m unittest` 기준 **25개 통과**
- 배포 스크립트: `tools/build_release.ps1`
- 배포 산출물:
  - `release/DugCanLinkTester-MonitorOnly-win64.zip`
  - `release/DugCanLinkTester-MonitorHID-win64.zip`
- 루트 `README.md`는 `DigCanLink JSON + legacy text` 기준 설명과 배포 절차를 반영한 상태다.
- 루트 `README.md`에 Device State 정상 상태 예시와 각 필드 판독 기준을 기록했다.

## 이 폴더 문서 역할

- `readme.md`
  - `_forAI` 폴더의 목적, 현재 상태, 읽는 순서를 정리
- `plan.md`
  - 지금 단계에서 유지할 방향과 남은 확인 항목 정리
- `dev_log.md`
  - 실제로 수행한 변경 작업과 검증 결과를 시간 순으로 기록
- `memo.md`
  - 개발 중 발견한 참고 사항, 아이디어, 임시 메모를 자유 형식으로 기록

## 권장 확인 순서

1. `_forAI/readme.md`
2. 루트 `README.md`
3. `_forAI/plan.md`
4. `_forAI/dev_log.md`
5. `_forAI/memo.md`

## 운영 원칙

- 루트 `README.md`는 사용자/실행 기준 문서로 유지한다.
- `_forAI/readme.md`는 "지금 프로젝트가 어떤 상태인지"를 빠르게 설명한다.
- `plan.md`는 아직 끝나지 않은 항목과 다음 확인 포인트를 정리한다.
- `dev_log.md`는 완료된 작업과 검증 결과를 누적 기록한다.
- `memo.md`는 정제 전 메모를 보관하고, 확정 내용만 다른 문서로 승격한다.
