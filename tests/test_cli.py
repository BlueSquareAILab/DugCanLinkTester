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

    def test_minimal_example_help(self):
        result = subprocess.run(
            [sys.executable, "examples/simulator_receiver_minimal.py", "--help"],
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0)
        self.assertIn("--port", result.stdout)


if __name__ == "__main__":
    unittest.main()
