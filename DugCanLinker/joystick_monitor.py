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
    args = parser.parse_args()

    app = QApplication(sys.argv)
    win = JoystickMonitorWindow(
        initial_port=args.port,
        baud=args.baud,
    )
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
