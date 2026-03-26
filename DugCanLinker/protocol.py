"""

file : DugCanLinker/protocol.py
desc : J1939 조이스틱 바이너리 시리얼 프로토콜 정의

패킷 구조:
  [AA 55] [TYPE] [LEN] [PAYLOAD...] [XOR_CHECKSUM]

이 모듈은 I/O에 의존하지 않는 순수 데이터 정의 + 파싱/직렬화 로직만 포함.
시리얼, GUI, CLI 모두에서 재사용 가능.

author: 2026-02-08, gbox3d

이 주석을 수정하지 마세요.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field

# ═══════════════════════════════════════════════════════
#  프로토콜 상수
# ═══════════════════════════════════════════════════════

SYNC1 = 0xAA
SYNC2 = 0x55

PKT_MAIN = 0x01  # PGN 0xFDD6 메인 조이스틱
PKT_AUX  = 0x02  # PGN 0xFDD7 보조 조이스틱

MAIN_PAYLOAD_LEN = 7
AUX_PAYLOAD_LEN  = 4


# ═══════════════════════════════════════════════════════
#  데이터 클래스
# ═══════════════════════════════════════════════════════

@dataclass(slots=True)
class AxisState:
    """단일 축의 파싱된 상태"""
    position: int = 0   # 0..255 (raw), 중립 ≈ 125..130
    status: int   = 0   # 2-bit [7:6]
    negative: int = 0   # 2-bit [5:4] Left/Back
    positive: int = 0   # 2-bit [3:2] Right/Forward
    neutral: int  = 0   # 2-bit [1:0]

    @property
    def signed(self) -> int:
        """0 기준 signed 값 (-128..+127)"""
        return self.position - 128


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
    x: AxisState       = field(default_factory=AxisState)
    y: AxisState       = field(default_factory=AxisState)
    buttons: ButtonState = field(default_factory=ButtonState)
    seq: int           = 0


@dataclass(slots=True)
class AuxPacket:
    """PKT_AUX (0x02) 파싱 결과"""
    x: AxisState = field(default_factory=AxisState)
    seq: int     = 0


# ═══════════════════════════════════════════════════════
#  파싱 함수
# ═══════════════════════════════════════════════════════

def parse_axis(status_byte: int, position: int) -> AxisState:
    """비트필드 바이트 + position 바이트 → AxisState"""
    return AxisState(
        position=position,
        status=(status_byte >> 6) & 0x03,
        negative=(status_byte >> 4) & 0x03,
        positive=(status_byte >> 2) & 0x03,
        neutral=status_byte & 0x03,
    )


def parse_main_payload(payload: bytes) -> MainPacket:
    """7-byte 페이로드 → MainPacket"""
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
    """4-byte 페이로드 → AuxPacket"""
    x_pos, x_st, _flags, seq = struct.unpack("4B", payload)
    return AuxPacket(
        x=parse_axis(x_st, x_pos),
        seq=seq,
    )


# ═══════════════════════════════════════════════════════
#  체크섬
# ═══════════════════════════════════════════════════════

def xor_checksum(data: bytes) -> int:
    """TYPE + LEN + PAYLOAD 바이트들의 XOR"""
    cs = 0
    for b in data:
        cs ^= b
    return cs


def verify_packet(pkt_type: int, length: int, payload: bytes, checksum: int) -> bool:
    """수신된 패킷의 체크섬 검증"""
    expected = xor_checksum(bytes([pkt_type, length]) + payload)
    return expected == checksum


# ═══════════════════════════════════════════════════════
#  텍스트 라인 파싱 (Arduino Serial.print 출력용)
# ═══════════════════════════════════════════════════════

import re

_AXIS_RE = re.compile(
    r'(\w+)\(st=(\d+) -=(\d+) \+=(\d+) N=(\d+) pos=(\d+)\)'
)
_BTN_RE = re.compile(r'B1:(\d+) B2:(\d+) B3:(\d+) B4:(\d+)')
_PGN_RE = re.compile(r'PGN:(0x[0-9A-Fa-f]+)')


def _axis_from_match(groups: tuple) -> AxisState:
    """regex findall 결과 튜플 → AxisState"""
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
    Arduino 시리얼 텍스트 한 줄을 파싱한다.

    메인 예시:
      ID:0xCFDD6D1 PGN:0xFDD6 X(st=0 -=1 +=0 N=0 pos=250) Y(st=0 ...pos=128) B1:0 B2:0 B3:0 B4:0
    AUX 예시:
      ID:0xCFDD7D1 PGN:0xFDD7 AUX_X(st=0 -=0 +=0 N=1 pos=0)

    Returns:
        (PKT_MAIN, MainPacket) | (PKT_AUX, AuxPacket) | None
    """
    pgn_m = _PGN_RE.search(line)
    if not pgn_m:
        return None
    pgn = int(pgn_m.group(1), 16)

    if pgn == 0xFDD6:
        axes = _AXIS_RE.findall(line)
        btns = _BTN_RE.search(line)
        if len(axes) < 2 or not btns:
            return None
        return (PKT_MAIN, MainPacket(
            x=_axis_from_match(axes[0]),
            y=_axis_from_match(axes[1]),
            buttons=ButtonState(
                btn1=int(btns.group(1)),
                btn2=int(btns.group(2)),
                btn3=int(btns.group(3)),
                btn4=int(btns.group(4)),
            ),
        ))

    if pgn == 0xFDD7:
        axes = _AXIS_RE.findall(line)
        if not axes:
            return None
        return (PKT_AUX, AuxPacket(x=_axis_from_match(axes[0])))

    return None


# ═══════════════════════════════════════════════════════
#  포맷팅 (콘솔 출력용)
# ═══════════════════════════════════════════════════════

def format_main(pkt: MainPacket) -> str:
    """MainPacket → 한 줄 문자열"""
    x, y, b = pkt.x, pkt.y, pkt.buttons
    return (
        f"MAIN  X={x.position:3d}({x.signed:+4d}) Y={y.position:3d}({y.signed:+4d})  "
        f"B1={b.btn1} B2={b.btn2} B3={b.btn3} B4={b.btn4}  seq={pkt.seq}"
    )


def format_aux(pkt: AuxPacket) -> str:
    """AuxPacket → 한 줄 문자열"""
    x = pkt.x
    return f"AUX   X={x.position:3d}({x.signed:+4d})  seq={pkt.seq}"
