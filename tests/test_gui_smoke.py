import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from DugCanLinker.joystick_monitor import JoystickMonitorWindow


class JoystickMonitorSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_window_constructs_offscreen(self):
        win = JoystickMonitorWindow()
        try:
            self.assertEqual(win.windowTitle(), "J1939 CAN Joystick Monitor")
            self.assertEqual(win.connect_btn.text(), "Connect")
            self.assertGreaterEqual(win.width(), 800)
        finally:
            win.close()


if __name__ == "__main__":
    unittest.main()
