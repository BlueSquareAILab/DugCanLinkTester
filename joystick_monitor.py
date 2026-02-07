#!/usr/bin/env python3
"""
joystick_monitor.py — J1939 조이스틱 바이너리 시리얼 수신 + PySide6 GUI

기능:
  - X/Y/AUX 아날로그 축: 실시간 스크롤 그래프 (0 기준 ±128)
  - Status 값: 숫자 표시 (0,1,2,3)
  - Button 3,4: LED 인디케이터

사용법:
  python joystick_monitor.py                   # 기본: /dev/ttyUSB0
  python joystick_monitor.py --port COM3       # Windows
  python joystick_monitor.py --port /dev/ttyACM0 --baud 115200
"""

import sys
import argparse
import struct
from collections import deque

from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QPainter, QColor, QPen, QFont, QBrush, QPainterPath
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QGroupBox, QGridLayout, QComboBox, QPushButton,
    QFrame, QSizePolicy,
)

import serial
import serial.tools.list_ports

# ═══════════════════════════════════════════════════════
#  프로토콜 파서 (joystick_receiver.py 에서 가져옴)
# ═══════════════════════════════════════════════════════

SYNC1    = 0xAA
SYNC2    = 0x55
PKT_MAIN = 0x01
PKT_AUX  = 0x02


def _parse_axis(status_byte: int, position: int) -> dict:
    return {
        "position": position,
        "status":   (status_byte >> 6) & 0x03,
        "negative": (status_byte >> 4) & 0x03,
        "positive": (status_byte >> 2) & 0x03,
        "neutral":  (status_byte)      & 0x03,
    }


def _xor_checksum(data: bytes) -> int:
    cs = 0
    for b in data:
        cs ^= b
    return cs


# ═══════════════════════════════════════════════════════
#  시리얼 수신 스레드
# ═══════════════════════════════════════════════════════

class SerialReaderThread(QThread):
    """바이너리 패킷을 수신하여 시그널로 전달"""

    main_received = Signal(dict)   # PKT_MAIN 파싱 결과
    aux_received  = Signal(dict)   # PKT_AUX  파싱 결과
    error_count   = Signal(int)    # 누적 에러 수
    connected     = Signal(bool)   # 연결 상태 변경

    def __init__(self, port: str, baud: int = 115200, parent=None):
        super().__init__(parent)
        self.port = port
        self.baud = baud
        self._running = False
        self._errors = 0

    def run(self):
        self._running = True
        try:
            ser = serial.Serial(self.port, self.baud, timeout=0.1)
            self.connected.emit(True)
        except serial.SerialException as e:
            print(f"Serial open failed: {e}")
            self.connected.emit(False)
            return

        try:
            while self._running:
                b = ser.read(1)
                if not b or b[0] != SYNC1:
                    continue
                b = ser.read(1)
                if not b or b[0] != SYNC2:
                    continue

                header = ser.read(2)
                if len(header) < 2:
                    continue
                pkt_type, length = header[0], header[1]
                if length > 16:
                    self._errors += 1
                    self.error_count.emit(self._errors)
                    continue

                rest = ser.read(length + 1)
                if len(rest) < length + 1:
                    self._errors += 1
                    self.error_count.emit(self._errors)
                    continue

                payload  = rest[:length]
                checksum = rest[length]
                expected = _xor_checksum(bytes([pkt_type, length]) + payload)
                if expected != checksum:
                    self._errors += 1
                    self.error_count.emit(self._errors)
                    continue

                if pkt_type == PKT_MAIN and length == 7:
                    x_pos, x_st, y_pos, y_st, buttons, flags, seq = struct.unpack("7B", payload)
                    data = {
                        "x": _parse_axis(x_st, x_pos),
                        "y": _parse_axis(y_st, y_pos),
                        "buttons": {
                            "btn1": (buttons >> 4) & 0x03,
                            "btn2": (buttons >> 6) & 0x03,
                            "btn3": (buttons)      & 0x03,
                            "btn4": (buttons >> 2) & 0x03,
                        },
                        "seq": seq,
                    }
                    self.main_received.emit(data)

                elif pkt_type == PKT_AUX and length == 4:
                    x_pos, x_st, flags, seq = struct.unpack("4B", payload)
                    data = {
                        "x": _parse_axis(x_st, x_pos),
                        "seq": seq,
                    }
                    self.aux_received.emit(data)

        except serial.SerialException:
            pass
        finally:
            ser.close()
            self.connected.emit(False)

    def stop(self):
        self._running = False
        self.wait(2000)


# ═══════════════════════════════════════════════════════
#  실시간 그래프 위젯
# ═══════════════════════════════════════════════════════

class AxisGraphWidget(QWidget):
    """
    0 기준 ±128 범위의 실시간 스크롤 그래프.
    raw 0..255 값을 -128..+127로 변환하여 표시.
    """

    def __init__(self, title: str, color: QColor, max_samples: int = 200, parent=None):
        super().__init__(parent)
        self.title = title
        self.line_color = color
        self.max_samples = max_samples
        self.data = deque([0.0] * max_samples, maxlen=max_samples)
        self.current_value = 0
        self.current_status = 0
        self.setMinimumHeight(120)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def push_value(self, raw_u8: int, status: int = 0):
        """raw 0..255 → signed -128..+127"""
        self.current_value = raw_u8 - 128
        self.current_status = status
        self.data.append(self.current_value)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()
        margin_left   = 45
        margin_right  = 80
        margin_top    = 20
        margin_bottom = 20
        gw = w - margin_left - margin_right
        gh = h - margin_top - margin_bottom

        if gw < 10 or gh < 10:
            p.end()
            return

        # ─── 배경 ───
        p.fillRect(self.rect(), QColor(30, 30, 35))

        # ─── 그래프 영역 배경 ───
        p.fillRect(margin_left, margin_top, gw, gh, QColor(20, 20, 25))

        # ─── 그리드 + 0 기준선 ───
        p.setPen(QPen(QColor(60, 60, 65), 1, Qt.DotLine))
        for val in [-128, -64, 64, 127]:
            y = margin_top + gh / 2 - (val / 128.0) * (gh / 2)
            p.drawLine(margin_left, int(y), margin_left + gw, int(y))

        # 0 기준선 (강조)
        zero_y = margin_top + gh / 2
        p.setPen(QPen(QColor(100, 100, 110), 1, Qt.SolidLine))
        p.drawLine(margin_left, int(zero_y), margin_left + gw, int(zero_y))

        # ─── Y축 라벨 ───
        p.setPen(QColor(160, 160, 170))
        font = QFont("Consolas", 8)
        p.setFont(font)
        for val in [-128, -64, 0, 64, 127]:
            y = margin_top + gh / 2 - (val / 128.0) * (gh / 2)
            p.drawText(0, int(y) - 6, margin_left - 4, 12, Qt.AlignRight | Qt.AlignVCenter, str(val))

        # ─── 데이터 라인 ───
        if len(self.data) > 1:
            path = QPainterPath()
            step = gw / (self.max_samples - 1)

            for i, val in enumerate(self.data):
                x = margin_left + i * step
                y = zero_y - (val / 128.0) * (gh / 2)
                if i == 0:
                    path.moveTo(x, y)
                else:
                    path.lineTo(x, y)

            p.setPen(QPen(self.line_color, 2))
            p.drawPath(path)

            # 채우기 (반투명)
            fill_path = QPainterPath(path)
            last_x = margin_left + (len(self.data) - 1) * step
            fill_path.lineTo(last_x, zero_y)
            fill_path.lineTo(margin_left, zero_y)
            fill_path.closeSubpath()
            fill_color = QColor(self.line_color)
            fill_color.setAlpha(30)
            p.fillPath(fill_path, fill_color)

        # ─── 타이틀 ───
        p.setPen(self.line_color)
        p.setFont(QFont("Consolas", 10, QFont.Bold))
        p.drawText(margin_left + 6, margin_top + 14, self.title)

        # ─── 우측 현재 값 표시 ───
        rx = margin_left + gw + 8
        p.setPen(QColor(220, 220, 230))
        p.setFont(QFont("Consolas", 18, QFont.Bold))
        val_str = f"{self.current_value:+4d}"
        p.drawText(rx, margin_top, margin_right - 12, 30, Qt.AlignLeft | Qt.AlignVCenter, val_str)

        # status
        p.setFont(QFont("Consolas", 9))
        p.setPen(QColor(140, 140, 150))
        p.drawText(rx, margin_top + 32, margin_right - 12, 16, Qt.AlignLeft, f"st={self.current_status}")

        # raw
        raw_val = self.current_value + 128
        p.drawText(rx, margin_top + 48, margin_right - 12, 16, Qt.AlignLeft, f"raw={raw_val}")

        # ─── 테두리 ───
        p.setPen(QPen(QColor(60, 60, 70), 1))
        p.drawRect(margin_left, margin_top, gw, gh)

        p.end()


# ═══════════════════════════════════════════════════════
#  LED 인디케이터 위젯
# ═══════════════════════════════════════════════════════

class LedIndicator(QWidget):
    """원형 LED 위젯 (on/off + 2-bit 값 표시)"""

    def __init__(self, label: str, on_color: QColor = QColor(0, 220, 80), parent=None):
        super().__init__(parent)
        self.label = label
        self.on_color = on_color
        self.off_color = QColor(50, 50, 55)
        self.value = 0
        self.setFixedSize(90, 90)

    def set_value(self, v: int):
        self.value = v & 0x03

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()
        cx = w // 2
        led_r = 22

        # 배경
        p.fillRect(self.rect(), QColor(30, 30, 35))

        # LED 원
        is_on = self.value > 0
        color = self.on_color if is_on else self.off_color

        # 글로우 효과
        if is_on:
            glow = QColor(color)
            glow.setAlpha(60)
            p.setBrush(glow)
            p.setPen(Qt.NoPen)
            p.drawEllipse(cx - led_r - 6, 10 - 6, (led_r + 6) * 2, (led_r + 6) * 2)

        p.setBrush(color)
        p.setPen(QPen(QColor(80, 80, 90), 2))
        p.drawEllipse(cx - led_r, 10, led_r * 2, led_r * 2)

        # 하이라이트
        if is_on:
            highlight = QColor(255, 255, 255, 80)
            p.setBrush(highlight)
            p.setPen(Qt.NoPen)
            p.drawEllipse(cx - led_r // 2, 15, led_r, led_r // 2)

        # 라벨
        p.setPen(QColor(200, 200, 210))
        p.setFont(QFont("Consolas", 10, QFont.Bold))
        p.drawText(0, 56, w, 16, Qt.AlignCenter, self.label)

        # 값
        p.setFont(QFont("Consolas", 9))
        p.setPen(QColor(140, 140, 150))
        p.drawText(0, 72, w, 14, Qt.AlignCenter, f"val={self.value}")

        p.end()


# ═══════════════════════════════════════════════════════
#  상태 비트필드 표시 위젯
# ═══════════════════════════════════════════════════════

class AxisStatusPanel(QWidget):
    """축의 2-bit 상태 필드들을 한 줄로 표시"""

    def __init__(self, axis_name: str, parent=None):
        super().__init__(parent)
        self.axis_name = axis_name
        self.status = 0
        self.negative = 0
        self.positive = 0
        self.neutral = 0
        self.setFixedHeight(28)

    def update_values(self, status, negative, positive, neutral):
        self.status = status
        self.negative = negative
        self.positive = positive
        self.neutral = neutral
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor(30, 30, 35))

        font = QFont("Consolas", 9)
        p.setFont(font)

        fields = [
            (f"{self.axis_name}:", QColor(180, 180, 190), None),
            ("st=", QColor(120, 120, 130), self.status),
            ("-=", QColor(255, 100, 100), self.negative),
            ("+=", QColor(100, 200, 100), self.positive),
            ("N=", QColor(100, 150, 255), self.neutral),
        ]

        x = 4
        for label, color, val in fields:
            p.setPen(color)
            text = label if val is None else f"{label}{val}"
            p.drawText(x, 0, 200, self.height(), Qt.AlignLeft | Qt.AlignVCenter, text)
            x += p.fontMetrics().horizontalAdvance(text) + 10

        p.end()


# ═══════════════════════════════════════════════════════
#  메인 윈도우
# ═══════════════════════════════════════════════════════

class JoystickMonitorWindow(QMainWindow):

    def __init__(self, initial_port: str = "", baud: int = 115200):
        super().__init__()
        self.setWindowTitle("J1939 CAN Joystick Monitor")
        self.setMinimumSize(800, 700)
        self.resize(900, 750)

        self._baud = baud
        self._reader: SerialReaderThread | None = None
        self._pkt_count = 0
        self._err_count = 0

        # ─── 중앙 위젯 ───
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(8, 8, 8, 8)
        root_layout.setSpacing(6)

        # ─── 연결 바 ───
        conn_layout = QHBoxLayout()
        conn_layout.setSpacing(6)

        self.port_combo = QComboBox()
        self.port_combo.setMinimumWidth(180)
        self._refresh_ports()
        if initial_port:
            idx = self.port_combo.findText(initial_port)
            if idx >= 0:
                self.port_combo.setCurrentIndex(idx)

        refresh_btn = QPushButton("⟳")
        refresh_btn.setFixedWidth(32)
        refresh_btn.clicked.connect(self._refresh_ports)

        self.connect_btn = QPushButton("Connect")
        self.connect_btn.setFixedWidth(100)
        self.connect_btn.clicked.connect(self._toggle_connection)

        self.status_label = QLabel("Disconnected")
        self.status_label.setStyleSheet("color: #888;")

        self.stats_label = QLabel("pkt: 0  err: 0")
        self.stats_label.setStyleSheet("color: #666; font-family: Consolas; font-size: 9pt;")

        conn_layout.addWidget(QLabel("Port:"))
        conn_layout.addWidget(self.port_combo)
        conn_layout.addWidget(refresh_btn)
        conn_layout.addWidget(self.connect_btn)
        conn_layout.addWidget(self.status_label)
        conn_layout.addStretch()
        conn_layout.addWidget(self.stats_label)
        root_layout.addLayout(conn_layout)

        # ─── 구분선 ───
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        root_layout.addWidget(line)

        # ─── 그래프 영역 ───
        self.graph_x = AxisGraphWidget("X Axis (Left/Right)", QColor(80, 180, 255))
        self.graph_y = AxisGraphWidget("Y Axis (Back/Forward)", QColor(255, 160, 60))
        self.graph_aux = AxisGraphWidget("AUX X Axis", QColor(180, 100, 255))

        root_layout.addWidget(self.graph_x, stretch=1)
        root_layout.addWidget(self.graph_y, stretch=1)
        root_layout.addWidget(self.graph_aux, stretch=1)

        # ─── 하단: 상태필드 + 버튼 LED ───
        bottom_layout = QHBoxLayout()
        bottom_layout.setSpacing(12)

        # 상태필드 패널
        status_group = QGroupBox("Axis Status (2-bit fields)")
        status_group.setStyleSheet("""
            QGroupBox {
                color: #aaa;
                border: 1px solid #444;
                border-radius: 4px;
                margin-top: 8px;
                padding-top: 14px;
                font-family: Consolas;
                font-size: 9pt;
            }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; }
        """)
        status_layout = QVBoxLayout(status_group)
        status_layout.setSpacing(2)

        self.x_status_panel   = AxisStatusPanel("X")
        self.y_status_panel   = AxisStatusPanel("Y")
        self.aux_status_panel = AxisStatusPanel("AUX")
        status_layout.addWidget(self.x_status_panel)
        status_layout.addWidget(self.y_status_panel)
        status_layout.addWidget(self.aux_status_panel)

        bottom_layout.addWidget(status_group, stretch=1)

        # 버튼 LED 패널
        btn_group = QGroupBox("Buttons")
        btn_group.setStyleSheet("""
            QGroupBox {
                color: #aaa;
                border: 1px solid #444;
                border-radius: 4px;
                margin-top: 8px;
                padding-top: 14px;
                font-family: Consolas;
                font-size: 9pt;
            }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; }
        """)
        btn_layout = QHBoxLayout(btn_group)
        btn_layout.setSpacing(4)

        self.led_btn1 = LedIndicator("BTN 1", QColor(80, 180, 255))
        self.led_btn2 = LedIndicator("BTN 2", QColor(80, 180, 255))
        self.led_btn3 = LedIndicator("BTN 3", QColor(0, 220, 80))
        self.led_btn4 = LedIndicator("BTN 4", QColor(255, 80, 80))
        btn_layout.addWidget(self.led_btn1)
        btn_layout.addWidget(self.led_btn2)
        btn_layout.addWidget(self.led_btn3)
        btn_layout.addWidget(self.led_btn4)

        bottom_layout.addWidget(btn_group)

        root_layout.addLayout(bottom_layout)

        # ─── 리프레시 타이머 ───
        self._paint_timer = QTimer()
        self._paint_timer.timeout.connect(self._repaint_graphs)
        self._paint_timer.start(33)  # ~30 fps

        # ─── 다크 테마 ───
        self.setStyleSheet("""
            QMainWindow, QWidget { background-color: #1e1e23; color: #ddd; }
            QLabel { font-family: Consolas; font-size: 10pt; }
            QComboBox, QPushButton {
                background-color: #2a2a30; color: #ccc;
                border: 1px solid #555; border-radius: 3px;
                padding: 4px 8px; font-family: Consolas;
            }
            QPushButton:hover { background-color: #3a3a42; }
            QPushButton:pressed { background-color: #222228; }
        """)

    # ─── 포트 관리 ─────────────────────────────────────

    def _refresh_ports(self):
        self.port_combo.clear()
        ports = serial.tools.list_ports.comports()
        for p in sorted(ports, key=lambda x: x.device):
            self.port_combo.addItem(p.device)

    def _toggle_connection(self):
        if self._reader and self._reader.isRunning():
            self._reader.stop()
            self._reader = None
            self.connect_btn.setText("Connect")
            self.status_label.setText("Disconnected")
            self.status_label.setStyleSheet("color: #888;")
            return

        port = self.port_combo.currentText()
        if not port:
            return

        self._pkt_count = 0
        self._err_count = 0

        self._reader = SerialReaderThread(port, self._baud, self)
        self._reader.main_received.connect(self._on_main)
        self._reader.aux_received.connect(self._on_aux)
        self._reader.error_count.connect(self._on_error)
        self._reader.connected.connect(self._on_connected)
        self._reader.start()

        self.connect_btn.setText("Disconnect")

    def _on_connected(self, ok: bool):
        if ok:
            self.status_label.setText("Connected")
            self.status_label.setStyleSheet("color: #0d8;")
        else:
            self.status_label.setText("Disconnected")
            self.status_label.setStyleSheet("color: #888;")
            self.connect_btn.setText("Connect")

    # ─── 데이터 수신 핸들러 ────────────────────────────

    def _on_main(self, data: dict):
        self._pkt_count += 1

        x = data["x"]
        y = data["y"]
        btn = data["buttons"]

        # 그래프
        self.graph_x.push_value(x["position"], x["status"])
        self.graph_y.push_value(y["position"], y["status"])

        # 상태 필드
        self.x_status_panel.update_values(x["status"], x["negative"], x["positive"], x["neutral"])
        self.y_status_panel.update_values(y["status"], y["negative"], y["positive"], y["neutral"])

        # 버튼 LED
        self.led_btn1.set_value(btn["btn1"])
        self.led_btn2.set_value(btn["btn2"])
        self.led_btn3.set_value(btn["btn3"])
        self.led_btn4.set_value(btn["btn4"])

        self._update_stats()

    def _on_aux(self, data: dict):
        self._pkt_count += 1
        x = data["x"]
        self.graph_aux.push_value(x["position"], x["status"])
        self.aux_status_panel.update_values(x["status"], x["negative"], x["positive"], x["neutral"])
        self._update_stats()

    def _on_error(self, count: int):
        self._err_count = count
        self._update_stats()

    def _update_stats(self):
        self.stats_label.setText(f"pkt: {self._pkt_count}  err: {self._err_count}")

    def _repaint_graphs(self):
        self.graph_x.update()
        self.graph_y.update()
        self.graph_aux.update()
        self.led_btn1.update()
        self.led_btn2.update()
        self.led_btn3.update()
        self.led_btn4.update()

    # ─── 종료 처리 ─────────────────────────────────────

    def closeEvent(self, event):
        if self._reader:
            self._reader.stop()
        event.accept()


# ═══════════════════════════════════════════════════════
#  Entry Point
# ═══════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="J1939 Joystick Monitor")
    parser.add_argument("--port", "-p", default="", help="Serial port (e.g. COM3, /dev/ttyUSB0)")
    parser.add_argument("--baud", "-b", type=int, default=115200, help="Baud rate")
    args = parser.parse_args()

    app = QApplication(sys.argv)
    win = JoystickMonitorWindow(initial_port=args.port, baud=args.baud)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
