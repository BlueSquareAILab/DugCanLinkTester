"""

file : DugCanLinker/serial_receiver.py
desc :
serial_receiver.py — 바이트 스트림 패킷 파서 + 시리얼 수신기

두 가지 레이어:
  1. PacketParser    — 순수 상태머신, 바이트를 feed하면 패킷 반환 (I/O 무관)
  2. SerialReceiver  — pyserial 래핑, 콜백/스레드 방식 수신

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
    SYNC1, SYNC2,
    PKT_MAIN, PKT_AUX,
    MAIN_PAYLOAD_LEN, AUX_PAYLOAD_LEN,
    MainPacket, AuxPacket,
    parse_main_payload, parse_aux_payload,
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
    """
    바이트를 한 개씩 feed()하면 완성된 패킷을 반환하는 상태머신.

    어떤 I/O 소스에서든 사용 가능 (시리얼, TCP, 파일, 테스트 등).

    사용법::

        parser = PacketParser()
        for byte in stream:
            result = parser.feed(byte)
            if result is not None:
                pkt_type, packet = result
                # packet은 MainPacket | AuxPacket
    """

    _WAIT_SYNC1    = 0
    _WAIT_SYNC2    = 1
    _WAIT_TYPE     = 2
    _WAIT_LEN      = 3
    _WAIT_PAYLOAD  = 4
    _WAIT_CHECKSUM = 5

    def __init__(self):
        self.stats = ReceiverStats()
        self._state = self._WAIT_SYNC1
        self._type = 0
        self._len = 0
        self._buf = bytearray()
        self._idx = 0

    def reset(self):
        """상태 초기화 (에러 카운트는 유지)"""
        self._state = self._WAIT_SYNC1
        self._buf.clear()
        self._idx = 0

    def feed(self, b: int) -> tuple[int, MainPacket | AuxPacket] | None:
        """
        바이트 1개를 공급한다.

        Returns:
            None — 아직 패킷 미완성
            (pkt_type, packet) — 유효한 패킷 완성 시
        """
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
#  SerialReceiver — pyserial + 스레드 래핑
# ═══════════════════════════════════════════════════════

class SerialReceiver:
    """
    시리얼 포트에서 패킷을 수신하여 콜백으로 전달하는 스레드 기반 수신기.

    콜백 시그니처::

        on_main(pkt: MainPacket) -> None
        on_aux(pkt: AuxPacket) -> None
        on_error(stats: ReceiverStats) -> None
        on_connect(connected: bool) -> None

    사용법::

        rx = SerialReceiver("COM3")
        rx.on_main = lambda pkt: print(pkt)
        rx.start()
        ...
        rx.stop()
    """

    def __init__(self, port: str, baud: int = 115200):
        self.port = port
        self.baud = baud

        # 콜백 (None이면 무시)
        self.on_main: Callable[[MainPacket], None] | None = None
        self.on_aux: Callable[[AuxPacket], None] | None = None
        self.on_error: Callable[[ReceiverStats], None] | None = None
        self.on_connect: Callable[[bool], None] | None = None

        self._parser = PacketParser()
        self._thread: threading.Thread | None = None
        self._running = False

    @property
    def stats(self) -> ReceiverStats:
        return self._parser.stats

    @property
    def is_running(self) -> bool:
        return self._running and self._thread is not None and self._thread.is_alive()

    def start(self):
        """수신 스레드 시작"""
        if self.is_running:
            return
        self._running = True
        self._parser = PacketParser()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 2.0):
        """수신 스레드 정지"""
        self._running = False
        if self._thread:
            self._thread.join(timeout)
            self._thread = None

    def _run_loop(self):
        try:
            ser = serial.Serial(self.port, self.baud, timeout=0.1)
        except serial.SerialException as e:
            print(f"Serial open failed: {e}")
            if self.on_connect:
                self.on_connect(False)
            return

        if self.on_connect:
            self.on_connect(True)

        try:
            while self._running:
                chunk = ser.read(64)  # 한번에 여러 바이트 읽기 (효율)
                for b in chunk:
                    result = self._parser.feed(b)
                    if result is None:
                        continue

                    pkt_type, packet = result

                    if pkt_type == PKT_MAIN and self.on_main:
                        self.on_main(packet)
                    elif pkt_type == PKT_AUX and self.on_aux:
                        self.on_aux(packet)

                    if self._parser.stats.errors > 0 and self.on_error:
                        self.on_error(self._parser.stats)

        except serial.SerialException:
            pass
        finally:
            ser.close()
            if self.on_connect:
                self.on_connect(False)
