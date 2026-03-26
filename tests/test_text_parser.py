import unittest

from DugCanLinker.protocol import (
    PKT_MAIN, PKT_AUX, parse_text_line,
)
from DugCanLinker.serial_receiver import TextLineParser


class TextLineParseTests(unittest.TestCase):
    """parse_text_line() 단위 테스트"""

    def test_parse_main_line(self):
        line = (
            "ID:0xCFDD6D1 PGN:0xFDD6 "
            "X(st=2 -=1 +=0 N=0 pos=200) "
            "Y(st=0 -=0 +=1 N=0 pos=140) "
            "B1:0 B2:1 B3:0 B4:3"
        )
        result = parse_text_line(line)
        self.assertIsNotNone(result)

        pkt_type, pkt = result
        self.assertEqual(pkt_type, PKT_MAIN)
        self.assertEqual(pkt.x.position, 200)
        self.assertEqual(pkt.x.status, 2)
        self.assertEqual(pkt.x.negative, 1)
        self.assertEqual(pkt.x.positive, 0)
        self.assertEqual(pkt.x.neutral, 0)
        self.assertEqual(pkt.y.position, 140)
        self.assertEqual(pkt.y.positive, 1)
        self.assertEqual(pkt.buttons.btn1, 0)
        self.assertEqual(pkt.buttons.btn2, 1)
        self.assertEqual(pkt.buttons.btn3, 0)
        self.assertEqual(pkt.buttons.btn4, 3)

    def test_parse_aux_line(self):
        line = "ID:0xCFDD7D1 PGN:0xFDD7 AUX_X(st=0 -=0 +=0 N=1 pos=0)"
        result = parse_text_line(line)
        self.assertIsNotNone(result)

        pkt_type, pkt = result
        self.assertEqual(pkt_type, PKT_AUX)
        self.assertEqual(pkt.x.position, 0)
        self.assertEqual(pkt.x.neutral, 1)
        self.assertEqual(pkt.x.status, 0)

    def test_ignores_init_message(self):
        line = "MCP2515 Init OK - Joystick CAN Reader"
        result = parse_text_line(line)
        self.assertIsNone(result)

    def test_ignores_empty_line(self):
        result = parse_text_line("")
        self.assertIsNone(result)


class TextLineParserTests(unittest.TestCase):
    """TextLineParser (바이트 단위 feed) 통합 테스트"""

    def _feed_string(self, parser: TextLineParser, text: str):
        results = []
        for ch in text.encode('ascii'):
            r = parser.feed(ch)
            if r is not None:
                results.append(r)
        return results

    def test_feed_main_line(self):
        parser = TextLineParser()
        line = (
            "ID:0xCFDD6D1 PGN:0xFDD6 "
            "X(st=0 -=1 +=0 N=0 pos=250) "
            "Y(st=0 -=0 +=0 N=0 pos=128) "
            "B1:0 B2:0 B3:0 B4:0\r\n"
        )
        results = self._feed_string(parser, line)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0][0], PKT_MAIN)
        self.assertEqual(results[0][1].x.position, 250)
        self.assertEqual(results[0][1].y.position, 128)
        self.assertEqual(parser.stats.good, 1)

    def test_feed_aux_line(self):
        parser = TextLineParser()
        line = "ID:0xCFDD7D1 PGN:0xFDD7 AUX_X(st=0 -=0 +=0 N=1 pos=0)\n"
        results = self._feed_string(parser, line)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0][0], PKT_AUX)
        self.assertEqual(results[0][1].x.position, 0)
        self.assertEqual(results[0][1].x.neutral, 1)

    def test_skips_init_line(self):
        parser = TextLineParser()
        stream = (
            "MCP2515 Init OK - Joystick CAN Reader\r\n"
            "ID:0xCFDD7D1 PGN:0xFDD7 AUX_X(st=0 -=0 +=0 N=1 pos=0)\n"
        )
        results = self._feed_string(parser, stream)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0][0], PKT_AUX)
        self.assertEqual(parser.stats.good, 1)

    def test_multiple_lines(self):
        parser = TextLineParser()
        stream = (
            "ID:0xCFDD6D1 PGN:0xFDD6 X(st=0 -=0 +=0 N=1 pos=128) "
            "Y(st=0 -=0 +=0 N=1 pos=128) B1:0 B2:0 B3:0 B4:0\n"
            "ID:0xCFDD7D1 PGN:0xFDD7 AUX_X(st=0 -=0 +=0 N=1 pos=0)\n"
        )
        results = self._feed_string(parser, stream)

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0][0], PKT_MAIN)
        self.assertEqual(results[1][0], PKT_AUX)
        self.assertEqual(parser.stats.good, 2)


if __name__ == "__main__":
    unittest.main()
