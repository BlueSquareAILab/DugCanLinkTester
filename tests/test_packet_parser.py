import unittest

from DugCanLinker.protocol import (
    AUX_PAYLOAD_LEN,
    MAIN_PAYLOAD_LEN,
    PKT_AUX,
    PKT_MAIN,
    xor_checksum,
)
from DugCanLinker.serial_receiver import PacketParser


def build_packet(pkt_type: int, payload: bytes) -> bytes:
    header = bytes([0xAA, 0x55, pkt_type, len(payload)])
    checksum = xor_checksum(bytes([pkt_type, len(payload)]) + payload)
    return header + payload + bytes([checksum])


class PacketParserTests(unittest.TestCase):
    def feed_all(self, data: bytes):
        parser = PacketParser()
        decoded = []
        for byte in data:
            result = parser.feed(byte)
            if result is not None:
                decoded.append(result)
        return parser, decoded

    def test_decodes_main_packet(self):
        payload = bytes([128, 0x59, 140, 0x86, 0x4C, 0, 7])
        parser, decoded = self.feed_all(build_packet(PKT_MAIN, payload))

        self.assertEqual(parser.stats.good, 1)
        self.assertEqual(parser.stats.errors, 0)
        self.assertEqual(len(decoded), 1)

        pkt_type, packet = decoded[0]
        self.assertEqual(pkt_type, PKT_MAIN)
        self.assertEqual(packet.x.position, 128)
        self.assertEqual(packet.y.position, 140)
        self.assertEqual(packet.buttons.btn2, 1)
        self.assertEqual(packet.buttons.btn4, 3)
        self.assertEqual(packet.seq, 7)

    def test_decodes_aux_packet(self):
        payload = bytes([200, 0xC5, 0, 9])
        parser, decoded = self.feed_all(build_packet(PKT_AUX, payload))

        self.assertEqual(parser.stats.good, 1)
        self.assertEqual(parser.stats.errors, 0)
        self.assertEqual(len(decoded), 1)

        pkt_type, packet = decoded[0]
        self.assertEqual(pkt_type, PKT_AUX)
        self.assertEqual(packet.x.position, 200)
        self.assertEqual(packet.x.status, 3)
        self.assertEqual(packet.seq, 9)

    def test_rejects_bad_checksum(self):
        payload = bytes([128, 0x59, 140, 0x86, 0x4C, 0, 7])
        bad_packet = bytes([0xAA, 0x55, PKT_MAIN, MAIN_PAYLOAD_LEN]) + payload + b"\x00"
        parser, decoded = self.feed_all(bad_packet)

        self.assertEqual(decoded, [])
        self.assertEqual(parser.stats.good, 0)
        self.assertEqual(parser.stats.errors, 1)

    def test_resynchronizes_after_noise(self):
        payload = bytes([128, 0x59, 140, 0x86, 0x4C, 0, 7])
        noisy_stream = b"\x00\x10\xAA\x00" + build_packet(PKT_MAIN, payload)
        parser, decoded = self.feed_all(noisy_stream)

        self.assertEqual(parser.stats.good, 1)
        self.assertEqual(parser.stats.errors, 0)
        self.assertEqual(len(decoded), 1)

    def test_rejects_too_long_payload(self):
        parser, decoded = self.feed_all(bytes([0xAA, 0x55, PKT_MAIN, 17]))

        self.assertEqual(decoded, [])
        self.assertEqual(parser.stats.good, 0)
        self.assertEqual(parser.stats.errors, 1)

    def test_payload_lengths_match_protocol_constants(self):
        self.assertEqual(MAIN_PAYLOAD_LEN, 7)
        self.assertEqual(AUX_PAYLOAD_LEN, 4)


if __name__ == "__main__":
    unittest.main()
