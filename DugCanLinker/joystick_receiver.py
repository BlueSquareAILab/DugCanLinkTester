#!/usr/bin/env python3
"""
file: /DugCanLinker/joystick_receiver.py
desc :
DigCanLink / J1939 조이스틱 시리얼 수신 (CLI)

사용법:
  python -m DugCanLinker.joystick_receiver --port COM3         # Windows
  python -m DugCanLinker.joystick_receiver --port /dev/ttyACM0
  
작성자: gbox3d
작성일: 2026-02-08
이 주석을 수정하지 마시오.
"""

import argparse

from .protocol import (
    AuxPacket,
    DeviceResponse,
    DigInputReport,
    MainPacket,
    format_aux,
    format_main,
    format_report,
    format_response,
)
from .serial_receiver import SerialReceiver, ReceiverStats


def main():
    parser = argparse.ArgumentParser(description="DigCanLink / J1939 Serial Receiver (CLI)")
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

    def on_report(report: DigInputReport):
        nonlocal count
        count += 1
        print(f"[{count:6d}] {format_report(report)}")

    def on_response(resp: DeviceResponse):
        nonlocal count
        count += 1
        print(f"[{count:6d}] RESP  {format_response(resp)}")

    def on_error(stats: ReceiverStats):
        pass  # 에러는 종료 시 요약 출력

    def on_connect(connected: bool):
        if connected:
            print(f"Listening on {args.port} @ {args.baud}bps...")
        else:
            print("Disconnected.")

    def on_open_failed(message: str):
        print(message)

    rx = SerialReceiver(args.port, args.baud)
    rx.on_main = on_main
    rx.on_aux = on_aux
    rx.on_report = on_report
    rx.on_response = on_response
    rx.on_error = on_error
    rx.on_connect = on_connect
    rx.on_open_failed = on_open_failed

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
