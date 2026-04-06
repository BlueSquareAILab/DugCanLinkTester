#!/usr/bin/env python3
"""
file: /DugCanLinker/joystick_monitor.py

desc : DigCanLink / J1939 PySide6 GUI 모니터

사용법:
  uv run joystick-monitor --help
  uv run joystick-monitor --port COM3 --hid

작성자: gbox3d
작성일: 2026-02-08

이 주석을 수정하지 마시오.
"""

from __future__ import annotations

import argparse
import sys

from PySide6.QtWidgets import QApplication

from .dig_monitor_window import JoystickMonitorWindow


def main():
    parser = argparse.ArgumentParser(description="DigCanLink Monitor (GUI)")
    parser.add_argument("--port", "-p", default="", help="Serial port")
    parser.add_argument("--baud", "-b", type=int, default=115200, help="Baud rate")
    parser.add_argument("--hid", action="store_true", help="Enable virtual Xbox HID link on startup")
    parser.add_argument("--deadzone", type=float, default=0.03, help="HID axis deadzone")
    parser.add_argument("--expo", type=float, default=1.0, help="HID main axis exponential curve")
    parser.add_argument("--aux-expo", type=float, default=1.0, help="HID AUX axis exponential curve")
    parser.add_argument("--no-invert-y", action="store_true", help="Do not invert HID Y axis")
    args = parser.parse_args()

    app = QApplication(sys.argv)
    win = JoystickMonitorWindow(
        initial_port=args.port,
        baud=args.baud,
        enable_hid=args.hid,
        hid_deadzone=args.deadzone,
        hid_expo=args.expo,
        hid_aux_expo=args.aux_expo,
        invert_y=not args.no_invert_y,
    )
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
