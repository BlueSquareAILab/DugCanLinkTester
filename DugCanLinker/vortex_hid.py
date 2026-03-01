"""
Windows virtual gamepad output for Vortex Studio integration.

This module converts parsed joystick packets into an Xbox 360 virtual pad
using the vgamepad driver stack.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .protocol import AuxPacket, AxisState, MainPacket

if TYPE_CHECKING:
    import vgamepad as vg


XUSB_MIN = -32768
XUSB_MAX = 32767


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


@dataclass(slots=True)
class AxisMapper:
    deadzone: float = 0.0
    expo: float = 1.0
    invert: bool = False

    def map_axis(self, axis: AxisState) -> int:
        raw = (axis.position - 128) / 127.0
        raw = _clamp(raw, -1.0, 1.0)

        if abs(raw) < self.deadzone:
            raw = 0.0
        elif self.deadzone > 0.0:
            sign = -1.0 if raw < 0.0 else 1.0
            scaled = (abs(raw) - self.deadzone) / (1.0 - self.deadzone)
            raw = sign * scaled

        if self.expo != 1.0:
            sign = -1.0 if raw < 0.0 else 1.0
            raw = sign * (abs(raw) ** self.expo)

        if self.invert:
            raw = -raw

        scaled = int(round(raw * XUSB_MAX))
        return max(XUSB_MIN, min(XUSB_MAX, scaled))


class VortexHID:
    def __init__(
        self,
        *,
        left_x: AxisMapper | None = None,
        left_y: AxisMapper | None = None,
        right_y: AxisMapper | None = None,
        auto_update: bool = True,
    ):
        try:
            import vgamepad as vg
        except ImportError as exc:
            raise RuntimeError(
                "vgamepad is required for HID output. Install with: uv sync --extra hid"
            ) from exc

        self._vg: vg = vg
        self.device = vg.VX360Gamepad()
        self.left_x = left_x or AxisMapper()
        self.left_y = left_y or AxisMapper(invert=True)
        self.right_y = right_y or AxisMapper()
        self.auto_update = auto_update
        self._last_main: MainPacket | None = None
        self._last_aux: AuxPacket | None = None

    def update_main(self, pkt: MainPacket) -> None:
        self._last_main = pkt
        lx = self.left_x.map_axis(pkt.x)
        ly = self.left_y.map_axis(pkt.y)
        self.device.left_joystick(x_value=lx, y_value=ly)
        self._apply_buttons(pkt)
        if self.auto_update:
            self.device.update()

    def update_aux(self, pkt: AuxPacket) -> None:
        self._last_aux = pkt
        ry = self.right_y.map_axis(pkt.x)
        self.device.right_joystick(x_value=0, y_value=ry)
        if self.auto_update:
            self.device.update()

    def update_from_packets(
        self,
        main_pkt: MainPacket | None = None,
        aux_pkt: AuxPacket | None = None,
    ) -> None:
        if main_pkt is not None:
            self._last_main = main_pkt
        if aux_pkt is not None:
            self._last_aux = aux_pkt

        if self._last_main is not None:
            self.device.left_joystick(
                x_value=self.left_x.map_axis(self._last_main.x),
                y_value=self.left_y.map_axis(self._last_main.y),
            )
            self._apply_buttons(self._last_main)

        if self._last_aux is not None:
            self.device.right_joystick(
                x_value=0,
                y_value=self.right_y.map_axis(self._last_aux.x),
            )

        self.device.update()

    def reset(self) -> None:
        self.device.reset()
        self.device.update()
        self._last_main = None
        self._last_aux = None

    def _apply_buttons(self, pkt: MainPacket) -> None:
        buttons = [
            (pkt.buttons.btn1, self._vg.XUSB_BUTTON.XUSB_GAMEPAD_A),
            (pkt.buttons.btn2, self._vg.XUSB_BUTTON.XUSB_GAMEPAD_B),
            (pkt.buttons.btn3, self._vg.XUSB_BUTTON.XUSB_GAMEPAD_X),
            (pkt.buttons.btn4, self._vg.XUSB_BUTTON.XUSB_GAMEPAD_Y),
        ]
        for value, code in buttons:
            if value > 0:
                self.device.press_button(code)
            else:
                self.device.release_button(code)
