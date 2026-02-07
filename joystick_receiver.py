#!/usr/bin/env python3
"""
joystick_receiver.py — J1939 조이스틱 바이너리 시리얼 수신 예제

패킷 구조:
  [AA 55] [TYPE] [LEN] [PAYLOAD...] [XOR_CHECKSUM]

사용법:
  python joystick_receiver.py              # 기본: /dev/ttyUSB0
  python joystick_receiver.py COM3         # Windows
  python joystick_receiver.py /dev/ttyACM0 # Linux
"""

import sys
import struct
import serial

# ─── 프로토콜 상수 ──────────────────────────────────────
SYNC1    = 0xAA
SYNC2    = 0x55
PKT_MAIN = 0x01
PKT_AUX  = 0x02

def parse_axis(status_byte: int, position: int) -> dict:
    """비트필드 바이트에서 축 상태 파싱"""
    return {
        'position': position,
        'status':   (status_byte >> 6) & 0x03,
        'negative': (status_byte >> 4) & 0x03,
        'positive': (status_byte >> 2) & 0x03,
        'neutral':  (status_byte)      & 0x03,
    }

def parse_main(payload: bytes) -> dict:
    """PKT_MAIN 페이로드 파싱 (7 bytes)"""
    x_pos, x_st, y_pos, y_st, buttons, flags, seq = struct.unpack('7B', payload)
    return {
        'type': 'MAIN',
        'x': parse_axis(x_st, x_pos),
        'y': parse_axis(y_st, y_pos),
        'buttons': {
            'btn1': (buttons >> 4) & 0x03,
            'btn2': (buttons >> 6) & 0x03,
            'btn3': (buttons)      & 0x03,
            'btn4': (buttons >> 2) & 0x03,
        },
        'seq': seq,
    }

def parse_aux(payload: bytes) -> dict:
    """PKT_AUX 페이로드 파싱 (4 bytes)"""
    x_pos, x_st, flags, seq = struct.unpack('4B', payload)
    return {
        'type': 'AUX',
        'x': parse_axis(x_st, x_pos),
        'seq': seq,
    }

def xor_checksum(data: bytes) -> int:
    cs = 0
    for b in data:
        cs ^= b
    return cs

def receive_loop(port: str, baud: int = 115200):
    """메인 수신 루프"""
    ser = serial.Serial(port, baud, timeout=1)
    print(f"Listening on {port} @ {baud}bps...")

    good = 0
    errors = 0

    try:
        while True:
            # SYNC 탐색
            b = ser.read(1)
            if not b or b[0] != SYNC1:
                continue
            b = ser.read(1)
            if not b or b[0] != SYNC2:
                continue

            # TYPE + LEN
            header = ser.read(2)
            if len(header) < 2:
                continue
            pkt_type, length = header[0], header[1]

            if length > 16:
                errors += 1
                continue

            # PAYLOAD + CHECKSUM
            rest = ser.read(length + 1)
            if len(rest) < length + 1:
                errors += 1
                continue

            payload  = rest[:length]
            checksum = rest[length]

            # 체크섬 검증
            expected = xor_checksum(bytes([pkt_type, length]) + payload)
            if expected != checksum:
                errors += 1
                continue

            good += 1

            # 파싱 & 출력
            if pkt_type == PKT_MAIN and length == 7:
                data = parse_main(payload)
                x = data['x']
                y = data['y']
                btn = data['buttons']
                print(f"[{good:6d}] MAIN  "
                      f"X={x['position']:3d} Y={y['position']:3d}  "
                      f"B1={btn['btn1']} B2={btn['btn2']} "
                      f"B3={btn['btn3']} B4={btn['btn4']}  "
                      f"seq={data['seq']}")

            elif pkt_type == PKT_AUX and length == 4:
                data = parse_aux(payload)
                x = data['x']
                print(f"[{good:6d}] AUX   "
                      f"X={x['position']:3d}  seq={data['seq']}")

    except KeyboardInterrupt:
        print(f"\nStopped. good={good} errors={errors}")
    finally:
        ser.close()

if __name__ == '__main__':
    port = sys.argv[1] if len(sys.argv) > 1 else '/dev/ttyUSB0'
    receive_loop(port)
