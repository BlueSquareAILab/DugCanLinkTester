#!/usr/bin/env python3
"""
file: /DugCanLinker/joystick_monitor.py

desc : J1939 조이스틱 PySide6 GUI 모니터

사용법:
  python -m DugCanLinker.joystick_monitor --help
  python -m DugCanLinker.joystick_monitor --port COM3
  
작성자: gbox3d
작성일: 2026-02-08

이 주석을 수정하지 마시오.
"""

import sys
import argparse
from collections import deque

from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QPainter, QColor, QPen, QFont, QPainterPath
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QGroupBox, QComboBox, QPushButton, QFrame, QSizePolicy,
)

import serial.tools.list_ports

from .protocol import AxisState, MainPacket, AuxPacket, PKT_MAIN, PKT_AUX
from .serial_receiver import PacketParser, ReceiverStats

import serial as pyserial


# ═══════════════════════════════════════════════════════
#  시리얼 수신 QThread (Qt 시그널 연동)
# ═══════════════════════════════════════════════════════

class SerialReaderThread(QThread):
    """PacketParser를 이용한 Qt 시그널 기반 수신 스레드"""

    main_received = Signal(object)   # MainPacket
    aux_received  = Signal(object)   # AuxPacket
    stats_updated = Signal(object)   # ReceiverStats
    connected     = Signal(bool)

    def __init__(self, port: str, baud: int = 115200, parent=None):
        super().__init__(parent)
        self.port = port
        self.baud = baud
        self._running = False
        self._parser = PacketParser()

    @property
    def stats(self) -> ReceiverStats:
        return self._parser.stats

    def run(self):
        self._running = True
        try:
            ser = pyserial.Serial(self.port, self.baud, timeout=0.1)
            self.connected.emit(True)
        except pyserial.SerialException as e:
            print(f"Serial open failed: {e}")
            self.connected.emit(False)
            return

        try:
            while self._running:
                chunk = ser.read(64)
                for b in chunk:
                    result = self._parser.feed(b)
                    if result is None:
                        continue

                    pkt_type, packet = result
                    if pkt_type == PKT_MAIN:
                        self.main_received.emit(packet)
                    elif pkt_type == PKT_AUX:
                        self.aux_received.emit(packet)

                    self.stats_updated.emit(self._parser.stats)

        except pyserial.SerialException:
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
    """0 기준 ±128 범위의 실시간 스크롤 그래프"""

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

    def push_axis(self, axis: AxisState):
        """AxisState 객체를 직접 수신"""
        self.current_value = axis.signed
        self.current_status = axis.status
        self.data.append(self.current_value)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        w, h = self.width(), self.height()
        ml, mr, mt, mb = 45, 80, 20, 20
        gw, gh = w - ml - mr, h - mt - mb

        if gw < 10 or gh < 10:
            p.end()
            return

        # 배경
        p.fillRect(self.rect(), QColor(30, 30, 35))
        p.fillRect(ml, mt, gw, gh, QColor(20, 20, 25))

        # 그리드
        p.setPen(QPen(QColor(60, 60, 65), 1, Qt.DotLine))
        for val in [-128, -64, 64, 127]:
            y = mt + gh / 2 - (val / 128.0) * (gh / 2)
            p.drawLine(ml, int(y), ml + gw, int(y))

        # 0 기준선
        zero_y = mt + gh / 2
        p.setPen(QPen(QColor(100, 100, 110), 1, Qt.SolidLine))
        p.drawLine(ml, int(zero_y), ml + gw, int(zero_y))

        # Y축 라벨
        p.setPen(QColor(160, 160, 170))
        p.setFont(QFont("Consolas", 8))
        for val in [-128, -64, 0, 64, 127]:
            y = mt + gh / 2 - (val / 128.0) * (gh / 2)
            p.drawText(0, int(y) - 6, ml - 4, 12, Qt.AlignRight | Qt.AlignVCenter, str(val))

        # 데이터 라인
        if len(self.data) > 1:
            path = QPainterPath()
            step = gw / (self.max_samples - 1)
            for i, val in enumerate(self.data):
                x = ml + i * step
                y = zero_y - (val / 128.0) * (gh / 2)
                if i == 0:
                    path.moveTo(x, y)
                else:
                    path.lineTo(x, y)

            p.setPen(QPen(self.line_color, 2))
            p.drawPath(path)

            # 반투명 채우기
            fill_path = QPainterPath(path)
            fill_path.lineTo(ml + (len(self.data) - 1) * step, zero_y)
            fill_path.lineTo(ml, zero_y)
            fill_path.closeSubpath()
            fc = QColor(self.line_color)
            fc.setAlpha(30)
            p.fillPath(fill_path, fc)

        # 타이틀
        p.setPen(self.line_color)
        p.setFont(QFont("Consolas", 10, QFont.Bold))
        p.drawText(ml + 6, mt + 14, self.title)

        # 우측 현재 값
        rx = ml + gw + 8
        p.setPen(QColor(220, 220, 230))
        p.setFont(QFont("Consolas", 18, QFont.Bold))
        p.drawText(rx, mt, mr - 12, 30, Qt.AlignLeft | Qt.AlignVCenter, f"{self.current_value:+4d}")

        p.setFont(QFont("Consolas", 9))
        p.setPen(QColor(140, 140, 150))
        p.drawText(rx, mt + 32, mr - 12, 16, Qt.AlignLeft, f"st={self.current_status}")
        p.drawText(rx, mt + 48, mr - 12, 16, Qt.AlignLeft, f"raw={self.current_value + 128}")

        # 테두리
        p.setPen(QPen(QColor(60, 60, 70), 1))
        p.drawRect(ml, mt, gw, gh)
        p.end()


# ═══════════════════════════════════════════════════════
#  LED 인디케이터 위젯
# ═══════════════════════════════════════════════════════

class LedIndicator(QWidget):
    """원형 LED 위젯 (2-bit 값 표시)"""

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

        w, h = self.width(), self.height()
        cx, led_r = w // 2, 22

        p.fillRect(self.rect(), QColor(30, 30, 35))

        is_on = self.value > 0
        color = self.on_color if is_on else self.off_color

        if is_on:
            glow = QColor(color)
            glow.setAlpha(60)
            p.setBrush(glow)
            p.setPen(Qt.NoPen)
            p.drawEllipse(cx - led_r - 6, 10 - 6, (led_r + 6) * 2, (led_r + 6) * 2)

        p.setBrush(color)
        p.setPen(QPen(QColor(80, 80, 90), 2))
        p.drawEllipse(cx - led_r, 10, led_r * 2, led_r * 2)

        if is_on:
            p.setBrush(QColor(255, 255, 255, 80))
            p.setPen(Qt.NoPen)
            p.drawEllipse(cx - led_r // 2, 15, led_r, led_r // 2)

        p.setPen(QColor(200, 200, 210))
        p.setFont(QFont("Consolas", 10, QFont.Bold))
        p.drawText(0, 56, w, 16, Qt.AlignCenter, self.label)

        p.setFont(QFont("Consolas", 9))
        p.setPen(QColor(140, 140, 150))
        p.drawText(0, 72, w, 14, Qt.AlignCenter, f"val={self.value}")
        p.end()


# ═══════════════════════════════════════════════════════
#  축 상태 패널
# ═══════════════════════════════════════════════════════

class AxisStatusPanel(QWidget):
    """축의 2-bit 상태 필드들을 한 줄로 표시"""

    def __init__(self, axis_name: str, parent=None):
        super().__init__(parent)
        self.axis_name = axis_name
        self._axis = AxisState()
        self.setFixedHeight(28)

    def update_axis(self, axis: AxisState):
        """AxisState 객체를 직접 수신"""
        self._axis = axis
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor(30, 30, 35))
        p.setFont(QFont("Consolas", 9))

        a = self._axis
        fields = [
            (f"{self.axis_name}:", QColor(180, 180, 190)),
            (f"st={a.status}", QColor(120, 120, 130)),
            (f"-={a.negative}", QColor(255, 100, 100)),
            (f"+={a.positive}", QColor(100, 200, 100)),
            (f"N={a.neutral}", QColor(100, 150, 255)),
        ]

        x = 4
        for text, color in fields:
            p.setPen(color)
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

        # ─── 중앙 위젯 ───
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        # ─── 연결 바 ───
        conn = QHBoxLayout()
        conn.setSpacing(6)

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

        conn.addWidget(QLabel("Port:"))
        conn.addWidget(self.port_combo)
        conn.addWidget(refresh_btn)
        conn.addWidget(self.connect_btn)
        conn.addWidget(self.status_label)
        conn.addStretch()
        conn.addWidget(self.stats_label)
        root.addLayout(conn)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        root.addWidget(line)

        # ─── 그래프 ───
        self.graph_x   = AxisGraphWidget("X Axis (Left/Right)", QColor(80, 180, 255))
        self.graph_y   = AxisGraphWidget("Y Axis (Back/Forward)", QColor(255, 160, 60))
        self.graph_aux = AxisGraphWidget("AUX X Axis", QColor(180, 100, 255))
        root.addWidget(self.graph_x, stretch=1)
        root.addWidget(self.graph_y, stretch=1)
        root.addWidget(self.graph_aux, stretch=1)

        # ─── 하단: 상태 + 버튼 ───
        bottom = QHBoxLayout()
        bottom.setSpacing(12)

        group_style = """
            QGroupBox {
                color: #aaa; border: 1px solid #444; border-radius: 4px;
                margin-top: 8px; padding-top: 14px;
                font-family: Consolas; font-size: 9pt;
            }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; }
        """

        status_group = QGroupBox("Axis Status (2-bit fields)")
        status_group.setStyleSheet(group_style)
        sl = QVBoxLayout(status_group)
        sl.setSpacing(2)
        self.x_status   = AxisStatusPanel("X")
        self.y_status   = AxisStatusPanel("Y")
        self.aux_status = AxisStatusPanel("AUX")
        sl.addWidget(self.x_status)
        sl.addWidget(self.y_status)
        sl.addWidget(self.aux_status)
        bottom.addWidget(status_group, stretch=1)

        btn_group = QGroupBox("Buttons")
        btn_group.setStyleSheet(group_style)
        bl = QHBoxLayout(btn_group)
        bl.setSpacing(4)
        self.led_btn1 = LedIndicator("BTN 1", QColor(80, 180, 255))
        self.led_btn2 = LedIndicator("BTN 2", QColor(80, 180, 255))
        self.led_btn3 = LedIndicator("BTN 3", QColor(0, 220, 80))
        self.led_btn4 = LedIndicator("BTN 4", QColor(255, 80, 80))
        bl.addWidget(self.led_btn1)
        bl.addWidget(self.led_btn2)
        bl.addWidget(self.led_btn3)
        bl.addWidget(self.led_btn4)
        bottom.addWidget(btn_group)
        root.addLayout(bottom)

        # ─── 타이머 ───
        self._paint_timer = QTimer()
        self._paint_timer.timeout.connect(self._repaint_all)
        self._paint_timer.start(33)

        # ─── 스타일 ───
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

    # ─── 포트 ───

    def _refresh_ports(self):
        self.port_combo.clear()
        for p in sorted(serial.tools.list_ports.comports(), key=lambda x: x.device):
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
        self._reader = SerialReaderThread(port, self._baud, self)
        self._reader.main_received.connect(self._on_main)
        self._reader.aux_received.connect(self._on_aux)
        self._reader.stats_updated.connect(self._on_stats)
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

    # ─── 데이터 핸들러 ───

    def _on_main(self, pkt: MainPacket):
        self._pkt_count += 1

        self.graph_x.push_axis(pkt.x)
        self.graph_y.push_axis(pkt.y)

        self.x_status.update_axis(pkt.x)
        self.y_status.update_axis(pkt.y)

        self.led_btn1.set_value(pkt.buttons.btn1)
        self.led_btn2.set_value(pkt.buttons.btn2)
        self.led_btn3.set_value(pkt.buttons.btn3)
        self.led_btn4.set_value(pkt.buttons.btn4)

    def _on_aux(self, pkt: AuxPacket):
        self._pkt_count += 1
        self.graph_aux.push_axis(pkt.x)
        self.aux_status.update_axis(pkt.x)

    def _on_stats(self, stats: ReceiverStats):
        self.stats_label.setText(f"pkt: {self._pkt_count}  err: {stats.errors}")

    def _repaint_all(self):
        for w in (self.graph_x, self.graph_y, self.graph_aux,
                  self.led_btn1, self.led_btn2, self.led_btn3, self.led_btn4):
            w.update()

    def closeEvent(self, event):
        if self._reader:
            self._reader.stop()
        event.accept()


# ═══════════════════════════════════════════════════════
#  Entry Point
# ═══════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="J1939 Joystick Monitor (GUI)")
    parser.add_argument("--port", "-p", default="", help="Serial port")
    parser.add_argument("--baud", "-b", type=int, default=115200, help="Baud rate")
    args = parser.parse_args()

    app = QApplication(sys.argv)
    win = JoystickMonitorWindow(initial_port=args.port, baud=args.baud)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
