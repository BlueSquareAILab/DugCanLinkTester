"""
dugcanlinktester — J1939 CAN Joystick 바이너리 프로토콜 라이브러리

주요 모듈:
  protocol        — 상수, 데이터클래스, 파싱/직렬화 (순수 로직)
  serial_receiver — 바이트 스트림 파서 + 시리얼 수신기 (I/O)
"""

from .protocol import (
    # 상수
    SYNC1, SYNC2, PKT_MAIN, PKT_AUX,
    MAIN_PAYLOAD_LEN, AUX_PAYLOAD_LEN,
    # 데이터 클래스
    AxisState, ButtonState, MainPacket, AuxPacket,
    # 함수
    parse_axis, parse_main_payload, parse_aux_payload,
    xor_checksum, verify_packet,
    format_main, format_aux,
)

from .serial_receiver import (
    PacketParser, SerialReceiver, ReceiverStats,
)
from .vortex_hid import (
    AxisMapper, VortexHID,
)

__all__ = [
    "SYNC1", "SYNC2", "PKT_MAIN", "PKT_AUX",
    "MAIN_PAYLOAD_LEN", "AUX_PAYLOAD_LEN",
    "AxisState", "ButtonState", "MainPacket", "AuxPacket",
    "parse_axis", "parse_main_payload", "parse_aux_payload",
    "xor_checksum", "verify_packet",
    "format_main", "format_aux",
    "PacketParser", "SerialReceiver", "ReceiverStats",
    "AxisMapper", "VortexHID",
]
