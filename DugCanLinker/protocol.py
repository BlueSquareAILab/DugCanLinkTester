"""

file : DugCanLinker/protocol.py
desc : DigCanLink JSON / legacy text / 보존된 binary helper 정의

현재 운영 기준:
  - DigCanLink JSON `input_report`, command response
  - CAN_Joystick_Sample legacy text line

보존 항목:
  - 향후 전환 가능성을 위한 binary packet 상수/파서

이 모듈은 I/O에 의존하지 않는 순수 데이터 정의 + 파싱/포맷팅 로직만 포함한다.
시리얼 수신기, GUI, CLI, 외부 시뮬레이터 예제에서 재사용 가능하다.

author: 2026-02-08, gbox3d

이 주석을 수정하지 마세요.
"""

from __future__ import annotations

import json
import re
import struct
from dataclasses import dataclass, field
from typing import Any

# ═══════════════════════════════════════════════════════
#  프로토콜 상수
# ═══════════════════════════════════════════════════════

SYNC1 = 0xAA
SYNC2 = 0x55

PKT_MAIN = 0x01      # 텍스트/바이너리 메인 조이스틱
PKT_AUX = 0x02       # 텍스트/바이너리 AUX 조이스틱
PKT_REPORT = 0x10    # DigCanLink JSON input_report
PKT_RESPONSE = 0x11  # DigCanLink JSON command response

MAIN_PAYLOAD_LEN = 7
AUX_PAYLOAD_LEN = 4


# ═══════════════════════════════════════════════════════
#  데이터 클래스
# ═══════════════════════════════════════════════════════

@dataclass(slots=True)
class AxisState:
    """단일 축의 파싱된 상태"""
    position: int = 0
    status: int = 0
    negative: int = 0
    positive: int = 0
    neutral: int = 0

    @property
    def signed(self) -> int:
        if self.neutral > 0 and self.negative == 0 and self.positive == 0:
            return 0
        if self.neutral == 0 and self.positive > 0 and self.negative == 0:
            return self.position
        if self.neutral == 0 and self.negative > 0 and self.positive == 0:
            return -self.position
        return self.position - 128

    @property
    def normalized(self) -> float:
        if self.neutral > 0 and self.negative == 0 and self.positive == 0:
            return 0.0
        if self.neutral == 0 and self.positive > 0 and self.negative == 0:
            return min(1.0, self.position / 255.0)
        if self.neutral == 0 and self.negative > 0 and self.positive == 0:
            return max(-1.0, -self.position / 255.0)
        return max(-1.0, min(1.0, (self.position - 128) / 127.0))


@dataclass(slots=True)
class ButtonState:
    """4개 버튼 (각 2-bit 값)"""
    btn1: int = 0
    btn2: int = 0
    btn3: int = 0
    btn4: int = 0


@dataclass(slots=True)
class MainPacket:
    """PKT_MAIN (0x01) 파싱 결과"""
    x: AxisState = field(default_factory=AxisState)
    y: AxisState = field(default_factory=AxisState)
    buttons: ButtonState = field(default_factory=ButtonState)
    seq: int = 0


@dataclass(slots=True)
class AuxPacket:
    """PKT_AUX (0x02) 파싱 결과"""
    x: AxisState = field(default_factory=AxisState)
    seq: int = 0


@dataclass(slots=True)
class ReportMainState:
    valid: bool = False
    age_ms: int | None = None
    x: AxisState = field(default_factory=AxisState)
    y: AxisState = field(default_factory=AxisState)
    buttons: ButtonState = field(default_factory=ButtonState)

    def to_packet(self) -> MainPacket:
        return MainPacket(x=self.x, y=self.y, buttons=self.buttons)


@dataclass(slots=True)
class ReportAuxState:
    valid: bool = False
    age_ms: int | None = None
    x: AxisState = field(default_factory=AxisState)

    def to_packet(self) -> AuxPacket:
        return AuxPacket(x=self.x)


@dataclass(slots=True)
class JoystickReport:
    sa: int = 0
    main: ReportMainState = field(default_factory=ReportMainState)
    aux: ReportAuxState = field(default_factory=ReportAuxState)


@dataclass(slots=True)
class PedalReport:
    name: str = ""
    expected_sa: int = 0
    sa: int | None = None
    valid: bool = False
    fresh: bool = False
    age_ms: int | None = None
    pgn: int | None = None
    can_id: int | None = None
    length: int = 0
    data: list[int] = field(default_factory=list)
    axis_2: AxisState = field(default_factory=AxisState)
    axis_1: AxisState = field(default_factory=AxisState)

    @property
    def hex_bytes(self) -> str:
        if self.length <= 0:
            return ""
        return " ".join(f"{value:02X}" for value in self.data[: self.length])

    @property
    def has_payload(self) -> bool:
        return self.length > 0 or any(self.data)


@dataclass(slots=True)
class DigInputReport:
    streaming: bool = False
    interval_ms: int = 0
    can_ready: bool = False
    can_updated: bool = False
    joystick_updated: bool = False
    pedal_updated: bool = False
    can_frame_count: int = 0
    joystick_frame_count: int = 0
    pedal_frame_count: int = 0
    can_rx_idle_ms: int | None = None
    joystick_rx_idle_ms: int | None = None
    pedal_rx_idle_ms: int | None = None
    last_can_id: int | None = None
    last_joystick_can_id: int | None = None
    last_pedal_can_id: int | None = None
    lh: JoystickReport = field(default_factory=JoystickReport)
    rh: JoystickReport = field(default_factory=JoystickReport)
    pedal_lh: PedalReport = field(default_factory=PedalReport)
    pedal_rh: PedalReport = field(default_factory=PedalReport)
    ain: dict[str, int] = field(default_factory=dict)
    din: dict[str, bool] = field(default_factory=dict)

    @property
    def primary_pedal(self) -> PedalReport:
        for pedal in (self.pedal_lh, self.pedal_rh):
            if pedal.valid or pedal.sa is not None or pedal.has_payload:
                return pedal
        return self.pedal_lh


@dataclass(slots=True)
class DeviceResponse:
    payload: dict[str, Any] = field(default_factory=dict)

    @property
    def result(self) -> str:
        return str(self.payload.get("result", ""))

    @property
    def message(self) -> str:
        return str(self.payload.get("ms", ""))


# ═══════════════════════════════════════════════════════
#  파싱 함수
# ═══════════════════════════════════════════════════════

def parse_axis(status_byte: int, position: int) -> AxisState:
    return AxisState(
        position=position,
        status=(status_byte >> 6) & 0x03,
        negative=(status_byte >> 4) & 0x03,
        positive=(status_byte >> 2) & 0x03,
        neutral=status_byte & 0x03,
    )


def parse_main_payload(payload: bytes) -> MainPacket:
    x_pos, x_st, y_pos, y_st, buttons, _flags, seq = struct.unpack("7B", payload)
    return MainPacket(
        x=parse_axis(x_st, x_pos),
        y=parse_axis(y_st, y_pos),
        buttons=ButtonState(
            btn1=(buttons >> 4) & 0x03,
            btn2=(buttons >> 6) & 0x03,
            btn3=buttons & 0x03,
            btn4=(buttons >> 2) & 0x03,
        ),
        seq=seq,
    )


def parse_aux_payload(payload: bytes) -> AuxPacket:
    x_pos, x_st, _flags, seq = struct.unpack("4B", payload)
    return AuxPacket(
        x=parse_axis(x_st, x_pos),
        seq=seq,
    )


# ═══════════════════════════════════════════════════════
#  체크섬
# ═══════════════════════════════════════════════════════

def xor_checksum(data: bytes) -> int:
    cs = 0
    for b in data:
        cs ^= b
    return cs


def verify_packet(pkt_type: int, length: int, payload: bytes, checksum: int) -> bool:
    expected = xor_checksum(bytes([pkt_type, length]) + payload)
    return expected == checksum


# ═══════════════════════════════════════════════════════
#  텍스트/JSON 라인 파싱
# ═══════════════════════════════════════════════════════

_AXIS_RE = re.compile(r"(\w+)\(st=(\d+) -=(\d+) \+=(\d+) N=(\d+) pos=(\d+)\)")
_BTN_RE = re.compile(r"B1:(\d+) B2:(\d+) B3:(\d+) B4:(\d+)")
_PGN_RE = re.compile(r"PGN:(0x[0-9A-Fa-f]+)")


def _axis_from_match(groups: tuple[str, ...]) -> AxisState:
    _, st, neg, pos, neu, position = groups
    return AxisState(
        position=int(position),
        status=int(st),
        negative=int(neg),
        positive=int(pos),
        neutral=int(neu),
    )


def parse_text_line(line: str) -> tuple[int, MainPacket | AuxPacket] | None:
    """
    레거시 Arduino Serial.print() 텍스트를 파싱한다.

    RH: FDD6 / FDD7
    LH: FDD8 / FDD9
    """
    pgn_m = _PGN_RE.search(line)
    if not pgn_m:
        return None
    pgn = int(pgn_m.group(1), 16)

    if pgn in (0xFDD6, 0xFDD8):
        axes = _AXIS_RE.findall(line)
        btns = _BTN_RE.search(line)
        if len(axes) < 2 or not btns:
            return None
        return (
            PKT_MAIN,
            MainPacket(
                x=_axis_from_match(axes[0]),
                y=_axis_from_match(axes[1]),
                buttons=ButtonState(
                    btn1=int(btns.group(1)),
                    btn2=int(btns.group(2)),
                    btn3=int(btns.group(3)),
                    btn4=int(btns.group(4)),
                ),
            ),
        )

    if pgn in (0xFDD7, 0xFDD9):
        axes = _AXIS_RE.findall(line)
        if not axes:
            return None
        return (PKT_AUX, AuxPacket(x=_axis_from_match(axes[0])))

    return None


def _axis_from_json(obj: dict[str, Any]) -> AxisState:
    return AxisState(
        position=int(obj.get("raw", 0)),
        status=int(obj.get("st", 0)),
        negative=int(obj.get("neg", 0)),
        positive=int(obj.get("pos", 0)),
        neutral=int(obj.get("neu", 0)),
    )


def _buttons_from_json(obj: dict[str, Any]) -> ButtonState:
    return ButtonState(
        btn1=int(obj.get("b1", 0)),
        btn2=int(obj.get("b2", 0)),
        btn3=int(obj.get("b3", 0)),
        btn4=int(obj.get("b4", 0)),
    )


def _main_state_from_json(obj: dict[str, Any]) -> ReportMainState:
    return ReportMainState(
        valid=bool(obj.get("valid", False)),
        age_ms=int(obj["age_ms"]) if "age_ms" in obj else None,
        x=_axis_from_json(dict(obj.get("x", {}))),
        y=_axis_from_json(dict(obj.get("y", {}))),
        buttons=_buttons_from_json(dict(obj.get("buttons", {}))),
    )


def _aux_state_from_json(obj: dict[str, Any]) -> ReportAuxState:
    return ReportAuxState(
        valid=bool(obj.get("valid", False)),
        age_ms=int(obj["age_ms"]) if "age_ms" in obj else None,
        x=_axis_from_json(dict(obj.get("x", {}))),
    )


def _joystick_from_json(obj: dict[str, Any]) -> JoystickReport:
    return JoystickReport(
        sa=int(obj.get("sa", 0)),
        main=_main_state_from_json(dict(obj.get("main", {}))),
        aux=_aux_state_from_json(dict(obj.get("aux", {}))),
    )


def _pedal_from_json(obj: dict[str, Any]) -> PedalReport:
    data = [int(value) for value in list(obj.get("data", []))]
    if len(data) < 8:
        data.extend([0] * (8 - len(data)))
    length = int(obj.get("len", 0))
    return PedalReport(
        name=str(obj.get("name", "")),
        expected_sa=int(obj.get("expected_sa", 0)),
        sa=int(obj["sa"]) if "sa" in obj else None,
        valid=bool(obj.get("valid", False)),
        fresh=bool(obj.get("fresh", False)),
        age_ms=int(obj["age_ms"]) if "age_ms" in obj else None,
        pgn=int(obj["pgn"]) if "pgn" in obj else None,
        can_id=int(obj["can_id"]) if "can_id" in obj else None,
        length=length,
        data=data[:8],
        axis_2=parse_axis(data[0], data[1]) if length >= 2 else AxisState(),
        axis_1=parse_axis(data[2], data[3]) if length >= 4 else AxisState(),
    )


def parse_input_report_obj(obj: dict[str, Any]) -> DigInputReport:
    data = dict(obj.get("data", {}))
    joy = dict(data.get("joystick", {}))
    pedal = dict(data.get("pedal", {}))
    return DigInputReport(
        streaming=bool(obj.get("streaming", False)),
        interval_ms=int(obj.get("interval_ms", 0)),
        can_ready=bool(data.get("can_ready", False)),
        can_updated=bool(data.get("can_updated", False)),
        joystick_updated=bool(data.get("joystick_updated", False)),
        pedal_updated=bool(data.get("pedal_updated", False)),
        can_frame_count=int(data.get("can_frame_count", 0)),
        joystick_frame_count=int(data.get("joystick_frame_count", 0)),
        pedal_frame_count=int(data.get("pedal_frame_count", 0)),
        can_rx_idle_ms=int(data["can_rx_idle_ms"]) if "can_rx_idle_ms" in data else None,
        joystick_rx_idle_ms=int(data["joystick_rx_idle_ms"]) if "joystick_rx_idle_ms" in data else None,
        pedal_rx_idle_ms=int(data["pedal_rx_idle_ms"]) if "pedal_rx_idle_ms" in data else None,
        last_can_id=int(data["last_can_id"]) if "last_can_id" in data else None,
        last_joystick_can_id=int(data["last_joystick_can_id"]) if "last_joystick_can_id" in data else None,
        last_pedal_can_id=int(data["last_pedal_can_id"]) if "last_pedal_can_id" in data else None,
        lh=_joystick_from_json(dict(joy.get("lh", {}))),
        rh=_joystick_from_json(dict(joy.get("rh", {}))),
        pedal_lh=_pedal_from_json(dict(pedal.get("lh", {}))),
        pedal_rh=_pedal_from_json(dict(pedal.get("rh", {}))),
        ain={str(k): int(v) for k, v in dict(data.get("ain", {})).items()},
        din={str(k): bool(v) for k, v in dict(data.get("din", {})).items()},
    )


def parse_json_line(line: str) -> tuple[int, DigInputReport | DeviceResponse] | None:
    try:
        obj = json.loads(line)
    except json.JSONDecodeError:
        return None

    if not isinstance(obj, dict):
        return None

    if obj.get("type") == "input_report":
        return (PKT_REPORT, parse_input_report_obj(obj))

    if "result" in obj:
        return (PKT_RESPONSE, DeviceResponse(payload=obj))

    return None


def parse_serial_line(line: str) -> tuple[int, MainPacket | AuxPacket | DigInputReport | DeviceResponse] | None:
    if not line:
        return None
    if line.lstrip().startswith("{"):
        return parse_json_line(line)
    return parse_text_line(line)


# ═══════════════════════════════════════════════════════
#  포맷팅 (콘솔 출력용)
# ═══════════════════════════════════════════════════════

def format_main(pkt: MainPacket) -> str:
    x, y, b = pkt.x, pkt.y, pkt.buttons
    return (
        f"MAIN  X={x.position:3d}({x.signed:+4d}) Y={y.position:3d}({y.signed:+4d})  "
        f"B1={b.btn1} B2={b.btn2} B3={b.btn3} B4={b.btn4}  seq={pkt.seq}"
    )


def format_aux(pkt: AuxPacket) -> str:
    x = pkt.x
    return f"AUX   X={x.position:3d}({x.signed:+4d})  seq={pkt.seq}"


def _format_joystick(label: str, report: JoystickReport) -> str:
    main = report.main
    aux = report.aux
    main_text = (
        f"main=Y X={main.x.signed:+4d} Y={main.y.signed:+4d}"
        if main.valid
        else "main=-"
    )
    aux_text = (
        f"aux=Y X={aux.x.signed:+4d}"
        if aux.valid
        else "aux=-"
    )
    return f"{label}[sa=0x{report.sa:02X} {main_text} {aux_text}]"


def _format_pedal(label: str, report: PedalReport) -> str:
    if not report.has_payload:
        expected = f"exp=0x{report.expected_sa:02X}" if report.expected_sa else "exp=-"
        return f"{label}[{expected} -]"
    sa_text = f"sa=0x{report.sa:02X}" if report.sa is not None else "sa=-"
    age_text = "-" if report.age_ms is None else f"{report.age_ms}ms"
    fresh_text = "Y" if report.fresh else "N"
    data_text = report.hex_bytes if report.hex_bytes else "-"
    return (
        f"{label}[{sa_text} age={age_text} fresh={fresh_text} "
        f"A2={report.axis_2.signed:+4d} A1={report.axis_1.signed:+4d} "
        f"data={data_text}]"
    )


def format_report(report: DigInputReport) -> str:
    din_active = [name for name, active in sorted(report.din.items()) if active]
    ain_text = " ".join(f"{name}={value}" for name, value in sorted(report.ain.items()))
    din_text = ",".join(din_active) if din_active else "-"
    last_can_text = (
        f"0x{report.last_can_id:X}" if report.last_can_id is not None else "-"
    )
    last_joy_can_text = (
        f"0x{report.last_joystick_can_id:X}" if report.last_joystick_can_id is not None else "-"
    )
    last_pedal_can_text = (
        f"0x{report.last_pedal_can_id:X}" if report.last_pedal_can_id is not None else "-"
    )
    can_idle_text = "-" if report.can_rx_idle_ms is None else f"{report.can_rx_idle_ms}ms"
    joy_idle_text = "-" if report.joystick_rx_idle_ms is None else f"{report.joystick_rx_idle_ms}ms"
    pedal_idle_text = "-" if report.pedal_rx_idle_ms is None else f"{report.pedal_rx_idle_ms}ms"
    primary_pedal = report.primary_pedal
    secondary_pedal = report.pedal_rh if primary_pedal is report.pedal_lh else report.pedal_lh
    secondary_text = (
        f" {_format_pedal('PED2', secondary_pedal)}"
        if secondary_pedal.valid or secondary_pedal.sa is not None or secondary_pedal.has_payload
        else ""
    )
    return (
        f"REPORT stream={'ON' if report.streaming else 'OFF'} "
        f"can={'OK' if report.can_ready else 'FAIL'} upd={'Y' if report.can_updated else '-'} "
        f"joy_upd={'Y' if report.joystick_updated else '-'} "
        f"ped_upd={'Y' if report.pedal_updated else '-'} "
        f"last={last_can_text} joy_last={last_joy_can_text} ped_last={last_pedal_can_text} "
        f"idle={can_idle_text} joy_idle={joy_idle_text} ped_idle={pedal_idle_text} "
        f"cnt={report.can_frame_count} joy_cnt={report.joystick_frame_count} ped_cnt={report.pedal_frame_count} "
        f"{_format_joystick('LH', report.lh)} "
        f"{_format_joystick('RH', report.rh)} "
        f"{_format_pedal('PEDU', primary_pedal)}"
        f"{secondary_text} "
        f"AIN[{ain_text}] DIN[{din_text}]"
    )


def format_response(resp: DeviceResponse) -> str:
    return json.dumps(resp.payload, ensure_ascii=False, separators=(",", ":"))
