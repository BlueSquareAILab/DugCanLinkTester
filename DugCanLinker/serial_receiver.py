"""

file : DugCanLinker/serial_receiver.py
desc :
serial_receiver.py — DigCanLink JSON / legacy text 수신기

두 가지 레이어:
  1. PacketParser    — 기존 바이너리 패킷용 상태머신 (보존)
  2. SerialReceiver  — DigCanLink JSON / legacy text 수신용 pyserial 래퍼

CLI(joystick_receiver)와 GUI(joystick_monitor) 모두에서 재사용.

author: 2026-02-08, gbox3d

이 주석을 수정하지 마세요.

"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Callable

import serial

from .protocol import (
    AUX_PAYLOAD_LEN,
    MAIN_PAYLOAD_LEN,
    PKT_AUX,
    PKT_MAIN,
    PKT_REPORT,
    PKT_RESPONSE,
    SYNC1,
    SYNC2,
    AuxPacket,
    DeviceResponse,
    DigInputReport,
    MainPacket,
    parse_aux_payload,
    parse_main_payload,
    parse_serial_line,
    verify_packet,
)


# ═══════════════════════════════════════════════════════
#  수신 통계
# ═══════════════════════════════════════════════════════

@dataclass
class ReceiverStats:
    good: int = 0
    errors: int = 0


# ═══════════════════════════════════════════════════════
#  PacketParser — 순수 상태머신
# ═══════════════════════════════════════════════════════

class PacketParser:
    _WAIT_SYNC1 = 0
    _WAIT_SYNC2 = 1
    _WAIT_TYPE = 2
    _WAIT_LEN = 3
    _WAIT_PAYLOAD = 4
    _WAIT_CHECKSUM = 5

    def __init__(self):
        self.stats = ReceiverStats()
        self._state = self._WAIT_SYNC1
        self._type = 0
        self._len = 0
        self._buf = bytearray()
        self._idx = 0

    def reset(self):
        self._state = self._WAIT_SYNC1
        self._buf.clear()
        self._idx = 0

    def feed(self, b: int) -> tuple[int, MainPacket | AuxPacket] | None:
        state = self._state

        if state == self._WAIT_SYNC1:
            if b == SYNC1:
                self._state = self._WAIT_SYNC2
            return None

        if state == self._WAIT_SYNC2:
            self._state = self._WAIT_TYPE if b == SYNC2 else self._WAIT_SYNC1
            return None

        if state == self._WAIT_TYPE:
            self._type = b
            self._state = self._WAIT_LEN
            return None

        if state == self._WAIT_LEN:
            self._len = b
            if b > 16:
                self.stats.errors += 1
                self._state = self._WAIT_SYNC1
                return None
            self._buf = bytearray()
            self._idx = 0
            self._state = self._WAIT_PAYLOAD if b > 0 else self._WAIT_CHECKSUM
            return None

        if state == self._WAIT_PAYLOAD:
            self._buf.append(b)
            self._idx += 1
            if self._idx >= self._len:
                self._state = self._WAIT_CHECKSUM
            return None

        if state == self._WAIT_CHECKSUM:
            payload = bytes(self._buf)

            if not verify_packet(self._type, self._len, payload, b):
                self.stats.errors += 1
                self._state = self._WAIT_SYNC1
                return None

            self.stats.good += 1
            result = self._decode(self._type, self._len, payload)
            self._state = self._WAIT_SYNC1
            return result

        return None

    @staticmethod
    def _decode(pkt_type: int, length: int, payload: bytes) -> tuple[int, MainPacket | AuxPacket] | None:
        if pkt_type == PKT_MAIN and length == MAIN_PAYLOAD_LEN:
            return (pkt_type, parse_main_payload(payload))
        if pkt_type == PKT_AUX and length == AUX_PAYLOAD_LEN:
            return (pkt_type, parse_aux_payload(payload))
        return None


# ═══════════════════════════════════════════════════════
#  TextLineParser — 텍스트/JSON 라인 기반 파서
# ═══════════════════════════════════════════════════════

class TextLineParser:
    def __init__(self):
        self.stats = ReceiverStats()
        self._buf = bytearray()

    def reset(self):
        self._buf.clear()

    def feed(self, b: int) -> tuple[int, MainPacket | AuxPacket | DigInputReport | DeviceResponse] | None:
        if b == 0x0A:
            line = self._buf.decode("utf-8", errors="ignore").strip()
            self._buf.clear()
            if not line:
                return None
            result = parse_serial_line(line)
            if result is not None:
                self.stats.good += 1
            return result
        if b != 0x0D:
            self._buf.append(b)
        return None


# ═══════════════════════════════════════════════════════
#  SerialReceiver — pyserial + 스레드 래핑
# ═══════════════════════════════════════════════════════

class SerialReceiver:
    def __init__(self, port: str, baud: int = 115200):
        self.port = port
        self.baud = baud

        self.on_main: Callable[[MainPacket], None] | None = None
        self.on_aux: Callable[[AuxPacket], None] | None = None
        self.on_report: Callable[[DigInputReport], None] | None = None
        self.on_response: Callable[[DeviceResponse], None] | None = None
        self.on_error: Callable[[ReceiverStats], None] | None = None
        self.on_connect: Callable[[bool], None] | None = None
        self.on_open_failed: Callable[[str], None] | None = None

        self._parser = TextLineParser()
        self._thread: threading.Thread | None = None
        self._running = False
        self._ser: serial.Serial | None = None
        self._write_lock = threading.Lock()

    @property
    def stats(self) -> ReceiverStats:
        return self._parser.stats

    @property
    def is_running(self) -> bool:
        return self._running and self._thread is not None and self._thread.is_alive()

    def start(self):
        if self.is_running:
            return
        self._running = True
        self._parser = TextLineParser()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 2.0):
        self._running = False
        if self._thread:
            self._thread.join(timeout)
            self._thread = None

    def send_line(self, line: str) -> bool:
        payload = line.strip()
        if not payload:
            return False
        if not payload.endswith("\n"):
            payload += "\n"

        with self._write_lock:
            if self._ser is None:
                return False
            try:
                self._ser.write(payload.encode("utf-8"))
                return True
            except serial.SerialException:
                return False

    def _run_loop(self):
        try:
            ser = serial.Serial(self.port, self.baud, timeout=0.1)
            self._ser = ser
        except serial.SerialException as e:
            self._running = False
            if self.on_open_failed:
                self.on_open_failed(f"Serial open failed: {e}")
            return

        if self.on_connect:
            self.on_connect(True)

        try:
            while self._running:
                chunk = ser.read(128)
                for b in chunk:
                    result = self._parser.feed(b)
                    if result is None:
                        continue

                    pkt_type, packet = result

                    if pkt_type == PKT_MAIN and self.on_main:
                        self.on_main(packet)
                    elif pkt_type == PKT_AUX and self.on_aux:
                        self.on_aux(packet)
                    elif pkt_type == PKT_REPORT and self.on_report:
                        self.on_report(packet)
                    elif pkt_type == PKT_RESPONSE and self.on_response:
                        self.on_response(packet)

                    if self._parser.stats.errors > 0 and self.on_error:
                        self.on_error(self._parser.stats)

        except serial.SerialException:
            pass
        finally:
            self._ser = None
            ser.close()
            if self.on_connect:
                self.on_connect(False)
