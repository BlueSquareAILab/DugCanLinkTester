"""
dugcanlinktester — DigCanLink 시리얼 모니터 / 시뮬레이터 연동 도구

주요 모듈:
  protocol        — JSON/legacy 텍스트 파싱, 데이터 클래스, 포맷팅
  serial_receiver — 라인 파서 + 시리얼 수신기 (I/O)
"""

from .protocol import (
    # 상수
    SYNC1, SYNC2, PKT_MAIN, PKT_AUX, PKT_REPORT, PKT_RESPONSE,
    MAIN_PAYLOAD_LEN, AUX_PAYLOAD_LEN,
    # 데이터 클래스
    AxisState, ButtonState, MainPacket, AuxPacket,
    ReportMainState, ReportAuxState, JoystickReport, PedalReport, DigInputReport, DeviceResponse,
    # 함수
    parse_axis, parse_main_payload, parse_aux_payload,
    xor_checksum, verify_packet,
    format_main, format_aux, format_report, format_response,
    parse_text_line, parse_json_line, parse_serial_line, parse_input_report_obj,
)

from .serial_receiver import (
    PacketParser, TextLineParser, SerialReceiver, ReceiverStats,
)
from .vortex_hid import (
    AxisMapper, VortexHID,
)

__all__ = [
    "SYNC1", "SYNC2", "PKT_MAIN", "PKT_AUX", "PKT_REPORT", "PKT_RESPONSE",
    "MAIN_PAYLOAD_LEN", "AUX_PAYLOAD_LEN",
    "AxisState", "ButtonState", "MainPacket", "AuxPacket",
    "ReportMainState", "ReportAuxState", "JoystickReport", "PedalReport", "DigInputReport", "DeviceResponse",
    "parse_axis", "parse_main_payload", "parse_aux_payload",
    "xor_checksum", "verify_packet",
    "format_main", "format_aux", "format_report", "format_response",
    "PacketParser", "TextLineParser", "SerialReceiver", "ReceiverStats",
    "parse_text_line", "parse_json_line", "parse_serial_line", "parse_input_report_obj",
    "AxisMapper", "VortexHID",
]
