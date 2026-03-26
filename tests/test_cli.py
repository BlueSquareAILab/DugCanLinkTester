import subprocess
import sys
import unittest


class JoystickReceiverCliTests(unittest.TestCase):
    def test_requires_port_argument(self):
        result = subprocess.run(
            [sys.executable, "-m", "DugCanLinker.joystick_receiver"],
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--port", result.stderr)


if __name__ == "__main__":
    unittest.main()
