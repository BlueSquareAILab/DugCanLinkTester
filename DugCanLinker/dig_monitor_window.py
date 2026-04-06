from __future__ import annotations

import json
import threading
from collections import deque
from datetime import datetime
from pathlib import Path

import serial as pyserial
import serial.tools.list_ports
from PySide6.QtCore import QThread, QTimer, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .protocol import AuxPacket, AxisState, DeviceResponse, DigInputReport, JoystickReport, MainPacket, PedalReport
from .serial_receiver import ReceiverStats, TextLineParser
from .vortex_hid import VortexHID


def _axis_to_dict(axis: AxisState) -> dict[str, int]:
    return {
        "raw": axis.position,
        "signed": axis.signed,
        "status": axis.status,
        "negative": axis.negative,
        "positive": axis.positive,
        "neutral": axis.neutral,
    }


def _pedal_direction_text(axis: AxisState, negative_label: str, positive_label: str) -> str:
    if axis.neutral > 0 and axis.negative == 0 and axis.positive == 0:
        return "Neutral"
    if axis.positive > 0 and axis.negative == 0:
        return f"{positive_label} ({axis.position})"
    if axis.negative > 0 and axis.positive == 0:
        return f"{negative_label} ({axis.position})"
    if axis.position == 0 and axis.status == 0 and axis.negative == 0 and axis.positive == 0 and axis.neutral == 0:
        return "-"
    return f"mixed st={axis.status}"


def _report_to_dict(report: DigInputReport) -> dict:
    def _main_to_dict(main) -> dict:
        return {
            "valid": main.valid,
            "age_ms": main.age_ms,
            "x": _axis_to_dict(main.x),
            "y": _axis_to_dict(main.y),
            "buttons": {
                "b1": main.buttons.btn1,
                "b2": main.buttons.btn2,
                "b3": main.buttons.btn3,
                "b4": main.buttons.btn4,
            },
        }

    def _aux_to_dict(aux) -> dict:
        return {
            "valid": aux.valid,
            "age_ms": aux.age_ms,
            "x": _axis_to_dict(aux.x),
        }

    def _pedal_to_dict(pedal: PedalReport) -> dict:
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
            "axis_2": _axis_to_dict(pedal.axis_2),
            "axis_1": _axis_to_dict(pedal.axis_1),
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
            "main": _main_to_dict(report.lh.main),
            "aux": _aux_to_dict(report.lh.aux),
        },
        "rh": {
            "sa": report.rh.sa,
            "main": _main_to_dict(report.rh.main),
            "aux": _aux_to_dict(report.rh.aux),
        },
        "pedal": {
            "lh": _pedal_to_dict(report.pedal_lh),
            "rh": _pedal_to_dict(report.pedal_rh),
        },
        "ain": dict(report.ain),
        "din": dict(report.din),
    }


class SerialReaderThread(QThread):
    main_received = Signal(object)
    aux_received = Signal(object)
    report_received = Signal(object)
    response_received = Signal(object)
    stats_updated = Signal(object)
    connected = Signal(bool)
    open_failed = Signal(str)

    def __init__(self, port: str, baud: int = 115200, parent=None):
        super().__init__(parent)
        self.port = port
        self.baud = baud
        self._running = False
        self._parser = TextLineParser()
        self._commands: deque[str] = deque()
        self._command_lock = threading.Lock()

    @property
    def stats(self) -> ReceiverStats:
        return self._parser.stats

    def queue_command(self, command: str) -> None:
        text = command.strip()
        if not text:
            return
        with self._command_lock:
            self._commands.append(text)

    def _flush_commands(self, ser: pyserial.Serial) -> None:
        while True:
            with self._command_lock:
                if not self._commands:
                    return
                text = self._commands.popleft()
            ser.write((text + "\n").encode("utf-8"))

    def run(self):
        self._running = True
        try:
            ser = pyserial.Serial(self.port, self.baud, timeout=0.1)
            self.connected.emit(True)
        except pyserial.SerialException as exc:
            self._running = False
            self.open_failed.emit(f"Serial open failed: {exc}")
            return

        try:
            while self._running:
                self._flush_commands(ser)
                for b in ser.read(128):
                    result = self._parser.feed(b)
                    if result is None:
                        continue
                    _pkt_type, packet = result
                    if isinstance(packet, MainPacket):
                        self.main_received.emit(packet)
                    elif isinstance(packet, AuxPacket):
                        self.aux_received.emit(packet)
                    elif isinstance(packet, DigInputReport):
                        self.report_received.emit(packet)
                    elif isinstance(packet, DeviceResponse):
                        self.response_received.emit(packet)
                    self.stats_updated.emit(self._parser.stats)
        except pyserial.SerialException:
            pass
        finally:
            ser.close()
            self.connected.emit(False)

    def stop(self):
        self._running = False
        self.wait(2000)


class AxisGraphWidget(QWidget):
    AXIS_LIMIT = 255.0

    def __init__(
        self,
        title: str,
        color: QColor,
        negative_label: str,
        positive_label: str,
        neutral_label: str = "Neutral",
        max_samples: int = 180,
        parent=None,
    ):
        super().__init__(parent)
        self.title = title
        self.line_color = color
        self.negative_label = negative_label
        self.positive_label = positive_label
        self.neutral_label = neutral_label
        self.max_samples = max_samples
        self.data = deque([0.0] * max_samples, maxlen=max_samples)
        self.current_value = 0
        self.current_raw = 0
        self.current_status = 0
        self.setMinimumHeight(110)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def clear(self):
        self.data = deque([0.0] * self.max_samples, maxlen=self.max_samples)
        self.current_value = 0
        self.current_raw = 0
        self.current_status = 0

    def push_axis(self, axis: AxisState):
        self.current_value = axis.signed
        self.current_raw = axis.position
        self.current_status = axis.status
        self.data.append(self.current_value)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        ml, mr, mt, mb = 45, 122, 20, 18
        gw, gh = w - ml - mr, h - mt - mb
        if gw < 10 or gh < 10:
            p.end()
            return
        p.fillRect(self.rect(), QColor(30, 30, 35))
        p.fillRect(ml, mt, gw, gh, QColor(20, 20, 25))
        p.setPen(QPen(QColor(60, 60, 65), 1, Qt.DotLine))
        for val in (-255, -128, 128, 255):
            y = mt + gh / 2 - (val / self.AXIS_LIMIT) * (gh / 2)
            p.drawLine(ml, int(y), ml + gw, int(y))
        zero_y = mt + gh / 2
        p.setPen(QPen(QColor(100, 100, 110), 1, Qt.SolidLine))
        p.drawLine(ml, int(zero_y), ml + gw, int(zero_y))
        p.setPen(QColor(160, 160, 170))
        p.setFont(QFont("Consolas", 8))
        for val in (-255, -128, 0, 128, 255):
            y = mt + gh / 2 - (val / self.AXIS_LIMIT) * (gh / 2)
            p.drawText(0, int(y) - 6, ml - 4, 12, Qt.AlignRight | Qt.AlignVCenter, str(val))
        if len(self.data) > 1:
            path = QPainterPath()
            step = gw / (self.max_samples - 1)
            for i, val in enumerate(self.data):
                x = ml + i * step
                y = zero_y - (val / self.AXIS_LIMIT) * (gh / 2)
                path.moveTo(x, y) if i == 0 else path.lineTo(x, y)
            p.setPen(QPen(self.line_color, 2))
            p.drawPath(path)
        p.setPen(self.line_color)
        p.setFont(QFont("Consolas", 10, QFont.Bold))
        p.drawText(ml + 6, mt + 14, self.title)
        rx = ml + gw + 8
        p.setPen(QColor(220, 220, 230))
        p.setFont(QFont("Consolas", 16, QFont.Bold))
        p.drawText(rx, mt, mr - 12, 26, Qt.AlignLeft | Qt.AlignVCenter, f"{self.current_value:+4d}")
        p.setFont(QFont("Consolas", 9))
        p.setPen(QColor(140, 140, 150))
        p.drawText(rx, mt + 28, mr - 12, 14, Qt.AlignLeft, f"st={self.current_status}")
        p.drawText(rx, mt + 44, mr - 12, 14, Qt.AlignLeft, f"raw={self.current_raw}")
        p.setFont(QFont("Consolas", 8, QFont.Bold))
        p.setPen(QColor(100, 200, 100))
        p.drawText(rx, mt + 62, mr - 12, 14, Qt.AlignLeft, f"+ {self.positive_label}")
        p.setPen(QColor(100, 150, 255))
        p.drawText(rx, mt + 76, mr - 12, 14, Qt.AlignLeft, self.neutral_label)
        p.setPen(QColor(255, 100, 100))
        p.drawText(rx, mt + 90, mr - 12, 14, Qt.AlignLeft, f"- {self.negative_label}")
        p.setPen(QPen(QColor(60, 60, 70), 1))
        p.drawRect(ml, mt, gw, gh)
        p.end()


class LedIndicator(QWidget):
    def __init__(self, label: str, on_color: QColor, size: int = 76, parent=None):
        super().__init__(parent)
        self.label = label
        self.on_color = on_color
        self.off_color = QColor(50, 50, 55)
        self.value = 0
        self.setFixedSize(size, size)

    def set_value(self, value: int):
        self.value = value & 0x03

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        cx = w // 2
        led_r = max(12, w // 4)
        text_y = led_r * 2 + 14
        p.fillRect(self.rect(), QColor(30, 30, 35))
        color = self.on_color if self.value > 0 else self.off_color
        p.setBrush(color)
        p.setPen(QPen(QColor(80, 80, 90), 2))
        p.drawEllipse(cx - led_r, 8, led_r * 2, led_r * 2)
        p.setPen(QColor(200, 200, 210))
        p.setFont(QFont("Consolas", 9, QFont.Bold))
        p.drawText(0, text_y, w, 14, Qt.AlignCenter, self.label)
        p.setPen(QColor(140, 140, 150))
        p.setFont(QFont("Consolas", 8))
        p.drawText(0, text_y + 14, w, 12, Qt.AlignCenter, f"val={self.value}")
        p.end()


class AxisStatusPanel(QWidget):
    def __init__(self, axis_name: str, negative_label: str, positive_label: str, parent=None):
        super().__init__(parent)
        self.axis_name = axis_name
        self.negative_label = negative_label
        self.positive_label = positive_label
        self._axis = AxisState()
        self.setFixedHeight(26)

    def update_axis(self, axis: AxisState):
        self._axis = axis
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(30, 30, 35))
        p.setFont(QFont("Consolas", 9))
        a = self._axis
        fields = [
            (f"{self.axis_name}:", QColor(180, 180, 190)),
            (f"st={a.status}", QColor(120, 120, 130)),
            (f"neg {self.negative_label}={a.negative}", QColor(255, 100, 100)),
            (f"pos {self.positive_label}={a.positive}", QColor(100, 200, 100)),
            (f"neutral={a.neutral}", QColor(100, 150, 255)),
        ]
        x = 4
        for text, color in fields:
            p.setPen(color)
            p.drawText(x, 0, 220, self.height(), Qt.AlignLeft | Qt.AlignVCenter, text)
            x += p.fontMetrics().horizontalAdvance(text) + 10
        p.end()


class AnalogValueWidget(QWidget):
    def __init__(self, name: str, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        self.name_label = QLabel(name)
        self.name_label.setFixedWidth(46)
        self.bar = QProgressBar()
        self.bar.setRange(0, 1023)
        self.bar.setTextVisible(False)
        self.value_label = QLabel("0")
        self.value_label.setFixedWidth(42)
        self.value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(self.name_label)
        layout.addWidget(self.bar, stretch=1)
        layout.addWidget(self.value_label)

    def set_value(self, value: int):
        self.bar.setValue(value)
        self.value_label.setText(str(value))


class ByteValueWidget(QWidget):
    def __init__(self, name: str, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        self.name_label = QLabel(name)
        self.name_label.setFixedWidth(28)
        self.bar = QProgressBar()
        self.bar.setRange(0, 255)
        self.bar.setTextVisible(False)
        self.value_label = QLabel("0")
        self.value_label.setFixedWidth(32)
        self.value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(self.name_label)
        layout.addWidget(self.bar, stretch=1)
        layout.addWidget(self.value_label)

    def set_value(self, value: int):
        self.bar.setValue(value)
        self.value_label.setText(str(value))


class BoolStateWidget(QWidget):
    def __init__(self, name: str, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        self.name_label = QLabel(name)
        self.name_label.setFixedWidth(48)
        self.state_label = QLabel("OFF")
        self.state_label.setAlignment(Qt.AlignCenter)
        self.state_label.setFixedWidth(54)
        layout.addWidget(self.name_label)
        layout.addWidget(self.state_label)
        layout.addStretch()
        self.set_active(False)

    def set_active(self, active: bool):
        if active:
            self.state_label.setText("ON")
            self.state_label.setStyleSheet("background:#0b5; color:#fff; border:1px solid #197; border-radius:3px; font-family:Consolas;")
        else:
            self.state_label.setText("OFF")
            self.state_label.setStyleSheet("background:#333; color:#aaa; border:1px solid #555; border-radius:3px; font-family:Consolas;")


class PedalPanel(QGroupBox):
    def __init__(self, title: str, parent=None):
        super().__init__(title, parent)
        layout = QVBoxLayout(self)
        layout.setSpacing(6)
        self.doc_label = QLabel("Sheet: single CAN node SA=0xED, Axis 2=B1/B2 (2-/2+), Axis 1=B3/B4 (1-/1+)")
        self.doc_label.setStyleSheet("color:#7db4ff; font-family:Consolas; font-size:9pt;")
        self.info_label = QLabel("No pedal CAN data")
        self.info_label.setStyleSheet("color:#9aa; font-family:Consolas; font-size:9pt;")
        self.state_label = QLabel("Axis 2: -    Axis 1: -")
        self.state_label.setStyleSheet("color:#b7d7ff; font-family:Consolas; font-size:9pt;")
        self.hex_label = QLabel("raw: -")
        self.hex_label.setStyleSheet("color:#888; font-family:Consolas; font-size:9pt;")
        layout.addWidget(self.doc_label)
        layout.addWidget(self.info_label)
        layout.addWidget(self.state_label)
        layout.addWidget(self.hex_label)
        self.graph_axis2 = AxisGraphWidget("Axis 2 (2-/2+)", QColor(80, 180, 255), "2-", "2+")
        self.graph_axis1 = AxisGraphWidget("Axis 1 (1-/1+)", QColor(80, 220, 120), "1-", "1+")
        graph_row = QHBoxLayout()
        graph_row.addWidget(self.graph_axis2, stretch=1)
        graph_row.addWidget(self.graph_axis1, stretch=1)
        layout.addLayout(graph_row)
        self.axis2_status = AxisStatusPanel("A2", "2-", "2+")
        self.axis1_status = AxisStatusPanel("A1", "1-", "1+")
        layout.addWidget(self.axis2_status)
        layout.addWidget(self.axis1_status)
        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(4)
        self.byte_widgets = [ByteValueWidget(f"B{i}") for i in range(8)]
        for idx, widget in enumerate(self.byte_widgets):
            grid.addWidget(widget, idx // 2, idx % 2)
        layout.addLayout(grid)

    def clear(self):
        self.info_label.setText("No pedal CAN data")
        self.state_label.setText("Axis 2: -    Axis 1: -")
        self.hex_label.setText("raw: -")
        self.graph_axis2.clear()
        self.graph_axis1.clear()
        zero = AxisState()
        self.axis2_status.update_axis(zero)
        self.axis1_status.update_axis(zero)
        for widget in self.byte_widgets:
            widget.set_value(0)

    def update_report(self, report: PedalReport):
        expected_text = f"exp=0x{report.expected_sa:02X}" if report.expected_sa else "exp=-"
        sa_text = f"sa=0x{report.sa:02X}" if report.sa is not None else "sa=-"
        age_text = "-" if report.age_ms is None else f"{report.age_ms}ms"
        pgn_text = "-" if report.pgn is None else f"0x{report.pgn:04X}"
        self.info_label.setText(
            f"json  {expected_text}  {sa_text}  valid={'Y' if report.valid else '-'} age={age_text}  pgn={pgn_text} len={report.length}"
        )
        can_id_text = "-" if report.can_id is None else f"0x{report.can_id:X}"
        raw_hex = report.hex_bytes if report.hex_bytes else "-"
        self.hex_label.setText(f"can_id={can_id_text}  raw={raw_hex}")
        self.state_label.setText(
            "Axis 2: "
            f"{_pedal_direction_text(report.axis_2, '2-', '2+')}    "
            "Axis 1: "
            f"{_pedal_direction_text(report.axis_1, '1-', '1+')}"
        )
        if report.has_payload:
            self.graph_axis2.push_axis(report.axis_2)
            self.graph_axis1.push_axis(report.axis_1)
            self.axis2_status.update_axis(report.axis_2)
            self.axis1_status.update_axis(report.axis_1)
        else:
            self.graph_axis2.clear()
            self.graph_axis1.clear()
            zero = AxisState()
            self.axis2_status.update_axis(zero)
            self.axis1_status.update_axis(zero)
        for idx, widget in enumerate(self.byte_widgets):
            value = report.data[idx] if idx < len(report.data) else 0
            widget.set_value(value)


class JoystickPanel(QGroupBox):
    def __init__(self, title: str, parent=None):
        super().__init__(title, parent)
        layout = QVBoxLayout(self)
        layout.setSpacing(6)
        self.info_label = QLabel("No data")
        self.info_label.setStyleSheet("color:#9aa; font-family:Consolas; font-size:9pt;")
        layout.addWidget(self.info_label)
        self.graph_x = AxisGraphWidget("X Axis", QColor(80, 180, 255), "Left", "Right")
        self.graph_y = AxisGraphWidget("Y Axis", QColor(255, 160, 60), "Down/Back", "Up/Forward")
        self.graph_aux = AxisGraphWidget("AUX X Axis", QColor(180, 100, 255), "Left", "Right")
        layout.addWidget(self.graph_x)
        layout.addWidget(self.graph_y)
        layout.addWidget(self.graph_aux)
        self.x_status = AxisStatusPanel("X", "Left", "Right")
        self.y_status = AxisStatusPanel("Y", "Down/Back", "Up/Forward")
        self.aux_status = AxisStatusPanel("AUX", "Left", "Right")
        layout.addWidget(self.x_status)
        layout.addWidget(self.y_status)
        layout.addWidget(self.aux_status)
        btn_row = QHBoxLayout()
        self.led_btn1 = LedIndicator("BTN1", QColor(80, 180, 255))
        self.led_btn2 = LedIndicator("BTN2", QColor(80, 180, 255))
        self.led_btn3 = LedIndicator("BTN3", QColor(0, 220, 80))
        self.led_btn4 = LedIndicator("BTN4", QColor(255, 80, 80))
        for led in (self.led_btn1, self.led_btn2, self.led_btn3, self.led_btn4):
            btn_row.addWidget(led)
        layout.addLayout(btn_row)

    def clear(self):
        self.info_label.setText("No data")
        self.graph_x.clear()
        self.graph_y.clear()
        self.graph_aux.clear()
        zero = AxisState()
        self.x_status.update_axis(zero)
        self.y_status.update_axis(zero)
        self.aux_status.update_axis(zero)
        for led in (self.led_btn1, self.led_btn2, self.led_btn3, self.led_btn4):
            led.set_value(0)

    def _info_text(self, sa: int | None, main_valid: bool, main_age: int | None, aux_valid: bool, aux_age: int | None, mode: str) -> str:
        sa_text = f"SA=0x{sa:02X}" if sa is not None else "SA=-"
        main_age_text = "-" if main_age is None else f"{main_age}ms"
        aux_age_text = "-" if aux_age is None else f"{aux_age}ms"
        return f"{mode}  {sa_text}  main={'Y' if main_valid else '-'} age={main_age_text}  aux={'Y' if aux_valid else '-'} age={aux_age_text}"

    def update_report(self, report: JoystickReport):
        self.info_label.setText(self._info_text(report.sa, report.main.valid, report.main.age_ms, report.aux.valid, report.aux.age_ms, "json"))
        if report.main.valid:
            self.graph_x.push_axis(report.main.x)
            self.graph_y.push_axis(report.main.y)
            self.x_status.update_axis(report.main.x)
            self.y_status.update_axis(report.main.y)
            self.led_btn1.set_value(report.main.buttons.btn1)
            self.led_btn2.set_value(report.main.buttons.btn2)
            self.led_btn3.set_value(report.main.buttons.btn3)
            self.led_btn4.set_value(report.main.buttons.btn4)
        else:
            for led in (self.led_btn1, self.led_btn2, self.led_btn3, self.led_btn4):
                led.set_value(0)
        if report.aux.valid:
            self.graph_aux.push_axis(report.aux.x)
            self.aux_status.update_axis(report.aux.x)

    def update_packets(self, main: MainPacket | None = None, aux: AuxPacket | None = None, sa: int | None = None):
        self.info_label.setText(self._info_text(sa, main is not None, None, aux is not None, None, "legacy"))
        if main is not None:
            self.graph_x.push_axis(main.x)
            self.graph_y.push_axis(main.y)
            self.x_status.update_axis(main.x)
            self.y_status.update_axis(main.y)
            self.led_btn1.set_value(main.buttons.btn1)
            self.led_btn2.set_value(main.buttons.btn2)
            self.led_btn3.set_value(main.buttons.btn3)
            self.led_btn4.set_value(main.buttons.btn4)
        if aux is not None:
            self.graph_aux.push_axis(aux.x)
            self.aux_status.update_axis(aux.x)


class JoystickMonitorWindow(QMainWindow):
    INITIAL_HANDSHAKE_DELAY_MS = 1800
    INITIAL_START_DELAY_MS = 2100

    def __init__(
        self,
        initial_port: str = "",
        baud: int = 115200,
        enable_hid: bool = False,
        hid_deadzone: float = 0.03,
        hid_expo: float = 1.0,
        hid_aux_expo: float = 1.0,
        invert_y: bool = True,
    ):
        super().__init__()
        self.setWindowTitle("DigCanLink Monitor")
        self.setMinimumSize(1100, 900)
        self.resize(1240, 980)

        self._baud = baud
        self._reader: SerialReaderThread | None = None
        self._event_count = 0
        self._hid: VortexHID | None = None
        self._last_main: MainPacket | None = None
        self._last_aux: AuxPacket | None = None
        self._protocol_mode = "idle"
        self._session_log_path: Path | None = None
        self._session_log_file = None
        self._connect_sequence = 0

        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll)
        content = QWidget()
        scroll.setWidget(content)
        root = QVBoxLayout(content)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        group_style = """
            QGroupBox { color:#bbb; border:1px solid #444; border-radius:4px; margin-top:8px; padding-top:14px; font-family:Consolas; font-size:9pt; }
            QGroupBox::title { subcontrol-origin: margin; left:10px; }
        """

        conn = QHBoxLayout()
        self.port_combo = QComboBox()
        self.port_combo.setMinimumWidth(180)
        self._refresh_ports()
        if initial_port:
            idx = self.port_combo.findText(initial_port)
            if idx >= 0:
                self.port_combo.setCurrentIndex(idx)
        refresh_btn = QPushButton("Refresh Ports")
        refresh_btn.clicked.connect(self._refresh_ports)
        self.connect_btn = QPushButton("Connect")
        self.connect_btn.setFixedWidth(100)
        self.connect_btn.clicked.connect(self._toggle_connection)
        self.start_btn = QPushButton("Start")
        self.stop_btn = QPushButton("Stop")
        self.about_btn = QPushButton("About")
        self.dump_btn = QPushButton("Dump")
        self.map_btn = QPushButton("Map")
        for btn, cmd in ((self.start_btn, "start"), (self.stop_btn, "stop"), (self.about_btn, "about"), (self.dump_btn, "input dump"), (self.map_btn, "input map")):
            btn.clicked.connect(lambda _=False, text=cmd: self._send_command(text))
        self.status_label = QLabel("Disconnected")
        self.status_label.setStyleSheet("color:#888;")
        self.stats_label = QLabel("evt: 0  good: 0  err: 0")
        self.stats_label.setStyleSheet("color:#666; font-family:Consolas; font-size:9pt;")
        conn.addWidget(QLabel("Port:"))
        conn.addWidget(self.port_combo)
        conn.addWidget(refresh_btn)
        conn.addWidget(self.connect_btn)
        conn.addWidget(self.start_btn)
        conn.addWidget(self.stop_btn)
        conn.addWidget(self.about_btn)
        conn.addWidget(self.dump_btn)
        conn.addWidget(self.map_btn)
        conn.addStretch()
        conn.addWidget(self.status_label)
        conn.addWidget(self.stats_label)
        root.addLayout(conn)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        root.addWidget(line)

        summary_group = QGroupBox("Device State")
        summary_group.setStyleSheet(group_style)
        sg = QGridLayout(summary_group)
        self.device_id_value = QLabel("-")
        self.version_value = QLabel("-")
        self.protocol_value = QLabel("idle")
        self.streaming_value = QLabel("-")
        self.interval_value = QLabel("-")
        self.can_value = QLabel("-")
        self.can_update_value = QLabel("-")
        self.joystick_update_value = QLabel("-")
        self.pedal_update_value = QLabel("-")
        self.can_idle_value = QLabel("-")
        self.joystick_idle_value = QLabel("-")
        self.pedal_idle_value = QLabel("-")
        self.can_frame_count_value = QLabel("-")
        self.joystick_frame_count_value = QLabel("-")
        self.pedal_frame_count_value = QLabel("-")
        self.last_can_value = QLabel("-")
        self.last_joystick_can_value = QLabel("-")
        self.last_pedal_can_value = QLabel("-")
        for idx, (label, widget) in enumerate((
            ("Device", self.device_id_value),
            ("Version", self.version_value),
            ("Protocol", self.protocol_value),
            ("Streaming", self.streaming_value),
            ("Interval", self.interval_value),
            ("CAN", self.can_value),
            ("CAN Update", self.can_update_value),
            ("Joy Update", self.joystick_update_value),
            ("Pedal Update", self.pedal_update_value),
            ("CAN Idle", self.can_idle_value),
            ("Joy Idle", self.joystick_idle_value),
            ("Pedal Idle", self.pedal_idle_value),
            ("CAN Frames", self.can_frame_count_value),
            ("Joy Frames", self.joystick_frame_count_value),
            ("Pedal Frames", self.pedal_frame_count_value),
            ("Last CAN ID", self.last_can_value),
            ("Last Joy CAN", self.last_joystick_can_value),
            ("Last Pedal CAN", self.last_pedal_can_value),
        )):
            row = idx // 3
            col = (idx % 3) * 2
            sg.addWidget(QLabel(label), row, col)
            sg.addWidget(widget, row, col + 1)
        root.addWidget(summary_group)

        hid_group = QGroupBox("Vortex HID Link")
        hid_group.setStyleSheet(group_style)
        hid_row = QHBoxLayout(hid_group)
        self.hid_enable = QCheckBox("Xbox Virtual Pad")
        self.hid_enable.toggled.connect(self._on_hid_toggled)
        self.hid_status_label = QLabel("Disabled")
        self.hid_status_label.setStyleSheet("color:#888; font-family:Consolas; font-size:9pt;")
        self.deadzone_spin = QDoubleSpinBox()
        self.deadzone_spin.setRange(0.0, 0.90)
        self.deadzone_spin.setSingleStep(0.01)
        self.deadzone_spin.setDecimals(2)
        self.deadzone_spin.setValue(hid_deadzone)
        self.deadzone_spin.valueChanged.connect(self._sync_hid_settings)
        self.expo_spin = QDoubleSpinBox()
        self.expo_spin.setRange(1.0, 4.0)
        self.expo_spin.setSingleStep(0.10)
        self.expo_spin.setDecimals(2)
        self.expo_spin.setValue(hid_expo)
        self.expo_spin.valueChanged.connect(self._sync_hid_settings)
        self.aux_expo_spin = QDoubleSpinBox()
        self.aux_expo_spin.setRange(1.0, 4.0)
        self.aux_expo_spin.setSingleStep(0.10)
        self.aux_expo_spin.setDecimals(2)
        self.aux_expo_spin.setValue(hid_aux_expo)
        self.aux_expo_spin.valueChanged.connect(self._sync_hid_settings)
        self.invert_y_check = QCheckBox("Invert Y")
        self.invert_y_check.setChecked(invert_y)
        self.invert_y_check.toggled.connect(self._sync_hid_settings)
        for widget in (self.hid_enable, QLabel("Deadzone"), self.deadzone_spin, QLabel("Main Expo"), self.expo_spin, QLabel("AUX Expo"), self.aux_expo_spin, self.invert_y_check):
            hid_row.addWidget(widget)
        hid_row.addStretch()
        hid_row.addWidget(self.hid_status_label)
        root.addWidget(hid_group)

        joy_row = QHBoxLayout()
        self.lh_panel = JoystickPanel("Joystick LH")
        self.lh_panel.setStyleSheet(group_style)
        self.rh_panel = JoystickPanel("Joystick RH")
        self.rh_panel.setStyleSheet(group_style)
        joy_row.addWidget(self.lh_panel, stretch=1)
        joy_row.addWidget(self.rh_panel, stretch=1)
        root.addLayout(joy_row)

        self.pedal_panel = PedalPanel("Travel Pedal Unit")
        self.pedal_panel.setStyleSheet(group_style)
        root.addWidget(self.pedal_panel)

        io_row = QHBoxLayout()
        analog_group = QGroupBox("Analog Inputs")
        analog_group.setStyleSheet(group_style)
        ag = QVBoxLayout(analog_group)
        self.analog_widgets = {name: AnalogValueWidget(name) for name in ("AIN1", "AIN2", "AIN3", "AIN4")}
        for widget in self.analog_widgets.values():
            ag.addWidget(widget)
        io_row.addWidget(analog_group, stretch=1)
        digital_group = QGroupBox("Digital Inputs")
        digital_group.setStyleSheet(group_style)
        dg = QGridLayout(digital_group)
        self.digital_widgets = {name: BoolStateWidget(name) for name in ("DIN1", "DIN2", "DIN3", "DIN4", "DIN5", "DIN6", "DIN7")}
        for idx, widget in enumerate(self.digital_widgets.values()):
            dg.addWidget(widget, idx // 2, idx % 2)
        io_row.addWidget(digital_group, stretch=1)
        root.addLayout(io_row)

        log_group = QGroupBox("Command / Response Log")
        log_group.setStyleSheet(group_style)
        lg = QVBoxLayout(log_group)
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(250)
        self.log_view.setMinimumHeight(180)
        lg.addWidget(self.log_view)
        root.addWidget(log_group)

        self._paint_timer = QTimer()
        self._paint_timer.timeout.connect(self._repaint_all)
        self._paint_timer.start(50)

        self._set_command_buttons(False)
        self._reset_view_state()
        self.setStyleSheet(
            """
            QMainWindow, QWidget { background-color:#1e1e23; color:#ddd; }
            QLabel { font-family:Consolas; font-size:10pt; }
            QComboBox, QPushButton, QDoubleSpinBox, QPlainTextEdit { background-color:#2a2a30; color:#ccc; border:1px solid #555; border-radius:3px; padding:4px 8px; font-family:Consolas; }
            QCheckBox { font-family:Consolas; font-size:9pt; color:#ccc; }
            QProgressBar { background-color:#22252b; border:1px solid #555; border-radius:3px; min-height:16px; }
            QProgressBar::chunk { background-color:#3b8cff; border-radius:2px; }
            QPushButton:hover { background-color:#3a3a42; }
            QPushButton:pressed { background-color:#222228; }
            QPushButton:disabled { color:#666; border-color:#444; background-color:#26262a; }
            """
        )
        if enable_hid:
            self.hid_enable.setChecked(True)

    def _append_log(self, text: str):
        self.log_view.appendPlainText(text)

    def _write_session_log(self, event_type: str, payload: dict):
        if not self._session_log_file:
            return
        entry = {
            "ts": datetime.now().isoformat(timespec="milliseconds"),
            "type": event_type,
            "payload": payload,
        }
        self._session_log_file.write(json.dumps(entry, ensure_ascii=False) + "\n")
        self._session_log_file.flush()

    def _open_session_log(self):
        self._close_session_log()
        log_dir = Path(__file__).resolve().parents[1] / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._session_log_path = log_dir / f"digcanlink_monitor_{stamp}.jsonl"
        self._session_log_file = self._session_log_path.open("a", encoding="utf-8")
        self._append_log(f"# session log: {self._session_log_path}")
        self._write_session_log(
            "session_start",
            {
                "port": self.port_combo.currentText(),
                "baud": self._baud,
            },
        )

    def _close_session_log(self):
        if self._session_log_file:
            self._write_session_log("session_end", {})
            self._session_log_file.close()
        self._session_log_file = None
        self._session_log_path = None

    def _set_update_value(self, label: QLabel, updated: bool):
        label.setText("RX" if updated else "-")
        label.setStyleSheet(
            "color:#0d8; font-family:Consolas; font-weight:bold;"
            if updated
            else "color:#888; font-family:Consolas;"
        )

    @staticmethod
    def _format_ms(value: int | None) -> str:
        return "-" if value is None else f"{value} ms"

    def _set_hid_status(self, text: str, color: str):
        self.hid_status_label.setText(text)
        self.hid_status_label.setStyleSheet(f"color:{color}; font-family:Consolas; font-size:9pt;")

    def _set_command_buttons(self, connected: bool):
        for btn in (self.start_btn, self.stop_btn, self.about_btn, self.dump_btn, self.map_btn):
            btn.setEnabled(connected)

    def _set_protocol_mode(self, mode: str):
        self._protocol_mode = mode
        self.protocol_value.setText(mode)

    def _reset_view_state(self):
        self.device_id_value.setText("-")
        self.version_value.setText("-")
        self.streaming_value.setText("-")
        self.interval_value.setText("-")
        self.can_value.setText("-")
        self._set_update_value(self.can_update_value, False)
        self._set_update_value(self.joystick_update_value, False)
        self._set_update_value(self.pedal_update_value, False)
        self.can_idle_value.setText("-")
        self.joystick_idle_value.setText("-")
        self.pedal_idle_value.setText("-")
        self.can_frame_count_value.setText("-")
        self.joystick_frame_count_value.setText("-")
        self.pedal_frame_count_value.setText("-")
        self.last_can_value.setText("-")
        self.last_joystick_can_value.setText("-")
        self.last_pedal_can_value.setText("-")
        self._set_protocol_mode("idle")
        self.lh_panel.clear()
        self.rh_panel.clear()
        self.pedal_panel.clear()
        for widget in self.analog_widgets.values():
            widget.set_value(0)
        for widget in self.digital_widgets.values():
            widget.set_active(False)

    def _on_hid_toggled(self, enabled: bool):
        if enabled:
            try:
                self._hid = VortexHID()
            except Exception as exc:
                self._hid = None
                self._set_hid_status("Unavailable", "#c88")
                self.hid_enable.blockSignals(True)
                self.hid_enable.setChecked(False)
                self.hid_enable.blockSignals(False)
                QMessageBox.warning(self, "HID Link", "vgamepad 초기화에 실패했습니다.\nuv sync --extra hid 후 다시 실행하세요.\n\n" f"detail: {exc}")
                return
            self._sync_hid_settings()
            self._set_hid_status("Enabled", "#0d8")
            if self._last_main or self._last_aux:
                self._hid.update_from_packets(self._last_main, self._last_aux)
            return
        if self._hid:
            self._hid.reset()
        self._hid = None
        self._set_hid_status("Disabled", "#888")

    def _sync_hid_settings(self, *_args):
        if not self._hid:
            return
        deadzone = self.deadzone_spin.value()
        main_expo = self.expo_spin.value()
        aux_expo = self.aux_expo_spin.value()
        invert_y = self.invert_y_check.isChecked()
        self._hid.left_x.deadzone = deadzone
        self._hid.left_x.expo = main_expo
        self._hid.left_y.deadzone = deadzone
        self._hid.left_y.expo = main_expo
        self._hid.left_y.invert = invert_y
        self._hid.right_y.deadzone = deadzone
        self._hid.right_y.expo = aux_expo
        if self._last_main or self._last_aux:
            self._hid.update_from_packets(self._last_main, self._last_aux)

    def _reset_hid_output(self):
        self._last_main = None
        self._last_aux = None
        if self._hid:
            self._hid.reset()

    def _update_hid_from_report(self, report: DigInputReport):
        if report.rh.main.valid:
            self._last_main = report.rh.main.to_packet()
        if report.rh.aux.valid:
            self._last_aux = report.rh.aux.to_packet()
        if self._hid and (self._last_main or self._last_aux):
            self._hid.update_from_packets(self._last_main, self._last_aux)

    def _refresh_ports(self):
        current = self.port_combo.currentText()
        self.port_combo.clear()
        for port in sorted(serial.tools.list_ports.comports(), key=lambda x: x.device):
            self.port_combo.addItem(port.device)
        if current:
            idx = self.port_combo.findText(current)
            if idx >= 0:
                self.port_combo.setCurrentIndex(idx)

    def _toggle_connection(self):
        if self._reader and self._reader.isRunning():
            self._reader.stop()
            self._reader = None
            self._reset_hid_output()
            self._set_command_buttons(False)
            self.connect_btn.setText("Connect")
            self.status_label.setText("Disconnected")
            self.status_label.setStyleSheet("color:#888;")
            return
        port = self.port_combo.currentText()
        if not port:
            return
        self._event_count = 0
        self._reset_view_state()
        self._reader = SerialReaderThread(port, self._baud, self)
        self._reader.main_received.connect(self._on_main)
        self._reader.aux_received.connect(self._on_aux)
        self._reader.report_received.connect(self._on_report)
        self._reader.response_received.connect(self._on_response)
        self._reader.stats_updated.connect(self._on_stats)
        self._reader.connected.connect(self._on_connected)
        self._reader.open_failed.connect(self._on_open_failed)
        self._reader.start()
        self.connect_btn.setText("Disconnect")

    def _send_command(self, command: str):
        if not self._reader or not self._reader.isRunning():
            return
        self._reader.queue_command(command)
        self._append_log(f">> {command}")
        self._write_session_log("command", {"text": command})

    def _send_command_if_current(self, sequence: int, command: str):
        if sequence != self._connect_sequence:
            return
        self._send_command(command)

    def _on_connected(self, ok: bool):
        if ok:
            self._open_session_log()
            self.status_label.setText("Connected")
            self.status_label.setStyleSheet("color:#0d8;")
            self._set_command_buttons(True)
            self._write_session_log(
                "connected",
                {"port": self.port_combo.currentText(), "baud": self._baud},
            )
            sequence = self._connect_sequence
            self._append_log(
                f"# waiting {self.INITIAL_HANDSHAKE_DELAY_MS} ms for Mega reboot before handshake"
            )
            QTimer.singleShot(
                self.INITIAL_HANDSHAKE_DELAY_MS,
                lambda seq=sequence: self._send_command_if_current(seq, "about"),
            )
            QTimer.singleShot(
                self.INITIAL_START_DELAY_MS,
                lambda seq=sequence: self._send_command_if_current(seq, "start"),
            )
        else:
            self._connect_sequence += 1
            self._reset_hid_output()
            self._set_command_buttons(False)
            self.status_label.setText("Disconnected")
            self.status_label.setStyleSheet("color:#888;")
            self.connect_btn.setText("Connect")
            self._write_session_log("disconnected", {})
            self._close_session_log()

    def _on_open_failed(self, message: str):
        self._connect_sequence += 1
        self._reset_hid_output()
        self._set_command_buttons(False)
        self.status_label.setText("Open failed")
        self.status_label.setStyleSheet("color:#c88;")
        self.connect_btn.setText("Connect")
        self._append_log(f"# {message}")
        self._close_session_log()

    def _on_main(self, pkt: MainPacket):
        self._event_count += 1
        self._set_protocol_mode("legacy_text")
        self._last_main = pkt
        self.rh_panel.update_packets(main=pkt, aux=self._last_aux, sa=0xD1)
        if self._hid:
            self._hid.update_main(pkt)

    def _on_aux(self, pkt: AuxPacket):
        self._event_count += 1
        self._set_protocol_mode("legacy_text")
        self._last_aux = pkt
        self.rh_panel.update_packets(main=self._last_main, aux=pkt, sa=0xD1)
        if self._hid:
            self._hid.update_aux(pkt)

    def _on_report(self, report: DigInputReport):
        self._event_count += 1
        self._set_protocol_mode("digcanlink_json")
        self.streaming_value.setText("ON" if report.streaming else "OFF")
        self.interval_value.setText(f"{report.interval_ms} ms")
        self.can_value.setText("OK" if report.can_ready else "FAIL")
        self._set_update_value(self.can_update_value, report.can_updated)
        self._set_update_value(self.joystick_update_value, report.joystick_updated)
        self._set_update_value(self.pedal_update_value, report.pedal_updated)
        self.can_idle_value.setText(self._format_ms(report.can_rx_idle_ms))
        self.joystick_idle_value.setText(self._format_ms(report.joystick_rx_idle_ms))
        self.pedal_idle_value.setText(self._format_ms(report.pedal_rx_idle_ms))
        self.can_frame_count_value.setText(str(report.can_frame_count))
        self.joystick_frame_count_value.setText(str(report.joystick_frame_count))
        self.pedal_frame_count_value.setText(str(report.pedal_frame_count))
        self.last_can_value.setText(f"0x{report.last_can_id:X}" if report.last_can_id is not None else "-")
        self.last_joystick_can_value.setText(
            f"0x{report.last_joystick_can_id:X}" if report.last_joystick_can_id is not None else "-"
        )
        self.last_pedal_can_value.setText(
            f"0x{report.last_pedal_can_id:X}" if report.last_pedal_can_id is not None else "-"
        )
        self.lh_panel.update_report(report.lh)
        self.rh_panel.update_report(report.rh)
        self.pedal_panel.update_report(report.primary_pedal)
        for name, widget in self.analog_widgets.items():
            widget.set_value(report.ain.get(name, 0))
        for name, widget in self.digital_widgets.items():
            widget.set_active(report.din.get(name, False))
        self._update_hid_from_report(report)
        self._write_session_log("input_report", _report_to_dict(report))

    def _on_response(self, resp: DeviceResponse):
        self._event_count += 1
        self._append_log("<< " + json.dumps(resp.payload, ensure_ascii=False))
        payload = resp.payload
        if "dev_id" in payload:
            self.device_id_value.setText(str(payload.get("dev_id", "-")))
        if "version" in payload:
            version = str(payload.get("version", "-"))
            if "system_version" in payload:
                version += f" / sys {payload.get('system_version')}"
            self.version_value.setText(version)
        if "streaming" in payload:
            self.streaming_value.setText("ON" if payload.get("streaming") else "OFF")
        if "report_interval_ms" in payload:
            self.interval_value.setText(f"{payload.get('report_interval_ms')} ms")
        if "can_ready" in payload:
            self.can_value.setText("OK" if payload.get("can_ready") else "FAIL")
        if "can_updated" in payload:
            self._set_update_value(self.can_update_value, bool(payload.get("can_updated")))
        if "joystick_updated" in payload:
            self._set_update_value(self.joystick_update_value, bool(payload.get("joystick_updated")))
        if "pedal_updated" in payload:
            self._set_update_value(self.pedal_update_value, bool(payload.get("pedal_updated")))
        if "can_rx_idle_ms" in payload:
            self.can_idle_value.setText(self._format_ms(int(payload.get("can_rx_idle_ms"))))
        if "joystick_rx_idle_ms" in payload:
            self.joystick_idle_value.setText(self._format_ms(int(payload.get("joystick_rx_idle_ms"))))
        if "pedal_rx_idle_ms" in payload:
            self.pedal_idle_value.setText(self._format_ms(int(payload.get("pedal_rx_idle_ms"))))
        if "can_frame_count" in payload:
            self.can_frame_count_value.setText(str(payload.get("can_frame_count")))
        if "joystick_frame_count" in payload:
            self.joystick_frame_count_value.setText(str(payload.get("joystick_frame_count")))
        if "pedal_frame_count" in payload:
            self.pedal_frame_count_value.setText(str(payload.get("pedal_frame_count")))
        if "last_can_id" in payload:
            self.last_can_value.setText(f"0x{int(payload.get('last_can_id')):X}")
        if "last_joystick_can_id" in payload:
            self.last_joystick_can_value.setText(f"0x{int(payload.get('last_joystick_can_id')):X}")
        if "last_pedal_can_id" in payload:
            self.last_pedal_can_value.setText(f"0x{int(payload.get('last_pedal_can_id')):X}")
        self._write_session_log("device_response", payload)

    def _on_stats(self, stats: ReceiverStats):
        self.stats_label.setText(f"evt: {self._event_count}  good: {stats.good}  err: {stats.errors}")

    def _repaint_all(self):
        for widget in (
            self.lh_panel.graph_x, self.lh_panel.graph_y, self.lh_panel.graph_aux,
            self.rh_panel.graph_x, self.rh_panel.graph_y, self.rh_panel.graph_aux,
            self.pedal_panel.graph_axis2, self.pedal_panel.graph_axis1,
            self.lh_panel.led_btn1, self.lh_panel.led_btn2, self.lh_panel.led_btn3, self.lh_panel.led_btn4,
            self.rh_panel.led_btn1, self.rh_panel.led_btn2, self.rh_panel.led_btn3, self.rh_panel.led_btn4,
        ):
            widget.update()

    def closeEvent(self, event):
        if self._reader:
            self._reader.stop()
        self._reset_hid_output()
        self._close_session_log()
        event.accept()
