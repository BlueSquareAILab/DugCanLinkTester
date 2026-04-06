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
            self.assertEqual(win.windowTitle(), "DigCanLink Monitor")
            self.assertEqual(win.connect_btn.text(), "Connect")
            self.assertGreaterEqual(win.width(), 1100)
            self.assertEqual(win.start_btn.text(), "Start")
            self.assertEqual(win.lh_panel.graph_x.negative_label, "Left")
            self.assertEqual(win.lh_panel.graph_x.positive_label, "Right")
            self.assertEqual(win.lh_panel.graph_y.negative_label, "Down/Back")
            self.assertEqual(win.lh_panel.graph_y.positive_label, "Up/Forward")
            self.assertEqual(win.pedal_panel.title(), "Travel Pedal Unit")
            self.assertEqual(win.pedal_panel.graph_axis2.negative_label, "2-")
            self.assertEqual(win.pedal_panel.graph_axis2.positive_label, "2+")
            self.assertEqual(win.pedal_panel.graph_axis1.negative_label, "1-")
            self.assertEqual(win.pedal_panel.graph_axis1.positive_label, "1+")
        finally:
            win.close()


if __name__ == "__main__":
    unittest.main()
