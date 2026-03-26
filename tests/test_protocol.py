import unittest

from DugCanLinker.protocol import parse_aux_payload, parse_main_payload


class ProtocolPayloadTests(unittest.TestCase):
    def test_parse_main_payload(self):
        packet = parse_main_payload(bytes([128, 0x59, 140, 0x86, 0x4C, 0, 7]))

        self.assertEqual(packet.x.position, 128)
        self.assertEqual(packet.x.signed, 0)
        self.assertEqual(packet.x.status, 1)
        self.assertEqual(packet.x.negative, 1)
        self.assertEqual(packet.x.positive, 2)
        self.assertEqual(packet.y.position, 140)
        self.assertEqual(packet.y.signed, 12)
        self.assertEqual(packet.buttons.btn1, 0)
        self.assertEqual(packet.buttons.btn2, 1)
        self.assertEqual(packet.buttons.btn3, 0)
        self.assertEqual(packet.buttons.btn4, 3)
        self.assertEqual(packet.seq, 7)

    def test_parse_aux_payload(self):
        packet = parse_aux_payload(bytes([200, 0xC5, 0, 9]))

        self.assertEqual(packet.x.position, 200)
        self.assertEqual(packet.x.signed, 72)
        self.assertEqual(packet.x.status, 3)
        self.assertEqual(packet.x.negative, 0)
        self.assertEqual(packet.x.positive, 1)
        self.assertEqual(packet.x.neutral, 1)
        self.assertEqual(packet.seq, 9)


if __name__ == "__main__":
    unittest.main()
