#!/usr/bin/env python3
"""
DigCanLink simulator integration reference.

권장 사용:
  uv run python .\examples\simulator_receiver_minimal.py --port COM3

이 예제는 SerialReceiver를 사용해 DigCanLink의 JSON input_report를 수신하고,
외부 시뮬레이터가 재사용하기 쉬운 형태로 stdout에 JSON 라인을 출력한다.
실제 납품처 연동 시에는 on_report() 안의 print() 부분을 시뮬레이터 API 호출로 교체하면 된다.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from DugCanLinker import DeviceResponse, DigInputReport, SerialReceiver


def axis_to_dict(axis) -> dict[str, int]:
    return {
        "raw": axis.position,
        "signed": axis.signed,
        "status": axis.status,
        "negative": axis.negative,
        "positive": axis.positive,
        "neutral": axis.neutral,
    }


def report_to_dict(report: DigInputReport) -> dict:
    def main_to_dict(main) -> dict:
        return {
            "valid": main.valid,
            "age_ms": main.age_ms,
            "x": axis_to_dict(main.x),
            "y": axis_to_dict(main.y),
            "buttons": {
                "b1": main.buttons.btn1,
                "b2": main.buttons.btn2,
                "b3": main.buttons.btn3,
                "b4": main.buttons.btn4,
            },
        }

    def aux_to_dict(aux) -> dict:
        return {
            "valid": aux.valid,
            "age_ms": aux.age_ms,
            "x": axis_to_dict(aux.x),
        }

    def pedal_to_dict(pedal) -> dict:
        return {
            "name": pedal.name,
            "expected_sa": pedal.expected_sa,
            "sa": pedal.sa,
            "valid": pedal.valid,
            "age_ms": pedal.age_ms,
            "pgn": pedal.pgn,
            "can_id": pedal.can_id,
            "len": pedal.length,
            "data": list(pedal.data),
        }

    return {
        "streaming": report.streaming,
        "interval_ms": report.interval_ms,
        "can_ready": report.can_ready,
        "can_updated": report.can_updated,
        "joystick_updated": report.joystick_updated,
        "pedal_updated": report.pedal_updated,
        "can_frame_count": report.can_frame_count,
        "joystick_frame_count": report.joystick_frame_count,
        "pedal_frame_count": report.pedal_frame_count,
        "can_rx_idle_ms": report.can_rx_idle_ms,
        "joystick_rx_idle_ms": report.joystick_rx_idle_ms,
        "pedal_rx_idle_ms": report.pedal_rx_idle_ms,
        "last_can_id": report.last_can_id,
        "last_joystick_can_id": report.last_joystick_can_id,
        "last_pedal_can_id": report.last_pedal_can_id,
        "lh": {
            "sa": report.lh.sa,
            "main": main_to_dict(report.lh.main),
            "aux": aux_to_dict(report.lh.aux),
        },
        "rh": {
            "sa": report.rh.sa,
            "main": main_to_dict(report.rh.main),
            "aux": aux_to_dict(report.rh.aux),
        },
        "pedal": {
            "lh": pedal_to_dict(report.pedal_lh),
            "rh": pedal_to_dict(report.pedal_rh),
        },
        "ain": dict(report.ain),
        "din": dict(report.din),
    }


def main():
    parser = argparse.ArgumentParser(description="DigCanLink simulator integration reference")
    parser.add_argument("--port", "-p", required=True, help="Serial port (required, e.g. COM3)")
    parser.add_argument("--baud", "-b", type=int, default=115200, help="Baud rate")
    parser.add_argument("--no-about", action="store_true", help="Do not send 'about' after connect")
    parser.add_argument("--no-start", action="store_true", help="Do not send 'start' after connect")
    args = parser.parse_args()

    rx = SerialReceiver(args.port, args.baud)

    def emit(obj: dict):
        print(json.dumps(obj, ensure_ascii=False), flush=True)

    def on_connect(connected: bool):
        emit({
            "type": "bridge_status",
            "connected": connected,
            "port": args.port,
            "baud": args.baud,
            "ts_ms": int(time.time() * 1000),
        })
        if not connected:
            return
        if not args.no_about:
            rx.send_line("about")
        if not args.no_start:
            rx.send_line("start")

    def on_report(report: DigInputReport):
        emit({
            "type": "sim_input",
            "source": "DigCanLink",
            "ts_ms": int(time.time() * 1000),
            "data": report_to_dict(report),
        })

    def on_response(resp: DeviceResponse):
        emit({
            "type": "device_response",
            "ts_ms": int(time.time() * 1000),
            "payload": resp.payload,
        })

    rx.on_connect = on_connect
    rx.on_report = on_report
    rx.on_response = on_response
    rx.start()

    try:
        while rx.is_running:
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        rx.stop()


if __name__ == "__main__":
    main()
