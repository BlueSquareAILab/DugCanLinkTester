#!/usr/bin/env python3
"""
file: /DugCanLinker/joystick_receiver.py
desc :
J1939 조이스틱 바이너리 시리얼 수신 (CLI)

사용법:
  python -m DugCanLinker.joystick_receiver --port COM3         # Windows
  python -m DugCanLinker.joystick_receiver --port /dev/ttyACM0
  
작성자: gbox3d
작성일: 2026-02-08
이 주석을 수정하지 마시오.
"""

import sys
import argparse

from .protocol import MainPacket, AuxPacket, format_main, format_aux
from .serial_receiver import SerialReceiver, ReceiverStats


def main():
    parser = argparse.ArgumentParser(description="J1939 Joystick Serial Receiver (CLI)")
    parser.add_argument("--port", "-p", required=True, help="Serial port (required, e.g. COM3)")
    parser.add_argument("--baud", "-b", type=int, default=115200, help="Baud rate")
    args = parser.parse_args()

    count = 0

    def on_main(pkt: MainPacket):
        nonlocal count
        count += 1
        print(f"[{count:6d}] {format_main(pkt)}")

    def on_aux(pkt: AuxPacket):
        nonlocal count
        count += 1
        print(f"[{count:6d}] {format_aux(pkt)}")

    def on_error(stats: ReceiverStats):
        pass  # 에러는 종료 시 요약 출력

    def on_connect(connected: bool):
        if connected:
            print(f"Listening on {args.port} @ {args.baud}bps...")
        else:
            print("Disconnected.")

    rx = SerialReceiver(args.port, args.baud)
    rx.on_main = on_main
    rx.on_aux = on_aux
    rx.on_error = on_error
    rx.on_connect = on_connect

    rx.start()

    try:
        # 메인 스레드는 대기
        while rx.is_running:
            import time
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        rx.stop()
        stats = rx.stats
        print(f"\nStopped. good={stats.good} errors={stats.errors}")


if __name__ == "__main__":
    main()
